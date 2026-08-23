# -*- coding: utf-8 -*-
"""Corrige medidas de previsao no TMDL e ajusta os visuais das duas paginas novas."""
import json
import os
import re
import sys
import uuid

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
MODEL = os.path.join(ROOT, "Projeto.SemanticModel", "definition")
PAGES = os.path.join(ROOT, "Projeto.Report", "definition", "pages")
NS = uuid.UUID("6f1d5b7e-0000-4000-8000-a1b0c2d4e6f8")
PAG_PREVISAO = "a1f0c2d4e6b8a0c2e4f6"
PAG_RISCO = "b2e1d3c5f7a9b1d3e5a7"

# ---------------------------------------------------------------- medidas
CORRIGIDAS = {
    "Previsto": (
        'IF (\n    ISFILTERED ( fPrevisoes[Escopo] ),\n    SUM ( fPrevisoes[Previsto] ),\n'
        '    CALCULATE ( SUM ( fPrevisoes[Previsto] ), fPrevisoes[Escopo] = "ALL" )\n)',
        "#,0", "Soma dos valores previstos. Sem escopo selecionado usa ALL, porque ALL ja contem P2 e P3."),
    "Realizado no backtest": (
        'IF (\n    ISFILTERED ( fPrevisoes[Escopo] ),\n    SUM ( fPrevisoes[Realizado] ),\n'
        '    CALCULATE ( SUM ( fPrevisoes[Realizado] ), fPrevisoes[Escopo] = "ALL" )\n)',
        "#,0", "Valor real observado nas linhas de backtest. Sem escopo selecionado usa ALL."),
    "Previsão D+1": (
        'VAR EscopoAtivo =\n    IF ( ISFILTERED ( fPrevisoes[Escopo] ), SELECTEDVALUE ( fPrevisoes[Escopo], "ALL" ), "ALL" )\n'
        'VAR Ult =\n    CALCULATE ( MAX ( fPrevisoes[Data] ), fPrevisoes[Horizonte] = "D+1", fPrevisoes[Escopo] = EscopoAtivo, REMOVEFILTERS ( dCalendario ) )\n'
        'RETURN\n    CALCULATE ( SUM ( fPrevisoes[Previsto] ), fPrevisoes[Horizonte] = "D+1", fPrevisoes[Escopo] = EscopoAtivo, fPrevisoes[Data] = Ult, REMOVEFILTERS ( dCalendario ) )',
        "#,0", "Previsao mais recente para o horizonte de um dia. Sem escopo selecionado usa ALL."),
    "Previsão D+7": (
        'VAR EscopoAtivo =\n    IF ( ISFILTERED ( fPrevisoes[Escopo] ), SELECTEDVALUE ( fPrevisoes[Escopo], "ALL" ), "ALL" )\n'
        'VAR Ult =\n    CALCULATE ( MAX ( fPrevisoes[Data] ), fPrevisoes[Horizonte] = "D+7", fPrevisoes[Escopo] = EscopoAtivo, REMOVEFILTERS ( dCalendario ) )\n'
        'RETURN\n    CALCULATE ( SUM ( fPrevisoes[Previsto] ), fPrevisoes[Horizonte] = "D+7", fPrevisoes[Escopo] = EscopoAtivo, fPrevisoes[Data] = Ult, REMOVEFILTERS ( dCalendario ) )',
        "#,0", "Previsao mais recente para o horizonte de sete dias. Sem escopo selecionado usa ALL."),
    "Erro absoluto médio": (
        'VAR ComFiltro =\n    AVERAGEX ( FILTER ( fPrevisoes, NOT ISBLANK ( fPrevisoes[Realizado] ) ), ABS ( fPrevisoes[Previsto] - fPrevisoes[Realizado] ) )\n'
        'VAR SomenteALL =\n    CALCULATE ( AVERAGEX ( FILTER ( fPrevisoes, NOT ISBLANK ( fPrevisoes[Realizado] ) ), ABS ( fPrevisoes[Previsto] - fPrevisoes[Realizado] ) ), fPrevisoes[Escopo] = "ALL" )\n'
        'RETURN\n    IF ( ISFILTERED ( fPrevisoes[Escopo] ), ComFiltro, SomenteALL )',
        "#,0.0", "Erro medio absoluto nas linhas de backtest. Compare com a Media realizada no backtest."),
    "Dias avaliados no backtest": (
        'VAR ComFiltro =\n    COUNTROWS ( FILTER ( fPrevisoes, NOT ISBLANK ( fPrevisoes[Realizado] ) ) )\n'
        'VAR SomenteALL =\n    CALCULATE ( COUNTROWS ( FILTER ( fPrevisoes, NOT ISBLANK ( fPrevisoes[Realizado] ) ) ), fPrevisoes[Escopo] = "ALL" )\n'
        'RETURN\n    IF ( ISFILTERED ( fPrevisoes[Escopo] ), ComFiltro, SomenteALL )',
        "#,0", "Linhas de previsao que ja tem valor real para comparar. Sem escopo selecionado usa ALL."),
}

