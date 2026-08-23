# -*- coding: utf-8 -*-
"""Troca o navegador nativo por um menu de botoes, no padrao do prototipo."""
import hashlib
import json
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
PAGES = os.path.join(ROOT, "Projeto.Report", "definition", "pages")
SCHEMA = ("https://developer.microsoft.com/json-schemas/fabric/item/report/"
          "definition/visualContainer/2.7.0/schema.json")

RAIL = "#060608"
ATIVO = "#101014"
BRAND = "#E30613"
INK = "#F5F5F7"
INK2 = "#A8A7B0"
MUTED = "#6E6D78"

# grupo -> paginas, na ordem do menu
GRUPOS = [
    ("OPERAÇÃO", ["Visão Geral", "Operação", "SLA e Atendimento"]),
    ("INTELIGÊNCIA", ["Previsões", "Risco Operacional"]),
    ("SISTEMA", ["Qualidade e Conferência"]),
]
ROTULOS = {"Qualidade e Conferência": "Qualidade"}

ALT_BOTAO, PASSO, ALT_GRUPO = 38, 42, 30
X, LARG = 12, 256


def vid(seed):
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]


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


def envelope(nome, tipo, x, y, w, h, z, objects, botao=False):
    v = {"$schema": SCHEMA, "name": nome,
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
         "visual": {"visualType": tipo, "objects": objects,
                    "visualContainerObjects": {
                        "title": [{"properties": {"show": b_lit(False)}}],
                        "subTitle": [{"properties": {"show": b_lit(False)}}]},
                    "drillFilterOtherVisuals": True}}
    if botao:
        v["howCreated"] = "InsertVisualButton"
    return v


def botao(nome, rotulo, destino, x, y, w, h, z, ativo):
    return envelope(nome, "actionButton", x, y, w, h, z, {
        "text": [{"properties": {
            "show": b_lit(True),
            "text": s_lit(rotulo),
            "fontColor": cor(INK if ativo else INK2),
            "fontSize": n_lit(11),
            "fontFamily": s_lit("Segoe UI"),
            "horizontalAlignment": s_lit("left"),
            "leftMargin": n_lit(14),
        }}],
        "fill": [{"properties": {
            "show": b_lit(True),
            "fillColor": cor(ATIVO if ativo else RAIL),
            "transparency": n_lit(0),
        }}],
        "outline": [{"properties": {"show": b_lit(False)}}],
        "action": [{"properties": {
            "type": s_lit("PageNavigation"),
            "navigationSection": {"expr": {"Section": {"Section": destino}}},
        }}],
    }, botao=True)


def acento(nome, y, z):
    return envelope(nome, "shape", X, y, 3, ALT_BOTAO, z, {
        "shape": [{"properties": {"tileShape": s_lit("rectangle")}}],
        "fill": [{"properties": {"show": b_lit(True), "fillColor": cor(BRAND),
                                 "transparency": n_lit(0)}}],
        "outline": [{"properties": {"show": b_lit(False)}}],
    })


def rotulo_grupo(nome, texto, y, z):
    return envelope(nome, "textbox", 20, y, 240, 22, z, {
        "general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": texto, "textStyle": {
                "color": MUTED, "fontSize": "8pt", "fontFamily": "Consolas"}}],
             "horizontalTextAlignment": "left"}]}}]
    })


