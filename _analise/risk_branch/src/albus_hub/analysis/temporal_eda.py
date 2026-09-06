from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

PRIORITY_SCOPES = ("ALL", "P2", "P3")

COUNT_COLUMNS = [
    "incident_count",
    "entered_kpi_count",
    "kpi_breach_count",
    "monitoring_incident_count",
    "no_intervention_count",
]

REQUIRED_COLUMNS = [
    "reference_date",
    "priority_scope",
    *COUNT_COLUMNS,
]

WEEKDAY_LABELS = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
}

REGIME_CHANGE_DATE = pd.Timestamp("2025-09-01")

REGIME_COMPARISON_START_DATE = pd.Timestamp("2025-01-01")


def prepare_daily_volume(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """Valida e prepara a Gold diária para análise."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))

    if missing:
        raise ValueError(f"Gold diária sem colunas obrigatórias: {missing}")

    if frame.empty:
        raise ValueError("A Gold diária está vazia.")

    daily = frame[REQUIRED_COLUMNS].copy()

    daily["reference_date"] = pd.to_datetime(
        daily["reference_date"],
        errors="coerce",
    )

    if daily["reference_date"].isna().any():
        invalid_dates = int(daily["reference_date"].isna().sum())

        raise ValueError(f"A Gold diária possui {invalid_dates} datas inválidas.")

    unexpected_scopes = sorted(set(daily["priority_scope"].dropna()) - set(PRIORITY_SCOPES))

    if unexpected_scopes:
        raise ValueError(f"Escopos de prioridade inesperados: {unexpected_scopes}")

    duplicate_keys = int(
        daily.duplicated(
            [
                "reference_date",
                "priority_scope",
            ]
        ).sum()
    )

    if duplicate_keys:
        raise ValueError(f"A Gold diária possui {duplicate_keys} chaves duplicadas.")

    for column in COUNT_COLUMNS:
        daily[column] = pd.to_numeric(
            daily[column],
            errors="coerce",
        )

        if daily[column].isna().any():
            raise ValueError(f"A coluna {column} possui valores inválidos.")

        if (daily[column] < 0).any():
            raise ValueError(f"A coluna {column} possui valores negativos.")

        daily[column] = daily[column].astype("int64")

    return daily.sort_values(
        [
            "reference_date",
            "priority_scope",
        ]
    ).reset_index(drop=True)


def build_daily_features(
    daily_volume: pd.DataFrame,
) -> pd.DataFrame:
    """Adiciona atributos temporais e médias móveis."""
    daily = prepare_daily_volume(daily_volume)
    parts: list[pd.DataFrame] = []

    for scope in PRIORITY_SCOPES:
        scoped = daily.loc[daily["priority_scope"].eq(scope)].copy()

        if scoped.empty:
            continue

        scoped = scoped.sort_values("reference_date").reset_index(drop=True)

        scoped["rolling_mean_7"] = (
            scoped["incident_count"]
            .rolling(
                window=7,
                min_periods=1,
            )
            .mean()
        )

        scoped["rolling_mean_30"] = (
            scoped["incident_count"]
            .rolling(
                window=30,
                min_periods=1,
            )
            .mean()
        )

        scoped["day_of_week_number"] = scoped["reference_date"].dt.dayofweek

        scoped["day_of_week"] = scoped["day_of_week_number"].map(WEEKDAY_LABELS)

        scoped["year_month"] = scoped["reference_date"].dt.to_period("M").astype("string")

        scoped["is_weekend"] = scoped["day_of_week_number"] >= 5

        parts.append(scoped)

    return (
        pd.concat(
            parts,
            ignore_index=True,
        )
        .sort_values(
            [
                "reference_date",
                "priority_scope",
            ]
        )
        .reset_index(drop=True)
    )


def build_monthly_summary(
    daily_features: pd.DataFrame,
) -> pd.DataFrame:
    """Cria o resumo mensal por escopo."""
    monthly = (
        daily_features.groupby(
            [
                "year_month",
                "priority_scope",
            ],
            as_index=False,
        )
        .agg(
            observed_days=(
                "reference_date",
                "nunique",
            ),
            incident_count=(
                "incident_count",
                "sum",
            ),
            average_daily_incidents=(
                "incident_count",
                "mean",
            ),
            entered_kpi_count=(
                "entered_kpi_count",
                "sum",
            ),
            kpi_breach_count=(
                "kpi_breach_count",
                "sum",
            ),
            monitoring_incident_count=(
                "monitoring_incident_count",
                "sum",
            ),
            no_intervention_count=(
                "no_intervention_count",
                "sum",
            ),
        )
        .sort_values(
            [
                "year_month",
                "priority_scope",
            ]
        )
        .reset_index(drop=True)
    )

    monthly["monitoring_share"] = monthly["monitoring_incident_count"] / monthly[
        "incident_count"
    ].replace(0, pd.NA)

    monthly["no_intervention_share"] = monthly["no_intervention_count"] / monthly[
        "incident_count"
    ].replace(0, pd.NA)

    return monthly


def build_weekday_summary(
    daily_features: pd.DataFrame,
) -> pd.DataFrame:
    """Resume o comportamento por dia da semana."""
    return (
        daily_features.groupby(
            [
                "day_of_week_number",
                "day_of_week",
                "priority_scope",
            ],
            as_index=False,
        )
        .agg(
            observed_days=(
                "reference_date",
                "count",
            ),
            total_incidents=(
                "incident_count",
                "sum",
            ),
            average_incidents=(
                "incident_count",
                "mean",
            ),
            median_incidents=(
                "incident_count",
                "median",
            ),
            maximum_incidents=(
                "incident_count",
                "max",
            ),
        )
        .sort_values(
            [
                "priority_scope",
                "day_of_week_number",
            ]
        )
        .reset_index(drop=True)
    )


def build_peak_days(
    daily_features: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """Seleciona os maiores picos diários por escopo."""
    parts: list[pd.DataFrame] = []

    for scope in PRIORITY_SCOPES:
        scoped = (
            daily_features.loc[daily_features["priority_scope"].eq(scope)]
            .nlargest(
                top_n,
                "incident_count",
            )
            .copy()
        )

        scoped["peak_rank"] = range(
            1,
            len(scoped) + 1,
        )

        parts.append(scoped)

    return (
        pd.concat(
            parts,
            ignore_index=True,
        )[
            [
                "priority_scope",
                "peak_rank",
                "reference_date",
                "incident_count",
                "entered_kpi_count",
                "kpi_breach_count",
                "monitoring_incident_count",
                "no_intervention_count",
            ]
        ]
        .sort_values(
            [
                "priority_scope",
                "peak_rank",
            ]
        )
        .reset_index(drop=True)
    )


def build_regime_comparison(
    daily_features: pd.DataFrame,
    cutoff_date: pd.Timestamp = REGIME_CHANGE_DATE,
) -> pd.DataFrame:
    """Compara o comportamento antes e depois da mudança."""
    comparison = daily_features.copy()

    comparison = comparison.loc[
        comparison["reference_date"].ge(REGIME_COMPARISON_START_DATE)
    ].copy()

    comparison["regime"] = (
        comparison["reference_date"]
        .lt(cutoff_date)
        .map(
            {
                True: "before_2025_09",
                False: "from_2025_09",
            }
        )
    )

    result = (
        comparison.groupby(
            [
                "priority_scope",
                "regime",
            ],
            as_index=False,
        )
        .agg(
            observed_days=(
                "reference_date",
                "count",
            ),
            incident_count=(
                "incident_count",
                "sum",
            ),
            average_daily_incidents=(
                "incident_count",
                "mean",
            ),
            median_daily_incidents=(
                "incident_count",
                "median",
            ),
            standard_deviation=(
                "incident_count",
                "std",
            ),
            p95_daily_incidents=(
                "incident_count",
                lambda values: values.quantile(0.95),
            ),
            maximum_daily_incidents=(
                "incident_count",
                "max",
            ),
            entered_kpi_count=(
                "entered_kpi_count",
                "sum",
            ),
            kpi_breach_count=(
                "kpi_breach_count",
                "sum",
            ),
            monitoring_incident_count=(
                "monitoring_incident_count",
                "sum",
            ),
            no_intervention_count=(
                "no_intervention_count",
                "sum",
            ),
        )
        .sort_values(
            [
                "priority_scope",
                "regime",
            ]
        )
        .reset_index(drop=True)
    )

    result["monitoring_share"] = result["monitoring_incident_count"] / result[
        "incident_count"
    ].replace(0, pd.NA)

    result["no_intervention_share"] = result["no_intervention_count"] / result[
        "incident_count"
    ].replace(0, pd.NA)

    return result


def _save_figure(
    figure: Figure,
    output_path: Path,
) -> None:
    """Grava uma figura utilizando o backend não interativo."""
    FigureCanvasAgg(figure)

    figure.savefig(
        output_path,
        bbox_inches="tight",
        dpi=150,
    )


def save_temporal_plots(
    daily_features: pd.DataFrame,
    monthly_summary: pd.DataFrame,
    weekday_summary: pd.DataFrame,
    output_dir: Path,
) -> list[str]:
    """Gera os gráficos da análise temporal."""
    generated_files: list[str] = []

    figure = Figure(figsize=(14, 6))
    axis = figure.add_subplot(111)

    for scope in PRIORITY_SCOPES:
        scoped = daily_features.loc[daily_features["priority_scope"].eq(scope)]

        axis.plot(
            scoped["reference_date"],
            scoped["incident_count"],
            label=scope,
        )

    axis.axvline(
        REGIME_CHANGE_DATE,
        linestyle="--",
        label="Setembro/2025",
    )
    axis.set_title("Volume diário de incidentes")
    axis.set_xlabel("Data")
    axis.set_ylabel("Incidentes")
    axis.legend()
    axis.grid(alpha=0.25)

    path = output_dir / "daily_volume.png"
    _save_figure(figure, path)
    generated_files.append(path.name)

    figure = Figure(figsize=(14, 6))
    axis = figure.add_subplot(111)

    for scope in PRIORITY_SCOPES:
        scoped = monthly_summary.loc[monthly_summary["priority_scope"].eq(scope)]

        axis.plot(
            scoped["year_month"],
            scoped["incident_count"],
            marker="o",
            label=scope,
        )

    axis.set_title("Volume mensal de incidentes")
    axis.set_xlabel("Mês")
    axis.set_ylabel("Incidentes")
    axis.tick_params(
        axis="x",
        rotation=70,
    )
    axis.legend()
    axis.grid(alpha=0.25)

    path = output_dir / "monthly_volume.png"
    _save_figure(figure, path)
    generated_files.append(path.name)

    all_scope = daily_features.loc[daily_features["priority_scope"].eq("ALL")]

    figure = Figure(figsize=(14, 6))
    axis = figure.add_subplot(111)

    axis.plot(
        all_scope["reference_date"],
        all_scope["incident_count"],
        label="Volume diário",
        alpha=0.35,
    )
    axis.plot(
        all_scope["reference_date"],
        all_scope["rolling_mean_7"],
        label="Média móvel 7 dias",
    )
    axis.plot(
        all_scope["reference_date"],
        all_scope["rolling_mean_30"],
        label="Média móvel 30 dias",
    )
    axis.axvline(
        REGIME_CHANGE_DATE,
        linestyle="--",
        label="Setembro/2025",
    )
    axis.set_title("Volume total e médias móveis")
    axis.set_xlabel("Data")
    axis.set_ylabel("Incidentes")
    axis.legend()
    axis.grid(alpha=0.25)

    path = output_dir / "rolling_means_all.png"
    _save_figure(figure, path)
    generated_files.append(path.name)

    figure = Figure(figsize=(11, 6))
    axis = figure.add_subplot(111)

    for scope in PRIORITY_SCOPES:
        scoped = weekday_summary.loc[weekday_summary["priority_scope"].eq(scope)]

        axis.plot(
            scoped["day_of_week"],
            scoped["average_incidents"],
            marker="o",
            label=scope,
        )

    axis.set_title("Média diária por dia da semana")
    axis.set_xlabel("Dia da semana")
    axis.set_ylabel("Média de incidentes")
    axis.tick_params(
        axis="x",
        rotation=30,
    )
    axis.legend()
    axis.grid(alpha=0.25)

    path = output_dir / "weekday_average.png"
    _save_figure(figure, path)
    generated_files.append(path.name)

    all_monthly = monthly_summary.loc[monthly_summary["priority_scope"].eq("ALL")]

    figure = Figure(figsize=(14, 6))
    axis = figure.add_subplot(111)

    axis.plot(
        all_monthly["year_month"],
        all_monthly["monitoring_share"],
        marker="o",
        label="Monitoramento",
    )
    axis.plot(
        all_monthly["year_month"],
        all_monthly["no_intervention_share"],
        marker="o",
        label="Sem Intervenção",
    )
    axis.set_title("Participação mensal de monitoramento e Sem Intervenção")
    axis.set_xlabel("Mês")
    axis.set_ylabel("Participação")
    axis.tick_params(
        axis="x",
        rotation=70,
    )
    axis.legend()
    axis.grid(alpha=0.25)

    path = output_dir / "operational_shares.png"
    _save_figure(figure, path)
    generated_files.append(path.name)

    return generated_files


def build_temporal_report(
    daily_features: pd.DataFrame,
    monthly_summary: pd.DataFrame,
    peak_days: pd.DataFrame,
    regime_comparison: pd.DataFrame,
    generated_charts: list[str],
) -> dict[str, object]:
    """Monta o relatório JSON da análise."""
    zero_days = {
        scope: int(
            (
                daily_features.loc[
                    daily_features["priority_scope"].eq(scope),
                    "incident_count",
                ]
                == 0
            ).sum()
        )
        for scope in PRIORITY_SCOPES
    }

    top_peaks: dict[str, list[dict[str, object]]] = {}

    for scope in PRIORITY_SCOPES:
        scoped = peak_days.loc[peak_days["priority_scope"].eq(scope)].head(5)

        top_peaks[scope] = [
            {
                "rank": int(row.peak_rank),
                "reference_date": (row.reference_date.isoformat()),
                "incident_count": int(row.incident_count),
            }
            for row in scoped.itertuples()
        ]

    regime_ratios: dict[str, float | None] = {}

    for scope in PRIORITY_SCOPES:
        scoped = regime_comparison.loc[regime_comparison["priority_scope"].eq(scope)]

        before = scoped.loc[
            scoped["regime"].eq("before_2025_09"),
            "average_daily_incidents",
        ]

        after = scoped.loc[
            scoped["regime"].eq("from_2025_09"),
            "average_daily_incidents",
        ]

        if before.empty or after.empty or float(before.iloc[0]) == 0:
            regime_ratios[scope] = None
        else:
            regime_ratios[scope] = round(
                float(after.iloc[0]) / float(before.iloc[0]),
                4,
            )

    return {
        "generated_at_utc": (datetime.now(UTC).isoformat()),
        "quality_status": "passed",
        "reference_date_min": (daily_features["reference_date"].min().isoformat()),
        "reference_date_max": (daily_features["reference_date"].max().isoformat()),
        "daily_rows": int(len(daily_features)),
        "monthly_rows": int(len(monthly_summary)),
        "available_priority_scopes": list(PRIORITY_SCOPES),
        "regime_change_date": (REGIME_CHANGE_DATE.isoformat()),
        "regime_comparison_start_date": (REGIME_COMPARISON_START_DATE.isoformat()),
        "zero_incident_days_by_scope": zero_days,
        "average_daily_ratio_after_vs_before": (regime_ratios),
        "top_peak_days": top_peaks,
        "generated_charts": generated_charts,
    }


def run_temporal_eda(
    daily_volume_path: Path,
    output_dir: Path,
    report_path: Path,
) -> dict[str, object]:
    """Executa a análise exploratória temporal."""
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    daily_volume = pd.read_parquet(daily_volume_path)

    daily_features = build_daily_features(daily_volume)
    monthly_summary = build_monthly_summary(daily_features)
    weekday_summary = build_weekday_summary(daily_features)
    peak_days = build_peak_days(daily_features)
    regime_comparison = build_regime_comparison(daily_features)

    daily_features.to_csv(
        output_dir / "daily_features.csv",
        index=False,
    )
    monthly_summary.to_csv(
        output_dir / "monthly_summary.csv",
        index=False,
    )
    weekday_summary.to_csv(
        output_dir / "weekday_summary.csv",
        index=False,
    )
    peak_days.to_csv(
        output_dir / "peak_days.csv",
        index=False,
    )
    regime_comparison.to_csv(
        output_dir / "regime_comparison.csv",
        index=False,
    )

    generated_charts = save_temporal_plots(
        daily_features=daily_features,
        monthly_summary=monthly_summary,
        weekday_summary=weekday_summary,
        output_dir=output_dir,
    )

    report = build_temporal_report(
        daily_features=daily_features,
        monthly_summary=monthly_summary,
        peak_days=peak_days,
        regime_comparison=regime_comparison,
        generated_charts=generated_charts,
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return report
