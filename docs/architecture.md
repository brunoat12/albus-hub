# Arquitetura da solução Albus-Hub

## Visão geral

O Albus-Hub é uma solução de AIOps voltada à análise operacional de
incidentes, previsão de volume e avaliação de risco de violação de
indicadores operacionais.

A implementação consolidada da Sprint 4 utiliza Azure como plataforma cloud principal,
mantendo os componentes da aplicação desacoplados da infraestrutura por
meio de Python, Docker e contratos de dados bem definidos.

## Arquitetura implementada

```text
Fonte de incidentes
        |
        v
Azure Data Factory
        |
        v
Azure Data Lake Storage Gen2
 raw / trusted / gold
        |
        +-------------+-------------+
        |             |             |
        v             v             v
 Gold analítico   ML Volume      DL Risco
        |          D+1 / D+7       Score
        |             |             |
        |             v             v
        |       Modelos no ADLS  Modelos no ADLS
        |             |             |
        +-------------+-------------+
                      |
                      v
          Azure Database for MySQL
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
     Gold serving  Previsões   Scores de risco
          |           |           |
          +-----------+-----------+
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

Airflow:
- treinamento ML
- inferência ML
- treinamento DL
- inferência DL
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

O Azure Data Factory permanece responsável pelos fluxos de Data Warehousing
desenvolvidos nas etapas anteriores do projeto.

Na Sprint 4, o Apache Airflow também orquestra os pipelines analíticos de
Machine Learning e Deep Learning:

- treinamento do modelo de previsão de volume;
- inferência de volume D+1 e D+7;
- treinamento do modelo de risco;
- inferência e geração dos scores de risco.

Os pipelines utilizam marcadores explícitos de sucesso para evitar que uma
execução parcialmente concluída seja considerada válida.

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

## Componentes analíticos integrados

### Previsão de volume

O pipeline de Machine Learning produz previsões D+1 e D+7 para os
escopos ALL, P1, P2, P3, P4 e P5.

Os artefatos são versionados no Azure Data Lake e as previsões vigentes
são persistidas no Azure MySQL.

Versão operacional:

`volume_v3.2_2026-08-21`

### Risco operacional

O pipeline de Deep Learning produz probabilidade de violação, score de
risco de 0 a 100, nível de risco e fatores explicativos.

Os artefatos são versionados no Azure Data Lake e os scores vigentes
são persistidos no Azure MySQL.

Versão operacional:

`risk-ann-v1-20260820`

### Gold e serving

A camada Gold suporta análise de volume, produto, categoria, grupo, item
de configuração, agrupamentos críticos e cascatas por parent_incident_id.

Os dados consumidos pelo Streamlit são materializados no Azure MySQL.

### RabbitMQ

O RabbitMQ permanece como evolução para integração orientada a eventos
e alertas críticos, fora do caminho crítico da entrega analítica.

## Portabilidade

A aplicação é empacotada em Docker e suas principais configurações são
fornecidas por variáveis de ambiente.

Essa abordagem reduz o acoplamento entre aplicação e provedor de cloud e
permite execução local ou em outra infraestrutura compatível com
containers.
