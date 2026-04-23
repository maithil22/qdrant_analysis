PYTHON    := .venv/bin/python
PIP       := .venv/bin/pip
CONFIG    ?= config/experiment_rf1_kill.yaml
RESULTS_DIR ?= $(shell ls -td results/*/ 2>/dev/null | head -1)

.PHONY: venv install-qdrant download-data ingest verify smoke-test experiment plot clean help

help:
	@echo "Targets:"
	@echo "  venv            Create .venv and install Python deps"
	@echo "  install-qdrant  Download Qdrant binary and install systemd service (sudo)"
	@echo "  download-data   Download sift-128-euclidean.hdf5 (~500MB)"
	@echo "  ingest          Ingest 1M vectors into Qdrant  (CONFIG=...)"
	@echo "  verify          Verify ingestion count and spot-check vectors"
	@echo "  smoke-test      Run unit tests + baseline recall check"
	@echo "  experiment      Run a full fault-injection experiment  (CONFIG=...)"
	@echo "  plot            Plot results from RESULTS_DIR"
	@echo "  clean           Remove .venv and __pycache__"

venv:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(PIP) freeze > requirements.txt
	@echo "Virtualenv ready. Activate with: source .venv/bin/activate"

install-qdrant:
	sudo bash setup/install_qdrant.sh

download-data:
	$(PYTHON) data/download_sift.py

ingest:
	$(PYTHON) setup/create_collection.py --config $(CONFIG)
	$(PYTHON) data/ingest.py --config $(CONFIG)

verify:
	$(PYTHON) data/verify_ingest.py --config $(CONFIG)

smoke-test:
	$(PYTHON) -m pytest tests/ -v
	$(PYTHON) -c "\
import sys; sys.path.insert(0, '.'); \
from workload.recall import load_ground_truth, recall_at_k; \
from qdrant_client import QdrantClient; \
from qdrant_client.models import SearchParams; \
import numpy as np; \
client = QdrantClient('localhost', port=6333, timeout=5); \
vecs, neighbors = load_ground_truth('data/sift-128-euclidean.hdf5', n_queries=200, k=10); \
recalls = [recall_at_k([r.id for r in client.search('sift128', vecs[i].tolist(), limit=10, with_payload=False, search_params=SearchParams(hnsw_ef=128))], neighbors[i], 10) for i in range(200)]; \
r = np.mean(recalls); \
print(f'Baseline Recall@10 = {r:.4f}'); \
assert r > 0.90, f'Recall too low: {r}'; \
print('PASS')"

experiment:
	$(PYTHON) workload/query_runner.py --config $(CONFIG)

plot:
	$(PYTHON) analysis/plot_recall.py --results-dir $(RESULTS_DIR)
	$(PYTHON) analysis/plot_latency.py --results-dir $(RESULTS_DIR)
	$(PYTHON) analysis/parse_metrics.py --results-dir $(RESULTS_DIR)

clean:
	rm -rf .venv __pycache__ */__pycache__ .pytest_cache
