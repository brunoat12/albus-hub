from pathlib import Path

import pandas as pd

from albus_hub.gold.daily_volume import (
    MISSING_DIMENSION_VALUE,
    build_daily_breakdown,
    build_daily_volume,
    build_gold_report,
    run_daily_volume_gold,
)


def make_sample_silver() -> pd.DataFrame:
    """Cria uma Silver sintética para os testes."""
    return pd.DataFrame(
        {
            "incident_id": [
                "INC0000001",
                "INC0000002",
                "INC0000003",
                "INC0000004",
            ],
            "opened_at": pd.to_datetime(
                [
                    "2025-01-01 08:00:00",
                    "2025-01-01 09:00:00",
                    "2025-01-03 10:00:00",
                    "2025-01-03 11:00:00",
                ]
            ),
            "priority_code": pd.Series(
                [2, 3, 4, 2],
                dtype="Int64",
            ),
            "assigned_group": [
                "Grupo A",
                "Grupo A",
                "Grupo B",
                "Grupo B",
            ],
            "product": [
                "Produto A",
                pd.NA,
                "Produto B",
                "Produto A",
            ],
            "category": [
                "Categoria 1",
                "Categoria 2",
                pd.NA,
                "Categoria 1",
            ],
            "configuration_item": [
                "CI-1",
                "CI-2",
                pd.NA,
                "CI-1",
            ],
            "parent_incident_id": [
                "INC-PARENT-1",
                pd.NA,
                "INC-PARENT-2",
                "INC-PARENT-1",
            ],
            "entered_kpi_source": pd.Series(
                [True, True, False, True],
                dtype="boolean",
            ),
            "kpi_breached_source": pd.Series(
                [True, False, pd.NA, False],
                dtype="boolean",
            ),
            "opened_by": [
                "Manual",
                "Monitoramento",
                "Monitoramento",
                "Manual",
            ],
            "status": [
                "Encerrado",
                "Encerrado",
                "Sem Intervenção",
                "Encerrado",
            ],
        }
    )


def select_daily_row(
    frame: pd.DataFrame,
    reference_date: str,
    priority_scope: str,
) -> pd.Series:
    """Seleciona uma linha específica da série diária."""
    selected = frame.loc[
        frame["reference_date"].eq(pd.Timestamp(reference_date))
        & frame["priority_scope"].eq(priority_scope)
    ]

    assert len(selected) == 1

    return selected.iloc[0]


def test_build_daily_volume_creates_continuous_series() -> None:
    silver = make_sample_silver()

    result = build_daily_volume(silver)

    # Três dias, multiplicados pelos três escopos.
    assert len(result) == 9

    assert set(result["priority_scope"]) == {
        "ALL",
        "P2",
        "P3",
    }

    january_first = select_daily_row(
        result,
        "2025-01-01",
        "ALL",
    )

    assert january_first["incident_count"] == 2
    assert january_first["entered_kpi_count"] == 2
    assert january_first["kpi_breach_count"] == 1
    assert january_first["monitoring_incident_count"] == 1
    assert january_first["no_intervention_count"] == 0

    january_second = select_daily_row(
        result,
        "2025-01-02",
        "ALL",
    )

    assert january_second["incident_count"] == 0
    assert january_second["entered_kpi_count"] == 0
    assert january_second["kpi_breach_count"] == 0

    january_third = select_daily_row(
        result,
        "2025-01-03",
        "ALL",
    )

    assert january_third["incident_count"] == 2
    assert january_third["entered_kpi_count"] == 1
    assert january_third["monitoring_incident_count"] == 1
    assert january_third["no_intervention_count"] == 1

    assert (
        result.loc[
            result["priority_scope"].eq("P2"),
            "incident_count",
        ].sum()
        == 2
    )

    assert (
        result.loc[
            result["priority_scope"].eq("P3"),
            "incident_count",
        ].sum()
        == 1
    )


