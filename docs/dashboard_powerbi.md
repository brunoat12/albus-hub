# Albus-Hub — Modelo Power BI e plano de páginas

Documento de apoio da frente de visualização. O modelo semântico descrito aqui
já está criado no arquivo aberto do Power BI Desktop; o que falta é montar os
visuais das páginas.

## Fonte de dados

O modelo lê diretamente os artefatos do pipeline, sem duplicar transformação:

| Tabela | Origem | Grão |
|---|---|---|
| `fIncidentes` | `data/silver/locaweb_incidents.parquet` | um incidente |
| `fVolumeGold` | `data/gold/daily_incident_volume.parquet` | data × escopo de prioridade |
| `dCalendario` | tabela calculada em DAX | um dia |
| `_Medidas` | tabela técnica | — |

Ler o Parquet direto (`Parquet.Document`) mantém uma única fonte de verdade: quando
o time reprocessar o pipeline, basta **Atualizar** no Power BI. Se os arquivos
mudarem de lugar, ajuste o caminho em Transformar dados → Fonte.

`fIncidentes` e `fVolumeGold` se relacionam com `dCalendario` por data, em
cardinalidade muitos-para-um e filtro em direção única. `dCalendario` está
marcada como tabela de datas.

## A coluna `Regime` — leia antes de montar qualquer visual

A base tem **três patamares de volume**, e misturá-los distorce qualquer média:

| Regime | Incidentes | Média diária | Duração mediana | % Monitoramento |
|---|---|---|---|---|
| Base histórica (até 2024) | 732 | 1,0 | 4.187 h | 26% |
| Transição (jan–ago/2025) | 28.388 | 116,8 | 1,5 h | 55% |
| Regime atual (set/2025+) | 93.423 | 765,8 | 0,16 h | 95% |

A leitura mais provável é que a Locaweb ampliou a cobertura de monitoramento
automático, não que a operação piorou: o percentual de incidentes abertos por
monitoramento sobe de 26% para 95% e a duração mediana cai de horas para minutos.

Por isso `dCalendario[Regime]` existe: use como segmentação fixa em todas as
páginas, com "Regime atual" pré-selecionado. A medida `Regime em foco` devolve um
texto de alerta quando o recorte mistura patamares — vale como cartão no topo.

Isso também é um recado para a frente de modelagem: treinar D+1/D+7 na série
inteira embute uma quebra estrutural de 7× no meio dos dados.

## Medidas disponíveis

**01 Volume** — `Incidentes`, `Incidentes P2`, `Incidentes P3`, `Dias no período`, `Média diária`

**02 KPI e SLA** — `Entraram no KPI`, `KPI violado`, `Taxa de violação`, `Aderência a SLA`

**03 Atendimento** — `Duração mediana (h)`, `Duração P90 (h)`, `% Monitoramento`, `% Sem intervenção`

**04 Tendência** — `Incidentes MM7`, `Incidentes mês anterior`, `Var % mês anterior`, `Incidentes acumulado no ano`, `Participação no total`

**05 Conferência** — `Incidentes (Gold)`, `Diferença vs Gold`

**06 Contexto** — `Regime em foco`

`Diferença vs Gold` deve marcar **zero** em qualquer recorte. É a checagem de que o
modelo Power BI conta a mesma coisa que o pipeline. Hoje marca zero nos três regimes.

Duração usa **mediana e P90**, não média: a distribuição tem cauda longa (média de
69 h contra mediana de 0,16 h no regime atual). Média aqui engana.

## Plano de páginas

### Página 1 — Visão Geral

Segmentações no topo: `Regime` (padrão: Regime atual), `dCalendario[Date]` como
intervalo, `Prioridade`.

- Cartões: `Incidentes`, `Média diária`, `Taxa de violação`, `Aderência a SLA`, `Duração mediana (h)`
- Cartão de texto com `Regime em foco`
- **Gráfico de linhas** — `Incidentes` e `Incidentes MM7` por `dCalendario[Date]`
- **Colunas** — `Incidentes` por `dCalendario[Mês]` (já ordenado por número do mês)
- **Colunas** — `Incidentes` por `dCalendario[Dia da semana]`

