from __future__ import annotations

import json
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

configure_observability()

st.set_page_config(
    page_title="Albus-Hub · AIOps",
    page_icon="🔴",
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
SERIES_3 = "#1eae72"  # verde — positivo
SERIES_4 = "#f2b705"  # âmbar — atenção
SERIES_1_SOFT = "#7fb3ee"  # azul claro — série de apoio

SEVERITY = {
    1: "#f2434f",
    2: "#f5803e",
    3: "#f2b705",
    4: "#4a9fe8",
    5: "#1eae72",
}

STATUS_GOOD = "#1eae72"
STATUS_WARNING = "#f2b705"
STATUS_SERIOUS = "#f5803e"
STATUS_CRITICAL = "#f2434f"

# Volume é série neutra: escala azul. O vermelho fica reservado ao que exige
# atenção — se tudo é vermelho, nada é urgente.
SEQUENTIAL_BLUE = [
    [0.00, "#1d1c23"],
    [0.25, "#173a5e"],
    [0.50, "#215d9c"],
    [0.75, "#3987e5"],
    [1.00, "#7fb3ee"],
]

REGIME_CHANGE_DATE = pd.Timestamp("2025-09-01")
REGIME_TRANSITION_DATE = pd.Timestamp("2025-01-01")

# Os três patamares de volume da base. Misturar dois deles em uma média ou em
# uma comparação produz números que não descrevem operação nenhuma.
REGIMES = (
    (pd.Timestamp.min, REGIME_TRANSITION_DATE, "Base histórica (até 2024)"),
    (REGIME_TRANSITION_DATE, REGIME_CHANGE_DATE, "Transição (jan–ago/2025)"),
    (REGIME_CHANGE_DATE, pd.Timestamp.max, "Regime atual (set/2025+)"),
)


def regime_of(moment: pd.Timestamp) -> str:
    """Devolve o nome do patamar de volume a que uma data pertence."""
    for start, end, label in REGIMES:
        if start <= moment < end:
            return label
    return REGIMES[-1][2]


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

DIMENSION_LABELS = {
    "assigned_group": "Grupo designado",
    "product": "Produto",
    "category": "Categoria",
    "configuration_item": "Item de configuração",
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
    "kpi_breached_rule_mismatch": "Violação de SLA diverge da regra",
}

MONTH_LABELS = {
    1: "jan",
    2: "fev",
    3: "mar",
    4: "abr",
    5: "mai",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "set",
    10: "out",
    11: "nov",
    12: "dez",
}

WEEKDAY_LABELS = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
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


def format_percentage(value: float, decimals: int = 1) -> str:
    """Formata percentual no padrão visual pt-BR."""
    return f"{value:.{decimals}f}%".replace(".", ",")


def format_hours(value: float) -> str:
    """Formata uma quantidade de horas no padrão visual pt-BR."""
    if value < 1:
        return f"{value * 60:.0f} min".replace(".", ",")

    return f"{value:.1f} h".replace(".", ",")


# --------------------------------------------------------------------------- #
# Carregamento
# --------------------------------------------------------------------------- #


@st.cache_data(show_spinner=False)
def load_parquet(path: str) -> pd.DataFrame:
    """Carrega um arquivo Parquet utilizado pelo dashboard."""
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def load_json_report(path: str) -> dict | None:
    """Carrega um relatório de qualidade gerado pelo pipeline."""
    report_path = Path(path)

    if not report_path.exists():
        return None

    with report_path.open(encoding="utf-8") as file:
        return json.load(file)


@st.cache_data(show_spinner=False)
def load_incident_profile(path: str) -> pd.DataFrame | None:
    """
    Carrega um recorte enxuto da camada Silver.

    A Gold responde pelo volume diário. As análises de duração, hora de
    abertura e aderência a SLA precisam do grão de incidente, por isso são
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
    '<span class="ah-brand-mark">locaweb</span>'
    '<span><span class="ah-brand-name">AlbusHub</span><br>'
    '<span class="ah-brand-sub">AIOps · Sprint 3</span></span>'
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
breakdown = load_parquet(str(breakdown_path))

daily_volume["reference_date"] = pd.to_datetime(daily_volume["reference_date"])
breakdown["reference_date"] = pd.to_datetime(breakdown["reference_date"])

incidents = load_incident_profile(str(silver_path))

min_date = daily_volume["reference_date"].min()
max_date = daily_volume["reference_date"].max()

# --------------------------------------------------------------------------- #
# Filtros
# --------------------------------------------------------------------------- #

st.sidebar.markdown('<div class="ah-kicker">Recorte</div>', unsafe_allow_html=True)

PERIOD_PRESETS = {
    "Últimos 30 dias": 30,
    "Últimos 90 dias": 90,
    "Regime atual (desde set/2025)": "regime",
    "Últimos 12 meses": 365,
    "Todo o período": None,
    "Personalizado": "custom",
}

preset = st.sidebar.radio(
    "Período",
    options=list(PERIOD_PRESETS),
    index=2,
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

priority_scope = st.sidebar.selectbox(
    "Escopo de prioridade",
    options=["ALL", "P2", "P3"],
    format_func=lambda value: PRIORITY_SCOPE_LABELS[value],
    label_visibility="collapsed",
)

st.sidebar.markdown(
    f'<div class="ah-card-foot" style="margin-top:26px;border-top:1px solid {BORDER};'
    f'padding-top:14px">base {min_date:%d/%m/%Y} — {max_date:%d/%m/%Y}<br>'
    f"ambiente {settings.app_env} · cloud {settings.cloud_provider}</div>",
    unsafe_allow_html=True,
)

period_days = (end_date - start_date).days + 1
previous_end = start_date - pd.Timedelta(days=1)
previous_start = previous_end - pd.Timedelta(days=period_days - 1)

daily_period = filter_period(daily_volume, "reference_date", start_date, end_date)
daily_previous = filter_period(daily_volume, "reference_date", previous_start, previous_end)
breakdown_period = filter_period(breakdown, "reference_date", start_date, end_date)

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
    '<div class="ah-title">Albus-Hub</div>'
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

tab_overview, tab_operations, tab_forecast, tab_risk, tab_quality = st.tabs(
    ["Visão Geral", "Operação", "Previsões", "Risco", "Qualidade"]
)

# --------------------------------------------------------------------------- #
# Visão Geral
# --------------------------------------------------------------------------- #

with tab_overview:
    total_incidents = scope_sum(daily_period, "ALL", "incident_count")
    p2_incidents = scope_sum(daily_period, "P2", "incident_count")
    p3_incidents = scope_sum(daily_period, "P3", "incident_count")
    entered_kpi = scope_sum(daily_period, "ALL", "entered_kpi_count")
    kpi_breaches = scope_sum(daily_period, "ALL", "kpi_breach_count")
    monitoring = scope_sum(daily_period, "ALL", "monitoring_incident_count")

    no_intervention = (
        scope_sum(daily_period, "ALL", "no_intervention_count")
        if "no_intervention_count" in daily_period.columns
        else None
    )

    breach_rate = 100 * kpi_breaches / entered_kpi if entered_kpi else 0.0
    monitoring_rate = 100 * monitoring / total_incidents if total_incidents else 0.0
    no_intervention_rate = (
        100 * no_intervention / total_incidents
        if no_intervention is not None and total_incidents
        else None
    )
    daily_average = total_incidents / period_days if period_days else 0.0

    previous_total = scope_sum(daily_previous, "ALL", "incident_count") if has_previous else 0
    previous_p2 = scope_sum(daily_previous, "P2", "incident_count") if has_previous else 0
    previous_entered = scope_sum(daily_previous, "ALL", "entered_kpi_count") if has_previous else 0
    previous_breaches = scope_sum(daily_previous, "ALL", "kpi_breach_count") if has_previous else 0
    previous_rate = 100 * previous_breaches / previous_entered if previous_entered else 0.0

    cards = st.columns(5)

    cards[0].markdown(
        kpi_card(
            "Incidentes",
            format_integer(total_incidents),
            foot=trend_foot(total_incidents, previous_total, comparable=comparable_previous),
            accent=True,
        ),
        unsafe_allow_html=True,
    )
    cards[1].markdown(
        kpi_card(
            "Média diária",
            format_integer(round(daily_average)),
            foot="incidentes por dia",
        ),
        unsafe_allow_html=True,
    )
    cards[2].markdown(
        kpi_card(
            "P2 — Alta",
            format_integer(p2_incidents),
            foot=trend_foot(p2_incidents, previous_p2, comparable=comparable_previous),
        ),
        unsafe_allow_html=True,
    )
    cards[3].markdown(
        kpi_card(
            "KPI violado",
            format_integer(kpi_breaches),
            foot=f"de {format_integer(entered_kpi)} no KPI",
            alert=kpi_breaches > 0,
        ),
        unsafe_allow_html=True,
    )

    if not comparable_previous:
        rate_delta = "período anterior em outro patamar"
    elif previous_entered:
        rate_delta = (
            f'<span class="{"ah-up" if breach_rate >= previous_rate else "ah-down"}">'
            f"{breach_rate - previous_rate:+.2f} p.p.</span> vs anterior".replace(".", ",")
        )
    else:
        rate_delta = "sem base de comparação"

    cards[4].markdown(
        kpi_card(
            "Taxa de violação",
            format_percentage(breach_rate, 2).replace("%", ""),
            unit="%",
            foot=rate_delta,
            alert=breach_rate > 1,
        ),
        unsafe_allow_html=True,
    )

    if len(current_regimes) > 1:
        st.markdown(
            '<div class="ah-note" style="margin-top:18px">'
            f"<strong>O recorte atravessa mais de um regime de volume "
            f"({' · '.join(current_regimes)}).</strong> "
            "A base tem três patamares: até dez/2024 são poucas dezenas de incidentes por mês, "
            "de jan/2025 a ago/2025 são cerca de 3,5 mil por mês, e a partir de 01/09/2025 o "
            "volume salta para cerca de 22 mil por mês — provável ampliação da cobertura de "
            "monitoramento, não aumento real de falhas. Médias que misturam esses patamares não "
            "descrevem a operação atual."
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)

    section("Evolução diária")

    # A média móvel é calculada sobre a série inteira e só depois recortada.
    # Calculá-la sobre a série já filtrada criaria uma rampa artificial nos
    # primeiros seis dias — justamente onde o regime atual começa.
    full_series = (
        daily_volume.loc[
            daily_volume["priority_scope"].eq(priority_scope),
            ["reference_date", "incident_count"],
        ]
        .sort_values("reference_date")
        .reset_index(drop=True)
    )
    full_series["moving_average"] = full_series["incident_count"].rolling(7, min_periods=7).mean()

    trend = filter_period(full_series, "reference_date", start_date, end_date).reset_index(
        drop=True
    )

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=trend["reference_date"],
            y=trend["incident_count"],
            name="Incidentes por dia",
            mode="lines",
            line={"color": SERIES_1, "width": 1},
            opacity=0.35,
            hovertemplate="%{x|%d/%m/%Y}<br>%{y} incidentes<extra></extra>",
        )
    )

    figure.add_trace(
        go.Scatter(
            x=trend["reference_date"],
            y=trend["moving_average"],
            name="Média móvel de 7 dias",
            mode="lines",
            line={"color": SERIES_1_SOFT, "width": 2.5},
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.0f} (média 7d)<extra></extra>",
        )
    )

    if start_date <= REGIME_CHANGE_DATE <= end_date:
        figure.add_vline(x=REGIME_CHANGE_DATE, line={"color": INK_MUTED, "width": 1, "dash": "dot"})
        figure.add_annotation(
            x=REGIME_CHANGE_DATE,
            yref="paper",
            y=1.0,
            text="mudança de regime",
            showarrow=False,
            xanchor="left",
            font={"color": INK_MUTED, "size": 10},
        )

    layout = base_layout(height=340, showlegend=True)
    layout["hovermode"] = "x unified"
    figure.update_layout(**layout)

    chart(figure)

    col_left, col_right = st.columns(2)

    with col_left:
        section("Composição por prioridade")

        other_incidents = max(total_incidents - p2_incidents - p3_incidents, 0)

        composition = pd.DataFrame(
            {
                "escopo": ["P2 — Alta", "P3 — Média", "Demais"],
                "incidentes": [p2_incidents, p3_incidents, other_incidents],
                "cor": [SEVERITY[2], SEVERITY[3], SEVERITY[4]],
            }
        )

        bars = go.Figure(
            go.Bar(
                x=composition["escopo"],
                y=composition["incidentes"],
                marker={"color": composition["cor"], "cornerradius": 3},
                text=[format_integer(value) for value in composition["incidentes"]],
                textposition="outside",
                textfont={"color": INK_SECONDARY, "size": 12},
                hovertemplate="%{x}<br>%{y} incidentes<extra></extra>",
            )
        )

        bars.update_layout(**base_layout(height=290))
        bars.update_yaxes(visible=False)

        chart(bars)

    with col_right:
        section("Incidentes por dia da semana")

        seasonal = daily_period.loc[daily_period["priority_scope"].eq(priority_scope)].copy()
        seasonal["dia"] = seasonal["reference_date"].dt.dayofweek

        weekday_profile = (
            seasonal.groupby("dia", as_index=False)["incident_count"].sum().sort_values("dia")
        )

        weekday_figure = go.Figure(
            go.Bar(
                x=[WEEKDAY_LABELS[day] for day in weekday_profile["dia"]],
                y=weekday_profile["incident_count"],
                marker={"color": SERIES_1, "cornerradius": 3},
                text=[format_integer(value) for value in weekday_profile["incident_count"]],
                textposition="outside",
                textfont={"color": INK_SECONDARY, "size": 12},
                hovertemplate="%{x}<br>%{y} incidentes<extra></extra>",
            )
        )

        weekday_figure.update_layout(**base_layout(height=290))
        weekday_figure.update_yaxes(visible=False)

        chart(weekday_figure)

    st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)

    section("Sazonalidade por mês")

    # Os dois visuais da Página 1 são obrigatórios: o perfil por dia da semana
    # acima e a sazonalidade aqui. Antes eles se excluíam conforme o recorte.
    if seasonal.empty:
        st.info("Não há dados no período selecionado.")
    elif seasonal["reference_date"].dt.year.nunique() > 1:
        seasonal["ano"] = seasonal["reference_date"].dt.year
        seasonal["mes"] = seasonal["reference_date"].dt.month

        pivot = seasonal.pivot_table(
            index="ano", columns="mes", values="incident_count", aggfunc="sum", fill_value=0
        )

        heatmap = go.Figure(
            go.Heatmap(
                z=pivot.values,
                x=[f"{month:02d}" for month in pivot.columns],
                y=[str(year) for year in pivot.index],
                colorscale=SEQUENTIAL_BLUE,
                hovertemplate="%{y}/%{x}<br>%{z} incidentes<extra></extra>",
                colorbar={
                    "outlinewidth": 0,
                    "tickfont": {"color": INK_MUTED, "size": 10},
                    "thickness": 10,
                },
            )
        )

        heatmap.update_layout(**base_layout(height=290))
        heatmap.update_xaxes(showgrid=False, type="category")
        heatmap.update_yaxes(showgrid=False, type="category")

        chart(heatmap)
    else:
        monthly = (
            seasonal.assign(mes=seasonal["reference_date"].dt.month)
            .groupby("mes", as_index=False)["incident_count"]
            .sum()
            .sort_values("mes")
        )

        monthly_figure = go.Figure(
            go.Bar(
                x=[MONTH_LABELS[month] for month in monthly["mes"]],
                y=monthly["incident_count"],
                marker={"color": SERIES_1, "cornerradius": 3},
                text=[format_integer(value) for value in monthly["incident_count"]],
                textposition="outside",
                textfont={"color": INK_SECONDARY, "size": 12},
                hovertemplate="%{x}<br>%{y} incidentes<extra></extra>",
            )
        )

        monthly_figure.update_layout(**base_layout(height=290))
        monthly_figure.update_yaxes(visible=False)

        chart(monthly_figure)

    st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)

    with st.expander("Série consolidada"):
        st.dataframe(
            daily_period.sort_values(["reference_date", "priority_scope"]),
            width="stretch",
            hide_index=True,
        )

# --------------------------------------------------------------------------- #
# Operação
# --------------------------------------------------------------------------- #

with tab_operations:
    section("Perfil operacional do recorte")

    # Ambas vêm da camada Gold, então continuam na tela mesmo sem a Silver.
    gold_cards = st.columns(4)

    gold_cards[0].markdown(
        kpi_card("Incidentes", format_integer(total_incidents), accent=True),
        unsafe_allow_html=True,
    )
    gold_cards[1].markdown(
        kpi_card("Média diária", format_integer(round(daily_average)), foot="incidentes por dia"),
        unsafe_allow_html=True,
    )
    gold_cards[2].markdown(
        kpi_card(
            "Aberto por monitoramento",
            format_percentage(monitoring_rate, 1).replace("%", ""),
            unit="%",
            foot="restante é abertura manual",
        ),
        unsafe_allow_html=True,
    )
    gold_cards[3].markdown(
        kpi_card(
            "Sem intervenção",
            format_percentage(no_intervention_rate, 1).replace("%", "")
            if no_intervention_rate is not None
            else "—",
            unit="%" if no_intervention_rate is not None else "",
            foot="encerrados sem ação humana"
            if no_intervention_rate is not None
            else "coluna ausente na camada Gold",
        ),
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)

    section("Concentração por dimensão")

    col_dimension, col_top = st.columns([2, 1])

    selected_dimension = col_dimension.selectbox(
        "Dimensão",
        options=list(DIMENSION_LABELS),
        format_func=lambda value: DIMENSION_LABELS[value],
    )

    top_n = col_top.slider("Itens exibidos", min_value=5, max_value=30, value=12, step=1)

    operational = breakdown_period.loc[
        breakdown_period["dimension_name"].eq(selected_dimension)
        & breakdown_period["priority_scope"].eq(priority_scope)
    ].copy()

    operational["dimension_value"] = (
        operational["dimension_value"].astype("string").replace("__MISSING__", "Sem informação")
    )

    ranking = (
        operational.groupby("dimension_value", as_index=False, dropna=False)
        .agg(
            incident_count=("incident_count", "sum"),
            entered_kpi_count=("entered_kpi_count", "sum"),
            kpi_breach_count=("kpi_breach_count", "sum"),
        )
        .sort_values("incident_count", ascending=False)
        .reset_index(drop=True)
    )

    if ranking.empty:
        st.info("Não há dados para os filtros selecionados.")
    else:
        grand_total = ranking["incident_count"].sum()

        ranking["share"] = 100 * ranking["incident_count"] / grand_total
        ranking["cumulative_share"] = ranking["share"].cumsum()
        ranking["breach_rate"] = (
            100 * ranking["kpi_breach_count"] / ranking["entered_kpi_count"]
        ).fillna(0.0)

        pareto = ranking.head(top_n)

        figure = go.Figure()

        figure.add_trace(
            go.Bar(
                x=pareto["dimension_value"],
                y=pareto["share"],
                name="Participação",
                marker={"color": SERIES_1, "cornerradius": 3},
                hovertemplate="%{x}<br>%{y:.1f}% do total<extra></extra>",
            )
        )

        figure.add_trace(
            go.Scatter(
                x=pareto["dimension_value"],
                y=pareto["cumulative_share"],
                name="Acumulado",
                mode="lines+markers",
                line={"color": SERIES_2, "width": 2},
                marker={"size": 7},
                hovertemplate="%{x}<br>%{y:.1f}% acumulado<extra></extra>",
            )
        )

        layout = base_layout(height=360, showlegend=True)
        figure.update_layout(**layout)
        figure.update_yaxes(ticksuffix="%")

        chart(figure)

        concentration = min(
            ranking.loc[ranking["cumulative_share"] <= 80].shape[0] + 1, len(ranking)
        )

        label = DIMENSION_LABELS[selected_dimension].lower()
        verb = "concentra" if concentration == 1 else "concentram"
        noun = label if concentration == 1 else f"valores de {label}"

        st.markdown(
            f'<div class="ah-card-foot">{format_integer(concentration)} {noun} {verb} 80% dos '
            f"incidentes, de {format_integer(len(ranking))} no total · participação e acumulado "
            f"na mesma escala percentual, sem eixo secundário</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)

        section("Taxa de violação de KPI")

        breach_ranking = (
            ranking.loc[ranking["entered_kpi_count"] >= 30]
            .sort_values("breach_rate", ascending=False)
            .head(top_n)
        )

        if breach_ranking.empty:
            st.info("Nenhum valor com volume suficiente (mínimo de 30 incidentes no KPI).")
        else:
            breach_figure = go.Figure(
                go.Bar(
                    x=breach_ranking["breach_rate"],
                    y=breach_ranking["dimension_value"],
                    orientation="h",
                    marker={"color": BRAND, "cornerradius": 3},
                    text=[format_percentage(value) for value in breach_ranking["breach_rate"]],
                    textposition="outside",
                    textfont={"color": INK_SECONDARY, "size": 11},
                    hovertemplate="%{y}<br>%{x:.2f}% de violação<extra></extra>",
                )
            )

            breach_figure.update_layout(**base_layout(height=360))
            breach_figure.update_xaxes(ticksuffix="%")
            breach_figure.update_yaxes(autorange="reversed")

            chart(breach_figure)

            st.markdown(
                '<div class="ah-card-foot">considera apenas valores com pelo menos 30 '
                "incidentes no KPI</div>",
                unsafe_allow_html=True,
            )

        with st.expander("Tabela completa"):
            table = ranking.copy()
            table["share"] = table["share"].map(format_percentage)
            table["cumulative_share"] = table["cumulative_share"].map(format_percentage)
            table["breach_rate"] = table["breach_rate"].map(lambda v: format_percentage(v, 2))

            st.dataframe(
                table.rename(
                    columns={
                        "dimension_value": DIMENSION_LABELS[selected_dimension],
                        "incident_count": "Incidentes",
                        "entered_kpi_count": "Entraram no KPI",
                        "kpi_breach_count": "KPI violado",
                        "share": "Participação",
                        "cumulative_share": "Acumulado",
                        "breach_rate": "Taxa de violação",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

    st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)

    section("Perfil de abertura e atendimento")

    if incidents is None:
        st.info(
            "As análises de hora de abertura e duração dependem da camada Silver. "
            "Execute `uv run python scripts/ingest_locaweb.py` para gerá-la."
        )
    else:
        scope_code = {"ALL": None, "P2": 2, "P3": 3}[priority_scope]

        profile = filter_period(incidents, "opened_date", start_date, end_date)

        if scope_code is not None:
            profile = profile.loc[profile["priority_code"].eq(scope_code)]

        if profile.empty:
            st.info("Não há incidentes no período e escopo selecionados.")
        else:
            median_duration = float(profile["duration_hours"].median())
            p90_duration = float(profile["duration_hours"].quantile(0.90))

            in_kpi = profile.loc[profile["entered_kpi_source"].fillna(False).astype(bool)]

            # kpi_breached_source é booleano anulável no contrato. Comparar com
            # False faria o nulo contar como violação em dtype object e ser
            # descartado em BooleanDtype — o número mudaria conforme o Parquet.
            breached = (
                in_kpi["kpi_breached_source"].map({True: 1.0, False: 0.0}).astype("float64")
            )
            breached = breached.dropna()

            sla_compliance = 100 * (1 - float(breached.mean())) if not breached.empty else 0.0
            sla_unknown = int(len(in_kpi) - len(breached))

            monitoring_share = 100 * float(profile["opened_by"].eq("Monitoramento").mean())

            profile_cards = st.columns(4)

            profile_cards[0].markdown(
                kpi_card("Duração mediana", format_hours(median_duration)),
                unsafe_allow_html=True,
            )
            profile_cards[1].markdown(
                kpi_card("Duração P90", format_hours(p90_duration), foot="90% resolvidos até aqui"),
                unsafe_allow_html=True,
            )
            profile_cards[2].markdown(
                kpi_card(
                    "Aderência a SLA",
                    format_percentage(sla_compliance, 2).replace("%", ""),
                    unit="%",
                    foot=(
                        "entre os que entraram no KPI"
                        if not sla_unknown
                        else f"entre os que entraram no KPI · {format_integer(sla_unknown)} sem marcação"
                    ),
                ),
                unsafe_allow_html=True,
            )
            profile_cards[3].markdown(
                kpi_card(
                    "Aberto por monitoramento",
                    format_percentage(monitoring_share, 1).replace("%", ""),
                    unit="%",
                    foot="restante é abertura manual",
                ),
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

            grid = (
                profile.groupby(["opened_day_of_week", "opened_hour"], dropna=True)
                .size()
                .reset_index(name="incidentes")
            )

            pivot_hours = grid.pivot(
                index="opened_day_of_week", columns="opened_hour", values="incidentes"
            ).reindex(index=range(7), columns=range(24), fill_value=0)

            hour_heatmap = go.Figure(
                go.Heatmap(
                    z=pivot_hours.values,
                    x=[f"{hour:02d}h" for hour in pivot_hours.columns],
                    y=[WEEKDAY_LABELS[day] for day in pivot_hours.index],
                    colorscale=SEQUENTIAL_BLUE,
                    hovertemplate="%{y}, %{x}<br>%{z} incidentes<extra></extra>",
                    colorbar={
                        "outlinewidth": 0,
                        "tickfont": {"color": INK_MUTED, "size": 10},
                        "thickness": 10,
                    },
                )
            )

            hour_heatmap.update_layout(**base_layout(height=320))
            hour_heatmap.update_xaxes(showgrid=False, type="category")
            hour_heatmap.update_yaxes(showgrid=False, type="category")

            chart(hour_heatmap)

            st.markdown(
                '<div class="ah-card-foot">abertura por dia da semana e hora</div>',
                unsafe_allow_html=True,
            )

# --------------------------------------------------------------------------- #
# Previsões
# --------------------------------------------------------------------------- #

with tab_forecast:
    section("Previsão de volume")

    predictions_path = settings.absolute_path(settings.locaweb_volume_predictions_file)

    try:
        predictions = load_volume_predictions(predictions_path)
    except VolumePredictionContractError as exc:
        st.error(f"O artefato de previsão não respeita o contrato: {exc}")
        predictions = None

    if predictions is None:
        forecast_cards = st.columns(3)

        forecast_cards[0].markdown(
            kpi_card("Previsão D+1", "—", foot="aguardando modelo", accent=True),
            unsafe_allow_html=True,
        )
        forecast_cards[1].markdown(
            kpi_card("Previsão D+7", "—", foot="aguardando modelo"), unsafe_allow_html=True
        )
        forecast_cards[2].markdown(
            kpi_card("Contrato", "OK", foot="interface pronta e validada"), unsafe_allow_html=True
        )

        st.markdown(
            '<div class="ah-note" style="margin-top:18px">'
            "A interface de previsão está pronta e validada pelo contrato de dados, aguardando o "
            "artefato da frente de modelagem em <strong>data/gold/volume_predictions.parquet</strong> "
            "com as colunas reference_date, generated_at, horizon, priority_scope, "
            "predicted_incident_count e model_version.</div>",
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
                    return "aguardando modelo"

                return f"para {linhas.iloc[-1]['reference_date']:%d/%m/%Y}"

            forecast_cards = st.columns(4)

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

            forecast_cards[3].markdown(
                kpi_card(
                    "Versão do modelo",
                    str(latest.iloc[-1]["model_version"]),
                    foot=f"publicado em {latest.iloc[-1]['generated_at']:%d/%m/%Y}",
                ),
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

            history = (
                daily_volume.loc[daily_volume["priority_scope"].eq(priority_scope)]
                .sort_values("reference_date")
                .tail(120)
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
                '<div class="ah-card-foot">a faixa vermelha é o intervalo conformal do modelo · '
                "os pontos cheios à direita são a previsão ainda sem valor realizado</div>",
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

    risk_score_path = settings.absolute_path(settings.locaweb_risk_scores_file)

    try:
        risk_scores = load_risk_scores(risk_score_path)
    except RiskScoreContractError as exc:
        st.error(f"O artefato de risco não respeita o contrato: {exc}")
        risk_scores = None

    if risk_scores is None:
        risk_cards = st.columns(3)

        risk_cards[0].markdown(
            kpi_card("Score médio", "—", foot="aguardando modelo", accent=True),
            unsafe_allow_html=True,
        )
        risk_cards[1].markdown(
            kpi_card("Alto ou crítico", "—", foot="aguardando modelo"), unsafe_allow_html=True
        )
        risk_cards[2].markdown(
            kpi_card("Contrato", "OK", foot="interface pronta e validada"), unsafe_allow_html=True
        )

        st.markdown(
            '<div class="ah-note" style="margin-top:18px">'
            "O score de risco de 0 a 100 e os níveis baixo, moderado, alto e crítico já estão "
            "contratados. Assim que a frente de modelagem publicar "
            "<strong>data/gold/risk_scores.parquet</strong>, esta aba passa a exibir a "
            "distribuição e a fila priorizada.</div>",
            unsafe_allow_html=True,
        )
    else:
        latest_scores = risk_scores.sort_values("scored_at").drop_duplicates(
            subset=["incident_id"], keep="last"
        )

        # O contrato tabela os níveis capitalizados e o exemplo de evento usa
        # inglês. Sem normalizar, uma variante de caixa zera os cartões em
        # silêncio, sem erro nenhum na tela.
        latest_scores = latest_scores.assign(
            risk_level=latest_scores["risk_level"].map(normalize_risk_level)
        )

        average_score = latest_scores["risk_score"].mean()
        critical_count = int(latest_scores["risk_level"].eq("crítico").sum())
        high_or_critical = int(latest_scores["risk_level"].isin(["alto", "crítico"]).sum())

        risk_cards = st.columns(3)

        risk_cards[0].markdown(
            kpi_card("Score médio", f"{average_score:.1f}".replace(".", ","), accent=True),
            unsafe_allow_html=True,
        )
        risk_cards[1].markdown(
            kpi_card("Alto ou crítico", format_integer(high_or_critical)), unsafe_allow_html=True
        )
        risk_cards[2].markdown(
            kpi_card("Críticos", format_integer(critical_count), alert=critical_count > 0),
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

        ranking = latest_scores.sort_values("risk_score", ascending=False).head(20).copy()
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

# --------------------------------------------------------------------------- #
# Qualidade
# --------------------------------------------------------------------------- #

with tab_quality:
    section("Qualidade dos dados")

    ingestion_report = load_json_report(str(ingestion_report_path))
    gold_report = load_json_report(str(gold_report_path))

    if ingestion_report is None and gold_report is None:
        st.info("Nenhum relatório de qualidade encontrado. Execute o pipeline de dados.")
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

            mismatch = ingestion_report["warning_checks"].get("kpi_breached_rule_mismatch", 0)

            if mismatch:
                st.markdown(
                    f'<div class="ah-note" style="margin-top:14px">'
                    f"O pipeline recalculou as regras de KPI e encontrou "
                    f"<strong>{format_integer(mismatch)}</strong> incidentes em que a marcação de "
                    f"violação da fonte diverge da regra de SLA por prioridade. Vale confirmar a "
                    f"regra com a Locaweb antes de tratar o campo original como verdade.</div>",
                    unsafe_allow_html=True,
                )

        if gold_report:
            st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
            section("Reconciliação por escopo")

            reconciliation = pd.DataFrame(gold_report["reconciliation"]).T.reset_index()
            reconciliation.columns = ["Escopo", "Silver", "Gold", "Confere"]
            reconciliation["Confere"] = reconciliation["Confere"].map({True: "Sim", False: "Não"})

            st.dataframe(reconciliation, width="stretch", hide_index=True)

st.markdown(
    f'<div class="ah-card-foot" style="margin-top:34px;border-top:1px solid {BORDER};'
    f'padding-top:14px">Albus-Hub · FIAP / Locaweb Challenge 2026 · '
    f"dados processados pelo pipeline Bronze → Silver → Gold</div>",
    unsafe_allow_html=True,
)
