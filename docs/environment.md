# Ambiente da solução Albus-Hub

## Objetivo

Documentar os principais componentes utilizados para desenvolvimento, processamento, persistência, execução e observabilidade do Albus-Hub.

## Ambiente local

O desenvolvimento e a validação operacional da solução utilizam:

- Python 3.12;
- `uv` para gerenciamento de dependências e ambiente Python;
- Docker;
- Streamlit;
- Apache Airflow executado localmente no WSL para orquestração dos pipelines de modelagem e inferência.

A aplicação também pode ser executada localmente para validações sem depender da camada de observabilidade do Azure.

## Azure

A infraestrutura consolidada da Sprint 4 está provisionada no Resource Group:

`rg-albus-hub-dev`

Região principal:

`eastus2`

### Azure Data Lake Storage Gen2

Storage utilizado pela solução:

`stcalbushubdev`

Containers / filesystems:

- `raw`;
- `trusted`;
- `gold`;
- `models`;
- `exports`;
- `backup`.

O filesystem `models` mantém os artefatos versionados utilizados pelos pipelines de inferência.

As principais responsabilidades do Data Lake são:

- armazenamento dos dados recebidos;
- armazenamento dos dados tratados;
- armazenamento das estruturas analíticas;
- versionamento dos artefatos de modelos;
- armazenamento de exports e backups.

### Azure Data Factory

Azure Data Factory:

`adf-albushub-fiap2026-dev`

O Azure Data Factory é responsável pela ingestão e transformação dos dados.

O fluxo implementado contempla:

- leitura da fonte de incidentes;
- Mapping Data Flow;
- padronização e transformação dos dados;
- criação de campos derivados;
- persistência dos dados tratados;
- alimentação das estruturas utilizadas pelas etapas posteriores da solução.

O Azure Data Factory atua na camada de ingestão e transformação.

A orquestração dos pipelines de modelagem e inferência é realizada pelo Apache Airflow.

### Apache Airflow

O Apache Airflow é utilizado para orquestrar os pipelines analíticos da Sprint 4.

As principais responsabilidades são:

- treinamento dos modelos de previsão de volume;
- inferência das previsões D+1 e D+7;
- treinamento do modelo de risco operacional;
- inferência dos scores de risco;
- validação dos resultados;
- publicação dos resultados no Azure Data Lake;
- persistência dos resultados no Azure MySQL.

O Airflow foi executado localmente no WSL durante a validação do projeto e não faz parte do container público do Streamlit.

### Azure Database for MySQL Flexible Server

Servidor:

`mysql-albushub-dev-2026`

Banco:

`albus_hub`

O Azure MySQL é utilizado como camada relacional de persistência e serving para a aplicação.

Principais tabelas utilizadas:

- `incidents_trusted`;
- `albus_app_runs`;
- `app_daily_incident_volume`;
- `app_daily_incident_breakdown`;
- `ml_volume_predictions_current`;
- `dl_risk_scores_current`.

As tabelas `app_*` materializam dados analíticos utilizados pelo dashboard.

`ml_volume_predictions_current` mantém as previsões operacionais vigentes de volume.

`dl_risk_scores_current` mantém os scores operacionais vigentes de risco.

O nome `dl_risk_scores_current` foi preservado por compatibilidade com a estrutura já implantada durante o desenvolvimento do projeto. Apesar do nome legado, os registros atuais são produzidos pelo modelo final de regressão logística.

O servidor utiliza acesso público controlado por regras de firewall.

A aplicação possui integração validada com operações de:

- health check;
- consulta;
- processamento;
- inserção;
- leitura dos registros persistidos.

## Modelos operacionais

### Previsão de volume

Versão operacional:

`volume_v3.2_2026-08-21`

A solução produz previsões para:

- D+1;
- D+7;
- ALL;
- P1;
- P2;
- P3;
- P4;
- P5.

Os resultados incluem:

- quantidade prevista;
- limite inferior;
- limite superior.

A solução compara diferentes abordagens e utiliza a mais adequada para cada série e horizonte.

Os artefatos são versionados no Azure Data Lake.

As previsões vigentes são persistidas no Azure MySQL para consumo pela aplicação.

### Risco operacional

Versão operacional:

`risk-logistic-v2-20260910`

O modelo utilizado é uma regressão logística calibrada.

O modelo estima a probabilidade calibrada de violação operacional.

Essa probabilidade é mantida separadamente do índice preditivo e do Risk Score.

O fluxo operacional é:

Probabilidade calibrada → Índice preditivo histórico → Risk Score 0-100

O Risk Score combina:

- 80% índice preditivo;
- 15% impacto da prioridade;
- 5% pressão operacional.

Os níveis são:

