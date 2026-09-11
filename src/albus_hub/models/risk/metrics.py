from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)


def classification_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> dict[str, object]:
    """Calcula métricas adequadas para a classe rara de violação."""
    y_true = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    predictions = probabilities >= threshold
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true,
        predictions,
        average="binary",
        zero_division=0,
    )
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        "threshold": float(threshold),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "confusion_matrix": {
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        },
    }


def ranking_metrics_at_k(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    fractions: tuple[float, ...] = (0.05, 0.10, 0.20, 0.30),
) -> list[dict[str, float | int]]:
    """Mede precisão, recall e lift ao revisar as maiores probabilidades."""
    y_true = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)

    if y_true.shape[0] != probabilities.shape[0]:
        raise ValueError("y_true e probabilities devem ter o mesmo tamanho.")
    if y_true.size == 0:
        return []

    order = np.argsort(-probabilities, kind="stable")
    ranked_target = y_true[order]

    total_rows = int(y_true.size)
    total_positives = int(y_true.sum())
    base_rate = float(y_true.mean())

    rows: list[dict[str, float | int]] = []
    for fraction in fractions:
        if not 0 < fraction <= 1:
            raise ValueError("Cada fração deve estar no intervalo (0, 1].")

        k = max(1, int(np.ceil(total_rows * fraction)))
        positives_in_top_k = int(ranked_target[:k].sum())
        precision_at_k = positives_in_top_k / k
        recall_at_k = positives_in_top_k / total_positives if total_positives else 0.0
        lift = precision_at_k / base_rate if base_rate > 0 else 0.0

        rows.append(
            {
                "requested_fraction": float(fraction),
                "rows_reviewed": int(k),
                "actual_fraction": float(k / total_rows),
                "positives_found": positives_in_top_k,
                "precision_at_k": float(precision_at_k),
                "recall_at_k": float(recall_at_k),
                "lift_vs_base_rate": float(lift),
            }
        )
    return rows


def lift_by_decile(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    n_bins: int = 10,
) -> list[dict[str, float | int]]:
    """Calcula lift e captura acumulada em faixas ordenadas por risco."""
    y_true = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)

    if y_true.shape[0] != probabilities.shape[0]:
        raise ValueError("y_true e probabilities devem ter o mesmo tamanho.")
    if y_true.size == 0:
        return []
    if n_bins < 2:
        raise ValueError("n_bins deve ser pelo menos 2.")

    order = np.argsort(-probabilities, kind="stable")
    ranked = pd.DataFrame(
        {
            "target": y_true[order],
            "probability": probabilities[order],
        }
    )
    ranked["bin"] = np.minimum(
        (np.arange(len(ranked)) * n_bins // len(ranked)) + 1,
        n_bins,
    )

    base_rate = float(ranked["target"].mean())
    total_positives = int(ranked["target"].sum())
    cumulative_positives = 0

    rows: list[dict[str, float | int]] = []
    for bin_number, group in ranked.groupby("bin", sort=True):
        positives = int(group["target"].sum())
        cumulative_positives += positives
        precision = float(group["target"].mean())
        lift = precision / base_rate if base_rate > 0 else 0.0
        cumulative_recall = cumulative_positives / total_positives if total_positives else 0.0

        rows.append(
            {
                "decile": int(bin_number),
                "rows": int(len(group)),
                "positives": positives,
                "precision": precision,
                "lift_vs_base_rate": float(lift),
                "cumulative_recall": float(cumulative_recall),
                "probability_min": float(group["probability"].min()),
                "probability_max": float(group["probability"].max()),
            }
        )
    return rows


def select_operating_threshold(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    minimum_recall: float = 0.70,
) -> tuple[float, pd.DataFrame]:
    """Prioriza recall mínimo e, dentro dele, maximiza precisão e F1."""
    candidates = np.unique(
        np.concatenate(
            [
                np.arange(0.01, 0.51, 0.01),
                np.array([0.30, 0.40, 0.50, 0.60]),
                np.quantile(probabilities, np.linspace(0.70, 0.995, 40)),
            ]
        )
    )
    rows = []
    for threshold in candidates:
        metrics = classification_metrics(y_true, probabilities, float(threshold))
        rows.append({key: metrics[key] for key in ["threshold", "precision", "recall", "f1"]})
    table = pd.DataFrame(rows).sort_values("threshold").reset_index(drop=True)
    eligible = table.loc[table["recall"].ge(minimum_recall)]
    if eligible.empty:
        selected = table.sort_values(["f1", "recall", "precision"], ascending=False).iloc[0]
    else:
        selected = eligible.sort_values(
            ["precision", "f1", "threshold"], ascending=[False, False, False]
        ).iloc[0]
    return float(selected["threshold"]), table
