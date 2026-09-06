from __future__ import annotations

import json
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from albus_hub.config import get_settings
from albus_hub.integration import (
    RiskScoreContractError,
    VolumePredictionContractError,
    load_risk_scores,
    load_volume_predictions,
)
from albus_hub.observability import configure_observability

settings = get_settings()
settings.create_local_directories()

try:
    APP_VERSION = package_version("albus-hub")
except PackageNotFoundError:
    APP_VERSION = "dev"

FAVICON_PATH = Path(__file__).parent / "assets" / "favicon.png"

configure_observability()

st.set_page_config(
    page_title="AlbusHub · AIOps",
    page_icon=str(FAVICON_PATH) if FAVICON_PATH.exists() else "🔴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- #
# Identidade visual — tema escuro Locaweb
# --------------------------------------------------------------------------- #

BRAND = "#e30613"
PLANE = "#0a0a0c"
SURFACE = "#16151b"
SURFACE_ALT = "#1d1c23"
BORDER = "#2a2932"

INK_PRIMARY = "#f5f5f7"
INK_SECONDARY = "#a8a7b0"
INK_MUTED = "#6e6d78"
GRIDLINE = "#232229"
AXIS_LINE = "#333139"

SERIES_1 = "#3987e5"  # azul — realizado
SERIES_2 = BRAND  # vermelho Locaweb — previsto / alerta

STATUS_GOOD = "#1eae72"
STATUS_WARNING = "#f2b705"
STATUS_SERIOUS = "#f5803e"
STATUS_CRITICAL = "#f2434f"

REGIME_CHANGE_DATE = pd.Timestamp("2025-09-01")
REGIME_TRANSITION_DATE = pd.Timestamp("2025-01-01")

# Os três patamares de volume da base. Misturar dois deles em uma média ou em
# uma comparação produz números que não descrevem operação nenhuma.
REGIMES = (
    (pd.Timestamp.min, REGIME_TRANSITION_DATE, "Base histórica (até 2024)"),
    (REGIME_TRANSITION_DATE, REGIME_CHANGE_DATE, "Transição (jan–ago/2025)"),
    (REGIME_CHANGE_DATE, pd.Timestamp.max, "Regime atual (set/2025+)"),
)


def regimes_between(start: pd.Timestamp, end: pd.Timestamp) -> list[str]:
    """Lista os patamares tocados por um intervalo, na ordem cronológica."""
    return [
        label
        for regime_start, regime_end, label in REGIMES
        if start < regime_end and end >= regime_start
    ]

PRIORITY_SCOPE_LABELS = {
    "ALL": "Todas as prioridades",
    "P2": "P2 — Alta",
    "P3": "P3 — Média",
}

CHECK_LABELS = {
    "mandatory_nulls": "Nulos em campos obrigatórios",
    "duplicate_incident_ids": "Números de incidente duplicados",
    "invalid_incident_ids": "Números fora do padrão INC0000000",
    "closed_before_opened": "Encerramento anterior à abertura",
    "negative_duration": "Duração negativa",
    "resolved_after_closed": "Resolução posterior ao encerramento",
    "duration_mismatch": "Duração informada diverge da calculada",
    "subcategory_without_category": "Subcategoria sem categoria",
    "entered_kpi_rule_mismatch": "Entrada no KPI diverge da regra",
    "kpi_breached_rule_mismatch": "Violação de OLA diverge da regra",
}

STYLE = f"""
<style>
:root {{
    --brand: {BRAND};
    --plane: {PLANE};
    --surface: {SURFACE};
    --surface-alt: {SURFACE_ALT};
    --border: {BORDER};
    --ink: {INK_PRIMARY};
    --ink-2: {INK_SECONDARY};
    --muted: {INK_MUTED};
}}

.stApp {{ background: var(--plane); }}

section[data-testid="stSidebar"] {{
    background: #060608;
    border-right: 1px solid var(--border);
}}

section[data-testid="stSidebar"] * {{ color: var(--ink-2); }}

.ah-brand {{
    display: flex; align-items: center; gap: 10px;
    padding: 2px 0 18px 0; margin-bottom: 6px;
    border-bottom: 1px solid var(--border);
}}
.ah-brand-mark {{
    background: var(--brand); color: #fff;
    font-weight: 700; font-size: 13px; letter-spacing: normal !important;
    padding: 5px 9px; border-radius: 3px; line-height: 1;
}}
.ah-brand-name {{ color: var(--ink); font-size: 17px; font-weight: 600; line-height: 1.1; }}
.ah-brand-sub {{
    color: var(--muted); font-size: 10px; letter-spacing: .18em;
    text-transform: uppercase; font-family: ui-monospace, "Cascadia Mono", monospace;
}}

.ah-kicker {{
    color: var(--muted); font-size: 11px; letter-spacing: .22em;
    text-transform: uppercase; font-family: ui-monospace, "Cascadia Mono", monospace;
    margin: 0 0 4px 0;
}}
.ah-title {{
    color: var(--ink); font-size: 30px; font-weight: 600;
    letter-spacing: -.01em; margin: 0 0 2px 0; line-height: 1.15;
}}
.ah-sub {{ color: var(--ink-2); font-size: 13px; margin: 0; }}

.ah-section {{
    color: var(--ink); font-size: 12px; letter-spacing: .18em;
    text-transform: uppercase; font-family: ui-monospace, "Cascadia Mono", monospace;
    margin: 6px 0 10px 0; padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}}

.ah-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; padding: 16px 18px; height: 100%;
    min-height: 128px; display: flex; flex-direction: column;
    justify-content: space-between;
}}
.ah-card-accent {{ border-top: 2px solid var(--brand); }}
.ah-card-label {{
    color: var(--muted); font-size: 10px; letter-spacing: .18em;
    text-transform: uppercase; font-family: ui-monospace, "Cascadia Mono", monospace;
    margin-bottom: 10px;
}}
.ah-card-value {{
    color: var(--ink); font-size: 38px; font-weight: 300;
    line-height: 1; letter-spacing: -.02em;
}}
.ah-card-value.alert {{ color: {STATUS_CRITICAL}; }}
.ah-card-unit {{ font-size: 17px; color: var(--ink-2); margin-left: 3px; }}
.ah-card-foot {{
    margin-top: 10px; font-size: 11.5px; color: var(--muted);
    font-family: ui-monospace, "Cascadia Mono", monospace;
}}
.ah-up {{ color: {STATUS_CRITICAL}; }}
.ah-down {{ color: {STATUS_GOOD}; }}

.ah-chip {{
    display: inline-block; padding: 2px 7px; border-radius: 3px;
    font-size: 11px; font-weight: 600; color: #0a0a0c;
    font-family: ui-monospace, "Cascadia Mono", monospace;
}}

.ah-note {{
    background: var(--surface); border: 1px solid var(--border);
    border-left: 2px solid {STATUS_WARNING};
    border-radius: 4px; padding: 13px 16px;
    color: var(--ink-2); font-size: 13px; line-height: 1.55;
}}
.ah-note strong {{ color: var(--ink); }}

.stTabs [data-baseweb="tab-list"] {{ gap: 26px; border-bottom: 1px solid var(--border); }}
.stTabs [data-baseweb="tab"] {{
    color: var(--muted); font-size: 12px; letter-spacing: .12em;
    text-transform: uppercase; font-family: ui-monospace, "Cascadia Mono", monospace;
    padding: 8px 0;
}}
.stTabs [aria-selected="true"] {{ color: var(--ink) !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--brand); }}

div[data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: 6px; }}
hr {{ border-color: var(--border); }}
.block-container {{ padding-top: 4.2rem; max-width: 1500px; }}
div[data-testid="stPlotlyChart"] {{
    border: 1px solid var(--border); border-radius: 6px; overflow: hidden;
}}
.ah-card-foot {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
section[data-testid="stSidebar"] .ah-card-foot {{ white-space: normal; }}
</style>
"""

st.markdown(STYLE, unsafe_allow_html=True)


def section(title: str) -> None:
    """Cabeçalho de seção no padrão visual do protótipo."""
    st.markdown(f'<div class="ah-section">{title}</div>', unsafe_allow_html=True)


def kpi_card(
    label: str,
    value: str,
    unit: str = "",
    foot: str = "",
    alert: bool = False,
    accent: bool = False,
) -> str:
    """Monta o HTML de um cartão de indicador."""
    classes = "ah-card ah-card-accent" if accent else "ah-card"
    value_class = "ah-card-value alert" if alert else "ah-card-value"
    unit_html = f'<span class="ah-card-unit">{unit}</span>' if unit else ""
    foot_html = f'<div class="ah-card-foot">{foot}</div>' if foot else ""

    return (
        f'<div class="{classes}">'
        f'<div class="ah-card-label">{label}</div>'
        f'<div class="{value_class}">{value}{unit_html}</div>'
        f"{foot_html}"
        f"</div>"
    )


def trend_foot(
    current: float,
    previous: float,
    suffix: str = "vs anterior",
    comparable: bool = True,
) -> str:
    """
    Rodapé de cartão com a variação contra o período anterior.

    Quando o período anterior cai em outro patamar de volume, a variação
    mediria a quebra estrutural e não a operação — nesse caso ela é suprimida.
    """
    if not comparable:
        return "período anterior em outro patamar"

    if previous <= 0:
        return "sem base de comparação"

    variation = 100 * (current - previous) / previous
    arrow = "↑" if variation >= 0 else "↓"
    css = "ah-up" if variation >= 0 else "ah-down"

    return f'<span class="{css}">{arrow} {abs(variation):.1f}%</span> {suffix}'.replace(".", ",")


def base_layout(height: int = 340, showlegend: bool = False) -> dict:
    """Layout comum a todos os gráficos, no tema escuro."""
    return {
        "height": height,
        "margin": {"l": 8, "r": 8, "t": 8, "b": 8},
        "paper_bgcolor": SURFACE,
        "plot_bgcolor": SURFACE,
        "font": {
            "family": 'system-ui, -apple-system, "Segoe UI", sans-serif',
            "color": INK_SECONDARY,
            "size": 12,
        },
        "showlegend": showlegend,
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.04,
            "x": 0,
            "font": {"color": INK_SECONDARY, "size": 11},
        },
        "hoverlabel": {
            "bgcolor": SURFACE_ALT,
            "bordercolor": BORDER,
            "font": {"color": INK_PRIMARY},
        },
        "xaxis": {
            "gridcolor": GRIDLINE,
            "linecolor": AXIS_LINE,
            "zeroline": False,
            "tickfont": {"color": INK_MUTED, "size": 11},
        },
        "yaxis": {
            "gridcolor": GRIDLINE,
            "linecolor": AXIS_LINE,
            "zeroline": False,
            "tickfont": {"color": INK_MUTED, "size": 11},
        },
    }


