from pathlib import Path

import pandas as pd
import pytest

from albus_hub.analysis.temporal_eda import (
    build_daily_features,
    build_monthly_summary,
    build_peak_days,
    build_regime_comparison,
    build_weekday_summary,
    prepare_daily_volume,
    run_temporal_eda,
)


def make_sample_daily_volume() -> pd.DataFrame:
    """Cria uma Gold diária sintética antes e depois de setembro."""
    dates = pd.date_range(
        "2025-08-29",
        "2025-09-03",
        freq="D",
    )

    counts_by_scope = {
        "ALL": [10, 12, 8, 100, 120, 110],
        "P2": [2, 3, 1, 20, 25, 22],
        "P3": [4, 5, 3, 40, 45, 42],
    }

    rows: list[dict[str, object]] = []

    for scope, counts in counts_by_scope.items():
        for date, incident_count in zip(
            dates,
            counts,
            strict=True,
        ):
            rows.append(
                {
                    "reference_date": date,
                    "priority_scope": scope,
                    "incident_count": incident_count,
                    "entered_kpi_count": (incident_count // 2),
                    "kpi_breach_count": (1 if incident_count >= 100 else 0),
                    "monitoring_incident_count": (incident_count // 3),
                    "no_intervention_count": (incident_count // 4),
                }
            )

    return pd.DataFrame(rows)


def test_prepare_daily_volume_validates_and_sorts() -> None:
    sample = make_sample_daily_volume().sample(
        frac=1,
        random_state=42,
    )

    result = prepare_daily_volume(sample)

    assert len(result) == 18
    assert set(result["priority_scope"]) == {
        "ALL",
        "P2",
        "P3",
    }

    assert result["reference_date"].dtype.kind == "M"

    assert not result.duplicated(
        [
            "reference_date",
            "priority_scope",
        ]
    ).any()


def test_prepare_daily_volume_rejects_duplicate_keys() -> None:
    sample = make_sample_daily_volume()

    duplicated = pd.concat(
        [
            sample,
            sample.iloc[[0]],
        ],
        ignore_index=True,
    )

    with pytest.raises(
        ValueError,
        match="chaves duplicadas",
    ):
        prepare_daily_volume(duplicated)


def test_build_daily_features_calculates_rolling_means() -> None:
    result = build_daily_features(make_sample_daily_volume())

    all_scope = (
        result.loc[result["priority_scope"].eq("ALL")]
        .sort_values("reference_date")
        .reset_index(drop=True)
    )

    assert all_scope.loc[0, "rolling_mean_7"] == 10
    assert all_scope.loc[1, "rolling_mean_7"] == 11
    assert all_scope.loc[2, "rolling_mean_7"] == 10
    assert all_scope.loc[3, "rolling_mean_7"] == 32.5

    assert all_scope.loc[0, "day_of_week"] == "Sexta"
    assert bool(all_scope.loc[1, "is_weekend"]) is True
    assert all_scope.loc[3, "year_month"] == "2025-09"


def test_temporal_summaries_are_created() -> None:
    features = build_daily_features(make_sample_daily_volume())

    monthly = build_monthly_summary(features)
    weekday = build_weekday_summary(features)
    peaks = build_peak_days(
        features,
        top_n=2,
    )

    # Dois meses para cada um dos três escopos.
    assert len(monthly) == 6

    august_all = monthly.loc[
        monthly["year_month"].eq("2025-08") & monthly["priority_scope"].eq("ALL")
    ]

    assert len(august_all) == 1
    assert august_all.iloc[0]["incident_count"] == 30
    assert august_all.iloc[0]["observed_days"] == 3

    assert set(weekday["day_of_week"]) == {
        "Segunda",
        "Terça",
        "Quarta",
        "Sexta",
        "Sábado",
        "Domingo",
    }

    all_peaks = peaks.loc[peaks["priority_scope"].eq("ALL")]

    assert len(all_peaks) == 2
    assert all_peaks.iloc[0]["incident_count"] == 120
    assert all_peaks.iloc[0]["peak_rank"] == 1


def test_regime_comparison_detects_volume_change() -> None:
    features = build_daily_features(make_sample_daily_volume())

    comparison = build_regime_comparison(features)

    all_scope = comparison.loc[comparison["priority_scope"].eq("ALL")]

    before = all_scope.loc[all_scope["regime"].eq("before_2025_09")].iloc[0]

    after = all_scope.loc[all_scope["regime"].eq("from_2025_09")].iloc[0]

    assert before["observed_days"] == 3
    assert after["observed_days"] == 3

    assert before["average_daily_incidents"] == 10
    assert after["average_daily_incidents"] == 110

    assert after["average_daily_incidents"] == (before["average_daily_incidents"] * 11)


def test_run_temporal_eda_writes_outputs(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "daily_volume.parquet"
    output_dir = tmp_path / "eda"
    report_path = output_dir / "report.json"

    make_sample_daily_volume().to_parquet(
        source_path,
        index=False,
    )

    report = run_temporal_eda(
        daily_volume_path=source_path,
        output_dir=output_dir,
        report_path=report_path,
    )

    assert report["quality_status"] == "passed"

    assert report["average_daily_ratio_after_vs_before"]["ALL"] == 11.0

    expected_files = {
        "daily_features.csv",
        "monthly_summary.csv",
        "weekday_summary.csv",
        "peak_days.csv",
        "regime_comparison.csv",
        "daily_volume.png",
        "monthly_volume.png",
        "rolling_means_all.png",
        "weekday_average.png",
        "operational_shares.png",
        "report.json",
    }

    generated_files = {path.name for path in output_dir.iterdir() if path.is_file()}

    assert expected_files == generated_files
