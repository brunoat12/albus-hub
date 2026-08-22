# Metodologia — Previsão de Volume de Incidentes (frente ML, Integrante 2)

Documento explicativo do **processo** (do dado bruto à previsão) e do **porquê** de cada
escolha. Escrito para ser entendível por não-especialistas e servir de defesa no relatório.
Complementa o `README.md` (que traz os resultados). Atualizado: 2026-08-16.

---

## 1. Objetivo
Prever o **volume diário de incidentes** para **D+1** (amanhã) e **D+7** (7 dias), por
prioridade, dando um número + uma faixa de incerteza que o time de operação/BI consome.

---

## 2. Como organizamos os dados (matéria-prima → série)

O arquivo bruto tem **122.543 linhas — uma por incidente**. Isso não serve direto; viramos
em **"quantos incidentes por dia"**. Passos:

1. **Backup + cache.** Cópia de segurança do Excel + versão `.parquet` (abre rápido) para
   trabalhar sem risco ao original.
2. **Período: só 2025.** 99,4% do dado é de 2025; antes era piloto esparso. Misturar regimes
   estraga o modelo, então focamos em 2025.
3. **Deduplicação de cascatas.** Contamos **eventos, não alarmes**. Quando um ativo cai, o
   monitoramento abre 1 incidente **pai** + dezenas/centenas de **filhos** (coluna
   `Incidente Pai`). Ficamos só com os incidentes **sem pai** (raiz). Ex.: 05/11 tinha 684
   incidentes em P2, mas 510 eram filhos de UMA falha → deduplicado, o dia cai para ~84.
   *Bônus:* o próprio dicionário diz que "`Incidente Pai` preenchido não entra no KPI" — ou
   seja, deduplicar = contar o que o negócio realmente mede.
4. **Separar por prioridade** (P1–P5): cada prioridade é uma série com comportamento próprio.
5. **Agregar por dia:** de "lista de incidentes" para "contagem diária" → a **série temporal**.

Resultado: **5 séries diárias limpas** (uma por prioridade).

---

## 3. Como o modelo treina

**Ideia:** ensinar o modelo a prever o número de um dia usando **pistas conhecidas de antemão**.

- **Features (pistas):** dia da semana do alvo, feriado (BR), Black Friday, valor de ontem,
  valor do mesmo dia na semana passada, média/desvio dos últimos 7 e 28 dias, exposição
  (nº de CIs ativos). *Feature = uma característica que ajuda a prever.*
- **Alvo:** o número de incidentes em D+1 ou D+7.
- **Treino = flashcards:** mostramos milhares de exemplos do passado ("dadas estas pistas → a
  resposta foi X") e o modelo aprende a relação.
- **Sem vazamento (leakage):** toda pista usa **só o passado** (`shift`); nunca deixamos o
  modelo espiar a resposta. O calendário do dia-alvo pode ser usado porque é determinístico.
- **Avaliação honesta (backtest walk-forward):** simulamos estar em cada dia sabendo só o
  passado, prevemos o próximo, conferimos com o real — repetindo por todo o período de teste
  (Set–Dez 2025). Split é **temporal** (passado treina, futuro testa), nunca aleatório.
- **Um modelo por série:** cada prioridade tem dinâmica diferente (ver §5), então afinamos.

---

## 4. Ferramentas
**Python** + **pandas** (tabelas) + **scikit-learn** (modelos) + **matplotlib** (gráficos) +
**holidays** (feriados BR). Formatos: `.xlsx` (bruto, fora do git) e `.parquet` (rápido).

---

## 5. Os algoritmos escolhidos — e POR QUÊ

Filosofia: uma **escada** — da régua boba ao modelo esperto — onde cada degrau tem função.

| Algoritmo | Papel | Por que escolhemos |
|---|---|---|
| **Naïve sazonal** (amanhã = mesmo dia da semana passada) | Régua/baseline | Em dado com forte sazonalidade semanal, é um baseline **honesto e difícil de bater**. Sem uma régua, não sabemos se o modelo aprendeu algo. |
| **Regressão linear / Ridge** | **Modelo principal** | (1) A disciplina exige um modelo **interpretável** — na regressão linear dá para **ler quais pistas pesam** (os coeficientes). (2) É **estável com poucos dados** (~122 dias). (3) O **Ridge** (linear com regularização) lida bem com pistas correlacionadas (lags/médias) sem "decorar" (overfit). (4) Na prática, **venceu**. |
| **Poisson / Poisson-offset** | Modelo correto p/ contagem | O alvo é **contagem** (inteiro ≥ 0, variância cresce com a média). Poisson é a família **estatisticamente correta** para isso e **nunca prevê negativo**. A versão *offset* usa a **exposição** (CIs ativos) para atravessar a mudança de monitoramento. Também é interpretável (efeitos multiplicativos). |
| **Gradient Boosting (GBR)** | Termômetro/teto | Modelo mais esperto que capta **padrões não-lineares**. Serve para medir o **teto de acerto**: se o modelo interpretável chega perto do GBR, sabemos que não estamos perdendo muito. Não é o entregável (é "caixa-preta"). |

**Por que ESTE conjunto (e não outros):**
- **Por que não Deep Learning / LSTM aqui?** Pouco dado (~122 dias) → redes neurais
  **overfittam** e não são interpretáveis; seria canhão para matar mosca. (ANN fica na frente
  de **risco/Deep Learning** — Integrante 3 — onde faz sentido.)
- **Por que não ARIMA/Prophet como principal?** São bons para série temporal, mas encaixam
  menos no requisito de **interpretabilidade por variável** e incorporam com menos naturalidade
  as features externas (exposição, Black Friday). Podem entrar como **comparação**, não como
  carro-chefe.

**Como o algoritmo casa com cada série (o que a EDA mostrou):**
- **P2 / P3** (dependem de calendário + nível recente) → regressão com features (Ridge/Poisson).
- **P4** (lisa, pura inércia) → mesmo arcabouço, dominado por lags (AR).
- **P5** (rara, quase sempre zero) → modelo de **contagem** (Poisson) ou demanda intermitente.
- **P1** (1 evento no ano) → **não há série**; tratamos como evento raro.

---

## 6. Como damos a nota (métricas)
- **MAE** — erro médio em **nº de incidentes** ("erra ~X/dia").
- **sMAPE** — erro em **%** (compara séries de tamanhos diferentes).
- **Skill vs naïve** — **quanto melhor** que a régua boba.
- **Cobertura do intervalo** — % de vezes que o real cai dentro da faixa prevista (meta ~80%).

---

## 7. Limitações declaradas
- Regime pleno tem ~4 meses (Set–Dez) → capta sazonalidade **semanal**, não anual.
- **Storms de cascata** são imprevisíveis no *timing* → vão para o **intervalo**, não o ponto.
- Previsões para 2026 **extrapolam** → mais incerteza.

---

## 8. Estado / versões
- **v2** (branch `feature/ml-volume-forecast`): recortes ALL/P2/P3, série crua. Já no repo.
- **v3** (em desenho): por prioridade, sobre a **série deduplicada** (mais previsível — em P2 o
  sMAPE caiu de ~55% para ~32% ao deduplicar). Este documento reflete a metodologia do v3.