def chart(figure: go.Figure) -> None:
    """Renderiza um gráfico dentro do painel escuro."""
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


def format_integer(value: int | float) -> str:
    """Formata inteiros no padrão visual pt-BR."""
    return f"{int(value):,}".replace(",", ".")


# --------------------------------------------------------------------------- #
# Carregamento
# --------------------------------------------------------------------------- #


# TTL de 15 minutos: em produção o processo fica no ar por dias, e sem TTL o
# cache congelaria a primeira leitura até o container reiniciar.
@st.cache_data(show_spinner=False, ttl=900)
def load_parquet(path: str) -> pd.DataFrame:
    """Carrega um arquivo Parquet utilizado pelo dashboard."""
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False, ttl=900)
def load_json_report(path: str) -> dict | None:
    """Carrega um relatório de qualidade gerado pelo pipeline."""
    report_path = Path(path)

    if not report_path.exists():
        return None

    with report_path.open(encoding="utf-8") as file:
        return json.load(file)


@st.cache_data(show_spinner=False, ttl=900)
def load_incident_profile(path: str) -> pd.DataFrame | None:
    """
    Carrega um recorte enxuto da camada Silver.

    A Gold responde pelo volume diário. As análises de duração, hora de
    abertura e aderência a OLA precisam do grão de incidente, por isso são
    lidas da Silver e permanecem opcionais: se o arquivo não existir, o
    dashboard continua funcionando apenas com a Gold.
    """
    silver_path = Path(path)

    if not silver_path.exists():
        return None

    columns = [
        "incident_id",
        "opened_at",
        "opened_date",
        "priority_code",
        "duration_hours",
        "opened_day_of_week",
        "opened_hour",
        "status",
        "opened_by",
        "entered_kpi_source",
        "kpi_breached_source",
    ]

    # A promessa do docstring é degradar com elegância. Ler colunas que a
    # Silver não tem levanta KeyError e derruba o app inteiro, então só
    # pedimos o que existe de fato no arquivo.
    try:
        import pyarrow.parquet as pq

        available: set[str] | None = set(pq.ParquetFile(silver_path).schema.names)
    except Exception:  # noqa: BLE001 — sem pyarrow ou schema ilegível
        available = None

    wanted = [column for column in columns if column in available] if available else columns

    try:
        frame = pd.read_parquet(silver_path, columns=wanted)
    except Exception:  # noqa: BLE001 — schema divergente do contrato
        try:
            frame = pd.read_parquet(silver_path)
        except Exception:  # noqa: BLE001 — arquivo ilegível
            return None

    essential = {"opened_date", "priority_code", "duration_hours"}
    if not essential.issubset(frame.columns):
        return None

    frame["opened_date"] = pd.to_datetime(frame["opened_date"])

    return frame


