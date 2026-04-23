#!/usr/bin/env python3
"""Download the ANN-benchmarks SIFT-128 dataset."""
import os
import sys
import urllib.request

URL = "http://ann-benchmarks.com/sift-128-euclidean.hdf5"
DEST = os.path.join(os.path.dirname(__file__), "sift-128-euclidean.hdf5")
EXPECTED_BYTES = 512_000_000  # ~500MB


class _Progress:
    def __init__(self, total: int):
        self.total = total
        self.seen = 0

    def __call__(self, blocks: int, block_size: int, total: int):
        if total > 0:
            self.total = total
        self.seen = min(blocks * block_size, self.total)
        pct = 100 * self.seen / max(self.total, 1)
        mb = self.seen / 1024 / 1024
        total_mb = self.total / 1024 / 1024
        print(f"\r  {pct:.1f}%  {mb:.0f} / {total_mb:.0f} MB", end="", flush=True)


def main():
    if os.path.exists(DEST):
        size = os.path.getsize(DEST)
        if size > EXPECTED_BYTES // 2:
            print(f"Already downloaded: {DEST} ({size / 1e6:.0f} MB)")
            return
        print(f"Partial file found ({size} bytes), re-downloading ...")

    print(f"Downloading {URL} -> {DEST}")
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (X11; Linux x86_64)")]
    urllib.request.install_opener(opener)
    progress = _Progress(EXPECTED_BYTES)
    urllib.request.urlretrieve(URL, DEST, reporthook=progress)
    print()

    import h5py
    with h5py.File(DEST, "r") as f:
        train_shape = f["train"].shape
        test_shape = f["test"].shape
        neighbors_shape = f["neighbors"].shape

    assert train_shape == (1_000_000, 128), f"Unexpected train shape: {train_shape}"
    assert test_shape == (10_000, 128), f"Unexpected test shape: {test_shape}"
    assert neighbors_shape[0] == 10_000, f"Unexpected neighbors shape: {neighbors_shape}"

    print(f"train: {train_shape}, test: {test_shape}, neighbors: {neighbors_shape}")
    print("Download verified OK.")


if __name__ == "__main__":
    main()
