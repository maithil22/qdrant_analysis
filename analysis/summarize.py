#!/usr/bin/env python3
"""Extract summary table for a single experiment run."""
import csv, sys, os

def summarize(results_dir):
    csv_path = os.path.join(results_dir, "metrics.csv")
    rows = list(csv.DictReader(open(csv_path)))

    baseline_recalls = [float(r['recall_at_k']) for r in rows if r['recall_at_k'] and float(r['elapsed_s']) < 30]
    baseline_p99 = [float(r['p99_ms']) for r in rows if r['p99_ms'] and float(r['elapsed_s']) < 30]

    fault_recalls = [float(r['recall_at_k']) for r in rows if r['recall_at_k'] and r['fault_active'] == '1']
    fault_p99 = [float(r['p99_ms']) for r in rows if r['p99_ms'] and r['fault_active'] == '1']
    fault_errors = sum(int(r['error_count']) for r in rows if r['fault_active'] == '1')

    heal_time = max(float(r['elapsed_s']) for r in rows if r['fault_active'] == '1')
    recovery_rows = [r for r in rows if r['fault_active'] == '0' and float(r['elapsed_s']) > heal_time]
    recovery_p99 = [float(r['p99_ms']) for r in recovery_rows if r['p99_ms']]

    baseline_avg = sum(baseline_recalls)/len(baseline_recalls) if baseline_recalls else 0
    mttr = 0
    for r in recovery_rows:
        if r['recall_at_k'] and float(r['recall_at_k']) >= baseline_avg - 0.01:
            mttr = float(r['elapsed_s']) - heal_time
            break

    rf = rows[0].get('replication_factor', '?')
    print(f"=== RF={rf} KILL SUMMARY ({os.path.basename(results_dir)}) ===")
    print(f"Baseline Recall@10:    {baseline_avg:.4f}" if baseline_recalls else "Baseline Recall@10:    N/A")
    print(f"Fault Recall@10 avg:   {sum(fault_recalls)/len(fault_recalls):.4f} (min: {min(fault_recalls):.4f})" if fault_recalls else "Fault Recall@10:       N/A (all queries failed)")
    print(f"Baseline p99:          {sum(baseline_p99)/len(baseline_p99):.1f}ms" if baseline_p99 else "Baseline p99:          N/A")
    print(f"Fault p99 avg:         {sum(fault_p99)/len(fault_p99):.1f}ms (max: {max(fault_p99):.1f}ms)" if fault_p99 else "Fault p99:             N/A")
    print(f"Recovery p99 spike:    {max(recovery_p99):.1f}ms" if recovery_p99 else "Recovery p99 spike:    N/A")
    print(f"MTTR (from heal):      {mttr:.1f}s")
    print(f"Errors during fault:   {fault_errors}")

if __name__ == "__main__":
    summarize(sys.argv[1])
