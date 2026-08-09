# Contratos de dados — Locaweb / Albus-Hub

## Fonte original

- Arquivo local: `data/raw/locaweb/LW-DATASET.xlsx`
- Planilha: `Dataset Geral`
- O arquivo original não deve ser enviado ao GitHub.

## Camada Bronze

Arquivo: `data/bronze/locaweb_incidents.parquet`

A Bronze preserva as 19 colunas originais e adiciona:

- `_source_file`
- `_source_row_number`
- `_ingested_at_utc`

## Camada Silver

Arquivo: `data/silver/locaweb_incidents.parquet`

| Fonte | Silver | Tipo / uso |
|---|---|---|
| Número | incident_id | string, chave única |
| Prioridade | priority_raw | string original |
| — | priority_code | inteiro 1 a 5 |
| — | priority_label | descrição da prioridade |
| Produto | product | string opcional |
| Categoria | category | string opcional |
| Subcategoria | subcategory | string opcional |
| Grupo designado | assigned_group | string obrigatório |
| Item de configuração | configuration_item | string opcional |
| Aberto | opened_at | datetime obrigatório |
| Resolvido | resolved_at | datetime opcional |
| Encerrado | closed_at | datetime obrigatório |
| Duração | duration_seconds | inteiro em segundos |
| — | duration_hours | duração convertida em horas |
| Código de fechamento | closure_code | string opcional |
| Descrição resumida | short_description | string obrigatório |
| Solução | solution_type | Contorno, Definitiva ou nulo |
| Aberto por | opened_by | Manual ou Monitoramento |
| Incidente Pai | parent_incident_id | string opcional |
| Status | status | domínio do dicionário |
| Entrou para KPI? | entered_kpi_raw | SIM ou NAO, preservado |
| — | entered_kpi_source | booleano derivado da fonte |
| KPI Violado? | kpi_breached_raw | SIM, NAO ou N/A, preservado |
| — | kpi_breached_source | booleano anulável |

A Silver também contém campos de auditoria de duração e das regras documentadas de KPI. Os campos recalculados não substituem os indicadores fornecidos pela empresa.

## Camada Gold de volume diário

A camada Gold de volume diário será construída a partir da camada Silver,
utilizando o campo `opened_at` como referência temporal.

Ela terá dois conjuntos de dados:

1. série diária contínua;
2. cortes por dimensões operacionais.

As prioridades P2 e P3 devem obrigatoriamente estar disponíveis de forma
separada.

### Série diária principal

Arquivo:

```text
data/gold/daily_incident_volume.parquet
```

A tabela terá uma linha por data e escopo de prioridade.

| Campo | Tipo | Regra |
|---|---|---|
| reference_date | date | Data de abertura do incidente |
| priority_scope | string | `ALL`, `P2` ou `P3` |
| incident_count | inteiro | Quantidade de incidentes abertos |
| entered_kpi_count | inteiro | Quantidade que entrou no KPI segundo a fonte |
| kpi_breach_count | inteiro | Quantidade com KPI violado segundo a fonte |
| monitoring_incident_count | inteiro | Quantidade aberta por monitoramento |
| no_intervention_count | inteiro | Quantidade com status `Sem Intervenção` |

A chave lógica da tabela será:

```text
reference_date + priority_scope
```

Não poderá existir mais de uma linha para a mesma combinação de data e
escopo de prioridade.

A série deverá conter todas as datas existentes entre a menor e a maior data
de abertura da base. Dias sem incidentes deverão ser representados com
contagens iguais a zero.

Os valores aceitos para `priority_scope` serão:

```text
ALL
P2
P3
```

O escopo `ALL` considera todas as prioridades. Os escopos `P2` e `P3`
consideram somente as respectivas prioridades.

Todas as colunas de contagem devem:

- ser inteiras;
- ser maiores ou iguais a zero;
- nunca ser nulas.

### Cortes operacionais

Arquivo:

```text
data/gold/daily_incident_breakdown.parquet
```

A tabela terá uma linha por data, dimensão, valor da dimensão e escopo de
prioridade.

| Campo | Tipo | Regra |
|---|---|---|
| reference_date | date | Data de abertura do incidente |
| dimension_name | string | Nome da dimensão analisada |
| dimension_value | string | Valor encontrado na dimensão |
| priority_scope | string | `ALL`, `P2` ou `P3` |
| incident_count | inteiro | Quantidade de incidentes |
| entered_kpi_count | inteiro | Quantidade que entrou no KPI |
| kpi_breach_count | inteiro | Quantidade com KPI violado |

