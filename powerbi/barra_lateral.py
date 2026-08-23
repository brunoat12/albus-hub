# -*- coding: utf-8 -*-
"""Reorganiza as paginas do relatorio em torno de uma barra lateral de navegacao."""
import hashlib
import json
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
PAGES = os.path.join(ROOT, "Projeto.Report", "definition", "pages")

SCHEMA = ("https://developer.microsoft.com/json-schemas/fabric/item/report/"
          "definition/visualContainer/2.7.0/schema.json")

LARGURA = 1920
ALTURA = 1080
BARRA = 280
MARGEM = 24
CONTEUDO_X = BARRA + MARGEM              # 304
CONTEUDO_W = LARGURA - CONTEUDO_X - MARGEM  # 1592

ANTIGO_X, ANTIGO_W = 40, 1840
ESCALA = CONTEUDO_W / ANTIGO_W

RAIL = "#060608"
LINHA = "#2A2932"
INK = "#F5F5F7"
INK2 = "#A8A7B0"
MUTED = "#6E6D78"
BRAND = "#E30613"

CONTEXTO = {"_Medidas.Rótulo do período", "_Medidas.Versão da previsão"}


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


def base(seed, tipo, x, y, w, h, z, objects=None, cont=None, botao=False):
    v = {"$schema": SCHEMA, "name": vid(seed),
         "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
         "visual": {"visualType": tipo, "drillFilterOtherVisuals": True}}
    if objects:
        v["visual"]["objects"] = objects
    v["visual"]["visualContainerObjects"] = cont if cont else {
        "title": [{"properties": {"show": b_lit(False)}}],
        "subTitle": [{"properties": {"show": b_lit(False)}}],
    }
    if botao:
        v["howCreated"] = "InsertVisualButton"
    return v


def fundo_barra(pagina):
    return base(f"rail-bg-{pagina}", "shape", 0, 0, BARRA, ALTURA, 0, objects={
        "shape": [{"properties": {"tileShape": s_lit("rectangle")}}],
        "fill": [{"properties": {"show": b_lit(True), "fillColor": cor(RAIL),
                                 "transparency": n_lit(0)}}],
        "outline": [{"properties": {"show": b_lit(False)}}],
    })


def texto(seed, x, y, w, h, z, paragrafos):
    return base(seed, "textbox", x, y, w, h, z, objects={
        "general": [{"properties": {"paragraphs": paragrafos}}]
    })


def marca(pagina):
    return texto(f"rail-marca-{pagina}", 20, 26, 240, 74, 1, [
        {"textRuns": [{"value": "ALBUSHUB",
                       "textStyle": {"color": INK, "fontSize": "17pt", "fontWeight": "bold",
                                     "fontFamily": "Segoe UI"}}],
         "horizontalTextAlignment": "left"},
        {"textRuns": [{"value": "AIOPS · LOCAWEB",
                       "textStyle": {"color": MUTED, "fontSize": "8pt",
                                     "fontFamily": "Consolas"}}],
         "horizontalTextAlignment": "left"},
    ])


def rotulo(seed, x, y, w, texto_rotulo, z):
    return texto(seed, x, y, w, 24, z, [
        {"textRuns": [{"value": texto_rotulo,
                       "textStyle": {"color": MUTED, "fontSize": "8pt",
                                     "fontFamily": "Consolas"}}],
         "horizontalTextAlignment": "left"},
    ])


def navegador(pagina):
    return base(f"rail-nav-{pagina}", "pageNavigator", 12, 138, 256, 300, 3, objects={
        "shape": [{"properties": {"tileShape": s_lit("rectangle"), "roundedCornerRadius": n_lit(3)}}],
        "fill": [{"properties": {"show": b_lit(True), "fillColor": cor(RAIL)}}],
        "text": [{"properties": {"fontColor": cor(INK2), "fontSize": n_lit(11),
                                 "horizontalAlignment": s_lit("left")}}],
        "outline": [{"properties": {"show": b_lit(False)}}],
    }, botao=True)


def remapear(v, deslocamento_y):
    p = v["position"]
    p["x"] = round(CONTEUDO_X + (p["x"] - ANTIGO_X) * ESCALA)
    p["width"] = max(80, round(p["width"] * ESCALA))
    if p["y"] >= 120:
        p["y"] = max(0, p["y"] - deslocamento_y)
    p["z"] = p["z"] + 10
    p["tabOrder"] = p["z"]
    return v


