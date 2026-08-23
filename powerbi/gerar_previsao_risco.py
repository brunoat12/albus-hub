# -*- coding: utf-8 -*-
"""Acrescenta previsao e risco ao modelo e ao relatorio (TMDL + PBIR)."""
import hashlib
import json
import os
import shutil
import sys
import uuid

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
MODEL = os.path.join(ROOT, "Projeto.SemanticModel", "definition")
REPORT = os.path.join(ROOT, "Projeto.Report", "definition")
PAGES = os.path.join(REPORT, "pages")

DADOS = r"C:\Users\cymko\Downloads\albus-hub\data\gold"
NS = uuid.UUID("6f1d5b7e-0000-4000-8000-a1b0c2d4e6f8")

SCHEMA_VISUAL = ("https://developer.microsoft.com/json-schemas/fabric/item/report/"
                 "definition/visualContainer/2.7.0/schema.json")
SCHEMA_PAGE = ("https://developer.microsoft.com/json-schemas/fabric/item/report/"
               "definition/page/2.1.0/schema.json")

BRAND = "#E30613"
SERIE = "#3987E5"
GOOD = "#1EAE72"
WARN = "#F2B705"
SERIOUS = "#F5803E"
CRITICAL = "#F2434F"
INK2 = "#A8A7B0"
MUTED = "#6E6D78"


def tag(seed):
    return str(uuid.uuid5(NS, seed))


def vid(seed):
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]


# =========================== TMDL: tabelas novas =========================== #

TMDL_PREVISOES = f"""/// Previsoes de volume publicadas pela frente de modelagem, ja traduzidas para o contrato de integracao.
table fPrevisoes
\tlineageTag: {tag("t-previsoes")}

\tcolumn Data
\t\tdataType: dateTime
\t\tformatString: dd/mm/yyyy
\t\tlineageTag: {tag("c-prev-data")}
\t\tsummarizeBy: none
\t\tsourceColumn: Data

\tcolumn Horizonte
\t\tdataType: string
\t\tlineageTag: {tag("c-prev-horizonte")}
\t\tsourceColumn: Horizonte

\tcolumn Escopo
\t\tdataType: string
\t\tlineageTag: {tag("c-prev-escopo")}
\t\tsourceColumn: Escopo

\tcolumn Previsto
\t\tdataType: int64
\t\tformatString: #,0
\t\tlineageTag: {tag("c-prev-previsto")}
\t\tsummarizeBy: sum
\t\tsourceColumn: Previsto

\tcolumn Realizado
\t\tdataType: double
\t\tformatString: #,0
\t\tlineageTag: {tag("c-prev-realizado")}
\t\tsummarizeBy: sum
\t\tsourceColumn: Realizado

\tcolumn 'Limite inferior'
\t\tdataType: int64
\t\tformatString: #,0
\t\tlineageTag: {tag("c-prev-inf")}
\t\tsummarizeBy: sum
\t\tsourceColumn: Limite inferior

\tcolumn 'Limite superior'
\t\tdataType: int64
\t\tformatString: #,0
\t\tlineageTag: {tag("c-prev-sup")}
\t\tsummarizeBy: sum
\t\tsourceColumn: Limite superior

\tcolumn Modelo
\t\tdataType: string
\t\tlineageTag: {tag("c-prev-modelo")}
\t\tsourceColumn: Modelo

\tcolumn 'Versão do modelo'
\t\tdataType: string
\t\tlineageTag: {tag("c-prev-versao")}
\t\tsourceColumn: Versão do modelo

\tpartition fPrevisoes = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t    Fonte = Parquet.Document(File.Contents("{DADOS}\\volume_predictions.parquet")),
\t\t\t\t    Tipos = Table.TransformColumnTypes(Fonte, {{
\t\t\t\t        {{"reference_date", type date}},
\t\t\t\t        {{"horizon", type text}},
\t\t\t\t        {{"priority_scope", type text}},
\t\t\t\t        {{"predicted_incident_count", Int64.Type}},
\t\t\t\t        {{"actual_incidents", type number}},
\t\t\t\t        {{"lower_bound", Int64.Type}},
\t\t\t\t        {{"upper_bound", Int64.Type}},
\t\t\t\t        {{"model", type text}},
\t\t\t\t        {{"model_version", type text}}
\t\t\t\t    }}),
\t\t\t\t    Renomeadas = Table.RenameColumns(Tipos, {{
\t\t\t\t        {{"reference_date","Data"}},
\t\t\t\t        {{"horizon","Horizonte"}},
\t\t\t\t        {{"priority_scope","Escopo"}},
\t\t\t\t        {{"predicted_incident_count","Previsto"}},
\t\t\t\t        {{"actual_incidents","Realizado"}},
\t\t\t\t        {{"lower_bound","Limite inferior"}},
\t\t\t\t        {{"upper_bound","Limite superior"}},
\t\t\t\t        {{"model","Modelo"}},
\t\t\t\t        {{"model_version","Versão do modelo"}}
\t\t\t\t    }}),
\t\t\t\t    Final = Table.SelectColumns(Renomeadas, {{"Data","Horizonte","Escopo","Previsto","Realizado","Limite inferior","Limite superior","Modelo","Versão do modelo"}})
\t\t\t\tin
\t\t\t\t    Final
"""

