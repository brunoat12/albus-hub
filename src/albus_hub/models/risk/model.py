from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class ANNConfig:
    """Configuração compacta de uma ANN binária."""

    name: str
    hidden_units: tuple[int, ...]
    dropout: float
    learning_rate: float
    batch_size: int = 256
    epochs: int = 60
    patience: int = 7

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


ANN_CONFIGS = [
    ANNConfig(
        name="compact-64-32",
        hidden_units=(64, 32),
        dropout=0.25,
        learning_rate=0.001,
    ),
    ANNConfig(
        name="reference-128-64-32",
        hidden_units=(128, 64, 32),
        dropout=0.30,
        learning_rate=0.001,
    ),
]


def build_ann(
    input_dimension: int,
    config: ANNConfig,
    *,
    compile_model: bool = True,
):
    """Constrói a rede Dense/ReLU/Dropout com saída sigmoide."""
    import tensorflow as tf

    layers = [tf.keras.layers.Input(shape=(input_dimension,))]
    for units in config.hidden_units:
        layers.extend(
            [
                tf.keras.layers.Dense(units, activation="relu"),
                tf.keras.layers.Dropout(config.dropout),
            ]
        )
    layers.append(tf.keras.layers.Dense(1, activation="sigmoid"))
    model = tf.keras.Sequential(layers, name=f"risk_{config.name}")
    if compile_model:
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=config.learning_rate),
            loss="binary_crossentropy",
            metrics=[tf.keras.metrics.AUC(curve="PR", name="pr_auc")],
        )
    return model


def train_ann(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_validation: np.ndarray,
    y_validation: np.ndarray,
    config: ANNConfig,
    seed: int,
):
    """Treina uma configuração com pesos de classe e early stopping."""
    import tensorflow as tf

    tf.keras.utils.set_random_seed(seed)
    model = build_ann(x_train.shape[1], config)
    positives = max(int(np.asarray(y_train).sum()), 1)
    negatives = max(len(y_train) - positives, 1)
    class_weight = {0: 1.0, 1: negatives / positives}
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_pr_auc",
            mode="max",
            patience=config.patience,
            restore_best_weights=True,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_pr_auc",
            mode="max",
            factor=0.5,
            patience=max(2, config.patience // 2),
            min_lr=1e-5,
        ),
    ]
    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_validation, y_validation),
        epochs=config.epochs,
        batch_size=config.batch_size,
        class_weight=class_weight,
        callbacks=callbacks,
        verbose=0,
    )
    return model, history.history, class_weight


def predict_ann(model, values: np.ndarray) -> np.ndarray:
    """Retorna a probabilidade sigmoide em um vetor unidimensional."""
    return model.predict(values, batch_size=1024, verbose=0).reshape(-1)
