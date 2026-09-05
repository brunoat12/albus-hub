# Albus-Hub

Projeto acadêmico de AIOps desenvolvido para o Challenge FIAP / Locaweb 2026.

O Albus-Hub tem como objetivo apoiar a operação de incidentes por meio de
análise de tendências, previsão de volume, avaliação de risco operacional,
observabilidade e visualização em dashboard.

## Objetivos

- prever o volume de incidentes em D+1 e D+7;
- estimar o risco operacional dos chamados;
- gerar um score de risco de 0 a 100;
- apoiar o acompanhamento de OLA, SLA e indicadores operacionais;
- disponibilizar tendências e previsões em dashboard;
- permitir geração de alertas para eventos críticos;
- manter rastreabilidade, persistência e observabilidade da solução.

## Arquitetura

A implementação consolidada da Sprint 4 utiliza Microsoft Azure como plataforma cloud principal.

Principais componentes:

- Azure Data Factory para integração e orquestração do fluxo de Data Warehousing;
- Azure Data Lake Storage Gen2 para as camadas `raw`, `trusted`, `gold`,
  `exports` e `backup`;
- Azure Database for MySQL Flexible Server para persistência relacional;
- Apache Airflow para processamento, validação, backup e recuperação;
- Streamlit para visualização da solução;
- Docker para empacotamento da aplicação;
- Azure Container Registry para armazenamento das imagens;
- Azure Container Instances para execução da aplicação;
- Azure Monitor e Log Analytics para observabilidade da infraestrutura;
- Application Insights com OpenTelemetry para telemetria da aplicação;
- RabbitMQ como componente de integração para eventos e alertas críticos.

A arquitetura detalhada está documentada em:

`docs/architecture.md`

## Pipeline de dados

O fluxo de Data Warehousing utiliza o Azure Data Factory para:

1. consumir a fonte de incidentes;
2. executar transformações por Mapping Data Flow;
3. criar colunas derivadas;
4. persistir a camada processada no Azure Data Lake;
5. persistir os registros no Azure Database for MySQL;
6. gerar a saída TXT exigida pela Sprint 3.

Detalhes:

`docs/sprint3/data_warehousing_architecture.md`

## Contratos de dados

Os contratos das camadas Bronze, Silver e Gold, das previsões, do score de
risco e dos eventos de alerta estão documentados em:

`docs/data_contracts.md`

## Aplicação

O dashboard é desenvolvido em Streamlit e distribuído como imagem Docker.

A imagem é armazenada no Azure Container Registry e executada em Azure
Container Instances na porta `8501`.

A aplicação possui healthcheck e integração validada com o Azure Database
for MySQL para consulta, processamento e persistência de dados.

## Sprint 4 — Modelagem analítica

### Previsão de volume

O pipeline de Machine Learning produz previsões de volume para:

- D+1;
- D+7;
- escopos ALL, P1, P2, P3, P4 e P5.

Versão operacional:

`volume_v3.2_2026-08-21`

Os artefatos do modelo são versionados no Azure Data Lake e as previsões
vigentes são persistidas no Azure MySQL para consumo pelo dashboard.

O dataset disponibilizado para o projeto termina em 31/12/2025. Por isso,
as previsões demonstradas no ambiente acadêmico partem do último ponto
temporal disponível na base.

### Risco operacional

O pipeline de Deep Learning estima a probabilidade de violação operacional
e produz um score de risco entre 0 e 100.

Versão operacional:

`risk-ann-v1-20260820`

O score combina:

- 70% da probabilidade prevista pelo modelo;
- 20% do impacto da prioridade;
- 10% da pressão operacional.

A solução utiliza o modelo como ferramenta de triagem e priorização, e não
como mecanismo automático de escalonamento.

### Agrupamentos críticos

A Gold analítica permite analisar combinações de:

`produto × categoria × prioridade`

Os rankings podem ser avaliados por volume, quantidade de violações ou taxa
de violação.

Entre os padrões encontrados no histórico está:

- produto `lsin`;
- categoria `cat31`;
- prioridade P3;
- 53 incidentes;
- 51 registros elegíveis ao KPI;
- 32 violações;
- taxa de violação de 62,75%.

As violações ocorreram em diversos dias, indicando um padrão recorrente e
não um único evento isolado.

### Incidentes recorrentes e cascatas

A solução utiliza `parent_incident_id` para identificar incidentes derivados
de uma mesma ocorrência principal.

No histórico analisado:

- 122.543 incidentes totais;
- 15.127 incidentes vinculados a um incidente-pai;
- 3.326 incidentes-pai distintos;
- 230 cascatas com pelo menos 10 filhos;
- 42 cascatas com pelo menos 50 filhos;
- maior cascata com 630 incidentes filhos.

Os incidentes em cascata representam aproximadamente 12,34% do volume total,
permitindo distinguir crescimento real da demanda de múltiplos chamados
correlacionados ao mesmo evento.

## Observabilidade

A solução possui duas camadas complementares de observabilidade:

### Azure Monitor / Log Analytics

Utilizado para eventos operacionais do Azure Container Instance, incluindo:

- download da imagem;
- inicialização do container;
- eventos de execução.

### Application Insights

A aplicação Python é instrumentada com Azure Monitor OpenTelemetry.

A telemetria é identificada pelo serviço:

`albus-hub`

A integração foi validada com envio e recebimento de traces no
Application Insights.

## Tecnologias

- Python 3.12
- Pandas
- SQLAlchemy
- PyMySQL
- Apache Airflow
- RabbitMQ
- Streamlit
- Docker / Docker Compose
- Terraform
- Azure Data Factory
- Azure Data Lake Storage Gen2
- Azure Database for MySQL
- Azure Container Registry
- Azure Container Instances
- Azure Monitor
- Log Analytics
- Application Insights
- OpenTelemetry
- GitHub Actions

## Status

### Implementado

- ingestão e transformação dos incidentes;
- camadas de dados Bronze, Silver e Gold;
- contratos de dados;
- pipeline Airflow;
- estratégia de backup e recuperação;
- integração com Azure MySQL;
- dashboard Streamlit;
- containerização Docker;
- Azure Container Registry;
- deploy em Azure Container Instances;
- Azure Monitor e Log Analytics;
- Application Insights e OpenTelemetry;
- CI com Ruff e Pytest.

### Sprint 4 integrada

A Sprint 4 consolida as frentes analíticas do projeto:

- previsão de volume D+1 e D+7;
- modelo de risco operacional;
- score de risco de 0 a 100;
- persistência dos resultados no Azure MySQL;
- agrupamentos críticos por produto, categoria e prioridade;
- identificação de incidentes recorrentes e cascatas;
- integração das previsões e scores ao dashboard Streamlit;
- orquestração operacional dos pipelines de ML e DL.

### Evidências finais pendentes

Antes da entrega final ainda devem ser registradas evidências de:

- deploy da versão integrada do dashboard no Azure;
- execução dos novos DAGs no ambiente Airflow final;
- screenshots do dashboard;
- atualização da documentação arquitetural;
- apresentação e demais materiais exigidos pela entrega.

A integração automática de alertas via RabbitMQ está implementada na
Sprint 4. Scores classificados como alto ou crítico podem gerar eventos
operacionais após a inferência DL, utilizando publisher e consumer
desacoplados por uma fila durável.

## Ambiente

A configuração do ambiente local e dos recursos Azure está documentada em:

`docs/environment.md`

## Qualidade

O projeto utiliza:

- Ruff para análise estática e formatação;
- Pytest para testes automatizados;
- GitHub Actions para validação contínua dos Pull Requests.