RISK_LEVEL_SYNONYMS = {
    "baixo": "baixo",
    "low": "baixo",
    "moderado": "moderado",
    "medio": "moderado",
    "medium": "moderado",
    "moderate": "moderado",
    "alto": "alto",
    "high": "alto",
    "critico": "crítico",
    "critical": "crítico",
}


def normalize_risk_level(value: object) -> str:
    """
    Normaliza o nível de risco para o vocabulário do dashboard.

    Aceita variações de caixa, acento e idioma — o contrato tabela os níveis
    capitalizados e o exemplo de evento usa inglês.
    """
    if not isinstance(value, str):
        return ""

    key = (
        value.strip()
        .lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )

    return RISK_LEVEL_SYNONYMS.get(key, key)


def filter_period(
    frame: pd.DataFrame,
    column: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Filtra um DataFrame por um intervalo de datas."""
    return frame.loc[frame[column].between(start_date, end_date)].copy()


def scope_sum(frame: pd.DataFrame, scope: str, column: str) -> int:
    """Soma uma métrica para um escopo de prioridade."""
    return int(frame.loc[frame["priority_scope"].eq(scope), column].sum())


# --------------------------------------------------------------------------- #
# Dados
# --------------------------------------------------------------------------- #

daily_volume_path = settings.absolute_path(settings.locaweb_gold_daily_volume_file)
breakdown_path = settings.absolute_path(settings.locaweb_gold_daily_breakdown_file)
silver_path = settings.absolute_path(settings.locaweb_silver_file)
ingestion_report_path = settings.absolute_path(settings.locaweb_quality_report)
gold_report_path = settings.absolute_path(settings.locaweb_gold_daily_volume_report)

st.sidebar.markdown(
    '<div class="ah-brand">'
    '<span class="ah-brand-mark">AH</span>'
    '<span><span class="ah-brand-name">AlbusHub</span><br>'
    '<span class="ah-brand-sub">AIOps Platform</span></span>'
    "</div>",
    unsafe_allow_html=True,
)

if not daily_volume_path.exists() or not breakdown_path.exists():
    st.error(
        "A camada Gold não foi encontrada. Execute o pipeline antes de abrir o dashboard: "
        "`uv run python scripts/ingest_locaweb.py` e "
        "`uv run python scripts/build_daily_volume_gold.py`."
    )
    st.stop()

daily_volume = load_parquet(str(daily_volume_path))
daily_volume["reference_date"] = pd.to_datetime(daily_volume["reference_date"])

incidents = load_incident_profile(str(silver_path))

# Artefatos das frentes de modelagem, carregados uma única vez. As abas
# decidem como degradar quando o artefato falta ou fere o contrato.
predictions: pd.DataFrame | None = None
predictions_error: str | None = None

try:
    predictions = load_volume_predictions(
        settings.absolute_path(settings.locaweb_volume_predictions_file)
    )
except VolumePredictionContractError as exc:
    predictions_error = str(exc)

risk_scores: pd.DataFrame | None = None
risk_error: str | None = None

try:
    risk_scores = load_risk_scores(settings.absolute_path(settings.locaweb_risk_scores_file))
except RiskScoreContractError as exc:
    risk_error = str(exc)

latest_scores: pd.DataFrame | None = None

if risk_scores is not None:
    latest_scores = risk_scores.sort_values("scored_at").drop_duplicates(
        subset=["incident_id"], keep="last"
    )

    # O contrato tabela os níveis capitalizados e o exemplo de evento usa
    # inglês. Sem normalizar, uma variante de caixa zera os cartões em
    # silêncio, sem erro nenhum na tela.
    latest_scores = latest_scores.assign(
        risk_level=latest_scores["risk_level"].map(normalize_risk_level)
    )


def latest_predictions_for(scope: str) -> pd.DataFrame | None:
    """Última previsão publicada por horizonte, para um escopo de prioridade."""
    if predictions is None:
        return None

    scoped = predictions.loc[predictions["priority_scope"].eq(scope)]

    if scoped.empty:
        return None

    return scoped.sort_values(["reference_date", "generated_at"]).drop_duplicates(
        subset=["horizon"], keep="last"
    )

min_date = daily_volume["reference_date"].min()
max_date = daily_volume["reference_date"].max()

# --------------------------------------------------------------------------- #
# Filtros
# --------------------------------------------------------------------------- #

st.sidebar.markdown('<div class="ah-kicker">Recorte</div>', unsafe_allow_html=True)

# Janelas curtas, de operação. Recortes longos e análises históricas moram no
# Power BI — aqui o interesse é o que está acontecendo e o que vem a seguir.
PERIOD_PRESETS = {
    "Últimos 7 dias": 7,
    "Últimos 14 dias": 14,
    "Últimos 30 dias": 30,
    "Regime atual (desde set/2025)": "regime",
    "Personalizado": "custom",
}

# O recorte e o escopo vivem na URL: um link colado no chat da equipe abre a
# mesma tela para todo mundo.
PERIOD_SLUGS = {
    "7d": "Últimos 7 dias",
    "14d": "Últimos 14 dias",
    "30d": "Últimos 30 dias",
    "regime": "Regime atual (desde set/2025)",
    "custom": "Personalizado",
}
SLUG_BY_PERIOD = {label: slug for slug, label in PERIOD_SLUGS.items()}

url_period = st.query_params.get("periodo", "")
default_period_index = (
    list(PERIOD_PRESETS).index(PERIOD_SLUGS[url_period])
    if url_period in PERIOD_SLUGS
    else 1
)

preset = st.sidebar.radio(
    "Período",
    options=list(PERIOD_PRESETS),
    index=default_period_index,
    label_visibility="collapsed",
)

preset_value = PERIOD_PRESETS[preset]

if preset_value == "regime":
    start_date = max(min_date, REGIME_CHANGE_DATE)
    end_date = max_date
elif preset_value == "custom":
    selected_period = st.sidebar.date_input(
        "Intervalo",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )

    if isinstance(selected_period, tuple) and len(selected_period) == 2:
        start_date = pd.Timestamp(selected_period[0])
        end_date = pd.Timestamp(selected_period[1])
    else:
        start_date, end_date = min_date, max_date
elif preset_value is None:
    start_date, end_date = min_date, max_date
else:
    end_date = max_date
    start_date = max(min_date, max_date - pd.Timedelta(days=preset_value - 1))

st.sidebar.markdown(
    '<div class="ah-kicker" style="margin-top:18px">Prioridade</div>',
    unsafe_allow_html=True,
)

SCOPE_OPTIONS = ["ALL", "P2", "P3"]
url_scope = st.query_params.get("escopo", "").upper()

priority_scope = st.sidebar.selectbox(
    "Escopo de prioridade",
    options=SCOPE_OPTIONS,
    index=SCOPE_OPTIONS.index(url_scope) if url_scope in SCOPE_OPTIONS else 0,
    format_func=lambda value: PRIORITY_SCOPE_LABELS[value],
    label_visibility="collapsed",
)

st.query_params["periodo"] = SLUG_BY_PERIOD[preset]
st.query_params["escopo"] = priority_scope

st.sidebar.markdown(
    f'<div class="ah-card-foot" style="margin-top:26px;border-top:1px solid {BORDER};'
    f'padding-top:14px">base {min_date:%d/%m/%Y} — {max_date:%d/%m/%Y}<br>'
    f"leitura às {datetime.now():%H:%M} · atualização a cada 15 min</div>",
    unsafe_allow_html=True,
)

period_days = (end_date - start_date).days + 1
previous_end = start_date - pd.Timedelta(days=1)
previous_start = previous_end - pd.Timedelta(days=period_days - 1)

daily_period = filter_period(daily_volume, "reference_date", start_date, end_date)
daily_previous = filter_period(daily_volume, "reference_date", previous_start, previous_end)

has_previous = not daily_previous.empty

# O período anterior só serve de comparação se estiver no mesmo patamar de
# volume que o recorte atual. Caso contrário a variação é a quebra estrutural.
current_regimes = regimes_between(start_date, end_date)
previous_regimes = regimes_between(previous_start, previous_end)
comparable_previous = (
    has_previous
    and len(current_regimes) == 1
    and len(previous_regimes) == 1
    and current_regimes == previous_regimes
)

st.markdown(
    '<div class="ah-kicker">Operação · Locaweb</div>'
    '<div class="ah-title">AlbusHub</div>'
    '<div class="ah-sub">Previsão de incidentes, risco operacional e priorização preventiva</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="ah-card-foot" style="margin:14px 0 6px 0">'
    f"recorte {start_date:%d/%m/%Y} — {end_date:%d/%m/%Y} · "
    f"{format_integer(period_days)} dias · {PRIORITY_SCOPE_LABELS[priority_scope].lower()}"
    f"</div>",
    unsafe_allow_html=True,
)

tab_ops, tab_alerts, tab_forecast, tab_risk, tab_quality = st.tabs(
    ["Operação", "Alertas", "Previsões", "Risco", "Qualidade"]
)

# --------------------------------------------------------------------------- #
# Operação — o pulso do recorte
# --------------------------------------------------------------------------- #

with tab_ops:
    section("Pulso do recorte")

    total_incidents = scope_sum(daily_period, priority_scope, "incident_count")
    daily_average = total_incidents / period_days if period_days else 0.0
    previous_total = (
        scope_sum(daily_previous, priority_scope, "incident_count") if has_previous else 0
    )

    latest = latest_predictions_for(priority_scope)

    def prediction_row(horizon: str) -> pd.Series | None:
        if latest is None:
            return None

        rows = latest.loc[latest["horizon"].eq(horizon)]

        return rows.iloc[-1] if not rows.empty else None

    next_prediction = prediction_row("D+1")
    predicted_next = (
        float(next_prediction["predicted_incident_count"])
        if next_prediction is not None
        else None
    )

    high_or_critical = (
        int(latest_scores["risk_level"].isin(["alto", "crítico"]).sum())
        if latest_scores is not None
        else None
    )

    # Violações de OLA no recorte, no grão de incidente. Nulos contam como
    # não violado — a decisão explícita evita que o pandas decida sozinho.
    ola_breaches: int | None = None

    if incidents is not None and "kpi_breached_source" in incidents.columns:
        profile_period = filter_period(incidents, "opened_date", start_date, end_date)

        if priority_scope != "ALL" and "priority_code" in profile_period.columns:
            profile_period = profile_period.loc[
                profile_period["priority_code"].eq(int(priority_scope[1]))
            ]

        ola_breaches = int(profile_period["kpi_breached_source"].fillna(False).astype(bool).sum())

    cards = st.columns(5)

    cards[0].markdown(
        kpi_card(
            "Incidentes no recorte",
            format_integer(total_incidents),
            foot=trend_foot(total_incidents, previous_total, comparable=comparable_previous),
            accent=True,
        ),
        unsafe_allow_html=True,
    )
    cards[1].markdown(
        kpi_card(
            "Média diária",
            f"{daily_average:,.0f}".replace(",", "."),
            foot="por dia no recorte",
        ),
        unsafe_allow_html=True,
    )
    cards[2].markdown(
        kpi_card(
            "Previsão D+1",
            format_integer(round(predicted_next)) if predicted_next is not None else "—",
            foot=(
                f"para {next_prediction['reference_date']:%d/%m/%Y}"
                if next_prediction is not None
                else "sem previsão publicada"
            ),
        ),
        unsafe_allow_html=True,
    )
    cards[3].markdown(
        kpi_card(
            "Alto ou crítico",
            format_integer(high_or_critical) if high_or_critical is not None else "—",
            foot="risco ativo" if high_or_critical is not None else "sem pontuação publicada",
            alert=bool(high_or_critical),
        ),
        unsafe_allow_html=True,
    )
    cards[4].markdown(
        kpi_card(
            "Violações de OLA",
            format_integer(ola_breaches) if ola_breaches is not None else "—",
            foot="no recorte" if ola_breaches is not None else "sem dados disponíveis",
            alert=bool(ola_breaches),
        ),
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    section("Realizado recente e previsão")

    history = (
        daily_period.loc[daily_period["priority_scope"].eq(priority_scope)]
        .sort_values("reference_date")
    )

    pulse_figure = go.Figure()

    pulse_figure.add_trace(
        go.Scatter(
            x=history["reference_date"],
            y=history["incident_count"],
            name="Realizado",
            mode="lines",
            line={"color": SERIES_1, "width": 2},
            hovertemplate="%{x|%d/%m/%Y}<br>%{y} incidentes<extra></extra>",
        )
    )

    if latest is not None and not history.empty:
        # A projeção parte do último realizado e segue tracejada até os
        # horizontes previstos — pontos soltos no meio do gráfico não contam
        # história nenhuma.
        anchor = history.iloc[-1]
        projection = latest.sort_values("reference_date")

        pulse_figure.add_trace(
            go.Scatter(
                x=[anchor["reference_date"], *projection["reference_date"]],
                y=[anchor["incident_count"], *projection["predicted_incident_count"]],
                mode="lines",
                line={"color": SERIES_2, "width": 2, "dash": "dot"},
                hoverinfo="skip",
                showlegend=False,
            )
        )

        pulse_figure.add_trace(
            go.Scatter(
                x=projection["reference_date"],
                y=projection["predicted_incident_count"],
                name="Previsto",
                mode="markers+text",
                text=list(projection["horizon"]),
                textposition="top center",
                textfont={"color": INK_SECONDARY, "size": 11},
                marker={
                    "size": 10,
                    "color": SERIES_2,
                    "line": {"color": SURFACE, "width": 2},
                },
                hovertemplate="%{x|%d/%m/%Y}<br>%{y:.0f} previstos<extra></extra>",
            )
        )

        pulse_figure.add_vline(
            x=anchor["reference_date"],
            line_color=AXIS_LINE,
            line_dash="dot",
            annotation_text="última leitura",
            annotation_position="top left",
            annotation_font={"color": INK_MUTED, "size": 10},
        )

    layout = base_layout(height=320, showlegend=True)
    layout["hovermode"] = "x unified"
    pulse_figure.update_layout(**layout)

    chart(pulse_figure)


# --------------------------------------------------------------------------- #
# Alertas — o que exige ação agora
# --------------------------------------------------------------------------- #

with tab_alerts:
    section("Painel de alertas críticos")

    # Os limiares são interativos de propósito: a operação calibra a régua
    # conforme o dia, sem depender de redeploy.
    threshold_columns = st.columns(2)

    with threshold_columns[0]:
        forecast_threshold = st.slider(
            "Alerta quando a previsão superar a média do recorte em (%)",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
        )

    with threshold_columns[1]:
        attention_score = st.slider(
            "Score mínimo para exigir atenção",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
        )

    ALERT_COLORS = {
        "crítico": STATUS_CRITICAL,
        "sério": STATUS_SERIOUS,
        "atenção": STATUS_WARNING,
    }

    alerts: list[tuple[str, str, str]] = []

    reference_average = (
        scope_sum(daily_period, priority_scope, "incident_count") / period_days
        if period_days
        else 0.0
    )
    latest_alert = latest_predictions_for(priority_scope)

    if latest_alert is not None and reference_average > 0:
        for horizon, severity in (("D+1", "crítico"), ("D+7", "sério")):
            rows = latest_alert.loc[latest_alert["horizon"].eq(horizon)]

            if rows.empty:
                continue

            predicted = float(rows.iloc[-1]["predicted_incident_count"])
            ceiling = reference_average * (1 + forecast_threshold / 100)

            if predicted > ceiling:
                excess = 100 * (predicted / reference_average - 1)
                alerts.append(
                    (
                        severity,
                        f"Previsão {horizon} acima do limiar",
                        f"{predicted:.0f} incidentes previstos para "
                        f"{rows.iloc[-1]['reference_date']:%d/%m/%Y} — "
                        f"{excess:.0f}% acima da média do recorte "
                        f"({reference_average:.0f}/dia).",
                    )
                )
    elif predictions_error:
        alerts.append(("sério", "Artefato de previsão fora do contrato", predictions_error))

    if latest_scores is not None:
        critical_incidents = int(latest_scores["risk_level"].eq("crítico").sum())
        above_score = int((latest_scores["risk_score"] >= attention_score).sum())

        if critical_incidents:
            alerts.append(
                (
                    "crítico",
                    f"{format_integer(critical_incidents)} incidentes em risco crítico",
                    "A fila priorizada da aba Risco ordena por score e traz a ação recomendada.",
                )
            )

        if above_score:
            alerts.append(
                (
                    "atenção",
                    f"{format_integer(above_score)} incidentes com score ≥ {attention_score}",
                    "Régua definida pelo controle acima.",
                )
            )
    elif risk_error:
        alerts.append(("sério", "Artefato de risco fora do contrato", risk_error))

    if incidents is not None and "kpi_breached_source" in incidents.columns:
        recent_start = incidents["opened_date"].max() - pd.Timedelta(days=6)
        recent = incidents.loc[incidents["opened_date"] >= recent_start]
        recent_breaches = int(recent["kpi_breached_source"].fillna(False).astype(bool).sum())

        if recent_breaches:
            alerts.append(
                (
                    "sério",
                    f"{format_integer(recent_breaches)} violações de OLA nos últimos 7 dias",
                    f"Janela {recent_start:%d/%m/%Y} — "
                    f"{incidents['opened_date'].max():%d/%m/%Y}, no grão de incidente da Silver.",
                )
            )

    quality_alert_report = load_json_report(str(ingestion_report_path))

    if quality_alert_report and quality_alert_report.get("quality_status") == "failed":
        alerts.append(
            (
                "crítico",
                "Pipeline reprovado nas checagens de qualidade",
                "Os números exibidos podem não ser confiáveis. Detalhes na aba Qualidade.",
            )
        )

    if not alerts:
        st.markdown(
            f'<div class="ah-note" style="border-left-color:{STATUS_GOOD}">'
            "Nenhum alerta ativo nos critérios atuais.</div>",
            unsafe_allow_html=True,
        )
    else:
        severity_rank = {"crítico": 0, "sério": 1, "atenção": 2}

        for severity, title, detail in sorted(alerts, key=lambda item: severity_rank[item[0]]):
            st.markdown(
                f'<div class="ah-note" style="border-left-color:{ALERT_COLORS[severity]};'
                f'margin-bottom:10px"><strong>{title}</strong> · '
                f'<span style="color:{ALERT_COLORS[severity]};text-transform:uppercase;'
                f'font-size:11px;letter-spacing:.12em">{severity}</span><br>'
                f"{detail}</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    section("Incidentes que exigem atenção")

    if latest_scores is None:
        st.markdown(
            '<div class="ah-note">Nenhuma pontuação de risco publicada no momento. '
            "Os incidentes que exigem atenção aparecem aqui assim que o serviço de "
            "modelagem publicar novos scores.</div>",
            unsafe_allow_html=True,
        )
    else:
        attention = latest_scores.loc[
            latest_scores["risk_level"].isin(["alto", "crítico"])
            | (latest_scores["risk_score"] >= attention_score)
        ]

        if attention.empty:
            st.info("Nenhum incidente acima da régua de atenção no momento.")
        else:
            attention_ranking = attention.sort_values("risk_score", ascending=False).copy()
            attention_ranking["risk_level"] = attention_ranking["risk_level"].str.title()

            st.dataframe(
                attention_ranking[
                    [
                        "incident_id",
                        "risk_score",
                        "risk_level",
                        "breach_probability",
                        "top_risk_factors",
                        "recommended_action",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

            st.download_button(
                "Baixar lista de atenção (CSV)",
                attention_ranking.to_csv(index=False).encode("utf-8-sig"),
                file_name="incidentes_atencao.csv",
                mime="text/csv",
            )

# --------------------------------------------------------------------------- #
# Previsões
# --------------------------------------------------------------------------- #

with tab_forecast:
    section("Previsão de volume")

    if predictions_error:
        st.error(f"O artefato de previsão não respeita o contrato: {predictions_error}")

    if predictions is None:
        forecast_cards = st.columns(3)

        forecast_cards[0].markdown(
            kpi_card("Previsão D+1", "—", foot="sem previsão publicada", accent=True),
            unsafe_allow_html=True,
        )
        forecast_cards[1].markdown(
            kpi_card("Previsão D+7", "—", foot="sem previsão publicada"), unsafe_allow_html=True
        )
        forecast_cards[2].markdown(
            kpi_card("Modelo", "—", foot="nenhuma versão publicada"), unsafe_allow_html=True
        )

        st.markdown(
            '<div class="ah-note" style="margin-top:18px">'
            "Nenhuma previsão publicada no momento. Os horizontes D+1 e D+7 aparecem "
            "nesta aba assim que o serviço de modelagem publicar novos resultados.</div>",
            unsafe_allow_html=True,
        )
    else:
        scoped = predictions.loc[predictions["priority_scope"].eq(priority_scope)].copy()

        if scoped.empty:
            st.info("Não há previsões disponíveis para o escopo selecionado.")
        else:
            tem_intervalo = {"lower_bound", "upper_bound"}.issubset(scoped.columns)
            tem_real = "actual_incidents" in scoped.columns

            latest = scoped.sort_values(["reference_date", "generated_at"]).drop_duplicates(
                subset=["horizon"], keep="last"
            )

            def previsao(horizonte: str) -> str:
                linhas = latest.loc[latest["horizon"].eq(horizonte)]

                if linhas.empty:
                    return "—"

                return format_integer(round(linhas.iloc[-1]["predicted_incident_count"]))

            def data_prevista(horizonte: str) -> str:
                linhas = latest.loc[latest["horizon"].eq(horizonte)]

                if linhas.empty:
                    return "sem previsão publicada"

                return f"para {linhas.iloc[-1]['reference_date']:%d/%m/%Y}"

            forecast_cards = st.columns(3)

            forecast_cards[0].markdown(
                kpi_card("Previsão D+1", previsao("D+1"), foot=data_prevista("D+1"), accent=True),
                unsafe_allow_html=True,
            )
            forecast_cards[1].markdown(
                kpi_card("Previsão D+7", previsao("D+7"), foot=data_prevista("D+7")),
                unsafe_allow_html=True,
            )

            # Erro médio absoluto medido nas linhas de backtest, quando o artefato as traz.
            if tem_real and scoped["actual_incidents"].notna().any():
                backtest = scoped.dropna(subset=["actual_incidents"])
                mae = float(
                    (backtest["predicted_incident_count"] - backtest["actual_incidents"])
                    .abs()
                    .mean()
                )
                forecast_cards[2].markdown(
                    kpi_card(
                        "Erro médio no backtest",
                        format_integer(round(mae)),
                        foot=f"D+1 e D+7 · {format_integer(len(backtest))} dias avaliados",
                    ),
                    unsafe_allow_html=True,
                )
            else:
                forecast_cards[2].markdown(
                    kpi_card("Erro no backtest", "—", foot="artefato sem histórico"),
                    unsafe_allow_html=True,
                )

            horizontes = sorted(scoped["horizon"].dropna().unique())

            horizonte = st.radio(
                "Horizonte",
                options=horizontes,
                horizontal=True,
                label_visibility="collapsed",
            )

            serie = scoped.loc[scoped["horizon"].eq(horizonte)].sort_values("reference_date")

            # O realizado obedece ao recorte da barra lateral; a previsão é
            # sempre futura e não é recortada.
            history = (
                daily_period.loc[daily_period["priority_scope"].eq(priority_scope)]
                .sort_values("reference_date")
            )

            forecast_figure = go.Figure()

            if tem_intervalo:
                forecast_figure.add_trace(
                    go.Scatter(
                        x=list(serie["reference_date"]) + list(serie["reference_date"])[::-1],
                        y=list(serie["upper_bound"]) + list(serie["lower_bound"])[::-1],
                        name="Faixa de confiança",
                        fill="toself",
                        fillcolor="rgba(227, 6, 19, 0.13)",
                        line={"width": 0},
                        hoverinfo="skip",
                        showlegend=True,
                    )
                )

            forecast_figure.add_trace(
                go.Scatter(
                    x=history["reference_date"],
                    y=history["incident_count"],
                    name="Realizado",
                    mode="lines",
                    line={"color": SERIES_1, "width": 2},
                    hovertemplate="%{x|%d/%m/%Y}<br>%{y} incidentes<extra></extra>",
                )
            )

            forecast_figure.add_trace(
                go.Scatter(
                    x=serie["reference_date"],
                    y=serie["predicted_incident_count"],
                    name=f"Previsto {horizonte}",
                    mode="lines",
                    line={"color": SERIES_2, "width": 2, "dash": "dot"},
                    hovertemplate="%{x|%d/%m/%Y}<br>%{y:.0f} previstos<extra></extra>",
                )
            )

            futuro = serie.loc[serie["actual_incidents"].isna()] if tem_real else serie.tail(1)

            if not futuro.empty:
                forecast_figure.add_trace(
                    go.Scatter(
                        x=futuro["reference_date"],
                        y=futuro["predicted_incident_count"],
                        name="Previsão em aberto",
                        mode="markers",
                        marker={
                            "size": 11,
                            "color": SERIES_2,
                            "line": {"color": SURFACE, "width": 2},
                        },
                        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.0f} previstos<extra></extra>",
                    )
                )

            layout = base_layout(height=360, showlegend=True)
            layout["hovermode"] = "x unified"
            forecast_figure.update_layout(**layout)

            chart(forecast_figure)

            st.markdown(
                f'<div class="ah-card-foot">a faixa vermelha é o intervalo conformal do modelo · '
                f"os pontos cheios à direita são a previsão ainda sem valor realizado · "
                f"modelo {latest.iloc[-1]['model_version']}, publicado em "
                f"{latest.iloc[-1]['generated_at']:%d/%m/%Y}</div>",
                unsafe_allow_html=True,
            )

            with st.expander("Artefato publicado"):
                colunas = [
                    "reference_date",
                    "horizon",
                    "priority_scope",
                    "predicted_incident_count",
                    "model_version",
                    "generated_at",
                ]
                extras = [
                    c
                    for c in ["actual_incidents", "lower_bound", "upper_bound", "model"]
                    if c in scoped.columns
                ]

                st.dataframe(
                    scoped[colunas + extras].sort_values(["horizon", "reference_date"]),
                    width="stretch",
                    hide_index=True,
                )

# --------------------------------------------------------------------------- #
# Risco
# --------------------------------------------------------------------------- #

with tab_risk:
    section("Risco operacional")

    st.markdown(
        '<div class="ah-card-foot" style="margin:-4px 0 14px 0">'
        "retrato mais recente publicado pelo serviço de modelagem · "
        "independe do recorte de datas</div>",
        unsafe_allow_html=True,
    )

    if risk_error:
        st.error(f"O artefato de risco não respeita o contrato: {risk_error}")

    if risk_scores is None:
        risk_cards = st.columns(3)

        risk_cards[0].markdown(
            kpi_card("Score médio", "—", foot="sem pontuação publicada", accent=True),
            unsafe_allow_html=True,
        )
        risk_cards[1].markdown(
            kpi_card("Alto ou crítico", "—", foot="sem pontuação publicada"), unsafe_allow_html=True
        )
        risk_cards[2].markdown(
            kpi_card("Críticos", "—", foot="sem pontuação publicada"), unsafe_allow_html=True
        )

        st.markdown(
            '<div class="ah-note" style="margin-top:18px">'
            "Nenhuma pontuação de risco publicada no momento. A distribuição por nível e a "
            "fila priorizada aparecem nesta aba assim que o serviço de modelagem publicar "
            "novos scores.</div>",
            unsafe_allow_html=True,
        )
    else:
        average_score = latest_scores["risk_score"].mean()
        critical_count = int(latest_scores["risk_level"].eq("crítico").sum())
        high_or_critical = int(latest_scores["risk_level"].isin(["alto", "crítico"]).sum())

        risk_cards = st.columns(3)

        risk_cards[0].markdown(
            kpi_card(
                "Score médio",
                f"{average_score:.1f}".replace(".", ","),
                foot="entre os incidentes pontuados",
                accent=True,
            ),
            unsafe_allow_html=True,
        )
        risk_cards[1].markdown(
            kpi_card(
                "Alto ou crítico",
                format_integer(high_or_critical),
                foot="requerem priorização",
            ),
            unsafe_allow_html=True,
        )
        risk_cards[2].markdown(
            kpi_card(
                "Críticos",
                format_integer(critical_count),
                foot="exigem ação imediata",
                alert=critical_count > 0,
            ),
            unsafe_allow_html=True,
        )

        level_order = ["baixo", "moderado", "alto", "crítico"]
        level_colors = {
            "baixo": STATUS_GOOD,
            "moderado": STATUS_WARNING,
            "alto": STATUS_SERIOUS,
            "crítico": STATUS_CRITICAL,
        }

        distribution = (
            latest_scores["risk_level"]
            .value_counts()
            .reindex(level_order, fill_value=0)
            .reset_index()
        )
        distribution.columns = ["nivel", "incidentes"]

        distribution_figure = go.Figure(
            go.Bar(
                x=distribution["nivel"].str.title(),
                y=distribution["incidentes"],
                marker={
                    "color": [level_colors[level] for level in distribution["nivel"]],
                    "cornerradius": 3,
                },
                text=[format_integer(value) for value in distribution["incidentes"]],
                textposition="outside",
                textfont={"color": INK_SECONDARY, "size": 12},
                hovertemplate="%{x}<br>%{y} incidentes<extra></extra>",
            )
        )

        distribution_figure.update_layout(**base_layout(height=290))
        distribution_figure.update_yaxes(visible=False)

        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        chart(distribution_figure)

        section("Fila priorizada")

        filter_columns = st.columns([2, 2])

        with filter_columns[0]:
            level_filter = st.multiselect(
                "Nível de risco",
                options=["baixo", "moderado", "alto", "crítico"],
                default=["alto", "crítico"],
                format_func=str.title,
            )

        with filter_columns[1]:
            incident_query = st.text_input(
                "Buscar incidente",
                placeholder="INC0000000",
            )

        queue = latest_scores

        if level_filter:
            queue = queue.loc[queue["risk_level"].isin(level_filter)]

        if incident_query.strip():
            queue = queue.loc[
                queue["incident_id"]
                .astype(str)
                .str.contains(incident_query.strip(), case=False, regex=False)
            ]

        if queue.empty:
            st.info("Nenhum incidente para os filtros selecionados.")
        else:
            ranking = queue.sort_values("risk_score", ascending=False).head(50).copy()
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
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

            st.download_button(
                "Baixar fila priorizada (CSV)",
                ranking.to_csv(index=False).encode("utf-8-sig"),
                file_name="fila_priorizada.csv",
                mime="text/csv",
            )

# --------------------------------------------------------------------------- #
# Qualidade
# --------------------------------------------------------------------------- #

with tab_quality:
    section("Qualidade dos dados")

    st.markdown(
        '<div class="ah-card-foot" style="margin:-4px 0 14px 0">'
        "retrato da última execução do pipeline · independe do recorte de datas</div>",
        unsafe_allow_html=True,
    )

    ingestion_report = load_json_report(str(ingestion_report_path))
    gold_report = load_json_report(str(gold_report_path))

    if ingestion_report is None and gold_report is None:
        st.info("Nenhum relatório de qualidade disponível para esta base.")
    else:
        STATUS_TEXT = {
            "passed": ("Aprovado", STATUS_GOOD),
            "passed_with_warnings": ("Aprovado com alertas", STATUS_WARNING),
            "failed": ("Reprovado", STATUS_CRITICAL),
        }

        quality_cards = st.columns(3)

        if ingestion_report:
            text, color = STATUS_TEXT.get(
                ingestion_report["quality_status"], (ingestion_report["quality_status"], INK_MUTED)
            )

            quality_cards[0].markdown(
                f'<div class="ah-card"><div class="ah-card-label">Ingestão · Bronze e Silver</div>'
                f'<div class="ah-card-value" style="color:{color};font-size:26px">{text}</div>'
                f'<div class="ah-card-foot">'
                f"{format_integer(ingestion_report['row_count'])} incidentes · "
                f"{ingestion_report['opened_at_min'][:10]} a "
                f"{ingestion_report['opened_at_max'][:10]}</div></div>",
                unsafe_allow_html=True,
            )

        if gold_report:
            text, color = STATUS_TEXT.get(
                gold_report["quality_status"], (gold_report["quality_status"], INK_MUTED)
            )

            quality_cards[1].markdown(
                f'<div class="ah-card"><div class="ah-card-label">Camada Gold</div>'
                f'<div class="ah-card-value" style="color:{color};font-size:26px">{text}</div>'
                f'<div class="ah-card-foot">'
                f"{format_integer(gold_report['daily_volume_rows'])} linhas na série diária · "
                f"{format_integer(gold_report['daily_breakdown_rows'])} no breakdown</div></div>",
                unsafe_allow_html=True,
            )

            failed = gold_report["checks"]["reconciliation_failed"]

            quality_cards[2].markdown(
                f'<div class="ah-card"><div class="ah-card-label">Reconciliação Silver → Gold</div>'
                f'<div class="ah-card-value" '
                f'style="color:{STATUS_CRITICAL if failed else STATUS_GOOD};font-size:26px">'
                f"{'Divergente' if failed else 'Confere'}</div>"
                f'<div class="ah-card-foot">contagens iguais nos escopos ALL, P2 e P3</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)

        if ingestion_report:
            col_blocking, col_warning = st.columns(2)

            with col_blocking:
                section("Checagens bloqueantes")

                blocking = pd.DataFrame(
                    [
                        (CHECK_LABELS.get(key, key), value)
                        for key, value in ingestion_report["blocking_checks"].items()
                    ],
                    columns=["Checagem", "Ocorrências"],
                )

                st.dataframe(blocking, width="stretch", hide_index=True)

            with col_warning:
                section("Alertas")

                warnings_frame = pd.DataFrame(
                    [
                        (CHECK_LABELS.get(key, key), value)
                        for key, value in ingestion_report["warning_checks"].items()
                    ],
                    columns=["Alerta", "Ocorrências"],
                )

                st.dataframe(warnings_frame, width="stretch", hide_index=True)

        if gold_report:
            st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
            section("Reconciliação por escopo")

            reconciliation = pd.DataFrame(gold_report["reconciliation"]).T.reset_index()
            reconciliation.columns = ["Escopo", "Silver", "Gold", "Confere"]
            reconciliation["Confere"] = reconciliation["Confere"].map({True: "Sim", False: "Não"})

            st.dataframe(reconciliation, width="stretch", hide_index=True)

st.markdown(
    f'<div class="ah-card-foot" style="margin-top:34px;border-top:1px solid {BORDER};'
    f'padding-top:14px">AlbusHub {APP_VERSION} · plataforma de operações preditivas · '
    f"© 2026 AlbusHub</div>",
    unsafe_allow_html=True,
)
