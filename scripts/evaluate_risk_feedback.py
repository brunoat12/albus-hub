from __future__ import annotations

import argparse
import json
from pathlib import Path

from albus_hub.models.risk.train import RiskTrainingConfig, train_risk_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Executa avaliação local do feedback de DL sem publicar artefatos "
            "no ADLS, MySQL ou ambiente Azure."
        )
    )
    parser.add_argument(
        "--silver",
        type=Path,
        default=Path("data/silver/locaweb_incidents.parquet"),
        help="Caminho da Silver local.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/dl_feedback_evaluation"),
        help="Diretório local para resultados da avaliação.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.silver.exists():
        raise FileNotFoundError(
            f"Silver não encontrada em {args.silver}. Informe o caminho com --silver."
        )

    output = args.output_dir
    config = RiskTrainingConfig(
        silver_path=args.silver,
        risk_features_path=output / "risk_features.parquet",
        risk_scores_path=output / "risk_scores.parquet",
        model_dir=output / "model",
        metrics_path=output / "metrics.json",
        figures_dir=output / "figures",
        model_version="risk-ann-feedback-eval",
    )

    metrics = train_risk_model(config)
    summary = {
        "label_audit": metrics["label_audit"],
        "baseline": {
            "selected_config": metrics["baseline"]["selected_config"],
            "raw_test_at_0_5": metrics["baseline"]["raw_test_at_0_5"],
            "test": metrics["baseline"]["test"],
            "probability_diagnostics": metrics["baseline"]["probability_diagnostics"],
        },
        "ann_test": metrics["ann"]["test"],
        "prioritization_ann": metrics["prioritization"]["ann"],
    }

    summary_path = output / "feedback_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("DL_FEEDBACK_EVAL=SUCCESS")
    print("Resumo:", summary_path)
    print("Métricas completas:", config.metrics_path)
    print("Figuras:", config.figures_dir)


if __name__ == "__main__":
    main()