TMDL_RISCOS = f"""/// Score de risco operacional por incidente, produzido pela frente de modelagem e validado pelo contrato.
table fRiscos
\tlineageTag: {tag("t-riscos")}

\tcolumn Incidente
\t\tdataType: string
\t\tlineageTag: {tag("c-risco-incidente")}
\t\tsourceColumn: Incidente

\tcolumn 'Pontuado em'
\t\tdataType: dateTime
\t\tformatString: dd/mm/yyyy hh:nn
\t\tlineageTag: {tag("c-risco-pontuado")}
\t\tsummarizeBy: none
\t\tsourceColumn: Pontuado em

\tcolumn 'Probabilidade de violação'
\t\tdataType: double
\t\tformatString: 0.0%
\t\tlineageTag: {tag("c-risco-prob")}
\t\tsummarizeBy: none
\t\tsourceColumn: Probabilidade de violação

\tcolumn 'Impacto da prioridade'
\t\tdataType: double
\t\tformatString: 0.00
\t\tlineageTag: {tag("c-risco-impacto")}
\t\tsummarizeBy: none
\t\tsourceColumn: Impacto da prioridade

\tcolumn 'Pressão operacional'
\t\tdataType: double
\t\tformatString: 0.00
\t\tlineageTag: {tag("c-risco-pressao")}
\t\tsummarizeBy: none
\t\tsourceColumn: Pressão operacional

\tcolumn 'Score de risco'
\t\tdataType: int64
\t\tformatString: #,0
\t\tlineageTag: {tag("c-risco-score")}
\t\tsummarizeBy: none
\t\tsourceColumn: Score de risco

\tcolumn 'Nível de risco'
\t\tdataType: string
\t\tlineageTag: {tag("c-risco-nivel")}
\t\tsourceColumn: Nível de risco
\t\tsortByColumn: 'Ordem do nível'

\tcolumn 'Ordem do nível'
\t\tdataType: int64
\t\tisHidden
\t\tlineageTag: {tag("c-risco-ordem")}
\t\tsummarizeBy: none
\t\tsourceColumn: Ordem do nível

\tcolumn 'Fatores de risco'
\t\tdataType: string
\t\tlineageTag: {tag("c-risco-fatores")}
\t\tsourceColumn: Fatores de risco

\tcolumn 'Ação recomendada'
\t\tdataType: string
\t\tlineageTag: {tag("c-risco-acao")}
\t\tsourceColumn: Ação recomendada

\tcolumn 'Versão do modelo'
\t\tdataType: string
\t\tlineageTag: {tag("c-risco-versao")}
\t\tsourceColumn: Versão do modelo

\tpartition fRiscos = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t    Fonte = Parquet.Document(File.Contents("{DADOS}\\risk_scores.parquet")),
\t\t\t\t    Ordem = Table.AddColumn(Fonte, "Ordem do nível", each
\t\t\t\t        if [risk_level] = "baixo" then 1
\t\t\t\t        else if [risk_level] = "moderado" then 2
\t\t\t\t        else if [risk_level] = "alto" then 3
\t\t\t\t        else 4, Int64.Type),
\t\t\t\t    Tipos = Table.TransformColumnTypes(Ordem, {{
\t\t\t\t        {{"incident_id", type text}},
\t\t\t\t        {{"scored_at", type datetime}},
\t\t\t\t        {{"breach_probability", type number}},
\t\t\t\t        {{"priority_impact", type number}},
\t\t\t\t        {{"operational_pressure", type number}},
\t\t\t\t        {{"risk_score", Int64.Type}},
\t\t\t\t        {{"risk_level", type text}},
\t\t\t\t        {{"top_risk_factors", type text}},
\t\t\t\t        {{"recommended_action", type text}},
\t\t\t\t        {{"model_version", type text}}
\t\t\t\t    }}),
\t\t\t\t    Renomeadas = Table.RenameColumns(Tipos, {{
\t\t\t\t        {{"incident_id","Incidente"}},
\t\t\t\t        {{"scored_at","Pontuado em"}},
\t\t\t\t        {{"breach_probability","Probabilidade de violação"}},
\t\t\t\t        {{"priority_impact","Impacto da prioridade"}},
\t\t\t\t        {{"operational_pressure","Pressão operacional"}},
\t\t\t\t        {{"risk_score","Score de risco"}},
\t\t\t\t        {{"risk_level","Nível de risco"}},
\t\t\t\t        {{"top_risk_factors","Fatores de risco"}},
\t\t\t\t        {{"recommended_action","Ação recomendada"}},
\t\t\t\t        {{"model_version","Versão do modelo"}}
\t\t\t\t    }})
\t\t\t\tin
\t\t\t\t    Renomeadas
"""

