#!/usr/bin/env python3
"""Main experiment driver: continuous querying with fault injection and metrics capture."""
import argparse
import logging
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml
from qdrant_client import QdrantClient
from qdrant_client.models import SearchParams

sys.path.insert(0, str(Path(__file__).parent.parent))
from workload.recall import load_ground_truth, recall_at_k, batch_recall_at_k
from workload.metrics_sink import MetricsSink
from fault_injection.fault import FaultAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

HNSW_EF_SEARCH = 128


class _QueryState:
    """Ring buffer shared between query thread and sampler thread."""

    def __init__(self):
        self._lock = threading.Lock()
        self._latencies: list[float] = []
        self._recalls: list[float] = []
        self._errors: int = 0
        self.fault_active = False
        self.stop = False

    def push(self, latency_ms: float, recall: float) -> None:
        with self._lock:
            self._latencies.append(latency_ms)
            self._recalls.append(recall)

    def push_error(self) -> None:
        with self._lock:
            self._errors += 1

    def drain(self) -> tuple[list[float], list[float], int]:
        with self._lock:
            lats = self._latencies[:]
            recs = self._recalls[:]
            errs = self._errors
            self._latencies.clear()
            self._recalls.clear()
            self._errors = 0
        return lats, recs, errs


def _query_loop(
    client: QdrantClient,
    collection_name: str,
    test_vecs: np.ndarray,
    true_neighbors: np.ndarray,
    k: int,
    target_qps: float,
    state: _QueryState,
) -> None:
    inter_query_s = 1.0 / target_qps
    rng = np.random.default_rng(1234)
    n = len(test_vecs)

    while not state.stop:
        t0 = time.monotonic()
        i = int(rng.integers(0, n))
        try:
            results = client.search(
                collection_name=collection_name,
                query_vector=test_vecs[i].tolist(),
                limit=k,
                with_payload=False,
                search_params=SearchParams(hnsw_ef=HNSW_EF_SEARCH),
            )
            latency_ms = (time.monotonic() - t0) * 1000
            returned_ids = [r.id for r in results]
            rec = recall_at_k(returned_ids, true_neighbors[i], k)
            state.push(latency_ms, rec)
        except Exception:
            state.push_error()

        elapsed = time.monotonic() - t0
        sleep_s = inter_query_s - elapsed
        if sleep_s > 0:
            time.sleep(sleep_s)


def _sample_loop(
    state: _QueryState,
    sink: MetricsSink,
    interval_s: float,
    exp_start: float,
) -> None:
    while not state.stop:
        time.sleep(interval_s)
        lats, recs, errs = state.drain()

        if lats:
            p50 = float(np.percentile(lats, 50))
            p95 = float(np.percentile(lats, 95))
            p99 = float(np.percentile(lats, 99))
        else:
            p50 = p95 = p99 = float("nan")

        recall = float(np.mean(recs)) if recs else float("nan")
        qps = len(lats) / interval_s

        sink.write_row(
            elapsed_s=time.monotonic() - exp_start,
            recall_at_k=recall,
            qps=qps,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            error_count=errs,
            fault_active=state.fault_active,
        )


def run_experiment(cfg: dict, host: str, port: int) -> None:
    collection_name = yaml.safe_load(
        open(cfg.get("nodes_config", "config/nodes.yaml"))
    )["collection"]["name"]

    output_dir = cfg["output_dir"].replace(
        "{timestamp}", datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    log.info(f"Output dir: {output_dir}")

    client = QdrantClient(host=host, port=port, timeout=3.0)

    log.info("Loading ground truth ...")
    test_vecs, true_neighbors = load_ground_truth(
        cfg["ground_truth_file"], n_queries=500, k=cfg["top_k"]
    )
    log.info(f"Loaded {len(test_vecs)} query vectors")

    sink = MetricsSink(Path(output_dir) / "metrics.csv", cfg)
    state = _QueryState()
    fault_agent = FaultAgent(cfg)

    query_thread = threading.Thread(
        target=_query_loop,
        args=(client, collection_name, test_vecs, true_neighbors,
              cfg["top_k"], cfg["query_rate_qps"], state),
        daemon=True,
    )
    exp_start = time.monotonic()
    sample_thread = threading.Thread(
        target=_sample_loop,
        args=(state, sink, cfg["recall_interval_s"], exp_start),
        daemon=True,
    )

    query_thread.start()
    sample_thread.start()

    # Pre-fault baseline window
    log.info(f"Baseline phase: {cfg['fault_injection_delay_s']}s ...")
    time.sleep(cfg["fault_injection_delay_s"])

    # Inject fault
    log.info(f"Injecting fault: {cfg['failure_mode']} on node {cfg['failure_target_node']}")
    state.fault_active = True
    fault_agent.inject()

    # Fault active window
    log.info(f"Fault active for {cfg['fault_duration_s']}s ...")
    time.sleep(cfg["fault_duration_s"])

    # Heal
    log.info("Healing fault ...")
    fault_agent.heal()
    state.fault_active = False

    # Post-heal recovery observation
    log.info("Recovery observation: 60s ...")
    time.sleep(60)

    state.stop = True
    query_thread.join(timeout=5)
    sample_thread.join(timeout=5)
    sink.close()

    log.info(f"Experiment complete. Results: {output_dir}/metrics.csv")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6333)
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    run_experiment(cfg, args.host, args.port)


if __name__ == "__main__":
    main()
