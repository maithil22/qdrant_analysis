#!/usr/bin/env python3
"""Create (or recreate) the Qdrant collection for SIFT-128 experiments."""
import argparse
import sys
import yaml
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    VectorParams,
)


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Experiment YAML config")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6333)
    args = parser.parse_args()

    exp_cfg = load_config(args.config)
    nodes_cfg = load_config(exp_cfg.get("nodes_config", "config/nodes.yaml"))
    col_cfg = nodes_cfg["collection"]

    rf = exp_cfg.get("replication_factor", 1)
    write_cf = exp_cfg.get("write_consistency", 1)

    client = QdrantClient(host=args.host, port=args.port, timeout=10)
    collection_name = col_cfg["name"]

    hnsw = col_cfg.get("hnsw_config", {})
    vector_params = VectorParams(
        size=col_cfg["vector_size"],
        distance=Distance.EUCLID,
    )
    hnsw_config = HnswConfigDiff(
        m=hnsw.get("m", 16),
        ef_construct=hnsw.get("ef_construct", 100),
        full_scan_threshold=hnsw.get("full_scan_threshold", 10000),
    )

    print(f"Creating collection '{collection_name}' (RF={rf}, write_consistency={write_cf}) ...")
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=vector_params,
        hnsw_config=hnsw_config,
        replication_factor=rf,
        write_consistency_factor=write_cf if isinstance(write_cf, int) else None,
    )

    info = client.get_collection(collection_name)
    print(f"Collection status: {info.status}")
    print(f"Points count: {info.points_count}")
    print("Done.")


if __name__ == "__main__":
    main()
