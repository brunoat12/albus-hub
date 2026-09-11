from __future__ import annotations

import numpy as np

from albus_hub.models.risk.metrics import lift_by_decile, ranking_metrics_at_k


def test_ranking_metrics_at_k_reports_precision_recall_and_lift() -> None:
    y_true = np.array([1, 0, 1, 0, 0])
    probabilities = np.array([0.90, 0.80, 0.70, 0.20, 0.10])

    rows = ranking_metrics_at_k(
        y_true,
        probabilities,
        fractions=(0.40,),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["rows_reviewed"] == 2
    assert row["positives_found"] == 1
    assert row["precision_at_k"] == 0.5
    assert row["recall_at_k"] == 0.5
    assert row["lift_vs_base_rate"] == 1.25


def test_lift_by_decile_orders_highest_probabilities_first() -> None:
    y_true = np.array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0])
    probabilities = np.array([0.99, 0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20, 0.10])

    rows = lift_by_decile(y_true, probabilities, n_bins=10)

    assert len(rows) == 10
    assert rows[0]["decile"] == 1
    assert rows[0]["positives"] == 1
    assert rows[0]["precision"] == 1.0
    assert rows[0]["lift_vs_base_rate"] == 5.0
    assert rows[0]["cumulative_recall"] == 0.5
