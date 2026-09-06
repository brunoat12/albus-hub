"""
Publica as previsões de volume no formato do contrato de integração.

A frente de modelagem entrega `ml_volume/outputs/predictions_volume.parquet`
com o vocabulário do pipeline dela. O dashboard consome
`data/gold/volume_predictions.parquet` no vocabulário do contrato definido em
`docs/data_contracts.md`. Este script faz a tradução entre os dois.

Decisão de escopo (sprint 3): o projeto acompanha apenas ALL, P2 e P3 — os
recortes que a camada Gold produz e que refletem a regra da Locaweb sobre o
que entra no KPI. As previsões de P1, P4 e P5 entregues pelo modelo são
descartadas aqui, de propósito, e o descarte é registrado no relatório.

Uso:
    uv run python scripts/publish_volume_predictions.py
    uv run python scripts/publish_volume_predictions.py --origem caminho/para/predictions_volume.parquet
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from albus_hub.config import get_settings
from albus_hub.integration import VolumePredictionContractError, validate_volume_predictions

ORIGEM_PADRAO = Path("ml_volume/outputs/predictions_volume.parquet")

ESCOPOS_DO_CONTRATO = ["ALL", "P2", "P3"]

RENOMEAR = {
    "scope": "priority_scope",
    "predicted_incidents": "predicted_incident_count",
}

COLUNAS_DO_CONTRATO = [
    "reference_date",
    "generated_at",
    "horizon",
    "priority_scope",
    "predicted_incident_count",
    "model_version",
]

# Colunas extras que o modelo entrega e que o dashboard aproveita quando existem.
COLUNAS_EXTRAS = ["actual_incidents", "lower_bound", "upper_bound", "model"]


def traduzir(bruto: pd.DataFrame, gerado_em: datetime) -> tuple[pd.DataFrame, dict]:
    """Converte o artefato do modelo para o vocabulário do contrato."""
    faltando = sorted(set(RENOMEAR) | {"reference_date", "horizon", "model_version"} - set(bruto.columns))
    ausentes = [c for c in faltando if c not in bruto.columns]

    if ausentes:
        raise ValueError(
            "O artefato de origem não tem as colunas esperadas do pipeline de "
            f"volume: {ausentes}. Colunas encontradas: {sorted(bruto.columns)}"
        )

    frame = bruto.rename(columns=RENOMEAR).copy()

    frame["reference_date"] = pd.to_datetime(frame["reference_date"]).dt.normalize()
    frame["generated_at"] = gerado_em
    frame["horizon"] = frame["horizon"].astype("string").str.strip().str.upper()
    frame["priority_scope"] = frame["priority_scope"].astype("string").str.strip().str.upper()
    frame["model_version"] = frame["model_version"].astype("string").str.strip()
    frame["predicted_incident_count"] = (
        pd.to_numeric(frame["predicted_incident_count"], errors="coerce").round().astype("int64")
    )

    fora = sorted(set(frame["priority_scope"].dropna()) - set(ESCOPOS_DO_CONTRATO))
    descartadas = int(frame["priority_scope"].isin(fora).sum()) if fora else 0

    frame = frame.loc[frame["priority_scope"].isin(ESCOPOS_DO_CONTRATO)].copy()

    extras = [c for c in COLUNAS_EXTRAS if c in frame.columns]
    frame = frame[COLUNAS_DO_CONTRATO + extras]

    frame = frame.sort_values(["priority_scope", "horizon", "reference_date"]).reset_index(drop=True)

    previstas = int(frame["actual_incidents"].isna().sum()) if "actual_incidents" in frame else 0

    relatorio = {
        "gerado_em_utc": gerado_em.isoformat(),
        "linhas_na_origem": int(len(bruto)),
        "linhas_publicadas": int(len(frame)),
        "escopos_publicados": sorted(frame["priority_scope"].unique()),
        "escopos_descartados": fora,
        "linhas_descartadas": descartadas,
        "linhas_de_backtest": int(len(frame)) - previstas,
        "linhas_de_previsao_futura": previstas,
        "versao_do_modelo": sorted(frame["model_version"].unique()),
        "data_minima": frame["reference_date"].min().date().isoformat(),
        "data_maxima": frame["reference_date"].max().date().isoformat(),
    }

    return frame, relatorio


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", type=Path, default=None)
    args = parser.parse_args()

    settings = get_settings()
    origem = args.origem or settings.absolute_path(ORIGEM_PADRAO)

    if not origem.exists():
        raise SystemExit(
            f"Artefato de origem não encontrado em {origem}.\n"
            "Faça o merge da branch feature/ml-volume-forecast ou passe --origem."
        )

    bruto = pd.read_parquet(origem)
    frame, relatorio = traduzir(bruto, datetime.now(UTC))

    # O contrato é a última palavra: se não passar aqui, não publica.
    validado = validate_volume_predictions(frame[COLUNAS_DO_CONTRATO])
    for coluna in [c for c in COLUNAS_EXTRAS if c in frame.columns]:
        validado[coluna] = frame[coluna].to_numpy()

    destino = settings.absolute_path(settings.locaweb_volume_predictions_file)
    destino.parent.mkdir(parents=True, exist_ok=True)
    validado.to_parquet(destino, index=False)

    relatorio_path = settings.absolute_path(Path("artifacts/quality/volume_predictions_publish.json"))
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    with relatorio_path.open("w", encoding="utf-8") as fh:
        json.dump(relatorio, fh, ensure_ascii=False, indent=2)

    print(f"Publicado em {destino}")
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except VolumePredictionContractError as exc:
        raise SystemExit(f"O artefato traduzido não respeita o contrato: {exc}") from exc
