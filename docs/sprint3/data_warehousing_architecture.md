# Arquitetura de Data Warehousing - Sprint 3

## Objetivo

Implementar um fluxo ETL em nuvem utilizando Azure Data Factory como
ferramenta central de orquestração para os dados de incidentes utilizados
pelo Albus-Hub.

## Arquitetura

A origem do processo é o arquivo de incidentes disponibilizado para o
Challenge, armazenado na camada `raw` do Azure Data Lake Storage Gen2.

O Azure Data Factory realiza a leitura do arquivo Excel e executa um Mapping
Data Flow responsável pela padronização e enriquecimento dos registros.

Durante o processamento são criadas colunas derivadas para padronização do
identificador do incidente, prioridade, identificação de eventos de
monitoramento, status sem intervenção e timestamp de processamento.

O resultado processado é persistido em dois destinos principais exigidos
pela Sprint:

- Azure Database for MySQL, utilizando a tabela `incidents_trusted`;
- arquivo TXT armazenado no container `exports` do Azure Data Lake.

Também é mantida uma camada intermediária `trusted` no Data Lake para
desacoplar o processamento dos destinos de consumo.

## Fluxo

LW-DATASET.xlsx
→ ADLS / raw
→ Azure Data Factory
→ Mapping Data Flow
→ Derived Columns
→ ADLS / trusted
→ Azure Database for MySQL
→ TXT / exports

## Decisão arquitetural

O MySQL utiliza acesso público controlado por firewall para simplificar o
ambiente acadêmico e reduzir a quantidade de infraestrutura permanente.

A escolha reduz custos e complexidade operacional sem alterar os requisitos
funcionais da Sprint, mantendo Azure Data Factory como orquestrador e Azure
Database for MySQL como SGBD PaaS.