- 0 a 39: Baixo;
- 40 a 59: Moderado;
- 60 a 79: Alto;
- 80 a 100: Crítico.

O Risk Score é um índice operacional de priorização e não deve ser interpretado como probabilidade.

O cálculo ocorre após a triagem inicial, quando atributos operacionais como grupo responsável, produto e categoria podem estar disponíveis.

O modelo não utiliza informações futuras de resolução, fechamento ou duração do mesmo incidente.

## Streamlit

O dashboard operacional é desenvolvido em Streamlit.

A aplicação apresenta:

- previsões D+1 e D+7;
- indicadores operacionais;
- risco por incidente;
- probabilidade de violação;
- índice preditivo;
- Risk Score;
- nível de risco;
- fila priorizada;
- recomendações operacionais.

A aplicação consulta os dados persistidos no Azure MySQL.

## Power BI

O Power BI é utilizado como camada analítica complementar para análise histórica e exploratória.

Ele permite:

- análise histórica;
- visualização de tendências;
- análise por prioridade;
- análise por produto;
- análise por categoria;
- aplicação de filtros;
- exploração dos indicadores operacionais.

## Docker

A aplicação Streamlit é empacotada em imagem Docker.

O container concentra apenas os componentes necessários para execução do dashboard.

Os pipelines de treinamento e processamento não são executados dentro do container público da aplicação.

## Azure Container Registry

Azure Container Registry:

`acralbushubfiap2026dev`

SKU:

`Basic`

Repositório:

`albus-hub`

Imagem final validada:

`acralbushubfiap2026dev.azurecr.io/albus-hub:sprint4-risk-v2-20260911`

O registry armazena as imagens Docker utilizadas para execução da aplicação em Azure Container Instances.

## Azure Container Instances

Container Group:

`aci-albus-hub-dev`

Aplicação:

`albus-hub`

Porta publicada:

`8501/TCP`

O container executa o dashboard Streamlit e utiliza imagem privada armazenada no Azure Container Registry.

A tag da imagem utilizada pelo ACI é parametrizada no Terraform pela variável:

`container_image_tag`

O Azure Container Instance pode permanecer parado fora das janelas de desenvolvimento e demonstração para reduzir consumo de recursos.

## Observabilidade

A solução utiliza Azure Monitor, Log Analytics e Application Insights.

### Azure Monitor e Log Analytics

Log Analytics Workspace:

`log-albus-hub-dev`

O Azure Container Instance envia eventos operacionais para o workspace.

Durante a validação foram observados eventos como:

- download da imagem;
- conclusão do download;
- inicialização do container;
- eventos relacionados à execução do recurso.

### Application Insights

Application Insights:

`appi-albus-hub-dev`

A aplicação Python é instrumentada utilizando Azure Monitor OpenTelemetry.

A connection string é fornecida ao ambiente por variável de configuração:

`APPLICATIONINSIGHTS_CONNECTION_STRING`

O nome lógico do serviço é configurado como:

`OTEL_SERVICE_NAME=albus-hub`

A integração foi validada com telemetria recebida pelo Application Insights e identificada pelo serviço `albus-hub`.

## Infraestrutura como código

Os principais recursos Azure são definidos utilizando Terraform.

A infraestrutura parametriza elementos como:

- região;
- nome do projeto;
- ambiente;
- credenciais do banco;
- tag da imagem Docker.

Valores sensíveis não devem possuir conteúdo real versionado no Git.

## Segurança de configuração

Credenciais e valores sensíveis não devem ser versionados.

Arquivos locais como:

- `.env`;
- `.env.local`;
- `terraform.tfvars`;
- `terraform.tfstate`;
- `terraform.tfstate.backup`;
- arquivos `*.tfplan`;
- arquivos de chave ou credenciais;

devem permanecer fora do versionamento Git.

Arquivos de exemplo podem permanecer no repositório desde que contenham apenas valores fictícios ou placeholders de desenvolvimento.

## Controle de custo

Recursos de compute utilizados apenas para testes ou demonstrações devem permanecer desligados quando não forem necessários.

Em particular:

- Azure Database for MySQL Flexible Server;
- Azure Container Instances.

Recursos persistentes de armazenamento, registry e observabilidade podem continuar provisionados para preservar dados, imagens e configuração do ambiente.

## Resumo da arquitetura operacional

O fluxo principal da solução é:

Fonte histórica → Azure Data Factory → Azure Data Lake Storage Gen2 → Apache Airflow → Previsão D+1/D+7 e Risco Operacional → Azure MySQL → Streamlit / Power BI

O fluxo de publicação da aplicação é:

Código Streamlit → Docker → Azure Container Registry → Azure Container Instances → Aplicação operacional
