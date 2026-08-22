# Previsão de Volume de Incidentes — resultados (frente ML, Integrante 2)

**O que é:** prevemos **quantos incidentes** vão abrir **amanhã (D+1)** e **daqui a 7 dias (D+7)**,
**por prioridade** (P1–P5) e no total (ALL). Versão atual: **v3.1** (`volume_v3.1_2026-08-21`).
Para entender *como* e *por quê*, leia o `METODOLOGIA.md`. Atualizado: 2026-08-21.

## O que mudou (e por que é melhor)
1. **v3 — Contamos eventos, não alarmes** (deduplicação de cascatas — ver METODOLOGIA §2). Isso
   limpou as séries: em P2 o erro caiu de **~56% para ~31%** (sMAPE).
2. **v3 — Um modelo por prioridade** (cada uma se comporta diferente).
3. **v3.1 — Faixa de incerteza que se ajusta sozinha** (*intervalo conformal adaptativo*,
   METODOLOGIA §6b). Antes a faixa tinha largura fixa e desafinava; agora **todas as séries
   ficam em 77–82% de cobertura** (meta 80%) — e em várias a faixa ainda **encolheu**.

## Resultado (backtest honesto, Set–Dez 2025)
"Skill" = quanto melhor que a régua boba (naïve). "Cobertura" = % de dias em que o real caiu
dentro da faixa (meta **80%**); "largura" = tamanho médio da faixa, em incidentes.

| Prioridade | eventos/dia | Melhor modelo (D+1) | MAE D+1 | sMAPE D+1 | Skill D+1 | Cobert. D+1 | Cobert. D+7 |
|---|---:|---|---:|---:|---:|---:|---:|
| **ALL** (total) | 687 | Ridge | 102 | **16%** | **+35%** | 78% | 79% |
| **P2** Alta | 34 | Poisson-offset | 11 | 31% | +21% | 80% | 80% |
| **P3** Média | 182 | Ridge | 42 | 25% | +30% | 79% | **81%** |
| **P4** Baixa | 471 | Ridge | 87 | 20% | +35% | 80% | 82% |
| **P5** Muito Baixa | 0,2 | GBR | 0,2 | *(ver nota)* | +24% | 77% | 79% |
| **P1** Crítica | ~0 | naïve | 0,0 | — | n/a | 100% | 100% |

*(D+7 erra um pouco mais em todas, como esperado — prever mais longe é mais difícil; detalhes
em `outputs/metrics.json`.)*

### Efeito do intervalo conformal (v3.1) — cobertura antes → depois
| Série | Faixa fixa (v3) | Conformal (v3.1) | Largura fixa → conformal |
|---|---:|---:|---:|
| P3 D+7 | 74% | **81%** | 124 → 146 *(alargou onde faltava)* |
| P4 D+1 | 86% | **80%** | 250 → 239 *(apertou onde sobrava)* |
| ALL D+1 | 82% | 78% | 308 → **272** *(mais estreita, mesma confiança)* |
| P5 D+1 | 71% | **77%** | 1 → 1 |

> **Nota honesta:** o "51%" citado na versão anterior vinha de um protocolo mais duro (calibrar
> uma vez em 60% do período e nunca mais atualizar). Na tabela acima **as duas colunas usam o
> mesmo protocolo** (recalibrando todo dia com os últimos 60 dias), então a comparação é justa:
> parte do ganho vem de recalibrar sempre, parte do conformal em si.

## Previsão futura (a partir de 2025-12-31) — no contrato
| Prioridade | D+1 (01/01) | D+7 (07/01) |
|---|---|---|
| ALL | 721 (603–842) | 889 (790–1092) |
| P2 | 27 (14–40) | 41 (25–60) |
| P3 | 266 (204–367) | 183 (122–266) |
| P4 | 389 (304–434) | 447 (367–559) |
| P5 | ~0 (0–1) | ~0 (0–1) |
| P1 | 0 | 0 |

## Notas honestas por prioridade
- **P4** é a mais previsível (série lisa, "puxa" o valor recente) → +35%.
- **P3** vai bem em D+1 (+30%) e o **intervalo de D+7 foi corrigido no v3.1** (74% → 81%).
- **P2** melhorou muito com a deduplicação; o modelo de **contagem (Poisson-offset)** venceu, como esperado.
- **P5** é **intermitente** (quase sempre 0): o sMAPE dá ~196% porque dividir por zero explode — **é métrica sem sentido aqui**; o número honesto é o MAE 0,2 ("esperar ~0, às vezes 1").
- **P1** teve **1 evento no ano inteiro** → não há série; tratamos como **evento raro**.

## Como rodar
```bash
python pipeline_prioridades.py    # v3: treina, backtest, gera outputs/ e plots/
python predict.py                 # imprime a previsão futura (contrato)
pip install streamlit && streamlit run app_streamlit.py   # painel do Bruno
```
```python
from predict import prever_volume
prever_volume(scope="P3", horizon="D+1")   # o Bruno/BI chamam assim
```

## Arquivos
- `pipeline_prioridades.py` — **pipeline v3.1** (por prioridade, deduplicado, intervalo conformal).
- `pipeline_volume.py` — v2 (ALL/P2/P3, série crua) — mantido por histórico.
- `predict.py` — função de inferência (lê o contrato).
- `app_streamlit.py` — painel.
- `METODOLOGIA.md` — processo e porquê das escolhas (explicado para leigos).
- `outputs/` (predições no contrato + `metrics.json`) · `plots/backtest_v3_D1.png`.

## Contrato de saída (congelado)
`reference_date, horizon (D+1|D+7), scope (ALL|P1..P5), predicted_incidents,
actual_incidents, lower_bound, upper_bound, model, model_version, generated_at`.

## Próximos passos
- ~~Intervalo conformal/adaptativo~~ → **feito no v3.1** (todas as séries em 77–82%).
- Modelo de **demanda intermitente** dedicado para P5 (Croston), se o negócio quiser.
- Handoff para a frente de **risco/score** (Integrante 3): mesmo dado tratado, alvo `KPI Violado?`.
- Plugar `prever_volume()` no app/Power BI.
