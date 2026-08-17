# -*- coding: utf-8 -*-
"""
Interface de INFERENCIA da frente de Volume (Integrante 2).
O Bruno (ou o app/Streamlit) chama isto sem abrir notebook.

    from predict import prever_volume
    prever_volume()                      # D+1 e D+7 futuros, ALL/P2/P3 (contrato)
    prever_volume(scope="P2", horizon="D+7")
    prever_volume(incluir_backtest=True) # tambem as predicoes de backtest (com actual)

As predicoes sao produzidas por pipeline_volume.py (re-rodar para atualizar/retreinar).
Saida no contrato: reference_date, horizon, scope, predicted_incidents,
actual_incidents, lower_bound, upper_bound, model, model_version, generated_at.
"""
import os, datetime as dt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PRED = os.path.join(HERE, "outputs", "predictions_volume.csv")
COLS = ["reference_date","horizon","scope","predicted_incidents","actual_incidents",
        "lower_bound","upper_bound","model","model_version","generated_at"]

def prever_volume(scope=None, horizon=None, incluir_backtest=False):
    if not os.path.exists(PRED):
        raise FileNotFoundError("Rode pipeline_volume.py primeiro para gerar as predicoes.")
    df = pd.read_csv(PRED, parse_dates=["reference_date"])
    df["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    if not incluir_backtest:
        df = df[df["actual_incidents"].isna()].copy()   # so a previsao futura
    if scope:   df = df[df["scope"] == scope]
    if horizon: df = df[df["horizon"] == horizon]
    return df[COLS].sort_values(["scope","horizon","reference_date"]).reset_index(drop=True)

if __name__ == "__main__":
    print("== PREVISAO FUTURA (contrato) ==")
    print(prever_volume().to_string(index=False))
