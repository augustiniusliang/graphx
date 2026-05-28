import numpy as np
from sklearn.cluster import KMeans


def kmeans(df, x_col, y_col, n_clusters=3, random_state=42):
    X = df[[x_col, y_col]].values
    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init="auto")
    labels = model.fit_predict(X)
    return {
        "type": "kmeans",
        "labels": labels,
        "centroids": model.cluster_centers_,
        "inertia": model.inertia_,
        "n_clusters": n_clusters,
    }


def elbow_method(df, x_col, y_col, max_k=10):
    X = df[[x_col, y_col]].values
    inertias = []
    ks = list(range(1, max_k + 1))
    for k in ks:
        model = KMeans(n_clusters=k, random_state=42, n_init="auto")
        model.fit(X)
        inertias.append(model.inertia_)
    # Simple knee detection: point furthest from line connecting endpoints
    optimal_k = max_k
    if max_k >= 3:
        p1 = np.array([ks[0], inertias[0]])
        p2 = np.array([ks[-1], inertias[-1]])
        distances = []
        for i in range(len(ks)):
            p = np.array([ks[i], inertias[i]])
            v = p2 - p1
            w = p1 - p
            d = abs(v[0] * w[1] - v[1] * w[0]) / np.linalg.norm(v)
            distances.append(d)
        optimal_k = ks[np.argmax(distances)]
    return {
        "type": "elbow",
        "k_values": ks,
        "inertias": inertias,
        "optimal_k": optimal_k,
    }
