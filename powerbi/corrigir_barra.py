# -*- coding: utf-8 -*-
"""Conserta preenchimento das formas e texto dos botoes da barra lateral.

O Power BI so aplica fill/text/outline em formas e botoes quando o objeto traz
selector {id: "default"} — o estado visual. Sem ele, cai no padrao do tema.
Margens usam sufixo L (inteiro), tamanhos de fonte usam D (double).
"""
import json
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
PAGES = os.path.join(ROOT, "Projeto.Report", "definition", "pages")

RAIL = "#060608"
ATIVO = "#101014"
BRAND = "#E30613"
INK = "#F5F5F7"
INK2 = "#A8A7B0"

PADRAO = {"id": "default"}


def s_lit(t):
    return {"expr": {"Literal": {"Value": f"'{t}'"}}}


def b_lit(f):
    return {"expr": {"Literal": {"Value": "true" if f else "false"}}}


def d_lit(n):
    return {"expr": {"Literal": {"Value": f"{n}D"}}}


def l_lit(n):
    return {"expr": {"Literal": {"Value": f"{n}L"}}}


def cor(h):
    return {"solid": {"color": s_lit(h)}}


def preencher(hexcode):
    return [{"properties": {"fillColor": cor(hexcode)}, "selector": dict(PADRAO)}]


def sem_contorno():
    return [{"properties": {"show": b_lit(False)}, "selector": dict(PADRAO)}]


def texto_botao(rotulo, ativo):
    return [{
        "properties": {
            "show": b_lit(True),
            "text": s_lit(rotulo),
            "fontColor": cor(INK if ativo else INK2),
            "fontSize": d_lit(11),
            "horizontalAlignment": s_lit("left"),
            "verticalAlignment": s_lit("middle"),
            "leftMargin": l_lit(14),
        },
        "selector": dict(PADRAO),
    }]


def rotulo_do_botao(v):
    props = v["visual"].get("objects", {}).get("text", [{}])[0].get("properties", {})
    valor = props.get("text", {}).get("expr", {}).get("Literal", {}).get("Value", "")
    return valor.strip("'")


def esta_ativo(v):
    props = v["visual"].get("objects", {}).get("fill", [{}])[0].get("properties", {})
    c = props.get("fillColor", {}).get("solid", {}).get("color", {})
    return c.get("expr", {}).get("Literal", {}).get("Value", "").strip("'").upper() == ATIVO


if __name__ == "__main__":
    ordem = json.load(open(os.path.join(PAGES, "pages.json"), encoding="utf-8"))["pageOrder"]
    formas = botoes = 0

    for pid in ordem:
        dir_v = os.path.join(PAGES, pid, "visuals")
        for d in sorted(os.listdir(dir_v)):
            c = os.path.join(dir_v, d, "visual.json")
            v = json.load(open(c, encoding="utf-8"))
            p, tipo = v["position"], v["visual"]["visualType"]
            if p["x"] >= 280:
                continue
            obj = v["visual"].setdefault("objects", {})

            if tipo == "shape":
                # fundo da barra (alto) ou acento da pagina ativa (estreito)
                alvo = BRAND if p["width"] < 8 else RAIL
                obj["shape"] = [{"properties": {"tileShape": s_lit("rectangle")}}]
                obj["fill"] = preencher(alvo)
                obj["outline"] = sem_contorno()
                formas += 1

            elif tipo == "actionButton":
                rotulo = rotulo_do_botao(v)
                ativo = esta_ativo(v)
                acao = obj.get("action")
                obj.clear()
                obj["text"] = texto_botao(rotulo, ativo)
                obj["fill"] = preencher(ATIVO if ativo else RAIL)
                obj["outline"] = sem_contorno()
                if acao:
                    obj["action"] = acao
                botoes += 1
            else:
                continue

            json.dump(v, open(c, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"{formas} formas e {botoes} botoes corrigidos")
