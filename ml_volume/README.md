# Albus Hub — Frente de ML: Previsão de Volume de Incidentes (D+1 / D+7)

**Integrante 2 · disciplina Machine Learning.** Prevê o **volume diário de incidentes abertos**
para **D+1** (amanhã) e **D+7** (7 dias), nos recortes **ALL / P2 / P3**.
Versão: `volume_v2_2026-08-16`. Atualizado: 2026-08-16.

## TL;DR — deu certo?
Sim. Todos os 6 casos (3 recortes × 2 horizontes) **batem o baseline honesto** (naïve sazonal)
por **15 a 34%** de MAE, com features sem vazamento e avaliação temporal (walk-forward).

| Recorte | Horizonte | Melhor modelo | MAE | sMAPE | **Ganho vs naïve** | Cobertura intervalo* |
|---|---|---|---:|---:|---:|---:|
| ALL | D+1 | Ridge | 137 | 18% | **+34%** | 92% |
| ALL | D+7 | GBR   | 168 | 23% | +19% | 96% |
| P2  | D+1 | GBR   | 49  | 56% | +22% | 76% |
| P2  | D+7 | GBR   | 51  | 55% | +18% | 78% |
| P3  | D+1 | GBR   | 58  | 29% | +24% | 49% |
| P3  | D+7 | Ridge | 64  | 34% | +17% | 69% |

\* Cobertura empírica *fora da amostra* do intervalo 10–90% (nominal 80%). Ver seção Calibração.

## Previsão futura (a partir de 2025-12-31) — saída no contrato
| scope | horizonte | data | previsto | intervalo 10–90% |
|---|---|---|---:|---|
| ALL | D+1 | 2026-01-01 | 824 | 607 – 986 |
| ALL | D+7 | 2026-01-07 | 985 | 757 – 1292 |
| P2  | D+1 | 2026-01-01 | 86  | 25 – 163 |
| P2  | D+7 | 2026-01-07 | 77  | 12 – 151 |
| P3  | D+1 | 2026-01-01 | 397 | 336 – 503 |
| P3  | D+7 | 2026-01-07 | 245 | 156 – 341 |

## Modelos (a "escada")
`naïve sazonal` (régua) · `Poisson` · **`Poisson-offset`** · **`Ridge`** (linear interpretável) · `GBR`.
- **Ridge/GBR vencem** em todos os recortes.
- **Poisson-offset** (taxa por CI ativo, `sample_weight=exposição`) é a versão *estatisticamente correta*
  para contagem e **interpretável**: consertou a instabilidade do Poisson simples (P2 D+1 saltou de
  **−102%** para **+18%** de skill). Fica competitivo, sobretudo em P2, e é a base dos *drivers*.

## Por que funciona
1. **Baseline honesto primeiro:** o naïve sazonal ("amanhã = mesmo dia da semana passada") já é forte
   pela sazonalidade semanal. Só aceitamos modelo que o supere.
2. **O que o naïve não vê, o modelo vê:** o **nível recente** (`last`, `roll7`, `roll28`) e a **deriva**
   (`trend`, exposição de CIs) capturam a alta de dezembro e o crescimento do monitoramento → +15–34% MAE.
3. **Usa TODO o 2025 (dois regimes)** sem cair na quebra de set/2025: `CIs ativos (exposição)` entra como
   feature/offset (`corr(volume, CIs)=0,93`) — o modelo entende que o salto foi instrumentação, não incidente.
4. **Interpretável:** drivers (Poisson-offset, efeito na taxa por CI, ALL D+1) sobem com o nível recente
   (`r_roll7`, `r_last`) e **caem** no fim de semana, feriado e véspera de feriado.

## Cascatas pai→filho
Os maiores picos são **cascatas** (em 22/09 um pai gerou **630 filhos**; em 05/11, 510). A série "raiz"
(sem filhos) é mais estável. Tratamento: feature `child_last` + **intervalos** que absorvem os surtos
(imprevisíveis no *timing*). Filhos não entram no KPI (regra do dicionário).

## Calendário BR / notícias (honesto)
- **Dia da semana** domina (fim de semana: ALL −18%, P3 −34%, **P2 −55%**).
- **Feriado quase não afeta o volume bruto** (monitoramento é 24/7).
- **Apagões públicos não explicam os picos:** AWS (20/10) → dia *abaixo* do previsto; Cloudflare (18/11) →
  neutro. Os picos são cascatas internas. **Black Friday (28/11)** → leve alta (+16/dia).
- Só features **conhecíveis de antemão** (calendário, Black Friday) entram no modelo; apagões de terceiros
  ficam como anotação, não como feature (não são previsíveis).

## Calibração dos intervalos (validação de cobertura)
Medida fora da amostra (calibra em 60% do teste, mede em 40%; nominal 80%):
- **ALL D+1/D+7 = 92%/96%** → conservador (intervalo um pouco largo).
- **P2 D+1/D+7 = 76%/78%** → bem calibrado.
- **P3 D+1 = 49%** → **sub-cobre** (intervalo estreito demais): a volatilidade de dezembro é maior que a
  de set/out usada na calibração. **Correção recomendada:** intervalo *conformal*/adaptativo por volatilidade.

## Como está montado (sem vazamento)
- **Split temporal** + **backtest walk-forward** (treino expande dia a dia; teste = Set–Dez 2025).
- Toda feature "olha só para trás" (`shift(h)`); o calendário usa o **dia-alvo** (determinístico).
- Métricas: MAE, RMSE, sMAPE + *skill* vs naïve + **cobertura do intervalo**.

## Como rodar
```bash
python pipeline_volume.py     # treina, backtest, gera outputs/ e plots/
python predict.py             # imprime a previsão futura (contrato)
pip install streamlit && streamlit run app_streamlit.py   # painel do Bruno
```
```python
from predict import prever_volume
prever_volume(scope="P2", horizon="D+7")   # o Bruno chama assim, sem notebook
```

## Arquivos
- `pipeline_volume.py` — pipeline completo (dados→features→backtest→predições→modelos→gráficos).
- `predict.py` — **função de inferência** (Definition of Done da frente).
- `app_streamlit.py` — painel Streamlit pronto (integração do Bruno).
- `outputs/predictions_volume.csv|parquet` — predições no contrato (backtest + futuro).
- `outputs/metrics.json` — métricas + cobertura por recorte/horizonte/modelo.
- `outputs/drivers_ALL_D1.csv`, `plots/backtest_D1.png`, `plots/drivers_ALL_D1.png`.

## Contrato de saída (congelado)
`reference_date, horizon (D+1|D+7), scope (ALL|P2|P3), predicted_incidents,
actual_incidents (backtest), lower_bound, upper_bound, model, model_version, generated_at`.

## Limitações (declaradas)
- Regime pleno tem ~4 meses (Set–Dez): capta sazonalidade **semanal**, não anual.
- Previsões 2026 **extrapolam** → mais incerteza (por isso os intervalos).
- **Cascatas são imprevisíveis no timing** — o modelo acerta o nível típico, não o surto exato.
- **Intervalo de P3 D+1 sub-cobre (49%)** → próximo passo é conformal/adaptativo.

## Handoff para a frente de risco (Integrante 3 / score)
Mesmo dataset, alvo `KPI Violado?` (~1% positivo, severamente desbalanceado): classificação com
PR-AUC/recall + class weights + ANN. As features de **abertura** e o tratamento pai/filho já mapeados
aqui reaproveitam; `data/incidents.parquet` (cache) e o `pipeline_volume.py` servem de ponto de partida.
