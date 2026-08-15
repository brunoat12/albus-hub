import pandas as pd
from pathlib import Path


# =========================================================
# Configurações
# =========================================================

INPUT_FILE = Path("data/silver/locaweb_incidents.parquet")
OUTPUT_DIR = Path("data/dw")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# Leitura da Silver
# =========================================================

df = pd.read_parquet(INPUT_FILE)

print(f"Incidentes lidos: {len(df):,}")


# =========================================================
# Padronizações
# =========================================================

dimension_string_columns = [
    "product",
    "category",
    "subcategory",
    "assigned_group",
    "configuration_item",
]

for col in dimension_string_columns:
    df[col] = (
        df[col]
        .astype("string")
        .fillna("Não informado")
        .str.strip()
    )

df["product"] = df["product"].replace("", "Não informado")
df["category"] = df["category"].replace("", "Não informado")
df["subcategory"] = df["subcategory"].replace("", "Não informado")
df["assigned_group"] = df["assigned_group"].replace("", "Não informado")
df["configuration_item"] = df["configuration_item"].replace(
    "", "Não informado"
)


# =========================================================
# DIM TEMPO
# =========================================================

dates = pd.date_range(
    start=df["opened_date"].min(),
    end=df["opened_date"].max(),
    freq="D",
)

dim_tempo = pd.DataFrame({"data": dates})

dim_tempo["sk_tempo"] = (
    dim_tempo["data"]
    .dt.strftime("%Y%m%d")
    .astype(int)
)

dim_tempo["ano"] = dim_tempo["data"].dt.year
dim_tempo["mes"] = dim_tempo["data"].dt.month
dim_tempo["dia"] = dim_tempo["data"].dt.day
dim_tempo["dia_semana"] = dim_tempo["data"].dt.dayofweek + 1
dim_tempo["semana_ano"] = (
    dim_tempo["data"].dt.isocalendar().week.astype(int)
)
dim_tempo["trimestre"] = dim_tempo["data"].dt.quarter
dim_tempo["fim_semana"] = (
    dim_tempo["data"].dt.dayofweek >= 5
)

dim_tempo = dim_tempo[
    [
        "sk_tempo",
        "data",
        "ano",
        "mes",
        "dia",
        "dia_semana",
        "semana_ano",
        "trimestre",
        "fim_semana",
    ]
]

# Formato compatível com ADF -> MySQL DATE
dim_tempo["data"] = dim_tempo["data"].dt.strftime("%Y-%m-%d")
# =========================================================
# DIM PRIORIDADE
# =========================================================

dim_prioridade = (
    df[
        [
            "priority_code",
            "priority_label",
        ]
    ]
    .drop_duplicates()
    .sort_values("priority_code")
    .reset_index(drop=True)
)

dim_prioridade.insert(
    0,
    "sk_prioridade",
    range(1, len(dim_prioridade) + 1),
)


# =========================================================
# DIM PRODUTO
# =========================================================

dim_produto = (
    df[["product"]]
    .drop_duplicates()
    .sort_values("product")
    .reset_index(drop=True)
)

dim_produto.insert(
    0,
    "sk_produto",
    range(1, len(dim_produto) + 1),
)

dim_produto = dim_produto.rename(
    columns={"product": "produto"}
)


# =========================================================
# DIM CATEGORIA
# =========================================================

dim_categoria = (
    df[
        [
            "category",
            "subcategory",
        ]
    ]
    .drop_duplicates()
    .sort_values(
        [
            "category",
            "subcategory",
        ]
    )
    .reset_index(drop=True)
)

dim_categoria.insert(
    0,
    "sk_categoria",
    range(1, len(dim_categoria) + 1),
)

dim_categoria = dim_categoria.rename(
    columns={
        "category": "categoria",
        "subcategory": "subcategoria",
    }
)


# =========================================================
# DIM GRUPO
# =========================================================

dim_grupo = (
    df[["assigned_group"]]
    .drop_duplicates()
    .sort_values("assigned_group")
    .reset_index(drop=True)
)

dim_grupo.insert(
    0,
    "sk_grupo",
    range(1, len(dim_grupo) + 1),
)

dim_grupo = dim_grupo.rename(
    columns={"assigned_group": "grupo"}
)


# =========================================================
# DIM ITEM CONFIGURAÇÃO
# =========================================================