MEDIDAS = [
    # ALL ja contem P2 e P3. Sem escopo selecionado, as medidas usam ALL —
    # somar os tres escopos contaria o mesmo incidente duas vezes.
    ("Previsto",
     'IF (\n    ISFILTERED ( fPrevisoes[Escopo] ),\n    SUM ( fPrevisoes[Previsto] ),\n    CALCULATE ( SUM ( fPrevisoes[Previsto] ), fPrevisoes[Escopo] = "ALL" )\n)',
     "#,0", "08 Previsão", "Soma dos valores previstos. Sem escopo selecionado usa ALL."),
    ("Realizado no backtest",
     'IF (\n    ISFILTERED ( fPrevisoes[Escopo] ),\n    SUM ( fPrevisoes[Realizado] ),\n    CALCULATE ( SUM ( fPrevisoes[Realizado] ), fPrevisoes[Escopo] = "ALL" )\n)',
     "#,0", "08 Previsão", "Valor real observado nas linhas de backtest. Sem escopo selecionado usa ALL."),
    ("Previsão D+1",
     'VAR EscopoAtivo =\n    IF ( ISFILTERED ( fPrevisoes[Escopo] ), SELECTEDVALUE ( fPrevisoes[Escopo], "ALL" ), "ALL" )\n'
     'VAR Ult =\n    CALCULATE ( MAX ( fPrevisoes[Data] ), fPrevisoes[Horizonte] = "D+1", fPrevisoes[Escopo] = EscopoAtivo, REMOVEFILTERS ( dCalendario ) )\n'
     'RETURN\n    CALCULATE ( SUM ( fPrevisoes[Previsto] ), fPrevisoes[Horizonte] = "D+1", fPrevisoes[Escopo] = EscopoAtivo, fPrevisoes[Data] = Ult, REMOVEFILTERS ( dCalendario ) )',
     "#,0", "08 Previsão", "Previsao mais recente para o horizonte de um dia."),
    ("Previsão D+7",
     'VAR EscopoAtivo =\n    IF ( ISFILTERED ( fPrevisoes[Escopo] ), SELECTEDVALUE ( fPrevisoes[Escopo], "ALL" ), "ALL" )\n'
     'VAR Ult =\n    CALCULATE ( MAX ( fPrevisoes[Data] ), fPrevisoes[Horizonte] = "D+7", fPrevisoes[Escopo] = EscopoAtivo, REMOVEFILTERS ( dCalendario ) )\n'
     'RETURN\n    CALCULATE ( SUM ( fPrevisoes[Previsto] ), fPrevisoes[Horizonte] = "D+7", fPrevisoes[Escopo] = EscopoAtivo, fPrevisoes[Data] = Ult, REMOVEFILTERS ( dCalendario ) )',
     "#,0", "08 Previsão", "Previsao mais recente para o horizonte de sete dias."),
    ("Erro absoluto médio",
     'VAR ComFiltro =\n    AVERAGEX ( FILTER ( fPrevisoes, NOT ISBLANK ( fPrevisoes[Realizado] ) ), ABS ( fPrevisoes[Previsto] - fPrevisoes[Realizado] ) )\n'
     'VAR SomenteALL =\n    CALCULATE ( AVERAGEX ( FILTER ( fPrevisoes, NOT ISBLANK ( fPrevisoes[Realizado] ) ), ABS ( fPrevisoes[Previsto] - fPrevisoes[Realizado] ) ), fPrevisoes[Escopo] = "ALL" )\n'
     'RETURN\n    IF ( ISFILTERED ( fPrevisoes[Escopo] ), ComFiltro, SomenteALL )',
     "#,0.0", "08 Previsão", "Erro medio absoluto nas linhas de backtest. Compare com a media realizada."),
    ("Dias avaliados no backtest",
     'VAR ComFiltro =\n    COUNTROWS ( FILTER ( fPrevisoes, NOT ISBLANK ( fPrevisoes[Realizado] ) ) )\n'
     'VAR SomenteALL =\n    CALCULATE ( COUNTROWS ( FILTER ( fPrevisoes, NOT ISBLANK ( fPrevisoes[Realizado] ) ) ), fPrevisoes[Escopo] = "ALL" )\n'
     'RETURN\n    IF ( ISFILTERED ( fPrevisoes[Escopo] ), ComFiltro, SomenteALL )',
     "#,0", "08 Previsão", "Linhas de previsao que ja tem valor real para comparar."),
    ("Média realizada no backtest", "DIVIDE ( [Realizado no backtest], [Dias avaliados no backtest] )",
     "#,0.0", "08 Previsão", "Media de incidentes por dia na janela de backtest."),
    ("Erro relativo", "DIVIDE ( [Erro absoluto médio], [Média realizada no backtest] )",
     "0.0%", "08 Previsão", "Erro medio dividido pela media realizada. Diz o tamanho do erro frente ao volume."),
    ("Versão da previsão", "SELECTEDVALUE ( fPrevisoes[Versão do modelo], MAX ( fPrevisoes[Versão do modelo] ) )",
     None, "08 Previsão", "Versao do artefato de previsao publicado."),
    ("Incidentes com score", "COUNTROWS ( fRiscos )", "#,0", "09 Risco",
     "Quantidade de incidentes que receberam score de risco."),
    ("Score médio", "AVERAGE ( fRiscos[Score de risco] )", "#,0.0", "09 Risco",
     "Media do score de risco na populacao pontuada."),
    ("Score máximo", "MAX ( fRiscos[Score de risco] )", "#,0", "09 Risco",
     "Maior score observado. Compare com os cortes de nivel."),
    ("Alto ou crítico",
     'CALCULATE ( COUNTROWS ( fRiscos ), fRiscos[Nível de risco] IN { "alto", "crítico" } )',
     "#,0", "09 Risco", "Incidentes classificados nos dois niveis superiores."),
    ("Probabilidade média de violação", "AVERAGE ( fRiscos[Probabilidade de violação] )",
     "0.00%", "09 Risco", "Media da probabilidade prevista pelo modelo."),
]


