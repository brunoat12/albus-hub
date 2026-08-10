# Arquitetura da solução Albus-Hub

## Visão geral

O Albus-Hub é uma solução de AIOps voltada à análise operacional de
incidentes, previsão de volume e avaliação de risco de violação de
indicadores operacionais.

A implementação da Sprint 3 utiliza Azure como plataforma cloud principal,
mantendo os componentes da aplicação desacoplados da infraestrutura por
meio de Python e Docker.

## Arquitetura implementada

```text
Fonte de incidentes
        |
        v
Azure Data Factory
        |
        +----------------------+
        |                      |
        v                      v
Azure Data Lake Gen2     Azure Database for MySQL
raw/trusted/gold         incidents_trusted
        |                      |
        +----------+-----------+
                   |
                   v
             Python / Airflow
                   |
          +--------+---------+
          |                  |
          v                  v
   Dados operacionais   Contratos de modelos
          |                  |
          +--------+---------+
                   |
                   v
               Streamlit
                   |
                Docker
                   |
                   v
       Azure Container Registry
                   |
                   v
      Azure Container Instances
                   |
          +--------+---------+
          |                  |
          v                  v
 Azure Monitor /        Application Insights
 Log Analytics          OpenTelemetry

```

## Camada de dados

### Raw

Mantém os arquivos recebidos sem transformação funcional.

### Trusted / Silver

Contém os registros padronizados e enriquecidos utilizados pelas etapas
posteriores da solução.

### Gold

Contém estruturas agregadas voltadas ao consumo analítico e aos modelos,
incluindo volume diário de incidentes e cortes operacionais.

Os contratos completos estão documentados em:

`docs/data_contracts.md`

## Orquestração

O Azure Data Factory é utilizado como orquestrador central do fluxo de
Data Warehousing requerido na Sprint 3.

O Airflow é utilizado pela solução para pipelines de processamento,
validação, geração da camada Gold, backup e recuperação.

## Persistência

A solução utiliza dois destinos principais para os dados processados:

- Azure Data Lake Storage Gen2;
- Azure Database for MySQL Flexible Server.

A camada de exports também mantém saídas TXT exigidas pela Sprint 3.

## Aplicação

O dashboard é desenvolvido em Streamlit e empacotado como imagem Docker.

A imagem é armazenada no Azure Container Registry e executada em Azure
Container Instances.

A aplicação possui healthcheck e pode ser publicada temporariamente para
validação e demonstração.

## Observabilidade

A solução utiliza duas frentes complementares.

### Azure Monitor / Log Analytics

Recebe eventos operacionais do Azure Container Instance, permitindo
acompanhar criação, download da imagem e inicialização do container.

### Application Insights

A aplicação Python utiliza Azure Monitor OpenTelemetry para envio de
telemetria da aplicação.

O serviço é identificado como:

`albus-hub`

## Componentes com contrato pronto e integração pendente

Alguns componentes dependem da conclusão dos artefatos de modelagem das
demais frentes do projeto.

### Previsão de volume

Contrato preparado para previsões:

- D+1;
- D+7;
- ALL;
- P2;
- P3.

### Risco operacional

Contrato preparado para:

- probabilidade de violação;
- score operacional de 0 a 100;
- classificação de nível de risco;
- principais fatores;
- ação recomendada.

### RabbitMQ

O RabbitMQ faz parte da arquitetura de integração para publicação de
eventos críticos.

Quando a integração do modelo de risco estiver concluída, previsões
classificadas como críticas poderão gerar eventos para consumo pelo
serviço de alertas.

Esse componente não é apresentado como deploy Azure concluído nesta etapa.

## Portabilidade

A aplicação é empacotada em Docker e suas principais configurações são
fornecidas por variáveis de ambiente.

Essa abordagem reduz o acoplamento entre aplicação e provedor de cloud e
permite execução local ou em outra infraestrutura compatível com
containers.
