# Albus-Hub

Projeto acadêmico de AIOps desenvolvido para o Challenge FIAP / Locaweb 2026.

O Albus-Hub tem como objetivo apoiar a operação de incidentes por meio de
análise de tendências, previsão de volume, avaliação de risco operacional,
observabilidade e visualização em dashboard.

## Objetivos

- prever o volume de incidentes em D+1 e D+7;
- estimar o risco operacional dos chamados;
- gerar um Risk Score de 0 a 100;
- apoiar o acompanhamento de OLA, SLA e indicadores operacionais;
- disponibilizar tendências e previsões em dashboard;
- priorizar incidentes com maior risco operacional;
- manter rastreabilidade, persistência e observabilidade da solução.

## Arquitetura

A implementação consolidada da Sprint 4 utiliza Microsoft Azure como
plataforma cloud principal.

Principais componentes:

- Azure Data Factory para ingestão e transformação do fluxo de dados;
- Azure Data Lake Storage Gen2 para as camadas `raw`, `trusted`, `gold`,
  `exports`, `backup` e armazenamento de artefatos de modelos;
- Azure Database for MySQL Flexible Server para persistência relacional;
- Apache Airflow para orquestração dos pipelines de modelagem e inferência;
- Streamlit para visualização operacional da solução;
- Power BI para análise histórica e exploratória;
- Docker para empacotamento da aplicação;
- Azure Container Registry para armazenamento das imagens;
- Azure Container Instances para execução da aplicação;
- Azure Monitor e Log Analytics para observabilidade da infraestrutura;
- Application Insights com OpenTelemetry para telemetria da aplicação.

A arquitetura detalhada está documentada em:

`docs/architecture.md`

## Pipeline de dados

O fluxo de Data Warehousing utiliza o Azure Data Factory para:

1. consumir a fonte de incidentes;
2. executar transformações por Mapping Data Flow;
3. criar colunas derivadas;
4. persistir a camada processada no Azure Data Lake;
5. persistir registros analíticos no Azure Database for MySQL;
6. gerar saídas exigidas pelas etapas anteriores do projeto.

Detalhes:

`docs/sprint3/data_warehousing_architecture.md`

## Contratos de dados

Os contratos das camadas de dados, das previsões e do score de risco estão
documentados em:

`docs/data_contracts.md`

## Aplicação

O dashboard é desenvolvido em Streamlit e distribuído como imagem Docker.

A imagem é armazenada no Azure Container Registry e executada em Azure
Container Instances na porta `8501`.

A aplicação possui integração validada com o Azure Database for MySQL para
consulta e apresentação dos dados operacionais.

## Sprint 4 — Modelagem analítica

### Previsão de volume

O pipeline de previsão de volume produz previsões para:

- D+1;
- D+7;
- escopos ALL, P1, P2, P3, P4 e P5.

Versão operacional:

`volume_v3.2_2026-08-21`

A solução compara diferentes abordagens e utiliza a mais adequada para cada
série e horizonte.

Os artefatos são versionados no Azure Data Lake e as previsões vigentes são
persistidas no Azure MySQL para consumo pelo dashboard.

O dataset disponibilizado para o projeto termina em 31/12/2025. Por isso,
as previsões demonstradas no ambiente acadêmico partem do último ponto
temporal disponível na base.

### Risco operacional

O modelo utilizado para risco operacional é uma regressão logística calibrada.

Versão operacional:

`risk-logistic-v2-20260910`

O modelo estima a probabilidade calibrada de violação operacional.

A partir dessa probabilidade, a solução calcula um índice preditivo relativo
ao histórico e gera o Risk Score operacional de 0 a 100.

O score combina:

- 80% do índice preditivo;
- 15% do impacto da prioridade;
- 5% da pressão operacional.

Classificação:

- 0 a 39: Baixo;
- 40 a 59: Moderado;
- 60 a 79: Alto;
- 80 a 100: Crítico.

A probabilidade de violação e o Risk Score são mantidos separadamente.

A probabilidade representa a estimativa produzida pelo modelo.

O Risk Score é um índice operacional de priorização e não deve ser interpretado
como probabilidade.

A solução utiliza o modelo como ferramenta de triagem e priorização, e não
como mecanismo automático de escalonamento.

O cálculo do risco é feito após a triagem inicial, quando atributos operacionais
como grupo responsável, produto e categoria podem estar disponíveis.

O modelo não utiliza informações futuras de resolução, fechamento ou duração
do mesmo incidente.

### Agrupamentos críticos

A camada Gold analítica permite analisar combinações de:

`produto × categoria × prioridade`

Os rankings podem ser avaliados por volume, quantidade de violações ou taxa
de violação.

### Incidentes recorrentes e cascatas

A solução utiliza `parent_incident_id` para identificar incidentes derivados
de uma mesma ocorrência principal.

Essa análise permite diferenciar aumento real de demanda de múltiplos chamados
correlacionados ao mesmo evento.

## Observabilidade

A solução possui duas camadas complementares de observabilidade.

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
- Scikit-learn
- SQLAlchemy
- PyMySQL
- Apache Airflow
- Streamlit
- Power BI
- Docker
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
- camadas de dados Raw, Trusted e Gold;
- contratos de dados;
- pipeline Airflow;
- integração com Azure MySQL;
- previsão de volume D+1 e D+7;
- regressão logística para risco operacional;
- Risk Score operacional de 0 a 100;
- dashboard Streamlit;
- análise histórica em Power BI;
- containerização Docker;
- Azure Container Registry;
- deploy em Azure Container Instances;
- Azure Monitor e Log Analytics;
- Application Insights e OpenTelemetry;
- CI com Ruff e Pytest.

### Sprint 4 integrada

A Sprint 4 consolida as frentes analíticas do projeto:

- previsão de volume D+1 e D+7;
- modelo de risco operacional com regressão logística;
- probabilidade calibrada de violação;
- índice preditivo;
- Risk Score de 0 a 100;
- persistência dos resultados no Azure MySQL;
- agrupamentos críticos por produto, categoria e prioridade;
- identificação de incidentes recorrentes e cascatas;
- integração das previsões e scores ao dashboard Streamlit;
- orquestração dos pipelines de modelagem e inferência via Airflow.

### Evidências finais

A aplicação integrada foi validada no Azure Container Instances.

Imagem implantada:

`acralbushubfiap2026dev.azurecr.io/albus-hub:sprint4-risk-v2-20260911`

## Ambiente

A configuração do ambiente local e dos recursos Azure está documentada em:

`docs/environment.md`

## Qualidade

O projeto utiliza:

- Ruff para análise estática e formatação;
- Pytest para testes automatizados;
- GitHub Actions para validação contínua dos Pull Requests.
