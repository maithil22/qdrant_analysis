"""Thread-safe CSV metrics writer."""
import csv
import os
import threading
import time
from pathlib import Path


COLUMNS = [
    "timestamp_unix",
    "elapsed_s",
    "recall_at_k",
    "qps",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "error_count",
    "fault_active",
    "fault_type",
    "replication_factor",
]


class MetricsSink:
    def __init__(self, path: str | Path, cfg: dict):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cfg = cfg
        self._lock = threading.Lock()
        self._fh = open(self.path, "w", newline="", buffering=1)
        self._writer = csv.DictWriter(self._fh, fieldnames=COLUMNS)
        self._writer.writeheader()
        self._fh.flush()

    def write_row(
        self,
        elapsed_s: float,
        recall_at_k: float,
        qps: float,
        p50_ms: float,
        p95_ms: float,
        p99_ms: float,
        error_count: int,
        fault_active: bool,
    ) -> None:
        row = {
            "timestamp_unix": time.time(),
            "elapsed_s": round(elapsed_s, 3),
            "recall_at_k": round(recall_at_k, 6) if recall_at_k == recall_at_k else "",
            "qps": round(qps, 2),
            "p50_ms": round(p50_ms, 3) if p50_ms == p50_ms else "",
            "p95_ms": round(p95_ms, 3) if p95_ms == p95_ms else "",
            "p99_ms": round(p99_ms, 3) if p99_ms == p99_ms else "",
            "error_count": error_count,
            "fault_active": int(fault_active),
            "fault_type": self._cfg.get("failure_mode", ""),
            "replication_factor": self._cfg.get("replication_factor", 1),
        }
        with self._lock:
            self._writer.writerow(row)
            self._fh.flush()

    def close(self) -> None:
        with self._lock:
            self._fh.close()