NOVAS = [
    ("Média realizada no backtest", "DIVIDE ( [Realizado no backtest], [Dias avaliados no backtest] )",
     "#,0.0", "08 Previsão", "Media de incidentes por dia na janela de backtest. E a base de comparacao do erro."),
    ("Erro relativo", "DIVIDE ( [Erro absoluto médio], [Média realizada no backtest] )",
     "0.0%", "08 Previsão", "Erro medio dividido pela media realizada. Diz o tamanho do erro frente ao volume."),
]


def corrigir_medidas(caminho):
    linhas = open(caminho, encoding="utf-8").read().split("\n")
    saida, i, trocadas = [], 0, 0
    while i < len(linhas):
        l = linhas[i]
        m = re.match(r"^\tmeasure '([^']+)' = (.*)$|^\tmeasure '([^']+)' =\s*$", l)
        nome = (m.group(1) or m.group(3)) if m else None
        if nome in CORRIGIDAS:
            expr, fmt, doc = CORRIGIDAS[nome]
            # remove a doc anterior, se houver
            if saida and saida[-1].startswith("\t/// "):
                saida.pop()
            saida.append(f"\t/// {doc}")
            saida.append(f"\tmeasure '{nome}' =")
            for e in expr.split("\n"):
                saida.append("\t\t\t" + e)
            # pula o corpo antigo e recupera as propriedades
            i += 1
            while i < len(linhas) and (linhas[i].startswith("\t\t\t") or
                                       (linhas[i].startswith("\t\t") and ":" not in linhas[i])):
                i += 1
            props = []
            while i < len(linhas) and linhas[i].startswith("\t\t") and ":" in linhas[i]:
                p = linhas[i]
                if p.strip().startswith("formatString:"):
                    p = f"\t\tformatString: {fmt}"
                props.append(p)
                i += 1
            saida.extend(props)
            trocadas += 1
            continue
        saida.append(l)
        i += 1
    return "\n".join(saida), trocadas


if __name__ == "__main__":
    caminho = os.path.join(MODEL, "tables", "_Medidas.tmdl")
    texto, n = corrigir_medidas(caminho)

    for nome, expr, fmt, pasta, doc in NOVAS:
        if f"measure '{nome}'" not in texto:
            bloco = [f"\t/// {doc}", f"\tmeasure '{nome}' = {expr}"]
            if fmt:
                bloco.append(f"\t\tformatString: {fmt}")
            bloco.append(f"\t\tdisplayFolder: {pasta}")
            bloco.append(f"\t\tlineageTag: {uuid.uuid5(NS, 'm-' + nome)}")
            texto = texto.rstrip("\n") + "\n\n" + "\n".join(bloco) + "\n"

    open(caminho, "w", encoding="utf-8").write(texto)
    print(f"{n} medidas corrigidas, {len(NOVAS)} acrescentadas")

    # ---------------------------------------------------------------- visuais
    trocas_card = {
        "_Medidas.Dias avaliados no backtest": ("_Medidas[Média realizada no backtest]", "Média realizada"),
        "_Medidas.Média diária": ("_Medidas[Erro relativo]", "Erro relativo ao volume"),
    }
    ajustados = 0
    for pag in [PAG_PREVISAO, PAG_RISCO]:
        base = os.path.join(PAGES, pag, "visuals")
        for d in sorted(os.listdir(base)):
            p = os.path.join(base, d, "visual.json")
            v = json.load(open(p, encoding="utf-8"))
            mudou = False

            # subtitulo automatico desligado
            cont = v["visual"].setdefault("visualContainerObjects", {})
            if "subTitle" not in cont:
                cont["subTitle"] = [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
                mudou = True

            q = v["visual"].get("query", {}).get("queryState", {})
            for balde in q.values():
                for proj in balde["projections"]:
                    if proj["queryRef"] in trocas_card:
                        ref, titulo = trocas_card[proj["queryRef"]]
                        ent, prop = ref.split("[", 1)
                        prop = prop.rstrip("]")
                        proj["field"] = {"Measure": {"Expression": {"SourceRef": {"Entity": ent}},
                                                     "Property": prop}}
                        proj["queryRef"] = f"{ent}.{prop}"
                        proj["nativeQueryRef"] = prop
                        cont["title"] = [{"properties": {
                            "text": {"expr": {"Literal": {"Value": f"'{titulo}'"}}},
                            "show": {"expr": {"Literal": {"Value": "true"}}},
                            "fontSize": {"expr": {"Literal": {"Value": "11D"}}},
                            "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#A8A7B0'"}}}}},
                            "alignment": {"expr": {"Literal": {"Value": "'left'"}}}}}]
                        mudou = True
                        ajustados += 1

            if mudou:
                json.dump(v, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{ajustados} cartoes reapontados; subtitulo desligado nas duas paginas")

    # auto date/time desligado: o modelo ja tem dCalendario explicito
    cm = os.path.join(MODEL, "model.tmdl")
    mod = open(cm, encoding="utf-8").read()
    if "__PBI_TimeIntelligenceEnabled = 1" in mod:
        mod = mod.replace("__PBI_TimeIntelligenceEnabled = 1", "__PBI_TimeIntelligenceEnabled = 0")
        open(cm, "w", encoding="utf-8").write(mod)
        print("auto date/time desligado")
