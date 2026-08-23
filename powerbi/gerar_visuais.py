# -*- coding: utf-8 -*-
"""Gera os visuais PBIR das quatro paginas do relatorio Albus-Hub."""
import hashlib
import json
import os
import shutil
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
REPORT = os.path.join(ROOT, "Projeto.Report")
PAGES = os.path.join(REPORT, "definition", "pages")

SCHEMA = ("https://developer.microsoft.com/json-schemas/fabric/item/report/"
          "definition/visualContainer/2.7.0/schema.json")

PAG = {
    "geral": "8b213feac439b85e06b2",
    "operacao": "5b80741d1af1bcad7a97",
    "sla": "2fdc36e8123f21bc95c2",
    "qualidade": "13d9f26cf1b9b9c90d51",
}

BRAND = "#E30613"
SERIE = "#3987E5"
GOOD = "#1EAE72"
WARN = "#F2B705"
SERIOUS = "#F5803E"
CRITICAL = "#F2434F"
INK2 = "#A8A7B0"
MUTED = "#6E6D78"


def vid(seed):
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]


def lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def s_lit(text):
    return lit("'%s'" % text)


def b_lit(flag):
    return lit("true" if flag else "false")


def n_lit(number):
    return lit("%sD" % number)


def color(hexcode):
    return {"solid": {"color": s_lit(hexcode)}}


def campo(ref, kind):
    entity, prop = ref.split("[", 1)
    prop = prop.rstrip("]")
    key = "Measure" if kind == "measure" else "Column"
    field = {key: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}
    return field, "%s.%s" % (entity, prop), prop


def proj(ref, kind, active=False):
    field, qref, nref = campo(ref, kind)
    item = {"field": field, "queryRef": qref, "nativeQueryRef": nref}
    if active:
        item["active"] = True
    return item


def bucket(refs, first_active=False):
    out = []
    for i, (ref, kind) in enumerate(refs):
        out.append(proj(ref, kind, active=(first_active and i == 0)))
    return {"projections": out}


def visual(seed, vtype, x, y, w, h, z, buckets=None, title=None,
           objects=None, sort=None, hide_title=False):
    v = {
        "$schema": SCHEMA,
        "name": vid(seed),
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": {"visualType": vtype, "drillFilterOtherVisuals": True},
    }
    if buckets:
        query = {"queryState": buckets}
        if sort:
            ref, direction = sort
            kind = "measure" if ref.startswith("_Medidas") else "column"
            field, _, _ = campo(ref, kind)
            query["sortDefinition"] = {"sort": [{"field": field, "direction": direction}]}
        v["visual"]["query"] = query
    if objects:
        v["visual"]["objects"] = objects

    container = {}
    if title:
        container["title"] = [{"properties": {
            "text": s_lit(title),
            "show": b_lit(True),
            "fontSize": n_lit(11),
            "fontColor": color(INK2),
            "alignment": s_lit("left"),
        }}]
    elif hide_title:
        container["title"] = [{"properties": {"show": b_lit(False)}}]
    v["visual"]["visualContainerObjects"] = container
    return v


def cor_dados(hexcode):
    return {"dataPoint": [{"properties": {"fill": color(hexcode)}}]}


def rotulos(show=True, size=10):
    return {"labels": [{"properties": {
        "show": b_lit(show), "fontSize": n_lit(size), "color": color(INK2),
    }}]}


def eixo_categoria(show=True):
    return {"categoryAxis": [{"properties": {
        "show": b_lit(show), "showAxisTitle": b_lit(False),
        "fontSize": n_lit(10), "labelColor": color(MUTED),
    }}]}


def eixo_valor(show=True):
    return {"valueAxis": [{"properties": {
        "show": b_lit(show), "showAxisTitle": b_lit(False),
        "fontSize": n_lit(10), "labelColor": color(MUTED),
    }}]}


def merge(*dicts):
    out = {}
    for d in dicts:
        for k, val in d.items():
            out.setdefault(k, []).extend(val) if k in out else out.__setitem__(k, val)
    return out


def slicer(seed, ref, kind, x, y, w, h, z, title, mode="Dropdown"):
    objs = {"data": [{"properties": {"mode": s_lit(mode)}}]} if mode else None
    return visual(seed, "slicer", x, y, w, h, z,
                  buckets={"Values": bucket([(ref, kind)], first_active=True)},
                  title=title, objects=objs)