if __name__ == "__main__":
    ordem = json.load(open(os.path.join(PAGES, "pages.json"), encoding="utf-8"))["pageOrder"]
    por_nome = {}
    for pid in ordem:
        nome = json.load(open(os.path.join(PAGES, pid, "page.json"), encoding="utf-8"))["displayName"]
        por_nome[nome] = pid

    faltando = [p for _, ps in GRUPOS for p in ps if p not in por_nome]
    if faltando:
        raise SystemExit(f"paginas do menu nao encontradas: {faltando}")

    criados = 0
    for pid_atual in ordem:
        atual = json.load(open(os.path.join(PAGES, pid_atual, "page.json"), encoding="utf-8"))["displayName"]
        dir_v = os.path.join(PAGES, pid_atual, "visuals")

        elementos = []
        y, z = 112, 2
        for grupo, paginas in GRUPOS:
            elementos.append(("grupo", rotulo_grupo(
                vid(f"menu-g-{pid_atual}-{grupo}"), grupo, y, z)))
            y += ALT_GRUPO
            z += 1
            for p in paginas:
                ativo = (p == atual)
                elementos.append(("botao", botao(
                    vid(f"menu-b-{pid_atual}-{p}"), ROTULOS.get(p, p), por_nome[p],
                    X, y, LARG, ALT_BOTAO, z, ativo)))
                z += 1
                if ativo:
                    elementos.append(("acento", acento(
                        vid(f"menu-a-{pid_atual}-{p}"), y, z)))
                    z += 1
                y += PASSO
            y += 10

        # reaproveita as pastas do navegador nativo e do rotulo antigo
        reuso = [vid(f"rail-nav-{pid_atual}"), vid(f"rail-lbl-nav-{pid_atual}")]
        for i, (_, v) in enumerate(elementos):
            destino_nome = reuso[i] if i < len(reuso) else v["name"]
            v["name"] = destino_nome
            d = os.path.join(dir_v, destino_nome)
            os.makedirs(d, exist_ok=True)
            json.dump(v, open(os.path.join(d, "visual.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            criados += 1

        nomes_menu = {v["name"] for _, v in elementos}

        # empurra as segmentacoes para baixo do menu, em ordem fixa
        fim_menu = y + 12

        NOMES = {
            "dCalendario.Regime": "REGIME",
            "dPrioridade.Prioridade": "PRIORIDADE",
            "dCalendario.Date": "PERÍODO",
            "fPrevisoes.Escopo": "ESCOPO",
            "fPrevisoes.Horizonte": "HORIZONTE",
            "fRiscos.Nível de risco": "NÍVEL DE RISCO",
        }
        PREFERENCIA = ["dCalendario.Regime", "dPrioridade.Prioridade", "dCalendario.Date",
                       "fPrevisoes.Escopo", "fPrevisoes.Horizonte", "fRiscos.Nível de risco"]

        slicers, rotulos = [], []
        for d in sorted(os.listdir(dir_v)):
            c = os.path.join(dir_v, d, "visual.json")
            v = json.load(open(c, encoding="utf-8"))
            if v["position"]["x"] >= 280:
                continue
            t = v["visual"]["visualType"]
            if t in {"slicer", "listSlicer", "textSlicer", "advancedSlicerVisual"}:
                q = v["visual"]["query"]["queryState"]
                ref = [pr["queryRef"] for b in q.values() for pr in b["projections"]][0]
                slicers.append((c, v, ref))
            elif t == "textbox" and v["name"] not in nomes_menu and v["position"]["y"] > 400:
                rotulos.append((c, v))

        slicers.sort(key=lambda t: PREFERENCIA.index(t[2]) if t[2] in PREFERENCIA else 99)

        yy = max(fim_menu, 512)
        for i, (c, v, ref) in enumerate(slicers):
            v["position"].update({"x": 16, "y": yy, "width": 248, "height": 52})
            json.dump(v, open(c, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            if i < len(rotulos):
                cr, vr = rotulos[i]
                vr["position"].update({"x": 20, "y": yy - 26, "width": 240, "height": 22})
                vr["visual"]["objects"]["general"][0]["properties"]["paragraphs"] = [
                    {"textRuns": [{"value": NOMES.get(ref, ref.split(".")[-1].upper()),
                                   "textStyle": {"color": MUTED, "fontSize": "8pt",
                                                 "fontFamily": "Consolas"}}],
                     "horizontalTextAlignment": "left"}]
                json.dump(vr, open(cr, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            yy += 80

        print(f"{atual:26} menu com {len([e for e in elementos if e[0]=='botao'])} botoes · "
              f"{len(slicers)} segmentacoes reposicionadas")

    print(f"\n{criados} elementos de menu gravados")
