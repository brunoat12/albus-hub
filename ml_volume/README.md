# Previsão de Volume de Incidentes — resultados (frente ML, Integrante 2)

**O que é:** prevemos **quantos incidentes** vão abrir **amanhã (D+1)** e **daqui a 7 dias (D+7)**,
**por prioridade** (P1–P5) e no total (ALL). Versão atual: **v3** (`volume_v3_2026-08-16`).
Para entender *como* e *por quê*, leia o `METODOLOGIA.md`. Atualizado: 2026-08-16.

## O que mudou no v3 (e por que é melhor)
1. **Contamos eventos, não alarmes** (deduplicação de cascatas — ver METODOLOGIA §2). Isso limpou
   as séries: em P2 o erro caiu de **~56% para ~31%** (sMAPE).
2. **Um modelo por prioridade** (cada uma se comporta diferente).

## Resultado (backtest honesto, Set–Dez 2025)
"Skill" = quanto melhor que a régua boba (naïve). "Cobertura" = % de vezes que o real caiu dentro da faixa (meta 80%).

| Prioridade | eventos/dia | Melhor modelo (D+1) | MAE D+1 | sMAPE D+1 | Skill D+1 | Cobertura |
|---|---:|---|---:|---:|---:|---:|
| **ALL** (total) | 687 | Ridge | 102 | **16%** | **+35%** | 94% |
| **P2** Alta | 34 | Poisson-offset | 11 | 31% | +21% | 88% |
| **P3** Média | 182 | Ridge | 42 | 25% | +30% | 69% |
| **P4** Baixa | 471 | Ridge | 87 | 20% | +35% | 92% |
| **P5** Muito Baixa | 0,2 | — | 0,2 | *(ver nota)* | — | — |
| **P1** Crítica | 0 | — | — | — | — | — |

*(D+7 fica um pouco pior em todas, como esperado — prever mais longe é mais difícil; detalhes em `outputs/metrics.json`.)*

## Previsão futura (a partir de 2025-12-31) — no contrato
| Prioridade | D+1 (01/01) | D+7 (07/01) |
|---|---|---|
| ALL | 721 (566–854) | 889 (788–1089) |
| P2 | 27 (7–40) | 41 (24–61) |
| P3 | 266 (211–340) | 183 (119–253) |
| P4 | 389 (259–482) | 447 (351–604) |
| P5 | ~0 (0–1) | ~0 (0–1) |
| P1 | 0 | 0 |

## Notas honestas por prioridade
- **P4** é a mais previsível (série lisa, "puxa" o valor recente) → +35%.
- **P3** vai bem em D+1 (+30%), mas o **intervalo de D+7 sub-cobre (51%)** → a corrigir com intervalo *conformal*.
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
- `pipeline_prioridades.py` — **pipeline v3** (por prioridade, deduplicado).
- `pipeline_volume.py` — v2 (ALL/P2/P3, série crua) — mantido por histórico.
- `predict.py` — função de inferência (lê o contrato).
- `app_streamlit.py` — painel.
- `METODOLOGIA.md` — processo e porquê das escolhas (explicado para leigos).
- `outputs/` (predições no contrato + `metrics.json`) · `plots/backtest_v3_D1.png`.

## Contrato de saída (congelado)
`reference_date, horizon (D+1|D+7), scope (ALL|P1..P5), predicted_incidents,
actual_incidents, lower_bound, upper_bound, model, model_version, generated_at`.

## Próximos passos
- Intervalo **conformal/adaptativo** (corrige a cobertura de P3 D+7).
- Modelo de **demanda intermitente** dedicado para P5 (Croston), se o negócio quiser.
- Handoff para a frente de **risco/score** (Integrante 3): mesmo dado tratado, alvo `KPI Violado?`.
