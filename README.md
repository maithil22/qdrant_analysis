# Qdrant Fault-Tolerance Analysis

Measures how **Replication Factor (RF)** and **failure timing** affect Recall@K degradation, tail latency (p95/p99), and Mean Time to Recovery (MTTR) in [Qdrant](https://qdrant.tech/) during live fault injection.

**Dataset:** ANN-Benchmarks SIFT-128 — 1M 128-dimensional vectors with precomputed ground truth.

# Experiment Results
 
## Summary Table
 
| Metric                  | RF=1 Kill | RF=2 Kill | RF=3 Kill |
|-------------------------|-----------|-----------|-----------|
| Baseline Recall@10      | —         | 0.9991    | —         |
| Fault Recall@10 (avg)   | —         | 0.9987    | —         |
| Fault Recall@10 (min)   | —         | 0.9867    | —         |
| Fault Behavior          | —         | Zero degradation, 0 errors | — |
| Baseline p99 (ms)       | —         | 14.5      | —         |
| Fault p99 avg (ms)      | —         | 12.9      | —         |
| Fault p99 max (ms)      | —         | 18.9      | —         |
| Recovery p99 spike (ms) | —         | 17.4      | —         |
| MTTR from heal (s)      | —         | 0.3       | —         |
| Errors during fault     | —         | 0         | —         |
 
## Key Findings
 
### RF=2 Kill (Node 1 killed via `kill -9`)
 
- **Zero recall degradation**: Recall@10 remained at 0.9987 during the 60s fault window, compared to a 0.9991 baseline — a difference of just 0.0004, well within noise.
- **No query failures**: All 50 QPS queries were served successfully by the surviving replica with zero errors.
- **Fault p99 lower than baseline**: Fault p99 (12.9ms) was actually lower than baseline p99 (14.5ms). With one node dead, queries fan out to fewer replicas, reducing coordination overhead.
- **Near-instant MTTR**: Recall returned to baseline within 0.3s of heal, indicating Raft leader election and shard recovery are fast.
- **Conclusion**: RF=2 completely masks a single-node crash from the query path — both search quality and latency are unaffected.
### RF=1 Kill
 
*(To be filled after experiment)*
 
### RF=3 Kill
 
*(To be filled after experiment)*
 
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
- **Fault injection**: `kill -9` via SSH + systemd on target node
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
