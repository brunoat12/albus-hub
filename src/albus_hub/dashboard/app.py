from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from albus_hub.config import get_settings
from albus_hub.integration import (
    RiskScoreContractError,
    validate_risk_scores,
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

@st.cache_data(
    ttl=60,
    show_spinner=False,
)
def load_current_predictions() -> pd.DataFrame:
    """Carrega as previsões operacionais vigentes do MySQL."""
    repository = get_mysql_repository()

    rows = repository.fetch_ml_volume_predictions()

    frame = pd.DataFrame(rows)

    if frame.empty:
        return frame

    frame["reference_date"] = pd.to_datetime(
        frame["reference_date"]
    )

    frame["generated_at"] = pd.to_datetime(
        frame["generated_at"]
    )

    return frame

@st.cache_data(
    ttl=60,
    show_spinner=False,
)
def load_current_risk_scores() -> pd.DataFrame:
    """Carrega os scores de risco operacionais vigentes do MySQL."""

    rows = (
        get_mysql_repository()
        .fetch_dl_risk_scores()
    )

    frame = pd.DataFrame(rows)

    if frame.empty:
        return frame

    return validate_risk_scores(frame)


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_daily_volume_from_mysql() -> pd.DataFrame:
    """Carrega o Gold diário da camada serving MySQL."""

    rows = (
        get_mysql_repository()
        .fetch_daily_incident_volume()
    )

    frame = pd.DataFrame(rows)

    if not frame.empty:
        frame["reference_date"] = pd.to_datetime(
            frame["reference_date"]
        )

    return frame


@st.cache_data(
    ttl=60,
    show_spinner=False,
)
def load_breakdown_ranking_from_mysql(
    start_date: str,
    end_date: str,
    priority_scope: str,
    dimension_name: str,
    top_n: int,
    ranking_metric: str = "incident_count",
    min_entered_kpi: int = 0,
    exclude_missing: bool = False,
) -> pd.DataFrame:
    """Consulta o ranking operacional diretamente no MySQL."""

    rows = (
        get_mysql_repository()
        .fetch_incident_breakdown_ranking(
            start_date=pd.Timestamp(
                start_date
            ).date(),
            end_date=pd.Timestamp(
                end_date
            ).date(),
            priority_scope=priority_scope,
            dimension_name=dimension_name,
            limit=top_n,
            ranking_metric=ranking_metric,
            min_entered_kpi=min_entered_kpi,
            exclude_missing=exclude_missing,
        )
    )

    return pd.DataFrame(rows)

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

try:
    daily_volume = load_daily_volume_from_mysql()
except SQLAlchemyError as exc:
    st.error(
        "Não foi possível carregar os dados "
        "analíticos do Azure MySQL."
    )
    st.caption(
        f"Detalhes técnicos: {exc}"
    )
    st.stop()


if daily_volume.empty:
    st.error(
        "A tabela serving de volume diário está vazia."
    )
    st.stop()


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

    try:
        ranking = load_breakdown_ranking_from_mysql(
            start_date=start_date.date().isoformat(),
            end_date=end_date.date().isoformat(),
            priority_scope=priority_scope,
            dimension_name=selected_dimension,
            top_n=top_n,
        )
    except SQLAlchemyError as exc:
        st.error(
            "Não foi possível consultar "
            "o breakdown operacional."
        )
        st.caption(
            f"Detalhes técnicos: {exc}"
        )
        ranking = pd.DataFrame()

    if not ranking.empty:
        ranking["dimension_value"] = (
            ranking["dimension_value"]
            .astype("string")
            .replace(
                "__MISSING__",
                "Sem informação",
        )
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


    st.divider()

    st.subheader(
        "Agrupamentos críticos"
    )

    st.caption(
        "Análise combinada de produto × categoria × prioridade. "
        "Os rankings permitem distinguir concentração operacional, "
        "impacto absoluto e risco proporcional."
    )

    try:
        critical_by_volume = (
            load_breakdown_ranking_from_mysql(
                start_date=start_date.date().isoformat(),
                end_date=end_date.date().isoformat(),
                priority_scope="ALL",
                dimension_name="critical_group",
                top_n=10,
                ranking_metric="incident_count",
                exclude_missing=True,
            )
        )

        critical_by_breach = (
            load_breakdown_ranking_from_mysql(
                start_date=start_date.date().isoformat(),
                end_date=end_date.date().isoformat(),
                priority_scope="ALL",
                dimension_name="critical_group",
                top_n=10,
                ranking_metric="kpi_breach_count",
                min_entered_kpi=10,
                exclude_missing=True,
            )
        )

        critical_by_rate = (
            load_breakdown_ranking_from_mysql(
                start_date=start_date.date().isoformat(),
                end_date=end_date.date().isoformat(),
                priority_scope="ALL",
                dimension_name="critical_group",
                top_n=10,
                ranking_metric="breach_rate_pct",
                min_entered_kpi=20,
                exclude_missing=True,
            )
        )

    except SQLAlchemyError as exc:
        st.error(
            "Não foi possível consultar os "
            "agrupamentos críticos."
        )

        st.caption(
            f"Detalhes técnicos: {exc}"
        )

    else:
        def prepare_critical_ranking(
            frame: pd.DataFrame,
        ) -> pd.DataFrame:
            if frame.empty:
                return frame

            result = frame.copy()

            parts = (
                result["dimension_value"]
                .astype("string")
                .str.split(
                    " | ",
                    n=2,
                    expand=True,
                    regex=False,
                )
            )

            result["Produto"] = parts[0]
            result["Categoria"] = parts[1]
            result["Prioridade"] = parts[2]

            result["breach_rate_pct"] = (
                pd.to_numeric(
                    result["breach_rate_pct"],
                    errors="coerce",
                )
                .round(2)
            )

            return result[
                [
                    "Produto",
                    "Categoria",
                    "Prioridade",
                    "incident_count",
                    "entered_kpi_count",
                    "kpi_breach_count",
                    "breach_rate_pct",
                ]
            ].rename(
                columns={
                    "incident_count": "Incidentes",
                    "entered_kpi_count": "Entraram no KPI",
                    "kpi_breach_count": "KPI violado",
                    "breach_rate_pct": "Taxa de violação (%)",
                }
            )

        critical_rankings = {
            "Maior volume": prepare_critical_ranking(
                critical_by_volume
            ),
            "Mais violações": prepare_critical_ranking(
                critical_by_breach
            ),
            "Maior taxa de violação": prepare_critical_ranking(
                critical_by_rate
            ),
        }

        critical_view = st.radio(
            "Critério do ranking",
            options=list(
                critical_rankings
            ),
            horizontal=True,
            key="critical_group_ranking",
        )

        selected_critical = (
            critical_rankings[
                critical_view
            ]
        )

        if selected_critical.empty:
            st.info(
                "Não há agrupamentos críticos "
                "para o período selecionado."
            )

        else:
            leader = (
                selected_critical.iloc[0]
            )

            st.caption(
                "Grupo líder: "
                f"{leader['Produto']} | "
                f"{leader['Categoria']} | "
                f"{leader['Prioridade']}"
            )

            col1, col2, col3 = (
                st.columns(3)
            )

            col1.metric(
                "Incidentes",
                format_integer(
                    leader["Incidentes"]
                ),
            )

            col2.metric(
                "Violações",
                format_integer(
                    leader["KPI violado"]
                ),
            )

            rate = leader[
                "Taxa de violação (%)"
            ]

            col3.metric(
                "Taxa de violação",
                (
                    "N/A"
                    if pd.isna(rate)
                    else format_percentage(
                        float(rate)
                    )
                ),
            )

            st.dataframe(
                selected_critical,
                width="stretch",
                hide_index=True,
            )

            if (
                critical_view
                == "Maior taxa de violação"
            ):
                st.caption(
                    "Para evitar distorções por amostras muito pequenas, "
                    "este ranking exige pelo menos 20 incidentes "
                    "elegíveis ao KPI."
                )




with tab_forecast:
    st.subheader("Previsão de Volume")

    forecast_scope = st.selectbox(
        "Escopo da previsão",
        options=[
            "ALL",
            "P1",
            "P2",
            "P3",
            "P4",
            "P5",
        ],
        format_func=lambda value: {
            "ALL": "Todas as prioridades",
            "P1": "P1 — Crítica",
            "P2": "P2 — Alta",
            "P3": "P3 — Média",
            "P4": "P4 — Baixa",
            "P5": "P5 — Planejada",
        }[value],
        key="forecast_priority_scope",
    )

    try:
        predictions = load_current_predictions()
    except SQLAlchemyError as exc:
        st.error(
            "Não foi possível consultar as previsões "
            "vigentes no Azure MySQL."
        )

        st.caption(
            f"Detalhes técnicos: {exc}"
        )

        predictions = pd.DataFrame()

    if predictions.empty:
        st.info(
            "Ainda não há previsões operacionais "
            "disponíveis no MySQL."
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

    else:
        scoped_predictions = predictions.loc[
            predictions[
                "priority_scope"
            ].eq(forecast_scope)
        ].copy()

        if scoped_predictions.empty:
            st.info(
                "Não há previsões disponíveis "
                "para o escopo selecionado."
            )

        else:
            latest_by_horizon = (
                scoped_predictions
                .sort_values(
                    [
                        "reference_date",
                        "generated_at",
                    ]
                )
                .drop_duplicates(
                    subset=["horizon"],
                    keep="last",
                )
            )

            def get_horizon_row(
                horizon: str,
            ) -> pd.Series | None:
                rows = latest_by_horizon.loc[
                    latest_by_horizon[
                        "horizon"
                    ].eq(horizon)
                ]

                if rows.empty:
                    return None

                return rows.iloc[-1]

            def format_prediction(
                horizon: str,
            ) -> str:
                row = get_horizon_row(
                    horizon
                )

                if row is None:
                    return "Indisponível"

                return format_integer(
                    round(
                        row[
                            "predicted_incident_count"
                        ]
                    )
                )

            col1, col2 = st.columns(2)

            col1.metric(
                "Previsão D+1",
                format_prediction("D+1"),
            )

            col2.metric(
                "Previsão D+7",
                format_prediction("D+7"),
            )

            st.caption(
                "Fonte operacional: "
                "Azure Database for MySQL • "
                "modelo vigente carregado pelo "
                "pipeline de inferência"
            )

            interval_rows = []

            for horizon in [
                "D+1",
                "D+7",
            ]:
                row = get_horizon_row(
                    horizon
                )

                if row is None:
                    continue

                interval_rows.append(
                    {
                        "Horizonte": horizon,
                        "Previsão": round(
                            float(
                                row[
                                    "predicted_incident_count"
                                ]
                            ),
                            2,
                        ),
                        "Limite inferior": (
                            None
                            if pd.isna(
                                row[
                                    "lower_bound"
                                ]
                            )
                            else round(
                                float(
                                    row[
                                        "lower_bound"
                                    ]
                                ),
                                2,
                            )
                        ),
                        "Limite superior": (
                            None
                            if pd.isna(
                                row[
                                    "upper_bound"
                                ]
                            )
                            else round(
                                float(
                                    row[
                                        "upper_bound"
                                    ]
                                ),
                                2,
                            )
                        ),
                        "Modelo": row[
                            "model_name"
                        ],
                        "Versão": row[
                            "model_version"
                        ],
                        "Data prevista": row[
                            "reference_date"
                        ],
                        "Gerado em": row[
                            "generated_at"
                        ],
                    }
                )

            st.subheader(
                "Detalhes da previsão"
            )

            st.dataframe(
                pd.DataFrame(
                    interval_rows
                ),
                width="stretch",
                hide_index=True,
            )


with tab_risk:
    st.subheader("Risco Operacional")

    try:
        risk_scores = load_current_risk_scores()
    except SQLAlchemyError as exc:
        st.error(
            "Não foi possível consultar os scores "
            "de risco vigentes no Azure MySQL."
        )
        st.caption(
            f"Detalhes técnicos: {exc}"
        )
        risk_scores = pd.DataFrame()
    except RiskScoreContractError as exc:
        st.error(
            "Os scores de risco no serving "
            f"não respeitam o contrato: {exc}"
        )
        risk_scores = pd.DataFrame()

    if risk_scores.empty:
        st.warning(
            "Ainda não há scores de risco "
            "operacionais disponíveis no MySQL."
        )

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

        st.caption(
            "Fonte operacional: "
            "Azure Database for MySQL"
        )

    else:
        latest_scores = (
            risk_scores
            .sort_values("scored_at")
            .drop_duplicates(
                subset=["incident_id"],
                keep="last",
            )
        )

        average_score = (
            latest_scores["risk_score"]
            .mean()
        )

        critical_count = int(
            latest_scores[
                "risk_level"
            ]
            .eq("crítico")
            .sum()
        )

        high_or_critical = int(
            latest_scores[
                "risk_level"
            ]
            .isin(
                [
                    "alto",
                    "crítico",
                ]
            )
            .sum()
        )

        moderate_count = int(
            latest_scores[
                "risk_level"
            ]
            .eq("moderado")
            .sum()
        )

        col1, col2, col3, col4 = (
            st.columns(4)
        )

        col1.metric(
            "Risk score médio",
            f"{average_score:.1f}",
        )

        col2.metric(
            "Moderados",
            format_integer(
                moderate_count
            ),
        )

        col3.metric(
            "Alto ou crítico",
            format_integer(
                high_or_critical
            ),
        )

        col4.metric(
            "Críticos",
            format_integer(
                critical_count
            ),
        )

        st.caption(
            "Fonte operacional: "
            "Azure Database for MySQL • "
            "modelo vigente sem retreinamento "
            "durante a inferência"
        )

        st.subheader(
            "Distribuição de risco"
        )

        risk_distribution = (
            latest_scores[
                "risk_level"
            ]
            .value_counts()
            .rename_axis(
                "Nível de risco"
            )
            .reset_index(
                name="Incidentes"
            )
        )

        st.bar_chart(
            risk_distribution,
            x="Nível de risco",
            y="Incidentes",
        )

        st.subheader(
            "Incidentes prioritários"
        )

        ranking = (
            latest_scores
            .sort_values(
                [
                    "risk_score",
                    "breach_probability",
                ],
                ascending=False,
            )
            .head(20)
            .copy()
        )

        ranking["risk_level"] = (
            ranking[
                "risk_level"
            ]
            .str.title()
        )

        st.dataframe(
            ranking[
                [
                    "incident_id",
                    "risk_score",
                    "risk_level",
                    "breach_probability",
                    "priority_impact",
                    "operational_pressure",
                    "top_risk_factors",
                    "recommended_action",
                    "model_version",
                    "scored_at",
                ]
            ].rename(
                columns={
                    "incident_id": (
                        "Incidente"
                    ),
                    "risk_score": (
                        "Risk score"
                    ),
                    "risk_level": (
                        "Nível"
                    ),
                    "breach_probability": (
                        "Prob. violação"
                    ),
                    "priority_impact": (
                        "Impacto prioridade"
                    ),
                    "operational_pressure": (
                        "Pressão operacional"
                    ),
                    "top_risk_factors": (
                        "Principais fatores"
                    ),
                    "recommended_action": (
                        "Ação recomendada"
                    ),
                    "model_version": (
                        "Versão do modelo"
                    ),
                    "scored_at": (
                        "Scoring em"
                    ),
                }
            ),
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
