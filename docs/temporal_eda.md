# Análise exploratória temporal da Locaweb

## Objetivo

A análise exploratória temporal avalia o comportamento histórico do volume
de incidentes da Locaweb antes da construção dos modelos de previsão D+1 e
D+7.

Os principais objetivos são:

1. identificar tendências de crescimento ou redução;
2. avaliar sazonalidade diária, semanal e mensal;
3. analisar separadamente P2 e P3;
4. identificar os maiores picos operacionais;
5. investigar a mudança de comportamento observada em setembro de 2025;
6. avaliar a participação de monitoramento e de incidentes sem intervenção;
7. produzir evidências para a divisão temporal entre treino, validação e teste;
8. preparar a engenharia de features de pressão operacional para o score de
   risco.

## Origem

A análise utiliza a tabela:

```text
data/gold/daily_incident_volume.parquet
```

Ela contém uma série diária contínua para os escopos:

```text
ALL
P2
P3
```

## Período analisado

O período disponível na base vai de:

```text
02/01/2023 a 31/12/2025
```

A maior parte dos registros está concentrada em 2025.

Essa concentração e a mudança de volume identificada no segundo semestre de
2025 precisam ser consideradas durante a modelagem.

## Variáveis analisadas

A análise utiliza:

- volume diário de incidentes;
- volume que entrou no KPI;
- volume com KPI violado;
- volume aberto por monitoramento;
- volume com status `Sem Intervenção`;
- prioridade;
- dia da semana;
- mês;
- médias móveis de 7 e 30 dias.

## Médias móveis

As médias móveis de 7 e 30 dias são usadas apenas para análise exploratória
e visualização de tendência.

Elas não são automaticamente consideradas features dos modelos.

Na futura engenharia de features, qualquer média móvel utilizada para prever
o dia `D` deverá ser calculada somente com dados disponíveis até `D-1`.

## Mudança de regime

A análise adota inicialmente:

```text
01/09/2025
```

como data de referência para comparar os regimes:

```text
before_2025_09
from_2025_09
```

Essa data foi escolhida devido ao aumento brusco de volume observado a partir
de setembro de 2025.

A comparação considera:

- quantidade de dias;
- volume total;
- média diária;
- mediana diária;
- desvio-padrão;
- percentil 95;
- maior volume diário;
- participação de monitoramento;
- participação de `Sem Intervenção`;
- P2 e P3 separadamente.

A data representa uma hipótese analítica inicial, e não uma regra definitiva
de negócio.

## Arquivos gerados

### Tabelas

```text
artifacts/eda/locaweb/daily_features.csv
artifacts/eda/locaweb/monthly_summary.csv
artifacts/eda/locaweb/weekday_summary.csv
artifacts/eda/locaweb/peak_days.csv
artifacts/eda/locaweb/regime_comparison.csv
```

### Gráficos

```text
artifacts/eda/locaweb/daily_volume.png
artifacts/eda/locaweb/monthly_volume.png
artifacts/eda/locaweb/rolling_means_all.png
artifacts/eda/locaweb/weekday_average.png
artifacts/eda/locaweb/operational_shares.png
```

### Relatório

```text
artifacts/eda/locaweb/temporal_eda_report.json
```

Os artefatos são gerados localmente e não devem ser enviados ao GitHub.

## Gráficos produzidos

### Volume diário

Compara os escopos `ALL`, `P2` e `P3` e destaca a referência de setembro de
2025.

### Volume mensal

Permite visualizar crescimento, redução e possíveis quebras estruturais.

### Médias móveis

Compara o volume total com as médias móveis de 7 e 30 dias.

### Dia da semana

Compara a média de incidentes por dia da semana para cada escopo.

### Participações operacionais

Avalia mensalmente a proporção de incidentes:

- abertos por monitoramento;
- encerrados como `Sem Intervenção`.

## Resultados observados

A comparação de regimes utiliza somente os dados de 2025:

```text
Regime anterior: 01/01/2025 a 31/08/2025
Regime atual: 01/09/2025 a 31/12/2025

## Cuidados para a modelagem

A divisão aleatória dos dados não será utilizada.

Os modelos deverão respeitar a ordem temporal dos registros, evitando que
informações futuras sejam utilizadas para prever períodos anteriores.

A estratégia deverá considerar:

1. treino em período histórico;
2. validação em período posterior;
3. teste no período mais recente;
4. comparação do desempenho antes e depois da mudança de regime;
5. avaliação separada de `ALL`, `P2` e `P3`.

A viabilidade de utilizar os registros anteriores a 2025 dependerá da
representatividade e compatibilidade deles com o regime operacional mais
recente.

## Relação com o score de risco

A análise temporal também apoia a futura criação da variável de pressão
operacional.

Entre as possíveis features estão:

- volume dos últimos 1, 7 e 30 dias;
- crescimento recente;
- desvio em relação à média histórica;
- volume recente por prioridade;
- volume recente por grupo responsável;
- volume recente por produto e categoria;
- previsão de volume D+1.

Para um incidente aberto no dia `D`, as agregações diárias utilizarão no
máximo informações disponíveis até `D-1`.

## Execução

Com a Gold diária disponível:

```bash
uv run python scripts/run_temporal_eda.py
```

A execução válida deve gerar:

```text
quality_status: passed
```

## Próximas decisões

Os resultados da análise serão utilizados para definir:

1. janela de treino;
2. janela de validação;
3. janela de teste;
4. necessidade de modelos separados por regime;
5. tratamento da quebra estrutural;
6. features sazonais;
7. baselines de previsão D+1 e D+7;
8. features futuras de pressão operacional.