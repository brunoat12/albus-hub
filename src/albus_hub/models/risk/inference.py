from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from albus_hub.integration.risk_scores import validate_risk_scores
from albus_hub.models.risk.contracts import MODEL_FEATURES
from albus_hub.models.risk.explainability import explain_by_perturbation
from albus_hub.models.risk.features import build_risk_features
from albus_hub.models.risk.model import ANNConfig, build_ann, predict_ann
from albus_hub.models.risk.preprocessing import prepare_model_frame
from albus_hub.models.risk.probability import apply_probability_calibrator
from albus_hub.models.risk.scoring import build_operational_scores


class RiskPredictor:
    """Carrega os artefatos salvos e executa inferência sem novo treinamento."""

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        self.preprocessor = joblib.load(self.model_dir / "preprocessor.joblib")
        self.calibrator = joblib.load(self.model_dir / "calibrator.joblib")
        self.metadata = json.loads((self.model_dir / "metadata.json").read_text(encoding="utf-8"))
        ann_config = dict(self.metadata["selected_ann_config"])
        ann_config["hidden_units"] = tuple(ann_config["hidden_units"])
        self.model = build_ann(
            int(self.metadata["transformed_dimension"]),
            ANNConfig(**ann_config),
            compile_model=False,
        )
        self.model.load_weights(self.model_dir / "ann.weights.h5")

    def predict_probability(self, feature_frame: pd.DataFrame) -> np.ndarray:
        prepared = prepare_model_frame(feature_frame[MODEL_FEATURES])
        transformed = self.preprocessor.transform(prepared).astype(np.float32)
        raw = predict_ann(self.model, transformed)
        return apply_probability_calibrator(self.calibrator, raw)

    def predict_features(
        self,
        feature_frame: pd.DataFrame,
        *,
        scored_at: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Gera o contrato final a partir de features já construídas."""
        probabilities = self.predict_probability(feature_frame)
        operational = build_operational_scores(
            feature_frame,
            probabilities,
            self.metadata["pressure_reference_p95"],
        )
        factors = explain_by_perturbation(
            feature_frame.reset_index(drop=True),
            probabilities,
            self.metadata["explanation_reference_values"],
            self.predict_probability,
        )
        timestamp = scored_at or pd.Timestamp.now(tz="UTC")
        output = pd.DataFrame(
            {
                "incident_id": feature_frame["incident_id"].astype("string").to_numpy(),
                "scored_at": timestamp,
                "model_version": self.metadata["model_version"],
                **{column: operational[column].to_numpy() for column in operational.columns},
                "top_risk_factors": factors,
            }
        )
        columns = [
            "incident_id",
            "scored_at",
            "model_version",
            "breach_probability",
            "priority_impact",
            "operational_pressure",
            "risk_score",
            "risk_level",
            "top_risk_factors",
            "recommended_action",
        ]
        return validate_risk_scores(output[columns])


def predict_risk(
    incident: dict[str, object] | pd.Series,
    history: pd.DataFrame,
    model_dir: Path,
) -> dict[str, object]:
    """Interface simples para um incidente novo e seu histórico disponível."""
    current = pd.DataFrame([dict(incident)])
    for column in history.columns:
        if column not in current:
            current[column] = pd.NA
    combined = pd.concat([history, current[history.columns]], ignore_index=True)
    features = build_risk_features(combined, require_targets=False)
    incident_id = str(current.iloc[0]["incident_id"])
    current_features = features.loc[features["incident_id"].astype(str).eq(incident_id)]
    if len(current_features) != 1:
        raise ValueError("O incidente de inferência deve possuir incident_id único.")
    result = RiskPredictor(model_dir).predict_features(current_features)
    return result.iloc[0].to_dict()