def card(seed, ref, x, y, w, h, z, title):
    return visual(seed, "card", x, y, w, h, z,
                  buckets={"Values": bucket([(ref, "measure")])},
                  title=title,
                  objects={
                      "labels": [{"properties": {"fontSize": n_lit(28), "color": color("#F5F5F7")}}],
                      "categoryLabels": [{"properties": {"show": b_lit(False)}}],
                  })


# --------------------------------------------------------------------------- #
paginas = {k: [] for k in PAG}

CARD_X = [40, 412, 784, 1156, 1528]
CARD_W = 352

# ============================ 1. VISÃO GERAL ============================
g = paginas["geral"]
g.append(slicer("g-sl-regime", "dCalendario[Regime]", "column", 40, 40, 420, 60, 1, "Regime"))
g.append(slicer("g-sl-prio", "dPrioridade[Prioridade]", "column", 480, 40, 380, 60, 2, "Prioridade"))
g.append(slicer("g-sl-data", "dCalendario[Date]", "column", 880, 40, 460, 60, 3, "Período", mode=None))
g.append(visual("g-ctx", "card", 1360, 40, 520, 60, 4,
                buckets={"Values": bucket([("_Medidas[Rótulo do período]", "measure")])},
                objects={"labels": [{"properties": {"fontSize": n_lit(11), "color": color(MUTED)}}],
                         "categoryLabels": [{"properties": {"show": b_lit(False)}}]},
                hide_title=True))

for i, (medida, rotulo) in enumerate([
    ("_Medidas[Incidentes]", "Incidentes"),
    ("_Medidas[Média diária]", "Média diária"),
    ("_Medidas[Taxa de violação]", "Taxa de violação"),
    ("_Medidas[Aderência a SLA]", "Aderência a SLA"),
    ("_Medidas[Duração mediana (h)]", "Duração mediana (h)"),
]):
    g.append(card("g-kpi-%d" % i, medida, CARD_X[i], 120, CARD_W, 120, 10 + i, rotulo))

g.append(visual("g-linha", "lineChart", 40, 260, 1210, 380, 20,
                buckets={
                    "Category": bucket([("dCalendario[Date]", "column")], first_active=True),
                    "Y": bucket([("_Medidas[Incidentes]", "measure"),
                                 ("_Medidas[Incidentes MM7]", "measure")]),
                },
                title="Evolução diária e média móvel de 7 dias",
                objects=merge(eixo_categoria(), eixo_valor(),
                              {"dataPoint": [
                                  {"properties": {"fill": color(SERIE)}, "selector": {"metadata": "_Medidas.Incidentes"}},
                                  {"properties": {"fill": color(BRAND)}, "selector": {"metadata": "_Medidas.Incidentes MM7"}},
                              ]},
                              {"legend": [{"properties": {"show": b_lit(True), "position": s_lit("TopLeft"),
                                                          "showTitle": b_lit(False), "fontSize": n_lit(10),
                                                          "labelColor": color(INK2)}}]})))

g.append(visual("g-prio", "columnChart", 1270, 260, 610, 380, 21,
                buckets={
                    "Category": bucket([("dPrioridade[Prioridade]", "column")], first_active=True),
                    "Y": bucket([("_Medidas[Incidentes]", "measure")]),
                },
                title="Volume por prioridade",
                objects=merge(cor_dados(SERIE), rotulos(), eixo_categoria(), eixo_valor(False))))

g.append(visual("g-mes", "columnChart", 40, 670, 910, 370, 22,
                buckets={
                    "Category": bucket([("dCalendario[Mês]", "column")], first_active=True),
                    "Y": bucket([("_Medidas[Incidentes]", "measure")]),
                },
                title="Sazonalidade por mês",
                objects=merge(cor_dados(SERIE), rotulos(), eixo_categoria(), eixo_valor(False))))

g.append(visual("g-dia", "columnChart", 970, 670, 910, 370, 23,
                buckets={
                    "Category": bucket([("dCalendario[Dia da semana]", "column")], first_active=True),
                    "Y": bucket([("_Medidas[Média diária]", "measure")]),
                },
                title="Média de incidentes por dia da semana",
                objects=merge(cor_dados(SERIE), rotulos(), eixo_categoria(), eixo_valor(False))))

