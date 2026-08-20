from __future__ import annotations

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, silhouette_score


def evaluate_clusters(
    values: np.ndarray,
    target: np.ndarray,
    validation_values: np.ndarray,
    validation_target: np.ndarray,
    baseline_validation_pr_auc: float,
    seed: int,
) -> dict[str, object]:
    """Avalia K-Means sem usar o target no ajuste e mede separação operacional."""
    rng = np.random.default_rng(seed)
    sample_size = min(len(values), 6000)
    sample_indices = np.sort(rng.choice(len(values), size=sample_size, replace=False))
    sample_values = values[sample_indices]
    sample_target = np.asarray(target)[sample_indices]
    candidates = []

    for clusters in (2, 3, 4, 5):
        model = MiniBatchKMeans(
            n_clusters=clusters,
            random_state=seed,
            n_init=10,
            batch_size=512,
        )
        labels = model.fit_predict(sample_values)
        silhouette = silhouette_score(
            sample_values,
            labels,
            sample_size=min(2000, sample_size),
            random_state=seed,
        )
        cluster_rates = {
            str(label): float(sample_target[labels == label].mean())
            for label in range(clusters)
        }
        candidates.append(
            {
                "clusters": clusters,
                "silhouette": float(silhouette),
                "breach_rates": cluster_rates,
            }
        )

    best = max(candidates, key=lambda item: item["silhouette"])
    selected_clusters = int(best["clusters"])
    cluster_model = MiniBatchKMeans(
        n_clusters=selected_clusters,
        random_state=seed,
        n_init=10,
        batch_size=512,
    ).fit(values)
    train_labels = cluster_model.predict(values)
    validation_labels = cluster_model.predict(validation_values)
    identity = np.eye(selected_clusters, dtype=np.float32)
    augmented_train = np.column_stack([values, identity[train_labels]])
    augmented_validation = np.column_stack(
        [validation_values, identity[validation_labels]]
    )
    comparison_model = LogisticRegression(
        class_weight="balanced",
        max_iter=1500,
        random_state=seed,
        solver="lbfgs",
    ).fit(augmented_train, target)
    augmented_probability = comparison_model.predict_proba(augmented_validation)[:, 1]
    augmented_pr_auc = float(
        average_precision_score(validation_target, augmented_probability)
    )
    absolute_gain = augmented_pr_auc - baseline_validation_pr_auc
    useful = best["silhouette"] >= 0.10 and absolute_gain >= 0.005
    return {
        "sample_size": sample_size,
        "candidates": candidates,
        "selected_clusters": selected_clusters,
        "selected_silhouette": best["silhouette"],
        "baseline_validation_pr_auc": baseline_validation_pr_auc,
        "baseline_with_cluster_validation_pr_auc": augmented_pr_auc,
        "absolute_pr_auc_gain": absolute_gain,
        "use_as_model_feature": useful,
        "conclusion": (
            "Cluster melhora materialmente o baseline e deve ser testado no modelo final."
            if useful
            else "Cluster não melhora o PR-AUC o suficiente para entrar no modelo final."
        ),
    }