def bloco_medida(nome, expr, fmt, pasta, doc):
    linhas = [f"\t/// {doc}"]
    if "\n" in expr:
        linhas.append(f"\tmeasure '{nome}' =")
        for linha in expr.split("\n"):
            linhas.append("\t\t\t" + linha)
    else:
        linhas.append(f"\tmeasure '{nome}' = {expr}")
    if fmt:
        linhas.append(f"\t\tformatString: {fmt}")
    linhas.append(f"\t\tdisplayFolder: {pasta}")
    linhas.append(f"\t\tlineageTag: {tag('m-' + nome)}")
    return "\n".join(linhas)


# =========================== PBIR: visuais =========================== #

def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def s_lit(t):
    return lit(f"'{t}'")


def b_lit(f):
    return lit("true" if f else "false")


def n_lit(n):
    return lit(f"{n}D")


def cor(h):
    return {"solid": {"color": s_lit(h)}}


def campo(ref, kind):
    ent, prop = ref.split("[", 1)
    prop = prop.rstrip("]")
    key = "Measure" if kind == "measure" else "Column"
    return {key: {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}}, f"{ent}.{prop}", prop


def bucket(refs, ativo=False):
    out = []
    for i, (ref, kind) in enumerate(refs):
        f, q, n = campo(ref, kind)
        item = {"field": f, "queryRef": q, "nativeQueryRef": n}
        if ativo and i == 0:
            item["active"] = True
        out.append(item)
    return {"projections": out}


