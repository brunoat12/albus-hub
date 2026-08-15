from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from albus_hub.config import get_settings
from albus_hub.integration import (
    RiskScoreContractError,
    VolumePredictionContractError,
    load_risk_scores,
    load_volume_predictions,
)
from albus_hub.observability import configure_observability
from albus_hub.storage.mysql import (
    MySQLRepository,
    create_mysql_engine,
)

settings = get_settings()
settings.create_local_directories()

configure_observability()

st.set_page_config(
    page_title="Albus-Hub",
    page_icon="🔵",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_parquet(path: str) -> pd.DataFrame:
    """Carrega um arquivo Parquet utilizado pelo dashboard."""
    return pd.read_parquet(path)

@st.cache_resource
def get_mysql_repository() -> MySQLRepository:
    """Cria o repositório utilizado pela aplicação para acessar o Azure MySQL."""
    engine = create_mysql_engine(settings)
    return MySQLRepository(engine)


def format_integer(value: int | float) -> str:
    """Formata inteiros no padrão visual pt-BR."""
    return f"{int(value):,}".replace(",", ".")


def format_percentage(value: float) -> str:
    """Formata percentual no padrão visual pt-BR."""
    return f"{value:.2f}%".replace(".", ",")


def filter_period(
    frame: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Filtra um DataFrame pelo período de referência."""
    return frame.loc[
        frame["reference_date"].between(
            start_date,
            end_date,
        )
    ].copy()


def scope_sum(
    frame: pd.DataFrame,
    scope: str,
    column: str,
) -> int:
    """Soma uma métrica para um escopo de prioridade."""
    return int(
        frame.loc[
            frame["priority_scope"].eq(scope),
            column,
        ].sum()
    )


daily_volume_path = settings.absolute_path(settings.locaweb_gold_daily_volume_file)

breakdown_path = settings.absolute_path(settings.locaweb_gold_daily_breakdown_file)


st.title("Albus-Hub")

st.caption("AIOps para previsão de incidentes, risco operacional e priorização preventiva.")


if not daily_volume_path.exists():
    st.error(
        "A camada Gold de volume diário não foi encontrada. Execute primeiro o pipeline de dados."
    )
    st.stop()

if not breakdown_path.exists():
    st.error(
        "A camada Gold de breakdown operacional não foi encontrada. "
        "Execute primeiro o pipeline de dados."
    )
    st.stop()


daily_volume = load_parquet(str(daily_volume_path))

breakdown = load_parquet(str(breakdown_path))

daily_volume["reference_date"] = pd.to_datetime(daily_volume["reference_date"])

breakdown["reference_date"] = pd.to_datetime(breakdown["reference_date"])


min_date = daily_volume["reference_date"].min()
max_date = daily_volume["reference_date"].max()


st.sidebar.header("Filtros")

selected_period = st.sidebar.date_input(
    "Período",
    value=(
        min_date.date(),
        max_date.date(),
    ),
    min_value=min_date.date(),
    max_value=max_date.date(),
)

priority_scope = st.sidebar.selectbox(
    "Escopo de prioridade",
    options=["ALL", "P2", "P3"],
    format_func=lambda value: {
        "ALL": "Todas",
        "P2": "P2 — Alta",
        "P3": "P3 — Média",
    }[value],
)

st.sidebar.divider()

st.sidebar.caption(f"Ambiente: {settings.app_env}")

st.sidebar.caption(f"Cloud provider: {settings.cloud_provider}")


if isinstance(selected_period, tuple) and len(selected_period) == 2:
    start_date = pd.Timestamp(selected_period[0])
    end_date = pd.Timestamp(selected_period[1])
else:
    start_date = min_date
    end_date = max_date


daily_period = filter_period(
    daily_volume,
    start_date,
    end_date,
)

breakdown_period = filter_period(
    breakdown,
    start_date,
    end_date,
)


tab_overview, tab_operations, tab_forecast, tab_risk, tab_cloud = st.tabs(
    [
        "Visão Geral",
        "Análise Operacional",
        "Previsões",
        "Risco Operacional",
        "Cloud / MySQL",
    ]
)


with tab_overview:
    st.subheader("Visão Geral")

    total_incidents = scope_sum(
        daily_period,
        "ALL",
        "incident_count",
    )

    p2_incidents = scope_sum(
        daily_period,
        "P2",
        "incident_count",
    )

    p3_incidents = scope_sum(
        daily_period,
        "P3",
        "incident_count",
    )

    entered_kpi = scope_sum(
        daily_period,
        "ALL",
        "entered_kpi_count",
    )

    kpi_breaches = scope_sum(
        daily_period,
        "ALL",
        "kpi_breach_count",
    )

    breach_rate = 100 * kpi_breaches / entered_kpi if entered_kpi else 0.0

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Incidentes",
        format_integer(total_incidents),
    )

    col2.metric(
        "P2",
        format_integer(p2_incidents),
    )

    col3.metric(
        "P3",
        format_integer(p3_incidents),
    )

    col4.metric(
        "KPI violado",
        format_integer(kpi_breaches),
    )

    col5.metric(
        "Taxa de violação",
        format_percentage(breach_rate),
    )

    st.divider()

    st.subheader(f"Evolução diária — {priority_scope}")

    trend = daily_period.loc[
        daily_period["priority_scope"].eq(priority_scope),
        [
            "reference_date",
            "incident_count",
        ],
    ].sort_values("reference_date")

    st.line_chart(
        trend,
        x="reference_date",
        y="incident_count",
        x_label="Data",
        y_label="Incidentes",
    )

    with st.expander("Ver dados consolidados"):
        st.dataframe(
            daily_period.sort_values(
                [
                    "reference_date",
                    "priority_scope",
                ]
            ),
            width="stretch",
            hide_index=True,
        )


with tab_operations:
    st.subheader("Análise Operacional")

    dimension_labels = {
        "product": "Produto",
        "category": "Categoria",
        "assigned_group": "Grupo designado",
        "configuration_item": "Item de configuração",
    }

    selected_dimension = st.selectbox(
        "Dimensão",
        options=list(dimension_labels),
        format_func=lambda value: dimension_labels[value],
    )

    top_n = st.slider(
        "Quantidade de itens",
        min_value=5,
        max_value=30,
        value=15,
        step=5,
    )

    operational = breakdown_period.loc[
        breakdown_period["dimension_name"].eq(selected_dimension)
        & breakdown_period["priority_scope"].eq(priority_scope)
    ].copy()

    operational["dimension_value"] = (
        operational["dimension_value"]
        .astype("string")
        .replace(
            "__MISSING__",
            "Sem informação",
        )
    )

    ranking = (
        operational.groupby(
            "dimension_value",
            as_index=False,
            dropna=False,
        )
        .agg(
            incident_count=(
                "incident_count",
                "sum",
            ),
            entered_kpi_count=(
                "entered_kpi_count",
                "sum",
            ),
            kpi_breach_count=(
                "kpi_breach_count",
                "sum",
            ),
        )
        .sort_values(
            "incident_count",
            ascending=False,
        )
        .head(top_n)
    )

    if ranking.empty:
        st.info("Não há dados para os filtros selecionados.")
    else:
        st.bar_chart(
            ranking,
            x="dimension_value",
            y="incident_count",
            x_label=dimension_labels[selected_dimension],
            y_label="Incidentes",
        )

        st.dataframe(
            ranking.rename(
                columns={
                    "dimension_value": dimension_labels[selected_dimension],
                    "incident_count": "Incidentes",
                    "entered_kpi_count": "Entraram no KPI",
                    "kpi_breach_count": "KPI violado",
                }
            ),
            width="stretch",
            hide_index=True,
        )


with tab_forecast:
    st.subheader("Previsão de Volume")

    predictions_path = settings.absolute_path(settings.locaweb_volume_predictions_file)

    try:
        predictions = load_volume_predictions(predictions_path)
    except VolumePredictionContractError as exc:
        st.error(f"O artefato de previsão não respeita o contrato: {exc}")
    else:
        if predictions is None:
            st.info(
                "A interface de previsão está preparada, "
                "mas o artefato D+1/D+7 ainda não foi integrado."
            )

            col1, col2 = st.columns(2)

            col1.metric(
                "Previsão D+1",
                "Aguardando modelo",
            )

            col2.metric(
                "Previsão D+7",
                "Aguardando modelo",
            )

            st.caption("Arquivo esperado: data/gold/volume_predictions.parquet")

        else:
            scoped_predictions = predictions.loc[
                predictions["priority_scope"].eq(priority_scope)
            ].copy()

            if scoped_predictions.empty:
                st.info("Não há previsões disponíveis para o escopo selecionado.")
            else:
                latest_by_horizon = scoped_predictions.sort_values(
                    [
                        "reference_date",
                        "generated_at",
                    ]
                ).drop_duplicates(
                    subset=["horizon"],
                    keep="last",
                )

                def prediction_value(
                    horizon: str,
                ) -> str:
                    rows = latest_by_horizon.loc[latest_by_horizon["horizon"].eq(horizon)]

                    if rows.empty:
                        return "Indisponível"

                    value = rows.iloc[-1]["predicted_incident_count"]

                    return format_integer(round(value))

                col1, col2 = st.columns(2)

                col1.metric(
                    "Previsão D+1",
                    prediction_value("D+1"),
                )

                col2.metric(
                    "Previsão D+7",
                    prediction_value("D+7"),
                )

                st.dataframe(
                    latest_by_horizon[
                        [
                            "reference_date",
                            "horizon",
                            "priority_scope",
                            "predicted_incident_count",
                            "model_version",
                            "generated_at",
                        ]
                    ].sort_values("horizon"),
                    width="stretch",
                    hide_index=True,
                )


with tab_risk:
    st.subheader("Risco Operacional")

    risk_score_path = settings.absolute_path(settings.locaweb_risk_scores_file)

    try:
        risk_scores = load_risk_scores(risk_score_path)
    except RiskScoreContractError as exc:
        st.error(f"O artefato de risco não respeita o contrato: {exc}")
    else:
        if risk_scores is None:
            st.warning("O modelo de risco e o score operacional ainda não foram integrados.")

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Risk score",
                "Aguardando modelo",
            )

            col2.metric(
                "Nível de risco",
                "Aguardando modelo",
            )

            col3.metric(
                "Incidentes críticos",
                "Aguardando modelo",
            )

            st.caption("Arquivo esperado: data/gold/risk_scores.parquet")

        else:
            latest_scores = risk_scores.sort_values("scored_at").drop_duplicates(
                subset=["incident_id"],
                keep="last",
            )

            average_score = latest_scores["risk_score"].mean()

            critical_count = int(latest_scores["risk_level"].eq("crítico").sum())

            high_or_critical = int(
                latest_scores["risk_level"]
                .isin(
                    [
                        "alto",
                        "crítico",
                    ]
                )
                .sum()
            )

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Risk score médio",
                f"{average_score:.1f}",
            )

            col2.metric(
                "Alto ou crítico",
                format_integer(high_or_critical),
            )

            col3.metric(
                "Críticos",
                format_integer(critical_count),
            )

            st.subheader("Incidentes prioritários")

            ranking = (
                latest_scores.sort_values(
                    "risk_score",
                    ascending=False,
                )
                .head(20)
                .copy()
            )

            ranking["risk_level"] = ranking["risk_level"].str.title()

            st.dataframe(
                ranking[
                    [
                        "incident_id",
                        "risk_score",
                        "risk_level",
                        "breach_probability",
                        "top_risk_factors",
                        "recommended_action",
                        "model_version",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

with tab_cloud:
    st.subheader("Integração Cloud")

    st.caption(
        "Integração da aplicação Albus-Hub com o "
        "Azure Database for MySQL."
    )

    try:
        repository = get_mysql_repository()

        connected = repository.health_check()

        col1, col2 = st.columns(2)

        col1.metric(
            "Azure MySQL",
            "Conectado" if connected else "Indisponível",
        )

        summary = repository.fetch_incident_summary()

        col2.metric(
            "Incidentes no Data Warehouse",
            format_integer(summary.total_incidents),
        )

        st.success(
            "Aplicação conectada ao Data Warehouse "
            "no Azure Database for MySQL."
        )

        st.divider()

        st.subheader("Processamento e persistência")

        st.write(
            "A aplicação consulta a FATO_INCIDENTE, "
            "processa o total de registros e pode persistir "
            "uma execução na tabela operacional albus_app_runs."
        )

        if st.button(
            "Executar processamento e registrar no MySQL",
            type="primary",
        ):
            run_id = repository.insert_app_run(
                app_env=settings.app_env,
                action="streamlit_incident_summary",
                processed_records=summary.total_incidents,
            )

            st.success(
                f"Execução registrada com sucesso: {run_id}"
            )

        st.divider()

        st.subheader("Últimas execuções")

        recent_runs = repository.fetch_recent_app_runs(limit=5)

        if recent_runs:
            st.dataframe(
                pd.DataFrame(recent_runs),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma execução registrada.")

    except SQLAlchemyError as exc:
        st.warning(
            "Não foi possível acessar o Azure MySQL neste ambiente."
        )

        st.caption(str(exc))


st.divider()

st.caption("Albus-Hub • FIAP / Locaweb Challenge 2026")
