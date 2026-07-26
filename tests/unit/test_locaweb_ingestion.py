from __future__ import annotations

import json

import pandas as pd

from albus_hub.ingestion.locaweb import SOURCE_COLUMNS, run_ingestion


def test_locaweb_ingestion_with_synthetic_excel(tmp_path) -> None:
    source = pd.DataFrame(
        [
            [
                "INC0000001",
                "2 - Alta",
                "prod1",
                "cat1",
                "sub1",
                "Team01",
                "IC00001",
                "01/01/2025 08:00:00",
                "01/01/2025 09:00:00",
                "01/01/2025 09:10:00",
                3600,
                "Falha de Aplicação",
                "Falha simulada",
                "Definitiva",
                "Manual",
                "",
                "Encerrado",
                "SIM",
                "NAO",
            ],
            [
                "INC0000002",
                "3 - Média",
                "prod2",
                "cat2",
                "sub2",
                "Team02",
                "IC00002",
                "02/01/2025 08:00:00",
                "",
                "02/01/2025 09:00:00",
                3600,
                "Outro",
                "Incidente relacionado",
                "",
                "Monitoramento",
                "INC0000001",
                "Encerrado Automaticamente",
                "NAO",
                "N/A",
            ],
            [
                "INC0000003",
                "4 - Baixa",
                "",
                "",
                "",
                "Team03",
                "IC00003",
                "03/01/2025 08:00:00",
                "",
                "03/01/2025 08:10:00",
                600,
                "",
                "Alerta sem intervenção",
                "",
                "Monitoramento",
                "",
                "Sem Intervenção",
                "NAO",
                "N/A",
            ],
        ],
        columns=SOURCE_COLUMNS,
    )

    source_path = tmp_path / "locaweb.xlsx"
    bronze_path = tmp_path / "bronze.parquet"
    silver_path = tmp_path / "silver.parquet"
    report_path = tmp_path / "quality.json"

    source.to_excel(
        source_path,
        sheet_name="Dataset Geral",
        index=False,
        engine="openpyxl",
    )

    report = run_ingestion(
        source_path=source_path,
        bronze_path=bronze_path,
        silver_path=silver_path,
        report_path=report_path,
    )

    silver = pd.read_parquet(silver_path)
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))

    assert bronze_path.exists()
    assert silver_path.exists()
    assert report_path.exists()
    assert len(silver) == 3
    assert silver["priority_code"].tolist() == [2, 3, 4]
    assert silver.loc[1, "kpi_breached_raw"] == "N/A"
    assert report["row_count"] == 3
    assert saved_report["row_count"] == 3
