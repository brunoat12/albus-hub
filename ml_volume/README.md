# Previsão de Volume de Incidentes — frente ML (Integrante 2)

Prevemos **quantos incidentes vão abrir amanhã (D+1) e daqui a 7 dias (D+7)**, por prioridade
(P1–P5) e no total (ALL), com **número + faixa de incerteza**.

**Versão:** `volume_v3.2_2026-08-21` · **Metodologia completa:** [`METODOLOGIA.md`](METODOLOGIA.md)
(dados, limpeza, EDA, comparações e o porquê de cada escolha).

---

## Resultado

**Protocolo:** o preditor é escolhido em **set–out/2025** e a nota sai em **nov–dez/2025 (61 dias
que não participaram da escolha)**. O ganho ("skill") é medido contra a **melhor** de três réguas
bobas — `naive7` (mesmo dia da semana passada), `media7` (média dos últimos 7 dias) e `ultimo`
(repete o último valor) — não contra a mais fraca.

| série | hor | preditor | tipo | MAE | sMAPE | **skill** | cobertura |
|---|---|---|---|---:|---:|---:|---:|
| ALL | D+1 | `ultimo` | régua simples | 76,6 | 10,3% | −4% | 77% |
| ALL | D+7 | GBR | modelo | 91,6 | 12,7% | **+13%** | 80% |
| P2 | D+1 | **Ridge** | modelo | 9,8 | 30,0% | **+16%** | 79% |
| P2 | D+7 | GBR | modelo | 10,0 | 30,9% | **+15%** | 79% |
| P3 | D+1 | GBR | modelo | 58,9 | 29,4% | −7% | 82% |
| P3 | D+7 | GBR | modelo | 62,1 | 30,8% | **+18%** | 79% |
| P4 | D+1 | `ultimo` | régua simples | 49,5 | 10,5% | +0% | 75% |
| P4 | D+7 | GBR | modelo | 66,2 | 14,3% | **+14%** | 84% |
| P5 | D+7 | GBR | modelo | 0,2 | *(ver nota)* | **+30%** | 82% |
| P1 | ambos | `naive7` | régua simples | 0,0 | — | n/a | 100% |

**Cobertura** = % de dias em que o real caiu dentro da faixa prevista (meta 80%).

### Como ler isso

- **Em D+7 o modelo ganha em todas as séries** (+13% a +30%). A 7 dias a regra trivial perde
  validade e as features (calendário, exposição, nível recente) passam a valer.
- **Em D+1 o modelo só ganha claramente no P2** (+16%). Em ALL e P4 — séries lisas — a regra
  trivial é imbatível, e o pipeline **entrega a regra trivial**. Isso é decisão de engenharia, não
  fracasso: `metrics.json` traz o MAE de todos os candidatos para auditar.
- **Mancha declarada:** no P3 D+1 a seleção escolheu GBR (−7%); o Ridge teria dado +16%. Errou
  porque 61 dias de seleção é pouco. Corrigir isso exigiria olhar o período da nota — o vício que
  o protocolo existe para eliminar. Fica registrado.
- **Versões anteriores anunciavam "+35%"**: era correto na aritmética, mas contra a régua fraca e
  com o modelo escolhido olhando o teste. Os números acima são menores e defensáveis.

## Previsão futura (a partir de 31/12/2025)

| série | D+1 (01/01) | D+7 (07/01) |
|---|---|---|
| ALL | 752 (635–900) | 889 (790–1092) |
| P2 | 29 (16–43) | 41 (25–60) |
| P3 | 395 (302–605) | 297 (207–528) |
| P4 | 367 (300–434) | 447 (367–559) |
| P5 | ~0 (0–1) | ~0 (0–1) |
| P1 | 0 | 0 |

*Nota P5:* série intermitente (quase sempre 0). O sMAPE explode por divisão perto de zero — **é
métrica sem sentido ali**; o número honesto é o MAE 0,2.

## Os três achados que sustentam tudo

1. **O salto de 7× em set/2025 não é aumento de incidente — é aumento de monitoramento.**
   Aberturas manuais caíram (0,77×), automáticas ×11,4, e a carga elegível a KPI ficou estável
   (0,85×). Volume bruto ×6,6, carga real estável.
2. **Os picos são cascatas, não crises.** Em 05/11 o P2 teve 684 incidentes — **510 eram filhos de
   uma única falha**. Contando eventos-raiz, o dia vira ~84. Deduplicar fez a previsibilidade do
   P2 saltar (acf1 de 0,05 → 0,32).
3. **Cada prioridade é um bicho diferente.** P2 é humana (cai 48% no fim de semana); **P4 é
   máquina** (força sazonal 0,03 — não sabe que é domingo). Foi isso que revelou que o baseline
   antigo era um espantalho para o P4.

## Como rodar

```bash
python pipeline_prioridades.py
```

```bash
python predict.py
```

```bash
streamlit run app_streamlit.py
```

```python
from predict import prever_volume
prever_volume(scope="P3", horizon="D+1")   # o BI / o app do time chamam assim
```

## Contrato de saída (congelado)

`reference_date, horizon (D+1|D+7), scope (ALL|P1..P5), predicted_incidents, actual_incidents,
lower_bound, upper_bound, model, model_version, generated_at`

## Arquivos

| Arquivo | O que é |
|---|---|
| `pipeline_prioridades.py` | pipeline **v3.2** — treina, faz backtest, gera tudo |
| `predict.py` | função de inferência (o time chama sem abrir notebook) |
| `app_streamlit.py` | painel |
| `METODOLOGIA.md` | **o documento**: dados, limpeza, EDA, comparações, decisões e limitações |
| `outputs/` | predições no contrato + `metrics.json` (MAE de todos os candidatos) |
| `plots/backtest_v32_D1.png` | previsto vs real com intervalo |
| `data/incidents.parquet` | dado tratado |

## Limitações (resumo — detalhe em METODOLOGIA §11)

Regime pleno tem ~4 meses → capta sazonalidade semanal, não anual · janela de seleção curta
(61 dias) · storms de cascata são imprevisíveis no *timing* · previsões para 2026 extrapolam ·
séries superdispersas têm teto de acerto.

## Próximos passos

- Avaliar jan–ago com **erro relativo** (adimensional) como teste de robustez no regime antigo.
- Croston (demanda intermitente) para P5, se o negócio quiser.
- Handoff para a frente de **risco/score** (Integrante 3): mesmo dado tratado, alvo `KPI Violado?`.
- Plugar `prever_volume()` no app do time / Power BI.