dim_item = (
    df[["configuration_item"]]
    .drop_duplicates()
    .sort_values("configuration_item")
    .reset_index(drop=True)
)

dim_item.insert(
    0,
    "sk_item_configuracao",
    range(1, len(dim_item) + 1),
)

dim_item = dim_item.rename(
    columns={
        "configuration_item": "item_configuracao"
    }
)


# =========================================================
# FATO INCIDENTE
# =========================================================

fato = df.copy()

fato["sk_tempo"] = (
    fato["opened_date"]
    .dt.strftime("%Y%m%d")
    .astype(int)
)


fato = fato.merge(
    dim_prioridade,
    on=[
        "priority_code",
        "priority_label",
    ],
    how="left",
)


fato = fato.merge(
    dim_produto,
    left_on="product",
    right_on="produto",
    how="left",
)


fato = fato.merge(
    dim_categoria,
    left_on=[
        "category",
        "subcategory",
    ],
    right_on=[
        "categoria",
        "subcategoria",
    ],
    how="left",
)


fato = fato.merge(
    dim_grupo,
    left_on="assigned_group",
    right_on="grupo",
    how="left",
)


fato = fato.merge(
    dim_item,
    left_on="configuration_item",
    right_on="item_configuracao",
    how="left",
)


# =========================================================
# Medidas / indicadores
# =========================================================

fato["qtd_incidente"] = 1


fato["entered_kpi"] = (
    fato["entered_kpi_raw"]
    .map(
        {
            "SIM": 1,
            "NAO": 0,
        }
    )
)


fato["kpi_breached"] = (
    fato["kpi_breached_raw"]
    .map(
        {
            "SIM": 1,
            "NAO": 0,
            "N/A": pd.NA,
        }
    )
    .astype("Int64")
)


# =========================================================
# Seleção final da FATO
# =========================================================

fato_incidente = fato[
    [
        "incident_id",
        "sk_tempo",
        "sk_prioridade",
        "sk_produto",
        "sk_categoria",
        "sk_grupo",
        "sk_item_configuracao",
        "qtd_incidente",
        "duration_seconds",
        "duration_hours",
        "entered_kpi",
        "kpi_breached",
        "is_monitoring_opened",
        "is_no_intervention",
        "opened_hour",
    ]
].copy()


# =========================================================
# Validações
# =========================================================

print("\n=== CONTAGENS ===")

print(
    "DIM_TEMPO:",
    len(dim_tempo),
)

print(
    "DIM_PRIORIDADE:",
    len(dim_prioridade),
)

print(
    "DIM_PRODUTO:",
    len(dim_produto),
)

print(
    "DIM_CATEGORIA:",
    len(dim_categoria),
)

print(
    "DIM_GRUPO:",
    len(dim_grupo),
)

print(
    "DIM_ITEM_CONFIGURACAO:",
    len(dim_item),
)

print(
    "FATO_INCIDENTE:",
    len(fato_incidente),
)


print("\n=== FKs NULAS ===")

fk_columns = [
    "sk_tempo",
    "sk_prioridade",
    "sk_produto",
    "sk_categoria",
    "sk_grupo",
    "sk_item_configuracao",
]

print(
    fato_incidente[
        fk_columns
    ]
    .isna()
    .sum()
)


print("\n=== DUPLICIDADE INCIDENT_ID ===")

print(
    fato_incidente[
        "incident_id"
    ]
    .duplicated()
    .sum()
)


# =========================================================
# Exportação
# =========================================================

dim_tempo.to_parquet(
    OUTPUT_DIR / "dim_tempo.parquet",
    index=False,
)

dim_prioridade.to_parquet(
    OUTPUT_DIR / "dim_prioridade.parquet",
    index=False,
)

dim_produto.to_parquet(
    OUTPUT_DIR / "dim_produto.parquet",
    index=False,
)

dim_categoria.to_parquet(
    OUTPUT_DIR / "dim_categoria.parquet",
    index=False,
)

dim_grupo.to_parquet(
    OUTPUT_DIR / "dim_grupo.parquet",
    index=False,
)

dim_item.to_parquet(
    OUTPUT_DIR / "dim_item_configuracao.parquet",
    index=False,
)

fato_incidente.to_parquet(
    OUTPUT_DIR / "fato_incidente.parquet",
    index=False,
)


print(
    "\nModelo dimensional gerado em:",
    OUTPUT_DIR,
)
