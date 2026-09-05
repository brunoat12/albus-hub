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
