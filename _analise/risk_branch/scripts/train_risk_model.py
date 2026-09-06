from __future__ import annotations

import json

from albus_hub.config import get_settings
from albus_hub.models.risk.train import RiskTrainingConfig, train_risk_model


def main() -> None:
    settings = get_settings()
    config = RiskTrainingConfig(
        silver_path=settings.absolute_path(settings.locaweb_silver_file),
        risk_features_path=settings.absolute_path(settings.locaweb_risk_features_file),
        risk_scores_path=settings.absolute_path(settings.locaweb_risk_scores_file),
        model_dir=settings.absolute_path(settings.model_risk_path),
        metrics_path=settings.absolute_path(settings.locaweb_risk_metrics_file),
        figures_dir=settings.absolute_path(settings.locaweb_risk_eda_output_dir),
    )
    metrics = train_risk_model(config)
    summary = {
        "selected_ann": metrics["selected_ann"],
        "selected_threshold": metrics["selected_threshold"],
        "test_metrics": metrics["ann"]["test"],
        "risk_scores_rows": metrics["risk_scores_rows"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
