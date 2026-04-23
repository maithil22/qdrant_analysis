#!/usr/bin/env python3
"""Plot p95/p99 latency over time for an experiment run."""
import argparse
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_csv(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))


def to_float(v: str) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return float("nan")


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
    elapsed = [to_float(r["elapsed_s"]) for r in rows]
    p95 = [to_float(r["p95_ms"]) for r in rows]
    p99 = [to_float(r["p99_ms"]) for r in rows]
    fault_active = [r["fault_active"] == "1" for r in rows]

    fault_start = next((elapsed[i] for i, fa in enumerate(fault_active) if fa), None)
    fault_end = next((elapsed[i] for i in reversed(range(len(rows))) if fault_active[i]), None)

    fig, ax = plt.subplots(figsize=(12, 5))

    if fault_start is not None and fault_end is not None:
        ax.axvspan(fault_start, fault_end, alpha=0.15, color="red", label="Fault active")

    ax.plot(elapsed, p95, linewidth=1.2, color="orange", label="p95 latency (ms)")
    ax.plot(elapsed, p99, linewidth=1.2, color="crimson", label="p99 latency (ms)")

    ax.set_xlabel("Elapsed (s)")
    ax.set_ylabel("Latency (ms)")
    ax.set_title(f"Tail Latency over time — {results_dir.name}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    out = results_dir / "latency_over_time.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
