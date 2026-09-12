# Contratos de dados — Locaweb / Albus-Hub

## Fonte original

- Arquivo local: `data/raw/locaweb/LW-DATASET.xlsx`
- Planilha: `Dataset Geral`
- O arquivo original não deve ser enviado ao GitHub.

## Camada Bronze

Arquivo:

```text
data/bronze/locaweb_incidents.parquet

A camada Bronze preserva as 19 colunas originais e adiciona:

_source_file
_source_row_number
_ingested_at_utc
Camada Silver

Arquivo:

data/silver/locaweb_incidents.parquet
Fonte	Silver	Tipo / uso
Número	incident_id	string, chave única
Prioridade	priority_raw	string original
—	priority_code	inteiro de 1 a 5
—	priority_label	descrição da prioridade
Produto	product	string opcional
Categoria	category	string opcional
Subcategoria	subcategory	string opcional
Grupo designado	assigned_group	string obrigatório
Item de configuração	configuration_item	string opcional
Aberto	opened_at	datetime obrigatório
Resolvido	resolved_at	datetime opcional
Encerrado	closed_at	datetime obrigatório
Duração	duration_seconds	inteiro em segundos
—	duration_hours	duração convertida em horas
Código de fechamento	closure_code	string opcional
Descrição resumida	short_description	string obrigatório
Solução	solution_type	Contorno, Definitiva ou nulo
Aberto por	opened_by	Manual ou Monitoramento
Incidente Pai	parent_incident_id	string opcional
Status	status	domínio do dicionário
Entrou para KPI?	entered_kpi_raw	SIM ou NAO, preservado
—	entered_kpi_source	booleano derivado da fonte
KPI Violado?	kpi_breached_raw	SIM, NAO ou N/A, preservado
—	kpi_breached_source	booleano anulável

A Silver também contém campos de auditoria de duração e das regras
documentadas de KPI.

Os campos recalculados não substituem os indicadores fornecidos pela empresa.

Camada Gold de volume diário

A camada Gold de volume diário é construída a partir da camada Silver,
utilizando o campo opened_at como referência temporal.

Ela possui dois conjuntos principais de dados:

série diária contínua;
cortes por dimensões operacionais.
Série diária principal

Arquivo:

data/gold/daily_incident_volume.parquet

A tabela possui uma linha por data e escopo de prioridade.

Campo	Tipo	Regra
reference_date	date	Data de abertura do incidente
priority_scope	string	ALL, P1, P2, P3, P4 ou P5
incident_count	inteiro	Quantidade de incidentes abertos
entered_kpi_count	inteiro	Quantidade que entrou no KPI segundo a fonte
kpi_breach_count	inteiro	Quantidade com KPI violado segundo a fonte
monitoring_incident_count	inteiro	Quantidade aberta por monitoramento
no_intervention_count	inteiro	Quantidade com status Sem Intervenção

A chave lógica da tabela é:

reference_date + priority_scope

Não pode existir mais de uma linha para a mesma combinação de data e escopo.

A série contém todas as datas entre a menor e a maior data de abertura da base.

Dias sem incidentes são representados com contagens iguais a zero.

Os valores aceitos para priority_scope são:

ALL
P1
P2
P3
P4
P5

O escopo ALL considera todas as prioridades.

Todas as colunas de contagem devem:

ser inteiras;
ser maiores ou iguais a zero;
nunca ser nulas.
Cortes operacionais

Arquivo:

data/gold/daily_incident_breakdown.parquet

A tabela possui uma linha por data, dimensão, valor da dimensão e escopo
de prioridade.

Campo	Tipo	Regra
reference_date	date	Data de abertura do incidente
dimension_name	string	Nome da dimensão analisada
dimension_value	string	Valor encontrado na dimensão
priority_scope	string	ALL, P1, P2, P3, P4 ou P5
incident_count	inteiro	Quantidade de incidentes
entered_kpi_count	inteiro	Quantidade que entrou no KPI
kpi_breach_count	inteiro	Quantidade com KPI violado

Os valores aceitos para dimension_name incluem:

assigned_group
product
category
configuration_item
critical_group
parent_incident_id

A chave lógica da tabela é:

reference_date
+ dimension_name
+ dimension_value
+ priority_scope

Valores nulos das dimensões não são excluídos da contagem.

Na Gold, eles são representados por:

__MISSING__

Essa substituição ocorre somente na tabela agregada.

Os valores nulos originais permanecem preservados na camada Silver.

Reconciliação da camada Gold

Para cada data:

incident_count de ALL
=
quantidade de incidentes abertos naquela data

Para os escopos específicos:

incident_count da prioridade
=
quantidade de incidentes com o respectivo priority_code

As contagens de KPI utilizam os indicadores fornecidos pela empresa:

entered_kpi_source
kpi_breached_source

As regras recalculadas de auditoria não substituem esses campos.

Consumidores da Gold de volume diário

A camada Gold de volume diário é utilizada por:

análise exploratória temporal;
modelos de previsão de volume D+1 e D+7;
dashboard operacional;
análise por prioridade;
identificação de picos operacionais;
engenharia de features de pressão operacional;
suporte às análises de risco.

A Gold histórica representa fatos observados.

Ela não deve conter resultados de inferência misturados aos fatos históricos.

As previsões e scores são mantidos em estruturas próprias.

Contrato para previsões de volume

Arquivo:

data/gold/volume_predictions.parquet

A tabela possui uma linha por data de referência, horizonte, escopo de
prioridade e versão do modelo.

Campo	Tipo	Regra
reference_date	date	Data utilizada como referência da previsão
generated_at	datetime	Momento em que a inferência foi executada
horizon	string	D+1 ou D+7
priority_scope	string	ALL, P1, P2, P3, P4 ou P5
predicted_incident_count	decimal	Quantidade prevista; valor não negativo
lower_bound	decimal	Limite inferior; valor não negativo
upper_bound	decimal	Limite superior; valor não negativo
model_name	string	Nome do modelo utilizado
model_version	string	Versão responsável pela inferência

A chave lógica é:

reference_date + horizon + priority_scope + model_version

O intervalo de previsão deve respeitar:

lower_bound <= predicted_incident_count <= upper_bound

Os horizontes suportados são:

D+1
D+7

Os escopos suportados são:

ALL
P1
P2
P3
P4
P5

Cada execução operacional gera 12 previsões:

seis escopos para D+1;
seis escopos para D+7.

A inferência valida:

valores não negativos;
consistência dos intervalos;
domínio dos horizontes;
domínio dos escopos;
identificação do modelo;
unicidade da chave lógica.

Versão operacional:

volume_v3.2_2026-08-21

O artefato operacional é publicado na camada Gold do ADLS.

As previsões vigentes também são persistidas no Azure MySQL para consumo
pela aplicação.

A solução compara diferentes abordagens e utiliza a mais adequada para cada
série e horizonte.

Contrato para features de risco

Arquivo:

data/gold/risk_features.parquet

A tabela possui uma linha por incidente avaliado pelo modelo de risco.

O objetivo é reunir informações disponíveis no momento operacional de
scoring, após a triagem inicial do incidente, além de informações históricas
anteriores ao incidente avaliado.

Identificação e contexto

Campos implementados:

Campo	Tipo	Uso
incident_id	string	Identificador único do incidente
opened_at	datetime	Momento da abertura
priority_code	inteiro	Prioridade de 1 a 5
product	string	Produto afetado
category	string	Categoria
subcategory	string	Subcategoria
assigned_group	string	Grupo responsável
configuration_item	string	Item de configuração
opened_by	string	Origem da abertura
Features temporais do incidente

Campos implementados:

opened_hour
opened_day_of_week
opened_month
is_weekend
Features históricas

Campos utilizados:

assigned_group_incidents_previous_1d
assigned_group_incidents_previous_7d
assigned_group_incidents_previous_30d
assigned_group_known_outcomes_previous_30d
assigned_group_breaches_previous_30d
assigned_group_breach_rate_previous_30d
product_incidents_previous_7d
category_incidents_previous_7d
priority_incidents_previous_7d

Toda feature histórica utiliza somente dados anteriores ao incidente.

Quando a origem é uma tabela diária, o cálculo considera no máximo o dia
anterior:

data da feature <= data de abertura - 1 dia

As contagens intradiárias consideram somente eventos com timestamp
estritamente anterior a opened_at.

População de treinamento

A população utilizada é:

entered_kpi_source == True

O target é:

kpi_breached_source

Os campos de target podem existir na base de treinamento para avaliação,
mas nunca são fornecidos como entrada para o modelo.

Campos proibidos como features

Não são utilizados como features do mesmo incidente:

resolved_at
closed_at
duration_seconds
duration_hours
calculated_duration_seconds
duration_difference_seconds
duration_mismatch
closure_code
solution_type
status
entered_kpi_source
kpi_breached_source
entered_kpi_raw
kpi_breached_raw
entered_kpi_recalculated_raw
kpi_breached_recalculated_raw
entered_kpi_rule_mismatch
kpi_breached_rule_mismatch

Essas informações são conhecidas posteriormente ou estão diretamente
relacionadas à definição do target.

Contrato para o score de risco

Arquivo:

data/gold/risk_scores.parquet

A tabela possui uma linha por incidente e execução de inferência.

Campo	Tipo	Regra
incident_id	string	Identificador do incidente
scored_at	datetime	Momento em que o score foi calculado
model_version	string	Versão do modelo utilizado
breach_probability	decimal	Probabilidade calibrada entre 0 e 1
predictive_risk_index	decimal	Índice relativo histórico entre 0 e 1
priority_impact	decimal	Impacto normalizado da prioridade entre 0 e 1
operational_pressure	decimal	Pressão operacional entre 0 e 1
risk_score	inteiro	Score operacional final entre 0 e 100
risk_level	string	Nível de risco
top_risk_factors	string ou lista	Principais fatores associados ao score
recommended_action	string	Recomendação operacional

A chave lógica é:

incident_id + scored_at + model_version
Modelo operacional de risco

O modelo utilizado é uma regressão logística calibrada.

Versão operacional:

risk-logistic-v2-20260910

A população utilizada para treinamento é:

entered_kpi_source == True

O target é:

kpi_breached_source

A probabilidade produzida pelo modelo é armazenada em:

breach_probability

Esse campo representa a probabilidade calibrada de violação operacional.

Índice preditivo

O campo:

predictive_risk_index

representa a posição relativa histórica da probabilidade calibrada em
relação à distribuição de referência utilizada pelo modelo.

O índice varia entre 0 e 1.

Valores maiores indicam posicionamento entre os casos historicamente mais
arriscados.

O índice preditivo não deve ser interpretado como probabilidade.

Risk Score

O Risk Score combina:

predictive_risk_index
priority_impact
operational_pressure

A fórmula operacional é:

risk_score =
100 × (
    0,80 × predictive_risk_index
    + 0,15 × priority_impact
    + 0,05 × operational_pressure
)

O score final é arredondado e limitado ao intervalo de 0 a 100.

Níveis de risco

Os níveis oficiais são:

Score	Nível
0 a 39	Baixo
40 a 59	Moderado
60 a 79	Alto
80 a 100	Crítico
Interpretação

Os campos abaixo possuem significados distintos:

breach_probability
predictive_risk_index
risk_score

breach_probability representa a probabilidade calibrada de violação.

predictive_risk_index representa a posição relativa histórica dessa
probabilidade.

risk_score é um índice operacional de priorização entre 0 e 100.

O Risk Score não deve ser interpretado como probabilidade.

Momento operacional

O score é calculado após a triagem inicial do incidente.

Nesse momento, atributos operacionais como grupo responsável, produto e
categoria podem estar disponíveis.

O modelo não utiliza informações futuras do mesmo incidente, como:

resolved_at
closed_at
duration_seconds
duration_hours
closure_code
solution_type
status

As features históricas utilizam somente informações anteriores ao incidente
avaliado.

Versionamento dos contratos

Mudanças de nome, tipo, domínio ou significado de campos devem ser
documentadas.

Alterações incompatíveis devem gerar nova versão do contrato ou migração
explícita.

Os dados originais da empresa e os indicadores fornecidos na fonte nunca
devem ser sobrescritos por cálculos derivados.

Persistência operacional

As previsões de volume vigentes são persistidas no Azure MySQL para consumo
pela aplicação.

Os scores de risco vigentes também são persistidos no Azure MySQL.

O dashboard consome esses contratos sem depender da implementação interna
dos modelos.

A ausência temporária de uma das estruturas de inferência não deve impedir o
funcionamento das demais funcionalidades do Albus-Hub.