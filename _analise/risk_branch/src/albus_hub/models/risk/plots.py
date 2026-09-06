from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

BLUE = "#2F6BFF"
GOLD = "#D8A31A"
INK = "#202735"
GRID = "#D9DEE8"


def _style_axis(axis) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color(INK)
    axis.tick_params(colors=INK)
    axis.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.7)


def create_risk_figures(
    eligible: pd.DataFrame,
    y_test: np.ndarray,
    baseline_probabilities: np.ndarray,
    ann_probabilities: np.ndarray,
    test_metrics: dict[str, object],
    output_dir: Path,
) -> list[Path]:
    """Gera um conjunto pequeno de figuras analiticamente úteis para o notebook."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    counts = eligible["kpi_breached_source"].value_counts().reindex([False, True], fill_value=0)
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.bar(["Não violou", "Violou"], counts.to_numpy(), color=[BLUE, GOLD])
    axis.set_yscale("log")
    axis.set_title("Distribuição do target de violação do KPI", color=INK)
    axis.set_ylabel("Incidentes (escala log)")
    for index, value in enumerate(counts):
        axis.text(index, value * 1.08, f"{value:,}".replace(",", "."), ha="center")
    _style_axis(axis)
    path = output_dir / "target_distribution.png"
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)
    paths.append(path)

    priority = eligible.groupby("priority_code")["kpi_breached_source"].agg(["size", "mean"])
    figure, axis = plt.subplots(figsize=(7, 4))
    labels = [f"P{int(value)}" for value in priority.index]
    rates = 100 * priority["mean"]
    axis.bar(labels, rates, color=BLUE)
    axis.set_title("Taxa de violação por prioridade", color=INK)
    axis.set_ylabel("Violações entre elegíveis (%)")
    axis.set_ylim(0, max(float(rates.max()) * 1.3, 1.2))
    for index, (rate, volume) in enumerate(zip(rates, priority["size"], strict=True)):
        axis.text(index, rate + 0.03, f"{rate:.2f}%\nn={volume:,}".replace(",", "."), ha="center")
    _style_axis(axis)
    path = output_dir / "breach_rate_by_priority.png"
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)
    paths.append(path)

    monthly = (
        eligible.assign(month=eligible["opened_at"].dt.to_period("M").dt.to_timestamp())
        .groupby("month")["kpi_breached_source"]
        .agg(eligible="size", breaches="sum")
    )
    monthly["breach_rate"] = 100 * monthly["breaches"] / monthly["eligible"]
    figure, (rate_axis, volume_axis) = plt.subplots(
        2,
        1,
        figsize=(10, 6),
        sharex=True,
        gridspec_kw={"height_ratios": [2, 1]},
    )
    rate_axis.plot(
        monthly.index,
        monthly["breach_rate"],
        color=BLUE,
        marker="o",
        markersize=3,
    )
    rate_axis.set_title("Taxa mensal de violação entre incidentes elegíveis", color=INK)
    rate_axis.set_ylabel("Violações (%)")
    _style_axis(rate_axis)
    volume_axis.bar(monthly.index, monthly["eligible"], width=20, color=GOLD)
    volume_axis.set_ylabel("Elegíveis")
    volume_axis.set_xlabel("Mês de abertura — jan/2023 a dez/2025")
    _style_axis(volume_axis)
    path = output_dir / "monthly_breach_rate.png"
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)
    paths.append(path)

    figure, axis = plt.subplots(figsize=(7, 5))
    for label, probabilities, color in [
        ("Regressão logística", baseline_probabilities, GOLD),
        ("ANN calibrada", ann_probabilities, BLUE),
    ]:
        precision, recall, _ = precision_recall_curve(y_test, probabilities)
        axis.plot(recall, precision, label=label, color=color, linewidth=2)
    axis.axhline(float(np.mean(y_test)), color=INK, linestyle="--", label="Prevalência")
    axis.set_title("Curvas Precision–Recall no teste temporal", color=INK)
    axis.set_xlabel("Recall")
    axis.set_ylabel("Precision")
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.legend(frameon=False)
    _style_axis(axis)
    path = output_dir / "precision_recall_test.png"
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)
    paths.append(path)

    matrix = test_metrics["confusion_matrix"]
    values = np.array(
        [
            [matrix["true_negative"], matrix["false_positive"]],
            [matrix["false_negative"], matrix["true_positive"]],
        ]
    )
    figure, axis = plt.subplots(figsize=(5.5, 4.5))
    image = axis.imshow(values, cmap="Blues")
    for row in range(2):
        for column in range(2):
            axis.text(column, row, str(values[row, column]), ha="center", va="center")
    axis.set_xticks([0, 1], ["Previsto 0", "Previsto 1"])
    axis.set_yticks([0, 1], ["Real 0", "Real 1"])
    axis.set_title("Matriz de confusão — ANN no teste temporal", color=INK)
    figure.colorbar(image, ax=axis, shrink=0.8)
    path = output_dir / "confusion_matrix_test.png"
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)
    paths.append(path)
    return paths
