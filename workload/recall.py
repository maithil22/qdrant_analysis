"""Recall@K computation and ground-truth loader for SIFT-128."""
import numpy as np
import h5py


def load_ground_truth(
    hdf5_path: str,
    n_queries: int = 500,
    k: int = 10,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Load a fixed random subsample of query vectors and their ground-truth neighbor IDs.

    Returns:
        test_vecs:      shape (n_queries, 128) float32
        true_neighbors: shape (n_queries, k)   int32  — row indices into /train
    """
    with h5py.File(hdf5_path, "r") as f:
        test_vecs = f["test"][:]        # (10000, 128)
        neighbors = f["neighbors"][:]   # (10000, 100)

    rng = np.random.default_rng(seed)
    idx = rng.choice(len(test_vecs), size=min(n_queries, len(test_vecs)), replace=False)
    return test_vecs[idx].astype(np.float32), neighbors[idx, :k].astype(np.int64)


def recall_at_k(returned_ids: list[int], true_ids: np.ndarray, k: int) -> float:
    """Recall@K = |intersection of returned top-K and true top-K| / K."""
    true_set = set(int(x) for x in true_ids[:k])
    returned_set = set(int(x) for x in returned_ids[:k])
    return len(true_set & returned_set) / k


def batch_recall_at_k(
    returned_ids_batch: list[list[int]],
    true_ids_batch: np.ndarray,
    k: int,
) -> float:
    """Mean Recall@K over a batch of queries."""
    if not returned_ids_batch:
        return float("nan")
    recalls = [
        recall_at_k(r, t, k)
        for r, t in zip(returned_ids_batch, true_ids_batch)
    ]
    return float(np.mean(recalls))
