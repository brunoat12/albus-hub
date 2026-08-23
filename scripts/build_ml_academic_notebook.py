from __future__ import annotations

import re
from pathlib import Path

import nbformat as nbf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_NOTEBOOK = PROJECT_ROOT / "ml_volume" / "notebook_volume.ipynb"
PIPELINE_PATH = PROJECT_ROOT / "ml_volume" / "pipeline_prioridades.py"
OUTPUT_NOTEBOOK = PROJECT_ROOT / "notebooks" / "EC_Sprint_3_Albus_Hub_ML.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


def source_text(cell) -> str:
    return str(cell.get("source", ""))


def find_cell_index(cells, needle: str, *, cell_type: str | None = None) -> int:
    for idx, cell in enumerate(cells):
        if cell_type and cell.cell_type != cell_type:
            continue
        if needle in source_text(cell):
            return idx
    raise RuntimeError(f"Célula não encontrada para o trecho: {needle!r}")


def build_embedded_pipeline(original_source: str, notebook_cells) -> str:
    """
    Embute o pipeline v3.2 no notebook acadêmico sem alterar a lógica de modelagem.

    A única adaptação executável é de caminho:
    - no .py, HERE depende de __file__;
    - no notebook, usamos ML, já localizado na primeira célula.
    """
    source = original_source

    path_block_pattern = re.compile(
        r'HERE\s*=\s*os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\s*\n'
        r'SRC\s*=\s*os\.path\.join\(HERE,\s*"\.\.",\s*"Dados",\s*"LW-DATASET\.xlsx"\)\s*\n'
        r'CACHE\s*=\s*os\.path\.join\(HERE,\s*"data",\s*"incidents\.parquet"\)\s*\n'
        r'OUT\s*=\s*os\.path\.join\(HERE,\s*"outputs"\);\s*PLOTS\s*=\s*os\.path\.join\(HERE,\s*"plots"\)',
        flags=re.MULTILINE,
    )

    replacement = (
        'HERE = ML\n'
        'SRC = os.path.join(os.path.dirname(ML), "Dados", "LW-DATASET.xlsx")\n'
        'CACHE = os.path.join(ML, "data", "incidents.parquet")\n'
        'OUT = os.path.join(ML, "outputs"); PLOTS = os.path.join(ML, "plots")'
    )

    source, count = path_block_pattern.subn(replacement, source, count=1)
    if count != 1:
        raise RuntimeError(
            "Não consegui adaptar o bloco de caminhos do pipeline. "
            "O pipeline_prioridades.py pode ter mudado; revise antes de gerar o notebook."
        )

    all_notebook_source = "\n".join(source_text(c) for c in notebook_cells)
    required_academic_exports = {"FEATS_LEVEL", "SELEND"}
    exports = sorted(
        set(re.findall(r"\bpl\.([A-Za-z_]\w*)", all_notebook_source))
        | required_academic_exports
    )

    proxy = (
        "\nfrom types import SimpleNamespace\n\n"
        f"_PL_EXPORTS = {exports!r}\n"
        "_pl_missing = [name for name in _PL_EXPORTS if name not in globals()]\n"
        "if _pl_missing:\n"
        "    raise RuntimeError(f\"Objetos esperados do pipeline não foram definidos: {_pl_missing}\")\n\n"
        "pl = SimpleNamespace(**{name: globals()[name] for name in _PL_EXPORTS})\n\n"
        "# O pipeline usa backend Agg para salvar o PNG. Reativamos o backend inline do notebook.\n"
        "try:\n"
        "    matplotlib.use(\"module://matplotlib_inline.backend_inline\")\n"
        "except Exception:\n"
        "    pass\n"
    )

    return source.rstrip() + "\n" + proxy


