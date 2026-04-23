#!/usr/bin/env python3
"""Verify that all 1M vectors were ingested correctly."""
import argparse
import random
import sys
import yaml
import h5py
import numpy as np
from qdrant_client import QdrantClient

HDF5_PATH = "data/sift-128-euclidean.hdf5"
EXPECTED_COUNT = 1_000_000
SPOT_CHECK_N = 100


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6333)
    parser.add_argument("--hdf5", default=HDF5_PATH)
    args = parser.parse_args()

    exp_cfg = load_config(args.config)
    nodes_cfg = load_config(exp_cfg.get("nodes_config", "config/nodes.yaml"))
    collection_name = nodes_cfg["collection"]["name"]

    client = QdrantClient(host=args.host, port=args.port, timeout=10)
    info = client.get_collection(collection_name)
    count = info.points_count

    if count != EXPECTED_COUNT:
        print(f"FAIL: Expected {EXPECTED_COUNT:,} points, got {count:,}", file=sys.stderr)
        sys.exit(1)
    print(f"Count OK: {count:,} / {EXPECTED_COUNT:,}")

    rng = random.Random(42)
    sample_ids = rng.sample(range(EXPECTED_COUNT), SPOT_CHECK_N)

    with h5py.File(args.hdf5, "r") as f:
        train = f["train"]
        gt_vecs = {i: train[i].astype(np.float32) for i in sample_ids}

    points = client.retrieve(
        collection_name=collection_name,
        ids=sample_ids,
        with_vectors=True,
    )

    errors = 0
    for p in points:
        stored = np.array(p.vector, dtype=np.float32)
        expected = gt_vecs[p.id]
        dist = float(np.linalg.norm(stored - expected))
        if dist > 1e-4:
            print(f"  MISMATCH id={p.id} dist={dist:.6f}")
            errors += 1

    if errors:
        print(f"FAIL: {errors} vector mismatches", file=sys.stderr)
        sys.exit(1)

    print(f"Spot-check OK: {SPOT_CHECK_N} random vectors match ground truth")


if __name__ == "__main__":
    main()