def eh_slicer(v):
    return v["visual"]["visualType"] in {"slicer", "listSlicer", "textSlicer", "advancedSlicerVisual"}


def refs(v):
    q = v["visual"].get("query", {}).get("queryState", {})
    return {p["queryRef"] for b in q.values() for p in b["projections"]}


def processar(pagina):
    dir_visuais = os.path.join(PAGES, pagina, "visuals")
    arquivos = sorted(os.listdir(dir_visuais))
    visuais = []
    for d in arquivos:
        caminho = os.path.join(dir_visuais, d, "visual.json")
        visuais.append((caminho, json.load(open(caminho, encoding="utf-8"))))

    # ja processada? (existe o fundo da barra)
    if any(v["name"] == vid(f"rail-bg-{pagina}") for _, v in visuais):
        return 0, 0, True

    slicers = [(c, v) for c, v in visuais if eh_slicer(v)]
    # numa pagina com segmentacoes, a faixa y<120 e a tira de contexto por construcao
    contexto = ([(c, v) for c, v in visuais if not eh_slicer(v) and v["position"]["y"] < 120]
                if slicers else [])
    movidos = {id(v) for _, v in slicers} | {id(v) for _, v in contexto}
    resto = [(c, v) for c, v in visuais if id(v) not in movidos]

    deslocamento = 80 if slicers else 0

    # empilha as segmentacoes na barra
    y = 470
    for i, (c, v) in enumerate(slicers):
        titulo = (v["visual"].get("visualContainerObjects", {}).get("title", [{}])[0]
                  .get("properties", {}).get("text", {}).get("expr", {})
                  .get("Literal", {}).get("Value", "'Filtro'")).strip("'")
        v["position"].update({"x": 16, "y": y, "width": 248, "height": 52, "z": 4 + i,
                              "tabOrder": 4 + i})
        cont = v["visual"].setdefault("visualContainerObjects", {})
        cont["title"] = [{"properties": {"show": b_lit(False)}}]
        cont["subTitle"] = [{"properties": {"show": b_lit(False)}}]
        json.dump(v, open(c, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        # rotulo acima da segmentacao
        extras.append((pagina, rotulo(f"rail-lbl-{pagina}-{i}", 20, y - 22, 240, titulo.upper(), 4 + i)))
        y += 74

    # contexto no rodape da barra
    yc = ALTURA - 120
    for i, (c, v) in enumerate(contexto):
        v["position"].update({"x": 16, "y": yc, "width": 248, "height": 44, "z": 8 + i,
                              "tabOrder": 8 + i})
        cont = v["visual"].setdefault("visualContainerObjects", {})
        cont["title"] = [{"properties": {"show": b_lit(False)}}]
        cont["subTitle"] = [{"properties": {"show": b_lit(False)}}]
        obj = v["visual"].setdefault("objects", {})
        obj["labels"] = [{"properties": {"fontSize": n_lit(9), "color": cor(MUTED)}}]
        obj["categoryLabels"] = [{"properties": {"show": b_lit(False)}}]
        json.dump(v, open(c, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        yc += 50

    for c, v in resto:
        remapear(v, deslocamento)
        v["visual"].setdefault("visualContainerObjects", {}).setdefault(
            "subTitle", [{"properties": {"show": b_lit(False)}}])
        json.dump(v, open(c, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    extras.append((pagina, fundo_barra(pagina)))
    extras.append((pagina, marca(pagina)))
    extras.append((pagina, navegador(pagina)))
    extras.append((pagina, rotulo(f"rail-lbl-nav-{pagina}", 20, 116, 240, "PÁGINAS", 2)))

    return len(slicers), len(resto), False


if __name__ == "__main__":
    extras = []
    ordem = json.load(open(os.path.join(PAGES, "pages.json"), encoding="utf-8"))["pageOrder"]
    for pagina in ordem:
        nome = json.load(open(os.path.join(PAGES, pagina, "page.json"), encoding="utf-8"))["displayName"]
        ns, nr, ja = processar(pagina)
        if ja:
            print(f"{nome:26} já tinha barra lateral, pulei")
        else:
            print(f"{nome:26} {ns} segmentações movidas · {nr} visuais remapeados")

    for pagina, v in extras:
        d = os.path.join(PAGES, pagina, "visuals", v["name"])
        os.makedirs(d, exist_ok=True)
        json.dump(v, open(os.path.join(d, "visual.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    print(f"\n{len(extras)} elementos de barra lateral criados")
