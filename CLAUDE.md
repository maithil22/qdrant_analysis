# Qdrant Fault-Tolerance Analysis

## Project Overview

Measures how Replication Factor (RF) and failure timing affect Recall@K degradation, tail latency (p95/p99), and Mean Time to Recovery (MTTR) in Qdrant during live fault injection. Dataset: ANN-Benchmarks SIFT-128 (~1M 128-dim vectors, precomputed ground truth).

## Quick Start (Single Node)

```bash
# 1. Create virtualenv and install Python deps
make venv

# 2. Install Qdrant binary + systemd service (requires sudo)
make install-qdrant

# 3. Download SIFT-128 dataset (~500MB)
make download-data

# 4. Create collection and ingest 1M vectors
make ingest CONFIG=config/experiment_rf1_kill.yaml

# 5. Verify ingestion
make verify

# 6. Run unit tests + baseline recall check
make smoke-test

# 7. Run a full single-node experiment
make experiment CONFIG=config/experiment_rf1_kill.yaml

# 8. Plot results
make plot RESULTS_DIR=results/<run_dir>
```

## Cluster Setup (3 Nodes)

```bash
# Fill in node1/node2 IPs in config/nodes.yaml, then:
NODE_ID=1 bash setup/install_qdrant.sh  # run on node1
NODE_ID=2 bash setup/install_qdrant.sh  # run on node2

# Bootstrap cluster from node0
bash setup/configure_cluster.sh

# Verify all 3 peers active
python3 setup/health_check.py --config config/nodes.yaml

# Run cluster experiments
make experiment CONFIG=config/experiment_rf2_kill.yaml
make experiment CONFIG=config/experiment_rf3_partition.yaml
```

## Project Structure

```
config/          YAML configs for nodes, experiments, Qdrant
setup/           Install scripts, cluster bootstrap, collection creation
data/            Download SIFT-128, ingest to Qdrant, verify
workload/        Continuous query loop, recall computation, CSV metrics
fault_injection/ kill -9 and iptables partition scripts + unified CLI
analysis/        Parse CSVs, compute MTTR, generate plots
tests/           Unit tests (recall math, config validation)
results/         Output directory (gitignored), one subdir per run
```

## Key Design Decisions

- **Native Qdrant binary + systemd**: Host iptables rules hit the process directly; Docker complicates fault injection.
- **File-based CSV metrics**: Avoids Prometheus/Grafana setup on ephemeral CloudLab nodes.
- **Point ID = HDF5 row index**: Directly matches `/neighbors` ground truth; no ID translation needed.
- **Recall sampling every 300ms**: Sub-second granularity without blocking the query thread.
- **SSH-based fault injection**: CloudLab injects SSH keys; no persistent agent needed on target nodes.

## Experiment Parameters

| Parameter | Values Tested |
|---|---|
| Replication Factor | 1, 2, 3 |
| Failure Mode | kill (kill -9), partition (iptables DROP) |
| Read Consistency | eventual, majority, quorum |
| Query Rate | 50 QPS |
| Recall@K | K=10 |
| HNSW ef_search | 128 |

## Expected Baselines

- Recall@10 on SIFT-128 (ef_search=128): ~0.97
- MTTR after kill with RF=1: ∞ (data lost until restart)
- MTTR after kill with RF=2: seconds (remaining replica serves queries)
- MTTR after partition with RF=3: ~0 (quorum preserved)

## Common Commands

```bash
# Check Qdrant health (v1.13.6+: root or /readyz)
curl -s http://localhost:6333/readyz

# Check collection status
curl -s http://localhost:6333/collections/sift128

# Tail experiment metrics live
tail -f results/<run_dir>/metrics.csv

# Inject fault manually (single-node)
python3 fault_injection/fault.py --action kill --local
python3 fault_injection/fault.py --action heal --local

# Inject fault on cluster node
python3 fault_injection/fault.py --action partition --target-node 1 --nodes-config config/nodes.yaml
```
