#!/usr/bin/env python3
"""Parse experiment CSVs and compute MTTR, min recall, and tail latency stats."""
import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np


def load_csv(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def to_float(v: str) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return float("nan")


def compute_stats(rows: list[dict], recovery_threshold: float = 0.99, stable_count: int = 5):
    """Compute experiment statistics from a metrics CSV.

    Returns a dict with:
        baseline_recall, min_recall_during_fault, mttr_s,
        p95_baseline, p99_baseline, p95_fault, p99_fault
    """
    recalls = [to_float(r["recall_at_k"]) for r in rows]
    p95s = [to_float(r["p95_ms"]) for r in rows]
    p99s = [to_float(r["p99_ms"]) for r in rows]
    fault_active = [r["fault_active"] == "1" for r in rows]
    elapsed = [to_float(r["elapsed_s"]) for r in rows]

    # Baseline: rows before fault
    pre_fault = [i for i, fa in enumerate(fault_active) if not fa and not math.isnan(recalls[i])]
    if not pre_fault:
        return {}
    # Use last 10 pre-fault samples as baseline
    baseline_idxs = pre_fault[-10:]
    baseline_recall = float(np.nanmean([recalls[i] for i in baseline_idxs]))
    p95_baseline = float(np.nanmean([p95s[i] for i in baseline_idxs]))
    p99_baseline = float(np.nanmean([p99s[i] for i in baseline_idxs]))

    # Fault window
    fault_idxs = [i for i, fa in enumerate(fault_active) if fa and not math.isnan(recalls[i])]
    if fault_idxs:
        min_recall = float(np.nanmin([recalls[i] for i in fault_idxs]))
        p95_fault = float(np.nanmean([p95s[i] for i in fault_idxs if not math.isnan(p95s[i])]))
        p99_fault = float(np.nanmean([p99s[i] for i in fault_idxs if not math.isnan(p99s[i])]))
        fault_start_s = elapsed[fault_idxs[0]]
    else:
        min_recall = float("nan")
        p95_fault = p99_fault = float("nan")
        fault_start_s = float("nan")

    # MTTR: after fault ends, first stretch of stable_count rows above threshold
    post_fault = [i for i in range(len(rows)) if not fault_active[i] and i > (fault_idxs[-1] if fault_idxs else 0)]
    threshold = baseline_recall * recovery_threshold
    mttr_s = float("nan")
    streak = 0
    for i in post_fault:
        if not math.isnan(recalls[i]) and recalls[i] >= threshold:
            streak += 1
            if streak >= stable_count:
                recovery_time = elapsed[i]
                # fault_start_s is the time the fault was injected relative to exp start
                # MTTR = recovery_time - time_fault_ended
                fault_end_idxs = [i for i, fa in enumerate(fault_active) if fa]
                if fault_end_idxs:
                    fault_end_s = elapsed[fault_end_idxs[-1]]
                    mttr_s = recovery_time - fault_end_s
                break
        else:
            streak = 0

    return {
        "baseline_recall": baseline_recall,
        "min_recall_during_fault": min_recall,
        "mttr_s": mttr_s,
        "p95_baseline_ms": p95_baseline,
        "p99_baseline_ms": p99_baseline,
        "p95_fault_ms": p95_fault,
        "p99_fault_ms": p99_fault,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    csv_file = results_dir / "metrics.csv"
    if not csv_file.exists():
        print(f"No metrics.csv in {results_dir}", file=sys.stderr)
        sys.exit(1)

    rows = load_csv(csv_file)
    stats = compute_stats(rows)

    print(f"Results: {results_dir.name}")
    print(f"  Baseline Recall@K:       {stats.get('baseline_recall', 'N/A'):.4f}")
    print(f"  Min Recall during fault:  {stats.get('min_recall_during_fault', 'N/A'):.4f}")
    print(f"  MTTR:                     {stats.get('mttr_s', 'N/A'):.1f}s")
    print(f"  p95 latency (baseline):   {stats.get('p95_baseline_ms', 'N/A'):.1f}ms")
    print(f"  p99 latency (baseline):   {stats.get('p99_baseline_ms', 'N/A'):.1f}ms")
    print(f"  p95 latency (fault):      {stats.get('p95_fault_ms', 'N/A'):.1f}ms")
    print(f"  p99 latency (fault):      {stats.get('p99_fault_ms', 'N/A'):.1f}ms")


if __name__ == "__main__":
    main()
