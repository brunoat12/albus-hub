# Ambiente da solução Albus-Hub

## Objetivo

Documentar os principais componentes utilizados para desenvolvimento,
processamento, persistência, execução e observabilidade do Albus-Hub.

## Ambiente local

O desenvolvimento da solução é realizado com:

- Python 3.12;
- `uv` para gerenciamento de dependências e ambiente Python;
- Docker;
- Docker Compose;
- PostgreSQL para serviços locais auxiliares;
- RabbitMQ para integração de eventos e alertas;
- Streamlit para visualização;
- Airflow para orquestração dos pipelines de dados.

A aplicação pode ser executada localmente sem depender dos serviços Azure
de observabilidade.

## Azure

A infraestrutura consolidada até a Sprint 4 está provisionada no Resource Group:

`rg-albus-hub-dev`

Região principal:

`eastus2`

### Data Lake

Azure Data Lake Storage Gen2:

`stcalbushubdev`

Containers / filesystems:

- `raw`;
- `trusted`;
- `gold`;
- `models`;
- `exports`;
- `backup`.

O filesystem `models` mantém os artefatos versionados dos modelos de
Machine Learning e Deep Learning utilizados pelos pipelines de inferência.

### Data Factory

Azure Data Factory:

`adf-albushub-fiap2026-dev`

Responsável pelo fluxo de integração solicitado na disciplina de Data
Warehousing, incluindo leitura da origem, Mapping Data Flow, criação de
colunas derivadas e persistência dos dados processados.

### Banco de dados

Azure Database for MySQL Flexible Server:

`mysql-albushub-dev-2026`

Banco:

`albus_hub`

Principais tabelas utilizadas pela aplicação:

- `incidents_trusted`;
- `albus_app_runs`;
- `app_daily_incident_volume`;
- `app_daily_incident_breakdown`;
- `ml_volume_predictions_current`;
- `dl_risk_scores_current`.

As tabelas `app_*` materializam dados analíticos para o dashboard.
`ml_volume_predictions_current` mantém as previsões operacionais vigentes
de volume e `dl_risk_scores_current` mantém a coorte vigente de scores
de risco.

O servidor utiliza acesso público controlado por regras de firewall.

A aplicação possui integração validada com operações de:

- health check;
- consulta;
- processamento;
- inserção;
- leitura dos registros persistidos.

### RabbitMQ

O RabbitMQ é utilizado na Sprint 4 como transporte dos eventos de alerta
de risco operacional.

No ambiente local, o serviço é disponibilizado via Docker Compose:

- AMQP: porta `5672`;
- interface de gerenciamento: porta `15672`;
- fila operacional: `albus_alerts`.

Após a inferência DL, apenas scores classificados como `alto` ou
`crítico` são elegíveis para publicação. O producer e o consumer foram
validados com fluxo real utilizando ACK após processamento bem-sucedido.

### Azure Container Registry

Azure Container Registry:

`acralbushubfiap2026dev`

SKU:

`Basic`

Repositório da aplicação:

`albus-hub`

O registry armazena as imagens Docker utilizadas para execução do
dashboard em Azure Container Instances.

### Azure Container Instances

Container Group:

`aci-albus-hub-dev`

Aplicação:

`albus-hub`

Porta publicada:

`8501/TCP`

O container executa o dashboard Streamlit e utiliza imagem privada
armazenada no Azure Container Registry.

A tag da imagem utilizada pelo ACI é parametrizada no Terraform por meio da
variável `container_image_tag`, permitindo atualizar a versão implantada sem
alterar diretamente a definição do recurso.

O ACI pode permanecer parado fora das janelas de desenvolvimento e
demonstração para reduzir consumo de recursos.

### Azure Monitor e Log Analytics

Log Analytics Workspace:

`log-albus-hub-dev`

O Azure Container Instance envia eventos operacionais para o workspace.

Durante a validação foram observados eventos como:

- download da imagem;
- conclusão do download;
- inicialização do container.

### Application Insights

Application Insights:

`appi-albus-hub-dev`

A aplicação Python é instrumentada com Azure Monitor OpenTelemetry.

A connection string é fornecida ao ACI por variável de ambiente segura:

`APPLICATIONINSIGHTS_CONNECTION_STRING`

O nome lógico do serviço é configurado como:

`OTEL_SERVICE_NAME=albus-hub`

A integração foi validada com telemetria recebida pelo Application
Insights e identificada pelo papel `albus-hub`.

## Segurança de configuração

Credenciais e valores sensíveis não devem ser versionados.

Arquivos locais como:

- `.env`;
- `terraform.tfvars`;
- `terraform.tfstate`;
- arquivos `*.tfplan`;

devem permanecer fora do versionamento Git.

## Controle de custo

Recursos de compute utilizados apenas para testes ou demonstrações devem
permanecer desligados quando não forem necessários.

Em particular:

- Azure Database for MySQL Flexible Server;
- Azure Container Instances.

Os recursos persistentes de armazenamento e observabilidade permanecem
provisionados para preservar os dados e a configuração do ambiente.