def visual(seed, vtype, x, y, w, h, z, buckets=None, titulo=None, objects=None,
           sort=None, sem_titulo=False):
    v = {"$schema": SCHEMA_VISUAL, "name": vid(seed),
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
         "visual": {"visualType": vtype, "drillFilterOtherVisuals": True}}
    if buckets:
        q = {"queryState": buckets}
        if sort:
            ref, direcao = sort
            kind = "measure" if ref.startswith("_Medidas") else "column"
            f, _, _ = campo(ref, kind)
            q["sortDefinition"] = {"sort": [{"field": f, "direction": direcao}]}
        v["visual"]["query"] = q
    if objects:
        v["visual"]["objects"] = objects
    cont = {}
    if titulo:
        cont["title"] = [{"properties": {"text": s_lit(titulo), "show": b_lit(True),
                                         "fontSize": n_lit(11), "fontColor": cor(INK2),
                                         "alignment": s_lit("left")}}]
    elif sem_titulo:
        cont["title"] = [{"properties": {"show": b_lit(False)}}]
    v["visual"]["visualContainerObjects"] = cont
    return v


def cartao(seed, ref, x, y, w, h, z, titulo):
    return visual(seed, "card", x, y, w, h, z,
                  buckets={"Values": bucket([(ref, "measure")])}, titulo=titulo,
                  objects={"labels": [{"properties": {"fontSize": n_lit(28), "color": cor("#F5F5F7")}}],
                           "categoryLabels": [{"properties": {"show": b_lit(False)}}]})


def slicer(seed, ref, x, y, w, h, z, titulo):
    return visual(seed, "slicer", x, y, w, h, z,
                  buckets={"Values": bucket([(ref, "column")], ativo=True)}, titulo=titulo,
                  objects={"data": [{"properties": {"mode": s_lit("Dropdown")}}]})


def eixos(cat=True, val=True):
    return {
        "categoryAxis": [{"properties": {"show": b_lit(cat), "showAxisTitle": b_lit(False),
                                         "fontSize": n_lit(10), "labelColor": cor(MUTED)}}],
        "valueAxis": [{"properties": {"show": b_lit(val), "showAxisTitle": b_lit(False),
                                      "fontSize": n_lit(10), "labelColor": cor(MUTED)}}],
    }


PAGINA_PREVISAO = "a1f0c2d4e6b8a0c2e4f6"
PAGINA_RISCO = "b2e1d3c5f7a9b1d3e5a7"

CARD_X = [40, 412, 784, 1156, 1528]
CARD_W = 352

previsao = [
    slicer("p-sl-escopo", "fPrevisoes[Escopo]", 40, 40, 380, 60, 1, "Escopo"),
    slicer("p-sl-horizonte", "fPrevisoes[Horizonte]", 440, 40, 340, 60, 2, "Horizonte"),
    visual("p-versao", "card", 1360, 40, 520, 60, 3,
           buckets={"Values": bucket([("_Medidas[Versão da previsão]", "measure")])},
           objects={"labels": [{"properties": {"fontSize": n_lit(12), "color": cor(MUTED)}}],
                    "categoryLabels": [{"properties": {"show": b_lit(False)}}]},
           sem_titulo=True),
    cartao("p-c1", "_Medidas[Previsão D+1]", CARD_X[0], 120, CARD_W, 120, 10, "Previsão D+1"),
    cartao("p-c2", "_Medidas[Previsão D+7]", CARD_X[1], 120, CARD_W, 120, 11, "Previsão D+7"),
    cartao("p-c3", "_Medidas[Erro absoluto médio]", CARD_X[2], 120, CARD_W, 120, 12, "Erro médio no backtest"),
    cartao("p-c4", "_Medidas[Dias avaliados no backtest]", CARD_X[3], 120, CARD_W, 120, 13, "Dias avaliados"),
    cartao("p-c5", "_Medidas[Média realizada no backtest]", CARD_X[4], 120, CARD_W, 120, 14, "Média realizada"),
    visual("p-linha", "lineChart", 40, 260, 1840, 420, 20,
           buckets={"Category": bucket([("fPrevisoes[Data]", "column")], ativo=True),
                    "Y": bucket([("_Medidas[Realizado no backtest]", "measure"),
                                 ("_Medidas[Previsto]", "measure")])},
           titulo="Realizado e previsto ao longo do backtest",
           objects={**eixos(),
                    "dataPoint": [
                        {"properties": {"fill": cor(SERIE)}, "selector": {"metadata": "_Medidas.Realizado no backtest"}},
                        {"properties": {"fill": cor(BRAND)}, "selector": {"metadata": "_Medidas.Previsto"}}],
                    "legend": [{"properties": {"show": b_lit(True), "position": s_lit("TopLeft"),
                                               "showTitle": b_lit(False), "fontSize": n_lit(10),
                                               "labelColor": cor(INK2)}}]}),
    visual("p-tabela", "tableEx", 40, 700, 1840, 340, 21,
           buckets={"Values": bucket([("fPrevisoes[Data]", "column"),
                                      ("fPrevisoes[Horizonte]", "column"),
                                      ("fPrevisoes[Escopo]", "column"),
                                      ("_Medidas[Previsto]", "measure"),
                                      ("_Medidas[Realizado no backtest]", "measure"),
                                      ("fPrevisoes[Modelo]", "column")])},
           titulo="Artefato publicado"),
]

