# Camada Gold de volume diário

## Objetivo

A camada Gold de volume diário transforma os registros individuais da
camada Silver em tabelas agregadas próprias para análise temporal,
dashboard e modelagem preditiva.

Ela será utilizada principalmente para:

1. previsão de volume D+1;
2. previsão de volume D+7;
3. análise separada das prioridades P2 e P3;
4. identificação de picos operacionais;
5. engenharia de features de pressão operacional;
6. enriquecimento futuro do score de risco.

## Origem

Arquivo de entrada:

```text
data/silver/locaweb_incidents.parquet