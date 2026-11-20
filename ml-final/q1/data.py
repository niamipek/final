"""Fashion-MNIST cho Câu 1.

- Tải 4 file gốc (định dạng IDX, nén gzip) và đọc bằng NumPy, không cần torchvision.
- Chia 60k ảnh train gốc thành train 50k / val 10k, stratified theo nhãn.
- Test 10k giữ nguyên tập test chính thức.
- Tiền xử lý: chia 255 về [0, 1], sau đó standardize bằng mean/std
  tính trên tập train (sau khi chia), áp dụng cho cả val và test.

Chạy kiểm tra nhanh (từ thư mục ml-final/):
    python -m q1.data
"""

from __future__ import annotations

import gzip
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "fashion_mnist"

MIRRORS = [
    "http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/",
    "https://github.com/zalandoresearch/fashion-mnist/raw/master/data/fashion/",
]

FILES = {
    "train_images": "train-images-idx3-ubyte.gz",
    "train_labels": "train-labels-idx1-ubyte.gz",
    "test_images": "t10k-images-idx3-ubyte.gz",
    "test_labels": "t10k-labels-idx1-ubyte.gz",
}

CLASS_NAMES = [
    "T-shirt/top", "Trouser", "Pullover", "Dress", "Coat",
    "Sandal", "Shirt", "Sneaker", "Bag", "Ankle boot",
]

VAL_SIZE = 10_000
SEED = 42


@dataclass
class Split:
    X: np.ndarray  # (N, 784) float32, đã standardize
    y: np.ndarray  # (N,) int64


@dataclass
class FashionMNIST:
    train: Split
    val: Split
    test: Split
    mean: float  # mean/std của pixel (thang [0, 1]) trên tập train
    std: float


def _download(data_dir: Path = DATA_DIR) -> None:
    """Tải các file còn thiếu, thử lần lượt từng mirror."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for fname in FILES.values():
        target = data_dir / fname
        if target.exists():
            continue
        last_err: Exception | None = None
        for base in MIRRORS:
            try:
                print(f"Downloading {base + fname}")
                tmp = target.with_suffix(".part")
                urllib.request.urlretrieve(base + fname, tmp)
                tmp.rename(target)
                break
            except Exception as err:  # thử mirror tiếp theo
                last_err = err
        else:
            raise RuntimeError(f"Không tải được {fname}: {last_err}")


def _read_idx(path: Path) -> np.ndarray:
    """Đọc file IDX nén gzip (định dạng của MNIST / Fashion-MNIST)."""
    with gzip.open(path, "rb") as f:
        data = f.read()
    magic = int.from_bytes(data[0:4], "big")
    ndim = magic & 0xFF
    shape = tuple(int.from_bytes(data[4 + 4 * i: 8 + 4 * i], "big") for i in range(ndim))
    return np.frombuffer(data, dtype=np.uint8, offset=4 + 4 * ndim).reshape(shape)


def load_raw(data_dir: Path = DATA_DIR):
    """Trả về (X_train, y_train, X_test, y_test) dạng uint8, ảnh đã flatten thành 784."""
    _download(data_dir)
    X_train = _read_idx(data_dir / FILES["train_images"]).reshape(-1, 28 * 28)
    y_train = _read_idx(data_dir / FILES["train_labels"]).astype(np.int64)
    X_test = _read_idx(data_dir / FILES["test_images"]).reshape(-1, 28 * 28)
    y_test = _read_idx(data_dir / FILES["test_labels"]).astype(np.int64)
    return X_train, y_train, X_test, y_test


def load_fashion_mnist(seed: int = SEED, data_dir: Path = DATA_DIR) -> FashionMNIST:
    """Train 50k / val 10k (stratified) / test 10k, đã scale [0,1] và standardize."""
    X_full, y_full, X_test, y_test = load_raw(data_dir)

    X_tr, X_val, y_tr, y_val = train_test_split(
        X_full, y_full, test_size=VAL_SIZE, stratify=y_full, random_state=seed
    )

    # 1) Scale về [0, 1]
    X_tr = X_tr.astype(np.float32) / 255.0
    X_val = X_val.astype(np.float32) / 255.0
    X_te = X_test.astype(np.float32) / 255.0

    # 2) Standardize bằng thống kê của tập train (tránh rò rỉ từ val/test)
    mean = float(X_tr.mean())
    std = float(X_tr.std())
    X_tr = (X_tr - mean) / std
    X_val = (X_val - mean) / std
    X_te = (X_te - mean) / std

    return FashionMNIST(
        train=Split(X_tr, y_tr),
        val=Split(X_val, y_val),
        test=Split(X_te, y_test),
        mean=mean,
        std=std,
    )


def make_loaders(data: FashionMNIST, batch_size: int | None = 64, seed: int = SEED):
    """DataLoader PyTorch cho train/val/test.

    batch_size=None nghĩa là full-batch (dùng cho Gradient Descent thuần).
    Chỉ tập train được shuffle.
    """
    import torch
    from torch.utils.data import DataLoader, TensorDataset

    def ds(split: Split) -> TensorDataset:
        return TensorDataset(torch.from_numpy(split.X), torch.from_numpy(split.y))

    train_bs = len(data.train.y) if batch_size is None else batch_size
    gen = torch.Generator().manual_seed(seed)
    train = DataLoader(ds(data.train), batch_size=train_bs, shuffle=True, generator=gen)
    val = DataLoader(ds(data.val), batch_size=1024, shuffle=False)
    test = DataLoader(ds(data.test), batch_size=1024, shuffle=False)
    return train, val, test


if __name__ == "__main__":
    d = load_fashion_mnist()
    print(f"Pixel mean/std (train, thang [0,1]): {d.mean:.4f} / {d.std:.4f}")
    for name, s in [("train", d.train), ("val", d.val), ("test", d.test)]:
        counts = np.bincount(s.y, minlength=10)
        print(
            f"{name:5s} X={s.X.shape} y={s.y.shape} "
            f"mean={s.X.mean():+.4f} std={s.X.std():.4f} "
            f"so mau/lop: min={counts.min()} max={counts.max()}"
        )