risco = [
    slicer("r-sl-nivel", "fRiscos[Nível de risco]", 40, 40, 380, 60, 1, "Nível de risco"),
    visual("r-versao", "card", 1360, 40, 520, 60, 2,
           buckets={"Values": bucket([("_Medidas[Score máximo]", "measure")])},
           objects={"labels": [{"properties": {"fontSize": n_lit(12), "color": cor(MUTED)}}],
                    "categoryLabels": [{"properties": {"show": b_lit(True), "color": cor(MUTED),
                                                       "fontSize": n_lit(10)}}]},
           sem_titulo=True),
    cartao("r-c1", "_Medidas[Incidentes com score]", CARD_X[0], 120, CARD_W, 120, 10, "Incidentes pontuados"),
    cartao("r-c2", "_Medidas[Score médio]", CARD_X[1], 120, CARD_W, 120, 11, "Score médio"),
    cartao("r-c3", "_Medidas[Score máximo]", CARD_X[2], 120, CARD_W, 120, 12, "Score máximo"),
    cartao("r-c4", "_Medidas[Alto ou crítico]", CARD_X[3], 120, CARD_W, 120, 13, "Alto ou crítico"),
    cartao("r-c5", "_Medidas[Probabilidade média de violação]", CARD_X[4], 120, CARD_W, 120, 14,
           "Probabilidade media"),
    visual("r-nivel", "columnChart", 40, 260, 910, 380, 20,
           buckets={"Category": bucket([("fRiscos[Nível de risco]", "column")], ativo=True),
                    "Y": bucket([("_Medidas[Incidentes com score]", "measure")])},
           titulo="Distribuição por nível de risco",
           objects={**eixos(val=False),
                    "labels": [{"properties": {"show": b_lit(True), "fontSize": n_lit(10),
                                               "color": cor(INK2)}}],
                    "dataPoint": [{"properties": {"fill": cor(SERIE)}}]}),
    visual("r-hist", "columnChart", 970, 260, 910, 380, 21,
           buckets={"Category": bucket([("fRiscos[Score de risco]", "column")], ativo=True),
                    "Y": bucket([("_Medidas[Incidentes com score]", "measure")])},
           titulo="Distribuição do score (0 a 100)",
           objects={**eixos(),
                    "dataPoint": [{"properties": {"fill": cor(SERIOUS)}}]}),
    visual("r-fila", "tableEx", 40, 660, 1840, 380, 22,
           buckets={"Values": bucket([("fRiscos[Incidente]", "column"),
                                      ("fRiscos[Score de risco]", "column"),
                                      ("fRiscos[Nível de risco]", "column"),
                                      ("fRiscos[Probabilidade de violação]", "column"),
                                      ("fRiscos[Fatores de risco]", "column"),
                                      ("fRiscos[Ação recomendada]", "column")])},
           titulo="Fila priorizada",
           sort=("fRiscos[Score de risco]", "Descending")),
]