### Página 2 — Operação

- **Barras horizontais** — `Incidentes` por `Grupo designado`, ordenado desc.
  Team14 concentra ~87% do volume no regime atual; considere um filtro Top N = 10.
- **Matriz** — linhas `Grupo designado`, colunas `Prioridade`, valores `Incidentes`
  e `Taxa de violação`
- **Barras** — `Taxa de violação` por `Grupo designado`, filtrando
  `Entraram no KPI >= 30` para não exibir taxa instável de grupo com volume baixo
- **Barras** — `Incidentes` por `Produto` e por `Categoria`

Sobre Pareto: se quiser a curva acumulada, coloque `Participação no total` como
coluna e o acumulado como linha, **ambos em percentual no mesmo eixo**. Não use
eixo secundário — duas escalas no mesmo gráfico é o erro mais comum em dashboard.

### Página 3 — SLA e Atendimento

- Cartões: `Entraram no KPI`, `KPI violado`, `Taxa de violação`, `Duração P90 (h)`
- **Mapa de árvore** ou barras — `KPI violado` por `Grupo designado`
- **Matriz** — linhas `dCalendario[Ano-Mês]`, valores `Aderência a SLA` e `Duração mediana (h)`
- **Colunas** — `Incidentes` por `fIncidentes[Hora de abertura]`

### Página 4 — Qualidade e Conferência

- Cartões `Incidentes`, `Incidentes (Gold)`, `Diferença vs Gold`
- Tabela por `dCalendario[Regime]` com as três medidas acima
- Texto documentando as 3.550 divergências entre a marcação de violação da fonte
  e a regra de SLA recalculada pelo pipeline (`entered_kpi_rule_mismatch` e
  `kpi_breached_rule_mismatch` no relatório de qualidade)

## Tema visual

O arquivo `docs/albus-hub-locaweb-dark.json` é um tema completo do Power BI no padrão
escuro Locaweb, alinhado ao protótipo e à versão Streamlit.

Para aplicar: **Exibir → Temas → Procurar temas** → selecione o arquivo. Ele define
fundo da página, fundo e borda dos visuais, cores de eixo e grade, tipografia dos
títulos em monoespaçada, tabelas e segmentações.

Lógica das cores — vale seguir mesmo ao criar visuais fora do tema:

| Papel | Cor | Onde usar |
|---|---|---|
| Série neutra / realizado | `#3987e5` | histórico, volume, participação |
| Previsto / alerta | `#e30613` | previsão D+1 e D+7, taxa de violação, acumulado |
| Positivo | `#1eae72` | aderência a SLA, checagens aprovadas |
| Atenção | `#f2b705` | alertas, P3 |
| Sério | `#f5803e` | P2, risco alto |
| Crítico | `#f2434f` | P1, KPI violado, risco crítico |
| Fundo da página | `#0a0a0c` | — |
| Fundo do visual | `#16151b` | — |
| Borda | `#2a2932` | — |
| Texto | `#f5f5f7` · secundário `#a8a7b0` · eixos `#6e6d78` | — |

Uma diferença deliberada em relação ao protótipo: lá quase todo número grande é
vermelho. Aqui o vermelho fica reservado para o que exige atenção — violação de SLA,
risco crítico, previsão. Número neutro fica em branco. Quando tudo é vermelho, nada é
urgente, e o olho para de encontrar o que importa.

A escala P1–P5 é ordinal de severidade e sempre aparece com o rótulo junto
(`dPrioridade[Rótulo curto]`), nunca só pela cor — quem enxerga cores de forma
diferente continua lendo o gráfico.

## Ordenação por prioridade

A tabela `dPrioridade` traz P1 a P5 com a coluna `Severidade` como chave de ordenação,
já configurada. Use `dPrioridade[Prioridade]` ou `dPrioridade[Rótulo curto]` nos eixos
para os visuais saírem na ordem certa em vez de alfabética.

Atenção ao montar: a base tem **1 único incidente P1** em três anos e apenas 20 P5 no
regime atual. Um gráfico de distribuição por prioridade vai parecer quebrado se você
esperar as cinco faixas equilibradas — o volume está concentrado em P4 (63%) e P3 (26%).
