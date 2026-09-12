# Arquitetura da solução Albus-Hub

## Visão geral

O Albus-Hub é uma solução de AIOps voltada à análise operacional de
incidentes, previsão de volume e avaliação de risco de violação de
indicadores operacionais.

A implementação consolidada da Sprint 4 utiliza Azure como plataforma cloud
principal, com componentes de ingestão, processamento, modelagem,
persistência, visualização e observabilidade.

## Arquitetura implementada

```text
Fonte histórica de incidentes
            |
            v
    Azure Data Factory
            |
            v
Azure Data Lake Storage Gen2
 Raw / Trusted / Gold / Models
            |
            v
       Apache Airflow
Orquestração de modelagem e inferência
       /              \
      v                v
Previsão de        Risco Operacional
Volume D+1/D+7     Regressão Logística
      |                |
      v                v
Previsões          Probabilidade calibrada
                   Índice preditivo
                   Risk Score 0-100
      \                /
       \              /
            v
Azure Database for MySQL
            |
       +----+----+
       |         |
       v         v
   Streamlit   Power BI
       |
       v
 Operações / Gestor

 Camada de dados
Raw

Mantém os arquivos recebidos sem transformação funcional.

Trusted

Contém os registros padronizados e enriquecidos utilizados pelas etapas
posteriores da solução.

Gold

Contém estruturas agregadas voltadas ao consumo analítico e aos modelos,
incluindo volume diário de incidentes, cortes operacionais e features
derivadas.

Models

Mantém artefatos versionados utilizados pelos pipelines de inferência.

Orquestração

O Azure Data Factory é responsável pela ingestão e transformação dos dados.

O Apache Airflow é utilizado para orquestrar os pipelines de modelagem e
inferência da Sprint 4:

treinamento dos modelos de previsão de volume;
inferência D+1 e D+7;
treinamento do modelo de risco;
inferência do risco operacional;
publicação dos resultados no Azure Data Lake e Azure MySQL.
Persistência

A solução utiliza:

Azure Data Lake Storage Gen2;
Azure Database for MySQL Flexible Server.

O Azure Data Lake mantém dados analíticos e artefatos versionados.

O Azure MySQL mantém os dados utilizados pela aplicação operacional.

Componentes analíticos
Previsão de volume

A solução produz previsões para:

D+1;
D+7;
ALL;
P1;
P2;
P3;
P4;
P5.

Versão operacional:

volume_v3.2_2026-08-21

Os resultados incluem quantidade prevista e intervalo de previsão.

Risco operacional

O modelo utilizado para risco operacional é uma regressão logística calibrada.

Versão operacional:

risk-logistic-v2-20260910

O fluxo operacional é:

Features operacionais e históricas
            |
            v
Regressão logística calibrada
            |
            v
Probabilidade de violação
            |
            v
Índice preditivo histórico
            |
            v
Risk Score 0-100

O Risk Score combina:

80% índice preditivo
15% impacto da prioridade
5% pressão operacional

Faixas:

0-39   Baixo
40-59  Moderado
60-79  Alto
80-100 Crítico

A probabilidade de violação é mantida separadamente do Risk Score.

O Risk Score é um índice operacional de priorização, e não uma probabilidade.

O cálculo ocorre após a triagem inicial, quando atributos operacionais como
grupo responsável, produto e categoria podem estar disponíveis.

O modelo não utiliza informações futuras de resolução, fechamento ou duração
do mesmo incidente.

Aplicação

O dashboard operacional é desenvolvido em Streamlit.

A aplicação apresenta:

previsões D+1 e D+7;
indicadores operacionais;
risco por incidente;
probabilidade de violação;
Risk Score;
classificação de risco;
fila priorizada;
recomendações operacionais.

A aplicação é empacotada em Docker, armazenada no Azure Container Registry
e executada em Azure Container Instances.

Power BI

O Power BI é utilizado como camada analítica complementar para:

análise histórica;
agrupamentos;
tendências;
filtros exploratórios;
acompanhamento visual de indicadores.
Observabilidade

A solução utiliza:

Azure Monitor;
Log Analytics;
Application Insights;
OpenTelemetry.
Portabilidade

A aplicação é empacotada em Docker e suas principais configurações são
fornecidas por variáveis de ambiente.