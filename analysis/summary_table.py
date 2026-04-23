#!/usr/bin/env python3
"""Generate a summary markdown table across all experiment result directories."""
import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from analysis.parse_metrics import load_csv, compute_stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", default="results", help="Root results directory")
    args = parser.parse_args()

    root = Path(args.results_root)
    run_dirs = sorted(d for d in root.iterdir() if d.is_dir() and (d / "metrics.csv").exists())

    if not run_dirs:
        print(f"No experiment results found in {root}", file=sys.stderr)
        sys.exit(1)

    headers = [
        "Experiment", "RF", "Fault",
        "Baseline Recall", "Min Recall", "MTTR (s)",
        "p99 Baseline (ms)", "p99 Fault (ms)",
    ]
    rows_out = []

    for run_dir in run_dirs:
        rows = load_csv(run_dir / "metrics.csv")
        if not rows:
            continue
        stats = compute_stats(rows)
        rf = rows[0].get("replication_factor", "?")
        fault = rows[0].get("fault_type", "?")

        def fmt(v, decimals=4):
            if isinstance(v, float) and math.isnan(v):
                return "N/A"
            return f"{v:.{decimals}f}"

        rows_out.append([
            run_dir.name[:30],
            rf,
            fault,
            fmt(stats.get("baseline_recall", float("nan"))),
            fmt(stats.get("min_recall_during_fault", float("nan"))),
            fmt(stats.get("mttr_s", float("nan")), 1),
            fmt(stats.get("p99_baseline_ms", float("nan")), 1),
            fmt(stats.get("p99_fault_ms", float("nan")), 1),
        ])

    col_widths = [max(len(h), max((len(r[i]) for r in rows_out), default=0))
                  for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in col_widths) + " |"
    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"

    print(header_line)
    print(sep)
    for row in rows_out:
        print("| " + " | ".join(row[i].ljust(col_widths[i]) for i in range(len(headers))) + " |")


if __name__ == "__main__":
    main()
