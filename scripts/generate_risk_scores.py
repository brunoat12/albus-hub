from __future__ import annotations

import pandas as pd

from albus_hub.config import get_settings
from albus_hub.models.risk.inference import RiskPredictor


def main() -> None:
    settings = get_settings()
    features = pd.read_parquet(
        settings.absolute_path(settings.locaweb_risk_features_file)
    )
    scoring_population = features.loc[features["dataset_split"].eq("test")].copy()
    predictor = RiskPredictor(settings.absolute_path(settings.model_risk_path))
    scores = predictor.predict_features(scoring_population)
    output_path = settings.absolute_path(settings.locaweb_risk_scores_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(output_path, index=False)
    print(f"Scores gerados: {len(scores)}")
    print(f"Arquivo: {output_path}")


if __name__ == "__main__":
    main()
