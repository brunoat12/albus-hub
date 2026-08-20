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

A implementação da Sprint 3 utiliza Microsoft Azure como plataforma cloud
principal.

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
- baseline e ANN para risco de violação do KPI/OLA;
- score operacional 0–100 e integração com o Streamlit;
- explicabilidade local e recomendações por incidente;
- notebook acadêmico reproduzível da frente de Deep Learning.

### Integração pendente

Dependente da conclusão dos artefatos de modelagem das demais frentes do
projeto:

- modelo de previsão D+1 e D+7;
- publicação de eventos críticos no RabbitMQ;
- consumo dos alertas;
- apresentação final dos resultados integrados no dashboard.

## Ambiente

A configuração do ambiente local e dos recursos Azure está documentada em:

`docs/environment.md`

## Qualidade

O projeto utiliza:

- Ruff para análise estática e formatação;
- Pytest para testes automatizados;
- GitHub Actions para validação contínua dos Pull Requests.

## Modelo de risco OLA/KPI

A implementação da frente de risco utiliza como fonte canônica:

```text
data/silver/locaweb_incidents.parquet
```

Os dados pesados e os artefatos treinados são ignorados pelo Git. Coloque a
Silver no caminho acima antes do treinamento.

Treinar baseline, clusterização e ANN, calibrar o threshold e gerar os scores:

```bash
uv run python scripts/train_risk_model.py
```

Regenerar somente o Parquet de scores usando os artefatos salvos:

```bash
uv run python scripts/generate_risk_scores.py
```

Gerar e executar o notebook acadêmico:

```bash
uv run python scripts/build_risk_notebook.py
uv run python scripts/execute_risk_notebook.py
```

Artefatos principais:

- `notebooks/EC_Sprint_3_Albus_Hub_DeepL.ipynb`;
- `models/risk/ann.weights.h5`;
- `models/risk/preprocessor.joblib`;
- `models/risk/calibrator.joblib`;
- `models/risk/metadata.json`;
- `data/gold/risk_features.parquet`;
- `data/gold/risk_scores.parquet`;
- `artifacts/metrics/risk_model_metrics.json`.

Os artefatos reproduzíveis em `models/`, `data/` e `artifacts/` não devem ser
commitados. Metodologia, métricas observadas e limitações estão detalhadas em
`docs/risk_score.md`.