# ============================ 2. OPERAÇÃO ============================
o = paginas["operacao"]
o.append(slicer("o-sl-regime", "dCalendario[Regime]", "column", 40, 40, 420, 60, 1, "Regime"))
o.append(slicer("o-sl-prio", "dPrioridade[Prioridade]", "column", 480, 40, 380, 60, 2, "Prioridade"))
o.append(slicer("o-sl-data", "dCalendario[Date]", "column", 880, 40, 460, 60, 3, "Período", mode=None))
o.append(visual("o-ctx", "card", 1360, 40, 520, 60, 4,
                buckets={"Values": bucket([("_Medidas[Rótulo do período]", "measure")])},
                objects={"labels": [{"properties": {"fontSize": n_lit(11), "color": color(MUTED)}}],
                         "categoryLabels": [{"properties": {"show": b_lit(False)}}]},
                hide_title=True))

o.append(visual("o-grupo", "clusteredBarChart", 40, 120, 920, 460, 10,
                buckets={
                    "Category": bucket([("fIncidentes[Grupo designado]", "column")], first_active=True),
                    "Y": bucket([("_Medidas[Incidentes]", "measure")]),
                },
                title="Incidentes por grupo designado",
                sort=("_Medidas[Incidentes]", "Descending"),
                objects=merge(cor_dados(SERIE), rotulos(), eixo_categoria(), eixo_valor(False))))

o.append(visual("o-violacao", "clusteredBarChart", 980, 120, 900, 460, 11,
                buckets={
                    "Category": bucket([("fIncidentes[Grupo designado]", "column")], first_active=True),
                    "Y": bucket([("_Medidas[Taxa de violação]", "measure")]),
                },
                title="Taxa de violação de KPI por grupo",
                sort=("_Medidas[Taxa de violação]", "Descending"),
                objects=merge(cor_dados(CRITICAL), rotulos(), eixo_categoria(), eixo_valor(False))))

o.append(visual("o-matriz", "pivotTable", 40, 600, 920, 440, 12,
                buckets={
                    "Rows": bucket([("fIncidentes[Grupo designado]", "column")], first_active=True),
                    "Columns": bucket([("dPrioridade[Rótulo curto]", "column")]),
                    "Values": bucket([("_Medidas[Incidentes]", "measure")]),
                },
                title="Grupo designado por prioridade"))

o.append(visual("o-categoria", "columnChart", 980, 600, 900, 440, 13,
                buckets={
                    "Category": bucket([("fIncidentes[Categoria]", "column")], first_active=True),
                    "Y": bucket([("_Medidas[Incidentes]", "measure")]),
                },
                title="Incidentes por categoria",
                sort=("_Medidas[Incidentes]", "Descending"),
                objects=merge(cor_dados(SERIE), rotulos(), eixo_categoria(), eixo_valor(False))))

# ============================ 3. SLA E ATENDIMENTO ============================
s = paginas["sla"]
s.append(slicer("s-sl-regime", "dCalendario[Regime]", "column", 40, 40, 420, 60, 1, "Regime"))
s.append(slicer("s-sl-prio", "dPrioridade[Prioridade]", "column", 480, 40, 380, 60, 2, "Prioridade"))
s.append(slicer("s-sl-data", "dCalendario[Date]", "column", 880, 40, 460, 60, 3, "Período", mode=None))
s.append(visual("s-ctx", "card", 1360, 40, 520, 60, 4,
                buckets={"Values": bucket([("_Medidas[Rótulo do período]", "measure")])},
                objects={"labels": [{"properties": {"fontSize": n_lit(11), "color": color(MUTED)}}],
                         "categoryLabels": [{"properties": {"show": b_lit(False)}}]},
                hide_title=True))

for i, (medida, rotulo) in enumerate([
    ("_Medidas[Entraram no KPI]", "Entraram no KPI"),
    ("_Medidas[KPI violado]", "KPI violado"),
    ("_Medidas[Taxa de violação]", "Taxa de violação"),
    ("_Medidas[Aderência a SLA]", "Aderência a SLA"),
    ("_Medidas[Duração P90 (h)]", "Duração P90 (h)"),
]):
    s.append(card("s-kpi-%d" % i, medida, CARD_X[i], 120, CARD_W, 120, 10 + i, rotulo))

