from __future__ import annotations

import streamlit as st

from albus_hub.config import get_settings

settings = get_settings()
settings.create_local_directories()

st.set_page_config(
    page_title="Albus-Hub",
    page_icon="🔎",
    layout="wide",
)

st.title("Albus-Hub")
st.caption("AIOps para previsão de incidentes e tendências operacionais")

col1, col2, col3 = st.columns(3)

col1.metric(
    label="Ambiente",
    value=settings.app_env,
)

col2.metric(
    label="Armazenamento",
    value=settings.cloud_provider,
)

col3.metric(
    label="Status",
    value="Configurando",
)

st.success("O ambiente Python e o dashboard inicial estão funcionando.")

st.subheader("Objetivos do projeto")

st.markdown(
    """
    - Prever o volume de incidentes em D+1 e D+7.
    - Estimar risco de quebra de OLA/SLA.
    - Calcular um score de priorização.
    - Gerar alertas operacionais.
    - Exibir tendências, previsões e riscos.
    """
)

st.subheader("Próximas integrações")

st.info(
    "Os dados de ingestão, features, modelos e alertas serão "
    "integrados conforme as entregas dos demais integrantes."
)