def main() -> None:
    if not SOURCE_NOTEBOOK.exists():
        raise FileNotFoundError(f"Notebook de origem não encontrado: {SOURCE_NOTEBOOK}")
    if not PIPELINE_PATH.exists():
        raise FileNotFoundError(f"Pipeline não encontrado: {PIPELINE_PATH}")

    notebook = nbf.read(SOURCE_NOTEBOOK, as_version=4)
    cells = list(notebook.cells)

    # 1) Cabeçalho acadêmico autocontido.
    first = source_text(cells[0])
    first = first.replace(
        "**Princípio de construção:** o notebook **não reimplementa** os modelos. Ele importa\n"
        "`pipeline_prioridades.py` — o mesmo arquivo que roda em produção — e usa as funções de lá.\n"
        "Assim não existe uma segunda versão da lógica que possa divergir em silêncio.",
        "**Versão acadêmica autocontida:** para atender ao formato de arquivo único da disciplina, "
        "as funções do `pipeline_prioridades.py` foram incorporadas ao próprio notebook. "
        "A lógica de modelagem é a mesma da versão v3.2; a adaptação serve apenas para que o `.ipynb` "
        "possa ser lido e executado sem depender de um módulo Python externo.",
    )
    cells[0].source = first

    # 2) AED / qualidade.
    idx_2025 = find_cell_index(
        cells,
        'd25 = df[df["Aberto"].dt.year == 2025].copy()',
        cell_type="code",
    )

    eda_quality_cells = [
        md(
            """
### 2.1 Qualidade dos dados: nulos, inválidos, imputação e outliers

Antes de criar as features, verificamos os pontos pedidos na análise exploratória: valores ausentes,
duplicidades, datas/prioridades inválidas, cobertura do calendário e valores extremos.

Nem todo nulo significa erro. Em `Incidente Pai`, por exemplo, o valor ausente identifica um incidente
raiz e é usado depois na deduplicação das cascatas. Por isso, os nulos são primeiro diagnosticados e só
depois interpretados.

Para o alvo diário de 2025 não é necessária imputação: o calendário possui os 365 dias. Os valores
extremos também não são removidos automaticamente, porque podem representar surtos reais ou a mudança
de regime operacional observada no ano.
"""
        ),
        code(
            r"""
# Nulos / missing values
nulos = df.isna().sum().sort_values(ascending=False)
qualidade_nulos = pd.DataFrame({
    "nulos": nulos,
    "percentual": (100 * nulos / len(df)).round(2),
})
display(qualidade_nulos[qualidade_nulos["nulos"] > 0].head(15))

# Duplicidade e dados inválidos
prioridade_invalida = int((~df["_prio"].isin([1, 2, 3, 4, 5]) & df["_prio"].notna()).sum())
prioridade_nula = int(df["_prio"].isna().sum())
datas_invalidas = int(df["Aberto"].isna().sum())
duplicados_numero = int(df["Número"].duplicated().sum())

diagnostico = pd.Series({
    "linhas": len(df),
    "numero_duplicado": duplicados_numero,
    "data_abertura_nula_ou_invalida": datas_invalidas,
    "prioridade_fora_de_P1_a_P5": prioridade_invalida,
    "prioridade_nao_identificada": prioridade_nula,
}, name="quantidade")
display(diagnostico.to_frame())

# Cobertura do calendário de 2025 / necessidade de imputação do alvo
calendario_2025 = pd.date_range("2025-01-01", "2025-12-31", freq="D")
dias_observados = pd.DatetimeIndex(d25["dia"].dropna().unique())
dias_sem_registro = calendario_2025.difference(dias_observados)

print(f"Dias do calendário 2025: {len(calendario_2025)}")
print(f"Dias com registro:          {len(dias_observados)}")
print(f"Dias sem registro:          {len(dias_sem_registro)}")
print("Imputação do alvo diário:", "não necessária" if len(dias_sem_registro) == 0 else "avaliar")

# Diagnóstico de extremos na série diária crua.
# O IQR é usado apenas para identificar dias atípicos; nenhum registro é removido.
serie_dia_2025 = (
    d25.groupby("dia")
       .size()
       .reindex(calendario_2025, fill_value=0)
       .rename("incidentes")
)
q1, q3 = serie_dia_2025.quantile([0.25, 0.75])
iqr = q3 - q1
limite_superior = q3 + 1.5 * iqr
outliers_dias = serie_dia_2025[serie_dia_2025 > limite_superior].sort_values(ascending=False)

print(f"\nLimite superior pelo IQR: {limite_superior:.1f} incidentes/dia")
print(f"Dias sinalizados como extremos: {len(outliers_dias)}")
display(outliers_dias.head(10).to_frame())
"""
        ),
        md(
            """
**Leitura da qualidade:** os extremos são mantidos para análise, e não tratados como erro automaticamente.
Na sequência do notebook investigamos se esses picos vêm de mudança de patamar, cascatas pai→filho,
sazonalidade ou ruído. Essa decisão evita apagar justamente os comportamentos operacionais que o modelo
precisa aprender.
"""
        ),
    ]
    cells[idx_2025 + 1:idx_2025 + 1] = eda_quality_cells

    # 3) Tabela de utilidade/vantagem/limitação das features.
    idx_motor_heading = find_cell_index(cells, "## 8. Carregando o motor", cell_type="markdown")
    cells.insert(
        idx_motor_heading,
        md(
            """
### 7.1 Resumo das features: utilidade, vantagem e limitação

| Feature / grupo | Utilidade | Vantagem | Limitação |
|---|---|---|---|
| `seas_lag7`, `seas_lag14` | Captar repetição semanal | Simples e fácil de interpretar | Perde força quando a série não tem sazonalidade semanal |
| `last` | Representar o nível mais recente conhecido | Reage rápido a mudanças | Pode carregar ruído de um único dia |
| `roll7_mean` | Nível médio recente | Suaviza oscilações pontuais | Responde com atraso a mudanças bruscas |
| `roll7_std` | Volatilidade recente | Diferencia períodos estáveis e turbulentos | Pode ficar instável em janelas curtas |
| `roll28_mean` | Patamar mensal aproximado | Mais robusta a picos isolados | Reage mais lentamente a quebras de regime |
| `exp_last`, `exp_roll7` | Medir exposição por CIs ativos | Ajuda a separar carga monitorada de taxa de incidentes | Depende da qualidade do campo de configuração |
| `r_last`, `r_roll7`, `r_seas7` | Incidentes por unidade de exposição | Úteis no modelo de taxa/Poisson | Ficam sensíveis quando a exposição é muito baixa |
| `trend` | Captar evolução ao longo do ano | Representação simples de tendência | Não representa sozinho mudanças abruptas |
| `dow_*`, `is_weekend`, `is_holiday` | Captar calendário operacional | Conhecidas no momento da previsão, sem leakage | O efeito pode mudar entre prioridades |
| `black_week`, `dec_season` | Captar períodos especiais | Introduz contexto de negócio conhecido previamente | São regras específicas do calendário adotado |
"""
        ),
    )

    # 4) Embute o pipeline e preserva interface pl.<nome>.
    idx_motor_heading = find_cell_index(cells, "## 8. Carregando o motor", cell_type="markdown")
    cells[idx_motor_heading].source = """
---
## 8. Motor de previsão incorporado ao notebook

Para a aplicação do projeto, a lógica continua mantida em `pipeline_prioridades.py`. Nesta versão
acadêmica, porém, o mesmo código é incorporado diretamente ao notebook para que a entrega seja um
**arquivo único executável**.

Não há mudança na regra de features, nos candidatos, no walk-forward, na seleção em set–out nem na
avaliação em nov–dez. A única adaptação é a resolução dos caminhos dos arquivos ao ambiente do notebook.

⏱️ Esta etapa executa o pipeline completo e pode levar alguns minutos.
""".strip()

    idx_import = find_cell_index(cells, "import pipeline_prioridades as pl", cell_type="code")
    pipeline_source = PIPELINE_PATH.read_text(encoding="utf-8")
    cells[idx_import].source = build_embedded_pipeline(pipeline_source, cells)
    cells[idx_import].outputs = []
    cells[idx_import].execution_count = None

    # 5) Correlações + interpretação do Ridge.
    idx_feature_sample = find_cell_index(
        cells,
        'X, y = pl.build_Xy(pl.series["P3"], 1)',
        cell_type="code",
    )

    correlation_cells = [
        md(
            """
### 8.1 Correlação entre as variáveis

A autocorrelação temporal já foi investigada na EDA. Aqui complementamos a análise com a correlação
entre as features numéricas e o alvo, usando P3 D+1 como exemplo. A correlação é **descritiva**:
não é usada para escolher features olhando o período de teste e, portanto, não altera o pipeline.

Valores altos entre lags e médias móveis são esperados porque essas variáveis descrevem versões
diferentes do nível recente da mesma série.
"""
        ),
        code(
            r"""
X_corr, y_corr = pl.build_Xy(pl.series["P3"], 1)
corr_frame = X_corr[pl.FEATS_LEVEL].copy()
corr_frame["target"] = y_corr
corr_frame = corr_frame.dropna()

correlacao_target = (
    corr_frame.corr(numeric_only=True)["target"]
    .drop("target")
    .sort_values(key=lambda s: s.abs(), ascending=False)
    .rename("correlacao_com_target")
)
display(correlacao_target.to_frame().round(3))

top_corr_cols = correlacao_target.head(8).index.tolist() + ["target"]
display(corr_frame[top_corr_cols].corr().round(2))
"""
        ),
        md(
            """
### 8.2 Modelo simples e interpretável: pesos do Ridge

A rubrica pede um modelo simples para avaliar o impacto potencial das features. Como o pipeline já
inclui Ridge, usamos P2 D+1 — combinação em que o Ridge foi selecionado — para inspecionar seus
coeficientes.

O ajuste abaixo é **somente interpretativo**. Ele usa dados disponíveis até o fim da janela de seleção
e não substitui nem reconfigura o modelo responsável pelas previsões finais. Como há `StandardScaler`,
os coeficientes podem ser comparados em magnitude: sinal positivo indica associação com aumento da
previsão e sinal negativo com redução, mantendo as demais variáveis constantes.
"""
        ),
        code(
            r"""
X_ridge, y_ridge = pl.build_Xy(pl.series["P2"], 1)
mask_ridge = (
    X_ridge[pl.FEATS_LEVEL].notna().all(axis=1)
    & y_ridge.notna()
    & (y_ridge.index <= pl.SELEND)
)

ridge_interpretavel = make_pipeline(StandardScaler(), Ridge(alpha=5.0))
ridge_interpretavel.fit(
    X_ridge.loc[mask_ridge, pl.FEATS_LEVEL],
    y_ridge.loc[mask_ridge],
)

coeficientes = pd.Series(
    ridge_interpretavel.named_steps["ridge"].coef_,
    index=pl.FEATS_LEVEL,
    name="coeficiente_padronizado",
)

coef_tabela = (
    coeficientes.to_frame()
    .assign(magnitude=lambda x: x["coeficiente_padronizado"].abs())
    .sort_values("magnitude", ascending=False)
)

display(coef_tabela.head(15).round(3))

print(
    "Leitura: os maiores valores absolutos são as features com maior influência "
    "no Ridge deste recorte. Isso não implica causalidade."
)
"""
        ),
    ]
    cells[idx_feature_sample + 1:idx_feature_sample + 1] = correlation_cells

    # 6) Exibe RMSE na tabela final; a métrica já era calculada pelo pipeline.
    idx_final_results = find_cell_index(
        cells,
        '"MAE": round(m["MAE"], 1), "sMAPE%": round(m["sMAPE"], 1)',
        cell_type="code",
    )
    final_source = source_text(cells[idx_final_results])
    final_source = final_source.replace(
        '"MAE": round(m["MAE"], 1), "sMAPE%": round(m["sMAPE"], 1),',
        '"MAE": round(m["MAE"], 1), "RMSE": round(m["RMSE"], 1), '
        '"sMAPE%": round(m["sMAPE"], 1),',
    )
    cells[idx_final_results].source = final_source
    cells[idx_final_results].outputs = []
    cells[idx_final_results].execution_count = None

    # 7) Checklist acadêmico.
    checklist = md(
        """
---
## Checklist acadêmico da disciplina

- **AED:** nulos/missing, duplicidades, dados inválidos, calendário, imputação, distribuições e valores extremos.
- **Engenharia de features:** código, utilidade, vantagens e limitações das variáveis.
- **Ordem temporal e leakage:** features defasadas e avaliação walk-forward.
- **Modelo simples e interpretável:** Ridge com inspeção dos coeficientes padronizados.
- **Avaliação:** baseline, MAE, RMSE, sMAPE, skill e cobertura do intervalo.
- **Aplicação:** previsões D+1 e D+7 para ALL e prioridades, incluindo previsão futura.

As células adicionais desta versão são de diagnóstico e interpretação. Elas não alteram a seleção dos
preditores nem os resultados produzidos pelo pipeline v3.2.
"""
    )

    conclusion_idx = None
    for i, cell in enumerate(cells):
        if cell.cell_type == "markdown":
            s = source_text(cell)
            if "## 12." in s or "# 12." in s:
                conclusion_idx = i
                break
    if conclusion_idx is None:
        cells.append(checklist)
    else:
        cells.insert(conclusion_idx, checklist)

    notebook.cells = cells

    # Validações.
    joined = "\n".join(source_text(c) for c in cells)
    checks = {
        "pipeline incorporado": "import pipeline_prioridades as pl" not in joined,
        "AED/qualidade": "### 2.1 Qualidade dos dados" in joined,
        "correlações": "### 8.1 Correlação entre as variáveis" in joined,
        "interpretação Ridge": "### 8.2 Modelo simples e interpretável" in joined,
        "RMSE exibido": '"RMSE": round(m["RMSE"], 1)' in joined,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError(f"Falharam as validações: {failed}")

    OUTPUT_NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, OUTPUT_NOTEBOOK)

    print(f"Notebook acadêmico gerado: {OUTPUT_NOTEBOOK}")
    print(f"Células: {len(notebook.cells)}")
    for name in checks:
        print(f"- {name}: OK")


if __name__ == "__main__":
    main()
