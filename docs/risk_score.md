# Modelo de risco OLA/KPI

## Objetivo

Estimar, no momento da abertura, a probabilidade de um incidente elegível
violar o KPI/OLA e transformá-la em um score operacional de 0 a 100 compatível
com o Streamlit.

## Fonte e população

- Fonte canônica: `data/silver/locaweb_incidents.parquet`.
- Registros totais: 122.543.
- População de treino: `entered_kpi_source == True`.
- Incidentes elegíveis: 25.600.
- Target: `kpi_breached_source`.
- Positivos: 248.
- Negativos: 25.352.
- Taxa positiva: 0,96875%.
- Período de abertura: 02/01/2023 a 31/12/2025.

Os indicadores fornecidos pela empresa são a fonte oficial. Divergências com
as regras recalculadas de auditoria não alteram a população nem o target.

## Prevenção de leakage

As features permitidas e proibidas estão declaradas em
`src/albus_hub/models/risk/contracts.py` e validadas antes do treino.

Campos pós-desfecho como resolução, encerramento, duração, status final,
solução e o próprio target nunca entram na matriz do modelo.

Contagens de carga usam somente incidentes com `opened_at` estritamente menor
que a abertura corrente. Timestamps simultâneos não enxergam uns aos outros.

A taxa histórica de violação da equipe usa somente incidentes cujo
`closed_at` é anterior à abertura corrente. O horário de fechamento serve como
relógio de disponibilidade do histórico e não como predictor do incidente
corrente.

## Features

Contexto disponível na abertura:

- prioridade;
- produto, categoria e subcategoria;
- equipe designada;
- item de configuração;
- origem da abertura;
- hora, dia da semana, mês e indicador de fim de semana.

Histórico estritamente anterior:

- carga da equipe em 1, 7 e 30 dias;
- quantidade e taxa de violações conhecidas da equipe em 30 dias;
- volume anterior em 7 dias por produto, categoria e prioridade.

Categorias nulas recebem marcador explícito, categorias novas são aceitas e
variáveis de alta cardinalidade usam agrupamento do encoder com no máximo 100
categorias por feature. A matriz final possui 377 colunas.

## Avaliação temporal

O split é cronológico 60%/20%/20%:

| Janela | Registros | Positivos | Período |
|---|---:|---:|---|
| Treino | 15.360 | 165 | 02/01/2023 a 26/07/2025 |
| Validação | 5.120 | 33 | 26/07/2025 a 01/10/2025 |
| Teste | 5.120 | 50 | 01/10/2025 a 31/12/2025 |

O teste não participa de ajuste de arquitetura, calibração ou threshold.

## Baseline e clusterização

A regressão logística com pesos de classe obteve no teste:

- PR-AUC: 0,0087;
- ROC-AUC: 0,4729;
- Recall no threshold 0,50: 92%;
- Precision no threshold 0,50: 1,21%.

Foram avaliados K-Means com 2 a 5 clusters. O melhor silhouette foi 0,1723
com dois clusters. Adicionar o cluster ao baseline reduziu ligeiramente o
PR-AUC de validação de 0,008778 para 0,008748. Portanto, o cluster não entra no
modelo final.

## ANN

Foram comparadas duas configurações:

1. Dense 64 → Dropout 0,25 → Dense 32 → Dropout → Sigmoid;
2. Dense 128 → Dropout 0,30 → Dense 64 → Dropout → Dense 32 → Dropout → Sigmoid.

Ambas usam binary cross-entropy, Adam, class weights, batch 256,
ReduceLROnPlateau e EarlyStopping por PR-AUC de validação.

A rede 64–32 foi selecionada:

- 14 épocas executadas;
- PR-AUC de validação: 0,0582;
- arquitetura 128–64–32: PR-AUC de validação 0,0409.

Após calibração de Platt na validação, o teste temporal obteve:

| Métrica | Resultado |
|---|---:|
| PR-AUC | 0,0726 |
| ROC-AUC | 0,8610 |
| Brier score | 0,00950 |
| Recall | 90,00% |
| Precision | 2,28% |
| F1 | 0,0444 |
| Verdadeiros positivos | 45 |
| Falsos negativos | 5 |
| Falsos positivos | 1.933 |
| Verdadeiros negativos | 3.137 |

O threshold selecionado na validação é 0,007790. A política exige recall de
pelo menos 70% e maximiza a precisão entre os candidatos elegíveis. Como a
classe é extremamente rara, thresholds genéricos 0,30–0,60 não identificam
positivos na validação.

## Score operacional

O score preserva três componentes auditáveis:

```text
risk_score = round(
    100 × (
        0,70 × breach_probability
        + 0,20 × priority_impact
        + 0,10 × operational_pressure
    )
)
```

O impacto da prioridade usa P1=1,00, P2=0,80, P3=0,60, P4=0,30 e P5=0,10.
A pressão operacional usa a carga anterior de 24 horas da equipe dividida pelo
percentil 95 do treino, com limite entre 0 e 1.

No teste, os scores variam de 12 a 37:

- 4.335 incidentes `baixo`;
- 785 incidentes `moderado`;
- nenhum `alto` ou `crítico`.

Isso não é erro de contrato. É consequência da combinação de probabilidades
calibradas baixas com as faixas provisórias 0–24/25–49/50–74/75–100. As faixas
não devem ser forçadas para fabricar alertas; devem ser recalibradas com a
operação e versionadas.

## Explicabilidade e recomendação

`top_risk_factors` é produzido por perturbação local: cada feature é levada ao
valor de referência do treino e mede-se a queda da probabilidade calibrada.
Assim, os fatores permanecem conectados à ANN e não são frases inventadas.

A recomendação é determinística por nível de risco e fica separada do modelo.

## Execução

```bash
uv sync
uv run python scripts/train_risk_model.py
uv run python scripts/generate_risk_scores.py
uv run python scripts/build_risk_notebook.py
uv run python scripts/execute_risk_notebook.py
uv run pytest
uv run ruff check .
```

O `pyproject.toml` declara as novas dependências do modelo. Neste ambiente, a
regeneração do `uv.lock` foi interrompida porque o índice configurado entregou
um arquivo de `duckdb==1.5.4` com hash diferente do esperado. O hash não foi
ignorado nem atualizado automaticamente. Antes do merge, regenere o lock em
um índice confiável e revise a alteração produzida.

## Limitações

- Há somente 248 positivos em toda a base.
- A cobertura da população elegível muda fortemente em 2025.
- A calibração contém apenas 33 positivos de validação.
- O threshold de alto recall gera muitos falsos positivos.
- Probabilidade, threshold de classificação, score e nível são conceitos
  diferentes e não devem ser tratados como equivalentes.
- Antes de produção, é necessário validar capacidade de alertas, drift,
  estabilidade da calibração e faixas de risco com a operação.
