# -*- coding: utf-8 -*-
"""
Pagina Streamlit da frente de Volume (Integrante 2) — pronta para o Bruno plugar.
Consome a API de inferencia (predict.prever_volume) e os outputs do pipeline.

Rodar:
    pip install streamlit
    streamlit run app_streamlit.py
"""
import os, json
import pandas as pd
import streamlit as st
from predict import prever_volume

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "outputs")

st.set_page_config(page_title="Albus Hub — Volume D+1/D+7", layout="wide")
st.title("Albus Hub — Previsão de Volume de Incidentes")
st.caption("Frente ML (Integrante 2) · D+1 e D+7 · recortes ALL / P2 / P3")

@st.cache_data
def carregar():
    pred = pd.read_csv(os.path.join(OUT, "predictions_volume.csv"), parse_dates=["reference_date"])
    with open(os.path.join(OUT, "metrics.json"), encoding="utf-8") as f:
        met = json.load(f)
    return pred, met

try:
    pred, met = carregar()
except FileNotFoundError:
    st.error("Rode `python pipeline_volume.py` primeiro para gerar as predições.")
    st.stop()

scope = st.sidebar.selectbox("Recorte", ["ALL", "P2", "P3"])
st.sidebar.markdown("Modelo: **" + str(pred["model_version"].iloc[0]) + "**")

# ---- cards de previsao futura ----
fut = prever_volume(scope=scope)
st.subheader(f"Previsão — {scope}")
cols = st.columns(2)
for col, hz in zip(cols, ["D+1", "D+7"]):
    linha = fut[fut.horizon == hz]
    if len(linha):
        row = linha.iloc[0]
        col.metric(f"{hz} · {row['reference_date'].date()}",
                   f"{int(row['predicted_incidents'])} incidentes",
                   help=f"intervalo 10–90%: {int(row['lower_bound'])} – {int(row['upper_bound'])}")
        col.caption(f"faixa provável: {int(row['lower_bound'])} – {int(row['upper_bound'])}")

# ---- metricas do backtest ----
st.subheader("Qualidade (backtest Set–Dez 2025)")
linhas = []
for hz in ["D+1", "D+7"]:
    mm = met[scope][hz]; b = mm["_best"]
    linhas.append({"horizonte": hz, "modelo": b, "MAE": round(mm[b]["MAE"], 1),
                   "sMAPE %": round(mm[b]["sMAPE"], 1),
                   "ganho vs naïve %": round(mm[b]["skill_vs_naive"]*100),
                   "cobertura intervalo %": round(mm["_coverage"]["empirico_oos"]*100)})
st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)

# ---- grafico previsto vs real ----
st.subheader("Previsto vs Real — D+1")
bt = pred[(pred.scope == scope) & (pred.horizon == "D+1") & (pred.actual_incidents.notna())].copy()
if len(bt):
    g = bt.set_index("reference_date")[["actual_incidents", "predicted_incidents"]]
    g.columns = ["real", "previsto"]
    st.line_chart(g)

# ---- tabela completa do contrato ----
with st.expander("Tabela completa (contrato de saída)"):
    st.dataframe(prever_volume(scope=scope, incluir_backtest=True), hide_index=True, use_container_width=True)

st.caption("Fonte: pipeline_volume.py · previsões em outputs/predictions_volume.csv (contrato congelado).")