s.append(visual("s-treemap", "treemap", 40, 260, 910, 380, 20,
                buckets={
                    "Group": bucket([("fIncidentes[Grupo designado]", "column")], first_active=True),
                    "Values": bucket([("_Medidas[KPI violado]", "measure")]),
                },
                title="Onde estão as violações de SLA",
                objects=rotulos()))

s.append(visual("s-hora", "columnChart", 970, 260, 910, 380, 21,
                buckets={
                    "Category": bucket([("fIncidentes[Hora de abertura]", "column")], first_active=True),
                    "Y": bucket([("_Medidas[Incidentes]", "measure")]),
                },
                title="Abertura por hora do dia",
                objects=merge(cor_dados(SERIE), rotulos(False), eixo_categoria(), eixo_valor())))

s.append(visual("s-matriz", "pivotTable", 40, 670, 1840, 370, 22,
                buckets={
                    "Rows": bucket([("dCalendario[Ano-Mês]", "column")], first_active=True),
                    "Values": bucket([("_Medidas[Incidentes]", "measure"),
                                      ("_Medidas[Entraram no KPI]", "measure"),
                                      ("_Medidas[Taxa de violação]", "measure"),
                                      ("_Medidas[Aderência a SLA]", "measure"),
                                      ("_Medidas[Duração mediana (h)]", "measure"),
                                      ("_Medidas[% Monitoramento]", "measure")]),
                },
                title="Indicadores mês a mês"))

# ============================ 4. QUALIDADE E CONFERÊNCIA ============================
q = paginas["qualidade"]
for i, (medida, rotulo) in enumerate([
    ("_Medidas[Incidentes]", "Incidentes no modelo"),
    ("_Medidas[Incidentes (Gold)]", "Incidentes na camada Gold"),
    ("_Medidas[Diferença vs Gold]", "Diferença — deve ser zero"),
]):
    q.append(card("q-kpi-%d" % i, medida, 40 + i * 620, 40, 600, 120, 1 + i, rotulo))

q.append(visual("q-tabela", "tableEx", 40, 180, 1840, 400, 10,
                buckets={
                    "Values": bucket([("dCalendario[Regime]", "column"),
                                      ("_Medidas[Incidentes]", "measure"),
                                      ("_Medidas[Incidentes (Gold)]", "measure"),
                                      ("_Medidas[Diferença vs Gold]", "measure"),
                                      ("_Medidas[Média diária]", "measure"),
                                      ("_Medidas[Taxa de violação]", "measure"),
                                      ("_Medidas[Duração mediana (h)]", "measure"),
                                      ("_Medidas[% Monitoramento]", "measure")]),
                },
                title="Reconciliação e perfil por patamar de volume"))

q.append(visual("q-regime", "columnChart", 40, 610, 910, 430, 11,
                buckets={
                    "Category": bucket([("dCalendario[Regime]", "column")], first_active=True),
                    "Y": bucket([("_Medidas[Incidentes]", "measure")]),
                },
                title="Volume por patamar",
                objects=merge(cor_dados(SERIE), rotulos(), eixo_categoria(), eixo_valor(False))))

q.append(visual("q-contexto", "multiRowCard", 970, 610, 910, 430, 12,
                buckets={
                    "Values": bucket([("_Medidas[Rótulo do período]", "measure"),
                                      ("_Medidas[Última data da base]", "measure"),
                                      ("_Medidas[Dias no período]", "measure"),
                                      ("_Medidas[Regime em foco]", "measure")]),
                },
                title="Contexto do recorte"))

# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    total = 0
    for chave, page_id in PAG.items():
        destino = os.path.join(PAGES, page_id, "visuals")
        if os.path.isdir(destino):
            shutil.rmtree(destino)
        for v in paginas[chave]:
            pasta = os.path.join(destino, v["name"])
            os.makedirs(pasta, exist_ok=True)
            with open(os.path.join(pasta, "visual.json"), "w", encoding="utf-8") as fh:
                json.dump(v, fh, ensure_ascii=False, indent=2)
            total += 1
        print("%-12s %s  ->  %d visuais" % (chave, page_id, len(paginas[chave])))
    print("total: %d visuais" % total)