def test_daily_volume_has_unique_keys_and_no_null_counts() -> None:
    result = build_daily_volume(make_sample_silver())

    assert not result.duplicated(
        [
            "reference_date",
            "priority_scope",
        ]
    ).any()

    count_columns = [
        "incident_count",
        "entered_kpi_count",
        "kpi_breach_count",
        "monitoring_incident_count",
        "no_intervention_count",
    ]

    assert not result[count_columns].isna().any().any()
    assert (result[count_columns] >= 0).all().all()


def test_build_daily_breakdown_preserves_missing_values() -> None:
    silver = make_sample_silver()

    result = build_daily_breakdown(silver)

    missing_product = result.loc[
        result["reference_date"].eq(pd.Timestamp("2025-01-01"))
        & result["dimension_name"].eq("product")
        & result["dimension_value"].eq(MISSING_DIMENSION_VALUE)
        & result["priority_scope"].eq("P3")
    ]

    assert len(missing_product) == 1
    assert missing_product.iloc[0]["incident_count"] == 1

    group_a = result.loc[
        result["reference_date"].eq(pd.Timestamp("2025-01-01"))
        & result["dimension_name"].eq("assigned_group")
        & result["dimension_value"].eq("Grupo A")
        & result["priority_scope"].eq("ALL")
    ]

    assert len(group_a) == 1
    assert group_a.iloc[0]["incident_count"] == 2

    critical_group = result.loc[
        result["reference_date"].eq(pd.Timestamp("2025-01-01"))
        & result["dimension_name"].eq("critical_group")
        & result["dimension_value"].eq("Produto A | Categoria 1 | P2")
        & result["priority_scope"].eq("ALL")
    ]

    assert len(critical_group) == 1
    assert critical_group.iloc[0]["incident_count"] == 1
    assert critical_group.iloc[0]["entered_kpi_count"] == 1
    assert critical_group.iloc[0]["kpi_breach_count"] == 1

    parent_group = result.loc[
        result["dimension_name"].eq("parent_incident_id")
        & result["dimension_value"].eq("INC-PARENT-1")
        & result["priority_scope"].eq("ALL")
    ]

    assert parent_group["incident_count"].sum() == 2

    assert not result["dimension_value"].isna().any()

    assert not result.duplicated(
        [
            "reference_date",
            "dimension_name",
            "dimension_value",
            "priority_scope",
        ]
    ).any()


def test_build_gold_report_reconciles_with_silver() -> None:
    silver = make_sample_silver()
    daily_volume = build_daily_volume(silver)
    breakdown = build_daily_breakdown(silver)

    report = build_gold_report(
        silver,
        daily_volume,
        breakdown,
    )

    assert report["quality_status"] == "passed"

    assert report["checks"] == {
        "daily_duplicate_keys": 0,
        "breakdown_duplicate_keys": 0,
        "daily_null_values": 0,
        "breakdown_null_values": 0,
        "negative_counts": 0,
        "reconciliation_failed": 0,
    }

    assert report["reconciliation"]["ALL"] == {
        "source_count": 4,
        "gold_count": 4,
        "matches": True,
    }

    assert report["reconciliation"]["P2"] == {
        "source_count": 2,
        "gold_count": 2,
        "matches": True,
    }

    assert report["reconciliation"]["P3"] == {
        "source_count": 1,
        "gold_count": 1,
        "matches": True,
    }


def test_run_daily_volume_gold_writes_outputs(
    tmp_path: Path,
) -> None:
    silver_path = tmp_path / "silver.parquet"
    daily_path = tmp_path / "daily.parquet"
    breakdown_path = tmp_path / "breakdown.parquet"
    report_path = tmp_path / "report.json"

    make_sample_silver().to_parquet(
        silver_path,
        index=False,
    )

    report = run_daily_volume_gold(
        silver_path=silver_path,
        daily_volume_path=daily_path,
        breakdown_path=breakdown_path,
        report_path=report_path,
    )

    assert report["quality_status"] == "passed"
    assert daily_path.exists()
    assert breakdown_path.exists()
    assert report_path.exists()

    daily = pd.read_parquet(daily_path)
    breakdown = pd.read_parquet(breakdown_path)

    assert len(daily) == 9
    assert not breakdown.empty
