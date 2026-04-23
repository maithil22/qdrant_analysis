"""Unit tests for Recall@K computation."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from workload.recall import recall_at_k, batch_recall_at_k


def test_perfect_recall():
    true_ids = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    returned = list(range(10))
    assert recall_at_k(returned, true_ids, k=10) == 1.0


def test_zero_recall():
    true_ids = np.array([0, 1, 2, 3, 4])
    returned = [10, 11, 12, 13, 14]
    assert recall_at_k(returned, true_ids, k=5) == 0.0


def test_partial_recall():
    true_ids = np.array([0, 1, 2, 3, 4])
    returned = [0, 1, 10, 11, 12]
    assert recall_at_k(returned, true_ids, k=5) == pytest.approx(2 / 5)


def test_recall_uses_only_top_k():
    # true top-3 are [0,1,2]; returned top-3 are [10,11,12] — no overlap
    # 0,1,2 appear only at positions 3,4 of returned (outside top-3)
    true_ids = np.array([0, 1, 2, 5, 6])
    returned = [10, 11, 12, 0, 1]
    assert recall_at_k(returned, true_ids, k=3) == 0.0


def test_recall_k_smaller_than_available():
    true_ids = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    returned = [0, 1, 2]
    assert recall_at_k(returned, true_ids, k=3) == 1.0


def test_batch_recall_empty():
    result = batch_recall_at_k([], np.array([]), k=10)
    assert result != result  # nan


def test_batch_recall_mean():
    true_ids = np.array([[0, 1, 2, 3, 4]] * 2)
    # First query: perfect recall; second: zero recall
    returned = [[0, 1, 2, 3, 4], [10, 11, 12, 13, 14]]
    result = batch_recall_at_k(returned, true_ids, k=5)
    assert result == pytest.approx(0.5)
