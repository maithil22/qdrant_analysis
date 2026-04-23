#!/usr/bin/env python3
"""Ingest SIFT-128 train vectors into Qdrant. Point ID = row index."""
import argparse
import time
import yaml
import h5py
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

HDF5_PATH = "data/sift-128-euclidean.hdf5"
BATCH_SIZE = 256
LOG_EVERY = 10_000


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def ingest(client: QdrantClient, collection_name: str, hdf5_path: str = HDF5_PATH):
    with h5py.File(hdf5_path, "r") as f:
        train = f["train"]
        n_vectors = train.shape[0]
        print(f"Ingesting {n_vectors:,} vectors into '{collection_name}' ...")

        t0 = time.monotonic()
        i = 0
        while i < n_vectors:
            end = min(i + BATCH_SIZE, n_vectors)
            batch_vecs = train[i:end].astype(np.float32)
            points = [
                PointStruct(id=i + j, vector=batch_vecs[j].tolist())
                for j in range(len(batch_vecs))
            ]
            client.upsert(collection_name=collection_name, points=points, wait=False)
            i = end
            if i % LOG_EVERY == 0 or i == n_vectors:
                elapsed = time.monotonic() - t0
                rate = i / elapsed
                remaining = (n_vectors - i) / rate if rate > 0 else float("inf")
                print(
                    f"  {i:>9,} / {n_vectors:,}  "
                    f"({100*i/n_vectors:.1f}%)  "
                    f"{rate:,.0f} vec/s  "
                    f"ETA {remaining:.0f}s"
                )

    elapsed = time.monotonic() - t0
    print(f"Ingestion complete: {n_vectors:,} vectors in {elapsed:.1f}s "
          f"({n_vectors/elapsed:,.0f} vec/s)")


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

    client = QdrantClient(host=args.host, port=args.port, timeout=30)
    ingest(client, collection_name, args.hdf5)


if __name__ == "__main__":
    main()