Os valores aceitos para `dimension_name` serão:

```text
assigned_group
product
category
configuration_item
```

A chave lógica da tabela será:

```text
reference_date
+ dimension_name
+ dimension_value
+ priority_scope
```

Valores nulos das dimensões não serão excluídos da contagem. Na Gold, eles
serão representados por:

```text
__MISSING__
```

Essa substituição será feita somente na tabela agregada. Os valores nulos
originais continuarão preservados na camada Silver.

Os valores aceitos para `priority_scope` serão:

```text
ALL
P2
P3
```

Todas as colunas de contagem devem:

- ser inteiras;
- ser maiores ou iguais a zero;
- nunca ser nulas.

### Reconciliação da camada Gold

A soma de `incident_count` no escopo `ALL`, considerando uma linha por data
na tabela principal, deverá ser igual à quantidade total de registros
válidos da Silver.

Para cada data:

```text
incident_count de ALL
=
quantidade de incidentes abertos naquela data
```

Para os escopos específicos:

```text
incident_count de P2
=
quantidade de incidentes com priority_code igual a 2

incident_count de P3
=
quantidade de incidentes com priority_code igual a 3
```

As contagens de KPI devem utilizar os indicadores fornecidos pela empresa:

```text
entered_kpi_source
kpi_breached_source
```

As regras recalculadas de auditoria não deverão substituir esses campos.

## Consumidores da Gold de volume diário

A camada Gold de volume diário será utilizada por:

1. análise exploratória temporal;
2. modelos de previsão de volume D+1 e D+7;
3. dashboard operacional;
4. análise de P2 e P3;
5. identificação de picos operacionais;
6. engenharia de features de pressão operacional;
7. enriquecimento futuro do score de risco.

A Gold de volume representa fatos agregados. Ela não deverá conter:

- previsões;
- probabilidades;
- médias móveis prontas para todos os modelos;
- score de risco;
- classificação de risco;
- recomendações;
- resultados de inferência.

Esses elementos serão mantidos em tabelas próprias.

## Contrato para features de risco

Arquivo futuro:

```text
data/gold/risk_features.parquet
```

A tabela terá uma linha por incidente avaliado pelo modelo de risco.

O objetivo será reunir informações disponíveis no momento da abertura do
incidente e informações históricas anteriores à abertura.

### Identificação e contexto

Campos planejados:

| Campo | Tipo | Uso |
|---|---|---|
| incident_id | string | Identificador único do incidente |
| opened_at | datetime | Momento da abertura |
| priority_code | inteiro | Prioridade de 1 a 5 |
| product | string | Produto afetado |
| category | string | Categoria |
| subcategory | string | Subcategoria |
| assigned_group | string | Grupo responsável |
| configuration_item | string | Item de configuração |
| opened_by | string | Origem da abertura |

### Features temporais do incidente

Campos planejados:

```text
opened_hour
opened_day_of_week
opened_month
is_weekend
```

### Features históricas planejadas

Exemplos:

```text
assigned_group_incidents_previous_1d
assigned_group_incidents_previous_7d
assigned_group_incidents_previous_30d
assigned_group_average_previous_7d
assigned_group_average_previous_30d
assigned_group_breach_rate_previous_30d
product_incidents_previous_7d
category_incidents_previous_7d
priority_incidents_previous_7d
predicted_volume_d1
operational_pressure
```

Os nomes definitivos poderão ser ajustados durante a engenharia de features.

Toda feature histórica deverá utilizar somente dados anteriores ao incidente.

Quando a origem for uma tabela diária, o cálculo deverá considerar no máximo
o dia anterior:

```text
data da feature <= data de abertura - 1 dia
```

Caso seja criada alguma feature intradiária, ela deverá considerar somente
eventos com timestamp estritamente anterior a `opened_at`.

### População de treinamento

A população histórica inicial será:

```text
entered_kpi_source == True
```

O target será:

```text
kpi_breached_source
```

Os campos de target poderão existir na base de treinamento para avaliação,
mas nunca deverão ser fornecidos como entrada para o modelo.

### Campos proibidos como features

Não poderão ser utilizados como features do mesmo incidente:

```text
resolved_at
closed_at
duration_seconds
duration_hours
calculated_duration_seconds
closure_code
solution_type
status final
entered_kpi_source
kpi_breached_source
entered_kpi_recalculated_raw
kpi_breached_recalculated_raw
```

