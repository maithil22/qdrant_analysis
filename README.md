# Qdrant Fault-Tolerance Analysis

Measures how **Replication Factor (RF)** and **failure timing** affect Recall@K degradation, tail latency (p95/p99), and Mean Time to Recovery (MTTR) in [Qdrant](https://qdrant.tech/) during live fault injection.

**Dataset:** ANN-Benchmarks SIFT-128 — 1M 128-dimensional vectors with precomputed ground truth.

## Results so far

| Experiment | Baseline Recall | Fault behavior | MTTR (from heal) | p99 recovery spike |
|---|---|---|---|---|
| RF=1 kill | ~0.997 | Binary outage (100% down) | ~2.3s | 437ms (one interval) |
| RF=2 kill | — | — | — | — |
| RF=2 partition | — | — | — | — |
| RF=3 kill | — | — | — | — |
| RF=3 partition | — | — | — | — |

**RF=1 kill key finding:** failure is all-or-nothing — no graceful recall degradation, just a hard outage for the duration of the fault window. Recall returns to 1.0 immediately on restart because data survives on disk.

## Setup

### Requirements

- Linux host (CloudLab or similar) with `sudo`
- Python 3.10+
- Qdrant v1.13.6+

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
