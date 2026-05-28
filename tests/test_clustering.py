import numpy as np
import pandas as pd
from graphx.analysis.clustering import kmeans, elbow_method


def _make_blob_data(n_samples=150):
    rng = np.random.default_rng(42)
    # 3 well-separated blobs
    centers = [(0, 0), (5, 5), (10, 0)]
    xs, ys = [], []
    for cx, cy in centers:
        xs.extend(rng.normal(cx, 0.5, n_samples // 3))
        ys.extend(rng.normal(cy, 0.5, n_samples // 3))
    return pd.DataFrame({"x": xs, "y": ys})


def test_kmeans_returns_correct_shape():
    df = _make_blob_data()
    result = kmeans(df, "x", "y", n_clusters=3)
    assert len(result["labels"]) == len(df)
    assert result["centroids"].shape == (3, 2)
    assert result["n_clusters"] == 3


def test_kmeans_keys():
    df = _make_blob_data()
    result = kmeans(df, "x", "y")
    for key in ("type", "labels", "centroids", "inertia", "n_clusters"):
        assert key in result


def test_elbow_method_length():
    df = _make_blob_data()
    result = elbow_method(df, "x", "y", max_k=8)
    assert len(result["k_values"]) == 8
    assert len(result["inertias"]) == 8


def test_elbow_optimal_k_in_range():
    df = _make_blob_data()
    result = elbow_method(df, "x", "y", max_k=6)
    assert 1 <= result["optimal_k"] <= 6


def test_inertias_decreasing():
    df = _make_blob_data()
    result = elbow_method(df, "x", "y", max_k=5)
    for i in range(len(result["inertias"]) - 1):
        assert result["inertias"][i] >= result["inertias"][i + 1]