Essas informações são conhecidas depois da abertura ou estão diretamente
ligadas à definição do target.

## Contrato para o score de risco

Arquivo futuro:

```text
data/gold/risk_scores.parquet
```

A tabela terá uma linha por incidente e execução de inferência.

| Campo | Tipo | Regra |
|---|---|---|
| incident_id | string | Identificador do incidente |
| scored_at | datetime | Momento em que o score foi calculado |
| model_version | string | Versão do modelo utilizado |
| breach_probability | decimal | Valor entre 0 e 1 |
| priority_impact | decimal | Impacto normalizado entre 0 e 1 |
| operational_pressure | decimal | Pressão operacional entre 0 e 1 |
| risk_score | inteiro | Score final entre 0 e 100 |
| risk_level | string | Nível do risco |
| top_risk_factors | string ou lista | Principais fatores do score |
| recommended_action | string | Recomendação operacional |

A chave lógica será:

```text
incident_id + scored_at + model_version
```

Os níveis iniciais planejados serão:

| Score | Nível |
|---:|---|
| 0 a 24 | Baixo |
| 25 a 49 | Moderado |
| 50 a 74 | Alto |
| 75 a 100 | Crítico |

Os limites são provisórios e poderão ser recalibrados após a avaliação do
modelo e da quantidade de alertas gerados.

### Componentes do score

A primeira versão do score poderá combinar:

```text
probabilidade de violação
impacto da prioridade
pressão operacional
```

Uma fórmula inicial de referência será:

```text
risk_score =
100 × (
    0,70 × breach_probability
    + 0,20 × priority_impact
    + 0,10 × operational_pressure
)
```

Os pesos são provisórios e deverão ser documentados, testados e ajustados.

O score não substituirá a probabilidade produzida pelo modelo. Os dois campos
serão mantidos para permitir auditoria e interpretação.

## Contrato para eventos de alerta

Scores classificados como altos ou críticos poderão gerar eventos para o
RabbitMQ.

Estrutura inicial planejada:

```json
{
  "event_type": "ola_risk_alert",
  "incident_id": "INC1234567",
  "scored_at": "2025-10-15T10:00:00",
  "model_version": "risk-model-v1",
  "breach_probability": 0.74,
  "risk_score": 82,
  "risk_level": "critical",
  "priority": 2,
  "assigned_group": "Grupo A",
  "recommended_action": "Priorizar atendimento e revisar capacidade da equipe"
}
```

O RabbitMQ transportará eventos e alertas após a inferência. Ele não será
utilizado como armazenamento da base histórica completa.

## Versionamento dos contratos

Mudanças de nome, tipo, domínio ou significado de campos deverão ser
documentadas.

Alterações incompatíveis deverão gerar uma nova versão do contrato ou uma
migração explícita.

Os dados originais da empresa e os indicadores fornecidos na fonte nunca
deverão ser sobrescritos por cálculos derivados.



## Contrato para previsões de volume

Arquivo futuro:

`data/gold/volume_predictions.parquet`

A tabela terá uma linha por data de referência, horizonte, escopo de prioridade e versão do modelo.

| Campo | Tipo | Regra |
|---|---|---|
| reference_date | date | Data utilizada como referência da previsão |
| generated_at | datetime | Momento em que a inferência foi executada |
| horizon | string | Apenas `D+1` ou `D+7` |
| priority_scope | string | Apenas `ALL`, `P2` ou `P3` |
| predicted_incident_count | decimal | Quantidade prevista de incidentes; valor não negativo |
| model_version | string | Versão do modelo responsável pela inferência |

A chave lógica será:

`reference_date + horizon + priority_scope + model_version`

### Regras de integração

A camada Gold histórica não deverá ser sobrescrita pelas previsões.

`data/gold/daily_incident_volume.parquet` representa fatos observados.

`data/gold/volume_predictions.parquet` representa resultados de inferência produzidos pelo modelo.

Os horizontes suportados inicialmente serão `D+1` e `D+7`.

Os escopos suportados serão `ALL`, `P2` e `P3`.

O dashboard deverá consumir esse contrato sem depender da implementação interna do modelo.

A ausência temporária do artefato de previsão não deverá impedir o funcionamento das demais funcionalidades do Albus-Hub.

Mudanças incompatíveis nesse contrato deverão ser documentadas e versionadas.
