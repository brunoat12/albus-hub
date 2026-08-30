from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from albus_hub.models.risk.contracts import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def prepare_model_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normaliza extensões Pandas para tipos aceitos de forma estável pelo sklearn."""
    result = frame[CATEGORICAL_FEATURES + NUMERIC_FEATURES].copy()
    for column in CATEGORICAL_FEATURES:
        result[column] = (
            result[column].astype("string").fillna("__MISSING__").astype(str)
        )
    for column in NUMERIC_FEATURES:
        result[column] = pd.to_numeric(result[column], errors="coerce").astype(float)
    return result


def build_preprocessor() -> ColumnTransformer:
    """Monta o pré-processamento reutilizado por baseline, ANN e inferência."""
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="__MISSING__")),
            (
                "encoder",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist",
                    max_categories=100,
                    sparse_output=False,
                    dtype=np.float32,
                ),
            ),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric, NUMERIC_FEATURES),
            ("categorical", categorical, CATEGORICAL_FEATURES),
        ],
        verbose_feature_names_out=False,
    )
