from pathlib import Path

import pandas as pd

from albus_hub.config import get_settings
from albus_hub.ml.volume_forecast_v32 import (
    load_volume_bundle,
    predict_volume,
)

ROOT = Path(
    __file__
).resolve().parents[2]

BUNDLE = (
    ROOT
    / "artifacts"
    / "runtime"
    / "ml_training_v32"
    / "model_bundle.joblib"
)


def main():
    settings = get_settings()

    silver = pd.read_parquet(
        settings.absolute_path(
            settings.locaweb_silver_file
        )
    )

    bundle = load_volume_bundle(
        BUNDLE
    )

    predictions = predict_volume(
        silver,
        bundle,
    )

    print(
        "=== INFERENCIA RAPIDA ML V3.2 ==="
    )

    print(
        predictions[
            [
                "priority_scope",
                "horizon",
                "reference_date",
                "predicted_incident_count",
                "lower_bound",
                "upper_bound",
                "model_name",
                "model_version",
            ]
        ].to_string(index=False)
    )

    expected = {
        ("ALL", "D+1"): (
            752, 635, 900, "ultimo"
        ),
        ("ALL", "D+7"): (
            889, 790, 1092, "gbr"
        ),
        ("P1", "D+1"): (
            0, 0, 0, "naive7"
        ),
        ("P1", "D+7"): (
            0, 0, 0, "naive7"
        ),
        ("P2", "D+1"): (
            29, 16, 43, "ridge"
        ),
        ("P2", "D+7"): (
            41, 25, 60, "gbr"
        ),
        ("P3", "D+1"): (
            395, 302, 605, "gbr"
        ),
        ("P3", "D+7"): (
            297, 207, 528, "gbr"
        ),
        ("P4", "D+1"): (
            367, 300, 434, "ultimo"
        ),
        ("P4", "D+7"): (
            447, 367, 559, "gbr"
        ),
        ("P5", "D+1"): (
            0, 0, 1, "gbr"
        ),
        ("P5", "D+7"): (
            0, 0, 1, "gbr"
        ),
    }

    for row in predictions.to_dict(
        orient="records"
    ):
        key = (
            row["priority_scope"],
            row["horizon"],
        )

        got = (
            int(
                round(
                    row[
                        "predicted_incident_count"
                    ]
                )
            ),
            int(
                round(
                    row["lower_bound"]
                )
            ),
            int(
                round(
                    row["upper_bound"]
                )
            ),
            row["model_name"],
        )

        if got != expected[key]:
            raise RuntimeError(
                f"Paridade falhou {key}: "
                f"{got} != {expected[key]}"
            )

    if len(predictions) != 12:
        raise RuntimeError(
            "Esperadas 12 previsoes."
        )

    print()
    print(
        "FAST_INFERENCE_PARITY=SUCCESS"
    )


if __name__ == "__main__":
    main()
