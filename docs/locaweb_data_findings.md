# Diagnóstico inicial da base Locaweb

Análise direta do arquivo `LW-DATASET (1).xlsx`.

## Estrutura

- 122.543 incidentes
- 19 colunas
- IDs únicos e válidos no padrão `INC` + 7 dígitos
- Período de abertura: 02/01/2023 a 31/12/2025
- 121.811 registros estão em 2025

## Distribuição

- P1: 1
- P2: 15.649
- P3: 41.732
- P4: 64.828
- P5: 333
- Entraram no KPI: 25.600
- KPI violado: 248
- KPI não violado: 25.352
- KPI não aplicável: 96.943

## Nulos relevantes

- Produto: 63,598%
- Categoria: 63,423%
- Subcategoria: 63,423%
- Resolvido: 67,162%
- Solução: 87,515%
- Incidente Pai: 87,656%

Os nulos de produto, categoria e subcategoria estão fortemente concentrados nos incidentes com status `Sem Intervenção`.

## Resultado das verificações de qualidade

O pipeline processou os 122.543 registros com o status:

Não foram encontrados erros bloqueantes:
- campos obrigatórios nulos: 0;
- IDs duplicados: 0;
- IDs inválidos: 0;
- encerramento anterior à abertura: 0;
- duração negativa: 0.

Foram encontrados os seguintes alertas:

- resolução posterior ao encerramento: 32;
- divergência de duração: 475;
- subcategoria sem categoria: 2;
- divergência na regra de entrada no KPI: 151;
- divergência na regra de violação do KPI: 3.550.

## Alertas para a modelagem

1. O volume muda fortemente a partir de setembro de 2025: os totais mensais passam de aproximadamente 3,2–4,0 mil para 21,5–27,3 mil incidentes.
2. A maior parte desse aumento está ligada a P4 e incidentes fora do KPI, mas P2/P3 também mudam de comportamento.
3. O target `KPI Violado?` possui apenas 248 casos positivos entre 25.600 incidentes elegíveis, aproximadamente 0,97%.
4. A comparação das regras simples do dicionário com os campos fornecidos encontrou:
   - 151 divergências em `Entrou para KPI?`
   - 3.550 divergências em `KPI Violado?`
5. Existem 32 casos em que `Resolvido` é posterior a `Encerrado`.
6. Existem 475 casos em que a duração difere em mais de 2 segundos do intervalo abertura → resolução/encerramento.
7. Existem 2 casos em que a subcategoria está preenchida, mas a categoria está nula.

Os indicadores originais devem ser preservados. As regras recalculadas servem para auditoria e para levar dúvidas objetivas ao mentor, não para sobrescrever a fonte.