PAGINAS_NOVAS = [
    (PAGINA_PREVISAO, "Previsões", previsao),
    (PAGINA_RISCO, "Risco Operacional", risco),
]


def escrever(caminho, conteudo):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(conteudo)


if __name__ == "__main__":
    # ---------- TMDL ----------
    escrever(os.path.join(MODEL, "tables", "fPrevisoes.tmdl"), TMDL_PREVISOES)
    escrever(os.path.join(MODEL, "tables", "fRiscos.tmdl"), TMDL_RISCOS)
    print("tabelas fPrevisoes e fRiscos escritas")

    # medidas
    caminho_medidas = os.path.join(MODEL, "tables", "_Medidas.tmdl")
    texto = open(caminho_medidas, encoding="utf-8").read().rstrip("\n")
    novas = [m for m in MEDIDAS if f"measure '{m[0]}'" not in texto]
    if novas:
        texto += "\n\n" + "\n\n".join(bloco_medida(*m) for m in novas) + "\n"
        escrever(caminho_medidas, texto)
    print(f"{len(novas)} medidas novas em _Medidas.tmdl")

    # calendario cobrindo as datas de previsao
    caminho_cal = os.path.join(MODEL, "tables", "dCalendario.tmdl")
    cal = open(caminho_cal, encoding="utf-8").read()
    antigo = "VAR MaxData = MAX ( fIncidentes[Data de abertura] )"
    # o corpo da expressao usa 4 tabs; indentacao menor faz o TMDL fechar o bloco
    novo = ("VAR MaxIncidente = MAX ( fIncidentes[Data de abertura] )\n"
            "\t\t\t\tVAR MaxPrevisao = MAX ( fPrevisoes[Data] )\n"
            "\t\t\t\tVAR MaxData = MAXX ( { MaxIncidente, MaxPrevisao }, [Value] )")
    if antigo in cal and "MaxPrevisao" not in cal:
        cal = cal.replace(antigo, novo)
        escrever(caminho_cal, cal)
        print("dCalendario ampliado para cobrir as datas de previsao")

    # relacionamento previsao -> calendario
    caminho_rel = os.path.join(MODEL, "relationships.tmdl")
    rel = open(caminho_rel, encoding="utf-8").read().rstrip("\n")
    if "dCalendario_fPrevisoes" not in rel:
        rel += ("\n\nrelationship dCalendario_fPrevisoes\n"
                "\tfromColumn: fPrevisoes.Data\n"
                "\ttoColumn: dCalendario.Date\n")
        escrever(caminho_rel, rel)
        print("relacionamento fPrevisoes -> dCalendario criado")

    # referencias no model.tmdl
    caminho_model = os.path.join(MODEL, "model.tmdl")
    mod = open(caminho_model, encoding="utf-8").read()
    for t in ["fPrevisoes", "fRiscos"]:
        if f"ref table {t}" not in mod:
            mod = mod.replace("ref table dPrioridade", f"ref table dPrioridade\nref table {t}", 1)
    escrever(caminho_model, mod)
    print("model.tmdl atualizado")

    # ---------- PBIR ----------
    total = 0
    for page_id, nome, visuais in PAGINAS_NOVAS:
        escrever(os.path.join(PAGES, page_id, "page.json"), json.dumps({
            "$schema": SCHEMA_PAGE, "name": page_id, "displayName": nome,
            "displayOption": "FitToPage", "height": 1080, "width": 1920,
        }, ensure_ascii=False, indent=2))
        destino = os.path.join(PAGES, page_id, "visuals")
        if os.path.isdir(destino):
            shutil.rmtree(destino)
        for v in visuais:
            escrever(os.path.join(destino, v["name"], "visual.json"),
                     json.dumps(v, ensure_ascii=False, indent=2))
            total += 1
        print(f"pagina {nome}: {len(visuais)} visuais")

    caminho_pages = os.path.join(PAGES, "pages.json")
    pages = json.load(open(caminho_pages, encoding="utf-8"))
    ordem = pages["pageOrder"]
    for page_id, _, _ in PAGINAS_NOVAS:
        if page_id not in ordem:
            ordem.insert(len(ordem) - 1, page_id)
    pages["pageOrder"] = ordem
    escrever(caminho_pages, json.dumps(pages, ensure_ascii=False, indent=2))
    print("pages.json atualizado ·", len(ordem), "paginas ·", total, "visuais novos")
