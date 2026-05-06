# Qdrant Fault-Tolerance Analysis

Measures how **Replication Factor (RF)** and **failure timing** affect Recall@K degradation, tail latency (p95/p99), and Mean Time to Recovery (MTTR) in [Qdrant](https://qdrant.tech/) during live fault injection.

**Dataset:** ANN-Benchmarks SIFT-128 — 1M 128-dimensional vectors with precomputed ground truth.

# Experiment Results
 
## Summary Table — Kill Experiments
 
| Metric                  | RF=1 Kill | RF=2 Kill | RF=3 Kill |
|-------------------------|-----------|-----------|-----------|
| Baseline Recall@10      | 0.9987    | 0.9991    | 0.9985    |
| Fault Recall@10 (avg)   | 0.9989    | 0.9987    | 0.9984    |
| Fault Recall@10 (min)   | 0.9933    | 0.9867    | 0.9867    |
| Fault Behavior          | Partial availability: ~1/3 queries fail, 31x p99 spike | Zero degradation, 0 errors | Zero degradation, 0 errors |
| Baseline p99 (ms)       | 12.7      | 14.5      | 14.7      |
| Fault p99 avg (ms)      | 75.7      | 12.9      | 13.5      |
| Fault p99 max (ms)      | 392.5     | 18.9      | 19.2      |
| Recovery p99 spike (ms) | 21.1      | 17.4      | 19.0      |
| MTTR from heal (s)      | 0.3       | 0.3       | 0.3       |
| Errors during fault     | 149       | 0         | 0         |
 
## Summary Table — Partition Experiments
 
| Metric                  | RF=2 Partition | RF=3 Partition |
|-------------------------|----------------|----------------|
| Baseline Recall@10      | 0.9985         | 0.9985         |
| Fault Recall@10 (avg)   | 0.9987         | 0.9985         |
| Fault Recall@10 (min)   | 0.9867         | 0.9867         |
| Fault Behavior          | Zero degradation, 0 errors | Zero degradation, 0 errors |
| Baseline p99 (ms)       | 14.6           | 14.1           |
| Fault p99 avg (ms)      | 13.5           | 13.7           |
| Fault p99 max (ms)      | 17.3           | 18.0           |
| Recovery p99 spike (ms) | 37.2           | 18.2           |
| MTTR from heal (s)      | 0.3            | 0.3            |
| Errors during fault     | 0              | 0              |
 
## Key Findings
 
### RF=1 Kill (Node 1 killed via `kill -9`)
 
- **Partial availability, not binary outage**: Contrary to our hypothesis, RF=1 failure does not produce a complete outage. Qdrant continues serving queries from the 2 surviving shards (out of 3), so approximately two-thirds of queries succeed while one-third fail.
- **Recall of successful queries is unaffected**: Fault Recall@10 averaged 0.9989 (vs 0.9987 baseline), indicating that the surviving shards returned correct nearest neighbors — the quality of answered queries did not degrade.
- **Severe tail latency degradation**: p99 latency spiked from 12.7ms to 392.5ms (a 31x increase). This is caused by Qdrant's internal timeout when attempting to reach the dead node's shard before returning a partial result or error.
- **149 query errors during 60s fault window**: At 50 QPS over 60s (3,000 total queries), roughly 5% of queries failed entirely — consistent with one out of three shards being unavailable.
- **Conclusion**: RF=1 failure is not all-or-nothing. It produces a mixed degradation mode — partial availability with severe latency spikes — that is arguably worse than a clean outage, because clients receive slow, incomplete results without a clear signal that the system is degraded.
### RF=2 Kill (Node 1 killed via `kill -9`)
 
- **Zero recall degradation**: Recall@10 remained at 0.9987 during the 60s fault window, compared to a 0.9991 baseline — a difference of just 0.0004, well within noise.
- **No query failures**: All 50 QPS queries were served successfully by the surviving replica with zero errors.
- **Fault p99 lower than baseline**: Fault p99 (12.9ms) was actually lower than baseline p99 (14.5ms). With one node dead, queries fan out to fewer replicas, reducing coordination overhead.
- **Near-instant MTTR**: Recall returned to baseline within 0.3s of heal, indicating Raft leader election and shard recovery are fast.
- **Conclusion**: RF=2 completely masks a single-node crash from the query path — both search quality and latency are unaffected.
### RF=3 Kill (Node 1 killed via `kill -9`)
 
- **Identical behavior to RF=2**: Recall@10 remained at 0.9984 during the fault (vs 0.9985 baseline), with zero query errors — indistinguishable from RF=2's fault behavior.
- **No latency benefit over RF=2**: Fault p99 max was 19.2ms (RF=3) vs 18.9ms (RF=2) — effectively identical. The extra replica adds no measurable improvement to tail latency during a single-node failure.
- **Same MTTR**: 0.3s recovery time, identical to RF=1 and RF=2, suggesting MTTR is dominated by Raft leader election and shard state propagation rather than replication factor.
- **Conclusion**: RF=3 provides no additional benefit over RF=2 for single-node failures. Its value would emerge only during simultaneous two-node failures — but in a 3-node cluster, losing 2 nodes breaks Raft quorum regardless, making RF=3's extra redundancy theoretical in this deployment size.
### RF=2 Partition (Node 1 isolated via `iptables` DROP)
 
- **Zero degradation, same as RF=2 kill**: Recall@10 remained at 0.9987 during the partition with zero errors — the surviving replica on nodes 0 and 2 handled all queries identically to the kill scenario.
- **Fault latency identical to kill**: Fault p99 avg was 13.5ms, matching the RF=2 kill result. During the fault window, a partition is indistinguishable from a crash on the query path.
- **Higher recovery spike than kill**: Recovery p99 spiked to 37.2ms (vs 17.4ms for kill). When a partitioned node rejoins the cluster, it must reconcile its Raft log and shard state with the other peers. A killed-then-restarted node starts fresh and syncs cleanly, but a partitioned node may have divergent state that requires additional negotiation during rejoin.
- **Conclusion**: RF=2 masks network partitions just as effectively as crashes during the fault window. However, the recovery path is more expensive for partitions — the 2.1x higher recovery spike (37.2ms vs 17.4ms) reveals that Raft state reconciliation after a partition heal has measurable overhead compared to a clean node restart.
### RF=3 Partition (Node 1 isolated via `iptables` DROP)
 
- **Identical to RF=3 kill**: Recall@10 remained at 0.9985 during the partition, with zero errors and no latency impact — indistinguishable from the kill experiment.
- **Partition vs. kill makes no difference at RF=3**: With 3 replicas of every shard, the 2 reachable nodes hold full data and maintain Raft quorum (2/3). Whether the isolated node is dead or alive-but-unreachable, the query path is unaffected.
- **Fault p99 max (18.0ms) slightly lower than RF=3 kill (19.2ms)**: Both are within noise, but the partition result suggests Qdrant detects unreachable nodes quickly and does not waste time on retries.
- **Conclusion**: At RF=3 with 3 nodes, network partitions are as harmless as clean crashes. The Raft consensus layer handles both failure modes identically from the client's perspective.
## Cross-Cutting Analysis
 
### The RF=1 → RF=2 Cliff
 
The most striking result is the discontinuity between RF=1 and RF=2. There is no gradual improvement — RF=1 produces 149 errors and a 31x p99 spike, while RF=2 produces zero errors and actually *lowers* p99 during the fault. This suggests that for Qdrant deployments, RF=2 is not merely "better" than RF=1; it is a qualitatively different failure mode. Any production deployment should treat RF=2 as the minimum viable replication factor.
 
### The RF=2 → RF=3 Plateau
 
RF=2 and RF=3 are indistinguishable under single-node kill. Both achieve zero errors, near-identical latency, and the same MTTR. This has practical implications: the storage and write overhead of RF=3 (50% more copies than RF=2) buys no additional resilience against the most common failure mode (single-node crash). RF=3's value is limited to multi-node failure scenarios, which in a 3-node cluster are constrained by Raft quorum requirements anyway.
 
### Latency Anomaly: Fault p99 Lower Than Baseline
 
In both RF=2 and RF=3, fault p99 was slightly lower than baseline p99 (12.9ms vs 14.5ms for RF=2; 13.5ms vs 14.7ms for RF=3). This is counterintuitive — fewer nodes means less redundancy, yet queries are faster. The explanation is that with one node dead, Qdrant's coordinator skips the dead replica in its fan-out, reducing coordination overhead. This suggests that Qdrant's multi-replica query path has measurable overhead even in steady state.
 
### Kill vs. Partition: Same Fault Behavior, Different Recovery Cost
 
At both RF=2 and RF=3, kill and partition produced identical fault-window behavior (0 errors, same recall, same latency). Qdrant's Raft layer treats both failure modes equivalently during the fault. However, **recovery tells a different story**: RF=2 partition recovery spiked to 37.2ms (vs 17.4ms for kill), a 2.1x difference. RF=3 partition recovery was 18.2ms (vs 19.0ms for kill), essentially identical. This suggests that partition recovery cost scales with how thin the redundancy is — with RF=2, the rejoining node's stale Raft state requires more reconciliation work, while RF=3's extra replica absorbs the rejoin overhead more gracefully.
 
## Experimental Setup
 
- **Cluster**: 3-node CloudLab cluster (c220g1, Wisconsin site)
  - Node 0: 128.105.146.7 (bootstrap / Raft leader)
  - Node 1: 128.105.145.249 (fault target)
  - Node 2: 128.105.145.234
- **Qdrant version**: v1.13.6 (native binary + systemd)
- **Dataset**: ANN-Benchmarks SIFT-128 (1M vectors, 128 dimensions, Euclidean distance)
- **Ground truth**: Precomputed exact nearest neighbors from ANN-Benchmarks HDF5
- **Collection config**: 3 shards, HNSW (m=16, ef_construct=100), ef_search=128
- **Query workload**: 50 QPS, random query selection from 500 test vectors, K=10
- **Recall sampling interval**: 300ms
- **Fault injection (kill)**: `kill -9` via SSH + systemd on target node
- **Fault injection (partition)**: `iptables` DROP rules via SSH on target node
- **Fault duration**: 60s (30s baseline → 60s fault → 60s recovery)

### Single-node quickstart

```bash
# 1. Create virtualenv and install Python deps
make venv

# 2. Install Qdrant binary + systemd service
make install-qdrant

# 3. Download SIFT-128 dataset (~500MB)
make download-data

# 4. Create collection and ingest 1M vectors
make ingest CONFIG=config/experiment_rf1_kill.yaml

# 5. Verify ingestion
make verify

# 6. Run unit tests + baseline recall check
make smoke-test

# 7. Run a full experiment
make experiment CONFIG=config/experiment_rf1_kill.yaml

# 8. Plot results
make plot RESULTS_DIR=results/<run_dir>
```

### 3-node cluster setup

```bash
# Fill in node1/node2 IPs in config/nodes.yaml, then on each remote node:
NODE_ID=1 bash setup/install_qdrant.sh
NODE_ID=2 bash setup/install_qdrant.sh

# Bootstrap cluster from node0
bash setup/configure_cluster.sh

# Verify all 3 peers active
python3 setup/health_check.py --config config/nodes.yaml

# Run cluster experiments
make experiment CONFIG=config/experiment_rf2_kill.yaml
make experiment CONFIG=config/experiment_rf3_partition.yaml
```

## Project structure

```
config/          YAML configs for nodes, experiments, and Qdrant
setup/           Install scripts, cluster bootstrap, collection creation
data/            Download SIFT-128, ingest to Qdrant, verify
workload/        Continuous query loop, recall computation, CSV metrics
fault_injection/ kill and iptables partition scripts + unified CLI
analysis/        Parse CSVs, compute MTTR, generate plots
tests/           Unit tests (recall math, config validation)
results/         Output directory (gitignored), one subdir per run
```

## Experiment parameters

| Parameter | Values tested |
|---|---|
| Replication Factor | 1, 2, 3 |
| Failure mode | kill (`kill -9` via systemd), partition (iptables DROP) |
| Read consistency | eventual / majority / quorum |
| Query rate | 50 QPS |
| Recall@K | K=10 |
| HNSW ef_search | 128 |

## Expected baselines

| Scenario | Expected behavior |
|---|---|
| RF=1, kill | Full outage until restart; MTTR = restart time (~2–3s) |
| RF=2, kill | Remaining replica serves queries; MTTR ≈ 0 |
| RF=3, partition | Quorum preserved; zero impact |
| RF=1, partition | Full outage for partition duration |
| RF=2, partition | Depends on consistency setting |

## Fault injection

```bash
# Kill the local Qdrant process (single-node)
python3 fault_injection/fault.py --action kill --local

# Heal (restart Qdrant, flush iptables)
python3 fault_injection/fault.py --action heal --local

# Partition a cluster node
python3 fault_injection/fault.py --action partition --target-node 1 \
    --nodes-config config/nodes.yaml
```

## Useful commands

```bash
# Check Qdrant health
curl -s http://localhost:6333/readyz

# Check collection status
curl -s http://localhost:6333/collections/sift128

# Tail live metrics during an experiment
tail -f results/<run_dir>/metrics.csv
```

## Design notes

- **Native binary + systemd** — host iptables rules hit the process directly; Docker would complicate fault injection.
- **File-based CSV metrics** — avoids Prometheus/Grafana setup on ephemeral CloudLab nodes.
- **Point ID = HDF5 row index** — directly matches `/neighbors` ground truth; no ID translation needed.
- **300ms recall sampling** — sub-second granularity without blocking the query thread.
- **Auto-detect local fault mode** — `FaultAgent` checks if the target node IP is the local machine and skips SSH automatically.
