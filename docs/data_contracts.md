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

## Contrato para previsão de volume

A engenharia de features deve gerar uma série diária baseada em `opened_at`, com P2 e P3 obrigatórias.

Arquivo futuro: `data/gold/daily_incident_volume.parquet`

Campos mínimos:

- `reference_date`
- `priority_code`
- `grouping_dimension` (`total`, `product`, `category`, `configuration_item`, `assigned_group`)
- `grouping_value`
- `incident_count`
- `entered_kpi_count`
- `kpi_breach_count`

## Contrato para risco de perda de OLA

Arquivo futuro: `data/gold/risk_training_base.parquet`

População inicial: `entered_kpi_source == True`.

Target: `kpi_breached_source`.

Features disponíveis no momento da abertura:

- prioridade
- produto
- categoria
- subcategoria
- grupo designado
- item de configuração
- aberto por
- descrição resumida
- data, dia da semana e hora de abertura
- agregações históricas calculadas apenas com eventos anteriores

Não usar como features do mesmo incidente:

- `resolved_at`
- `closed_at`
- `duration_seconds`
- `closure_code`
- `solution_type`
- status final
- `kpi_breached_source`
