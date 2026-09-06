# Metodologia — Previsão de Volume de Incidentes
### Albus Hub · Challenge Locaweb/FIAP 2026 · Frente de Machine Learning (Integrante 2)

Documento completo do processo: **do arquivo bruto até a previsão**, explicando *o que* fizemos,
*por que* fizemos e *o que descartamos no caminho* — sempre com o número que sustenta a decisão.
Escrito para ser entendido por quem não é especialista e servir de defesa no relatório.

Versão do modelo: **`volume_v3.2_2026-08-21`** · Atualizado: 21/08/2026

---

## 1. O objetivo

Prever **quantos incidentes vão ser abertos** amanhã (**D+1**) e daqui a uma semana (**D+7**),
separado por **prioridade** (P1 a P5) e no total (ALL), entregando **um número e uma faixa de
incerteza** que a operação e o BI consomem sem abrir notebook.

É uma **ferramenta de apoio à decisão**: dimensionar plantão, antecipar pressão sobre times.
Não emite parecer nem substitui julgamento humano.

---

## 2. A matéria-prima

| Item | Valor |
|---|---|
| Arquivo | `LW-DATASET.xlsx`, aba `Dataset Geral` |
| Tamanho | **122.543 linhas × 19 colunas** |
| Chave | `Número` (formato `INCxxxxx`) — **100% única**, sem duplicata |
| Período (`Aberto`) | 02/01/2023 → 31/12/2025 |
| Integridade das datas | **0** violações de ordem (`Aberto` ≤ `Resolvido` ≤ `Encerrado`), **0** datas futuras |

**Colunas que importam para volume:** `Aberto` (quando o incidente nasceu — é o nosso relógio),
`Prioridade` (1 Crítica … 5 Muito Baixa), `Incidente Pai` (liga um incidente-filho ao evento que
o causou), `Item de configuração` (o "CI" — o ativo monitorado), `Aberto por` (Manual ou
Monitoramento).

**Primeira coisa que fizemos: backup.** Antes de qualquer transformação, cópia do original em
`Dados/backup/LW-DATASET_ORIGINAL_2026-08-11.xlsx` com hash SHA-256 registrado em `MANIFEST.txt`
(`6e736d88…5de1ca`, conferido). Regra do projeto: **o arquivo bruto é fonte de verdade e nunca é
sobrescrito.**

---

## 3. Limpeza e preparo — o que fizemos e por quê

O arquivo tem **uma linha por incidente**. Um modelo de série temporal precisa de **uma linha por
dia**. A transformação tem 5 passos, e cada um foi uma decisão consciente.

### 3.1 Cache em Parquet
O `.xlsx` demora ~30s para abrir; convertemos para `.parquet` (formato colunar comprimido) que
abre em menos de 1s. *Por quê:* iterar rápido. O parquet é derivado — se o bruto mudar, ele é
regerado.

### 3.2 Recorte: só 2025
2023 + 2024 juntos somam **732 linhas** em 730 dias — cerca de **1 incidente por dia**. Isso é
período piloto, não operação: não forma série diária utilizável. 2025 tem **99,4% do dado** e
**calendário 100% completo** (365 de 365 dias com registro), então não há buraco para imputar.

### 3.3 Deduplicação de cascatas — a decisão que mais mudou o resultado

**O problema:** quando um ativo cai, o monitoramento não abre 1 incidente. Abre **1 pai + dezenas
ou centenas de filhos** (cada serviço afetado vira um alarme). A coluna `Incidente Pai` marca
quem é filho.

**Exemplos reais medidos:**
- **05/11/2025** — P2 registrou 684 incidentes no dia. **510 deles eram filhos de UMA única
  falha.** Deduplicado, o dia cai para ~84.
- **22/09/2025** — um único incidente-pai gerou **630 filhos**.

**A decisão:** ficar apenas com os incidentes **sem pai** (os "raiz"). Ou seja, **contar eventos,
não alarmes.**

**Por que é legítimo (e não "jogar dado fora"):** o próprio dicionário de dados diz que
*incidente com `Incidente Pai` preenchido não entra no KPI*. Deduplicar é justamente contar o que
o negócio já mede. Um pico de 684 alarmes não é 684 problemas — é **um** problema.

**O efeito, medido:**

| Métrica | P2 cru | P2 dedup | P3 cru | P3 dedup |
|---|---:|---:|---:|---:|
| Máximo em um dia | 684 | **84** | — | — |
| Coeficiente de variação (cv) | 1,01 | **0,44** | — | — |
| Autocorrelação lag-1 | 0,05 | **0,32** | 0,57 | **0,76** |
| Erro do modelo (sMAPE) | ~55% | **~32%** | — | — |

A leitura importante é o **acf1** (o quanto o dia de hoje ajuda a prever o de amanhã): em P2 ele
sai de 0,05 — praticamente nada, série imprevisível — para 0,32. **A dedup não melhorou o
modelo; ela revelou o sinal que os alarmes escondiam.**

### 3.4 Separação por prioridade
P1…P5 viram séries independentes. *Por quê:* a seção 4.4 mostra que elas têm comportamentos
**qualitativamente diferentes** (P2 é humana e cai no fim de semana; P4 é máquina e não sabe que
é domingo). Um modelo só para todas seria a média de coisas que não se parecem.

### 3.5 Agregação diária
`groupby(dia).size()` sobre a série deduplicada, reindexado no calendário completo. Resultado:
**6 séries diárias limpas** (ALL + P1…P5).

---

## 4. EDA — por que os dados oscilam

Esta é a parte que explica o comportamento do dado. Encontramos **quatro fontes de oscilação
diferentes**, e cada uma pede um tratamento diferente.

### 4.1 Patamar — a quebra de regime de 1º/set/2025 (a mais importante)

O volume **saltou ~7×** de um dia para o outro:

| Período | Média/dia |
|---|---:|
| jan–ago/2025 | ~117 |
| set–dez/2025 | ~766 |

**Isso não é aumento de incidente. É aumento de monitoramento.** A prova está em decompor o
salto por origem (razão set–dez ÷ jan–ago):

| Recorte | Razão | Leitura |
|---|---:|---|
| Aberto por **Manual** | **0,77×** | aberturas humanas **caíram** |
| Aberto por **Monitoramento** | **11,4×** | explosão de alarmes automáticos |
| Elegíveis a **KPI** | **0,85×** | carga que o negócio mede ficou **estável** |

Complementando: entraram **~1.718 CIs novos** em setembro, e praticamente todo o crescimento está
em **um único time (`Team14`, 76% das aberturas)** e em templates de alerta.

> **Insight de pitch:** o volume bruto multiplicou por ~6,6, mas a **carga operacional real ficou
> estável**. Quem olhar só o gráfico de volume conclui "a operação está afundando" — e está
> errado. O dado só ganhou visibilidade.

**Consequência prática:** são dois mundos. O modelo **treina** com os dois (ver 8.2), mas a
**nota** só pode ser tirada no mundo em que ele vai operar — o de 766/dia. Medir acerto em
jan–ago daria um MAE pequeno só porque a loja era pequena, não porque acertamos mais.

### 4.2 Surto — os picos são cascatas, não crises

Investigamos os dias de pico (acima de média + 1,5 desvio) e a composição é dominada por
**cascatas pai→filho** (ver 3.3) concentradas em poucos templates de alerta. Depois da
deduplicação, os picos somem sem que o sinal de fundo mude.

**Tratamento:** o que sobra de imprevisível vai para o **intervalo de incerteza**, não para o
número central. Não faz sentido tentar prever *o dia* em que um roteador vai cair.

### 4.3 Ciclo — calendário

Testamos dia da semana, feriados nacionais (biblioteca `holidays`, Brasil), Black Friday e
temporada de dezembro.

- **Sazonalidade semanal existe, mas só onde há mão humana** (números na 4.4).
- **Feriados:** efeito fraco e inconsistente — mantido como feature, mas não é driver.
- **Black Friday:** alta leve e mensurável (~+16/dia na semana).
- **Eventos externos:** verificamos as quedas públicas de **AWS (20/10/2025)** e **Cloudflare
  (18/11/2025)**. **Não correlacionam** com os picos do dataset. Foi um teste que deu negativo — e
  isso é resultado: descarta a hipótese "os picos vêm de incidentes globais de nuvem".

### 4.4 Anatomia de cada série (set–dez, deduplicada)

| série | média/dia | dp | cv | var/média | força sazonal | força tendência | acf1 | acf7 | fds/útil |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **ALL** | 687,1 | 160,6 | 0,23 | 37,5 | 0,22 | 0,63 | 0,73 | 0,37 | 0,86 |
| **P2** | 34,5 | 15,1 | 0,44 | 6,6 | **0,46** | 0,24 | 0,32 | 0,36 | **0,52** |
| **P3** | 181,5 | 105,6 | 0,58 | **61,5** | 0,41 | **0,82** | 0,76 | 0,67 | 0,67 |
| **P4** | 471,0 | 120,1 | 0,26 | 30,6 | **0,03** | 0,54 | 0,75 | **0,00** | **0,97** |
| **P5** | 0,2 | 0,5 | 2,76 | 1,2 | 0,09 | 0,23 | 0,15 | 0,02 | — |

*Como ler:* **força sazonal/tendência** vão de 0 (não existe) a 1 (domina). **var/média** seria
**1** se fosse contagem pura (Poisson); acima disso indica surtos. **acf1/acf7** medem o quanto o
dia anterior / o mesmo dia da semana passada ajudam a prever. **fds/útil** = volume médio de fim
de semana dividido pelo de dia útil.

**Perfil semanal (média por dia da semana):**

| série | seg | ter | qua | qui | sex | sáb | dom |
|---|---:|---:|---:|---:|---:|---:|---:|
| ALL | 702 | 744 | 713 | 694 | 723 | 632 | 596 |
| P2 | 39 | 46 | 40 | 39 | 35 | **22** | **19** |
| P3 | 214 | 212 | 191 | 172 | 211 | 141 | 125 |
| P4 | 449 | 486 | 482 | 482 | 477 | **469** | **451** |

**O que isso ensina, série por série:**

- **P2 é humana.** Cai **pela metade** no fim de semana (0,52) e tem a maior força sazonal (0,46).
  Segue horário comercial.
- **P4 é máquina.** Força sazonal **0,03** e acf7 **0,00**: é totalmente plana, roda 24/7 e **não
  sabe que é domingo**. Isso tem consequência direta na escolha do baseline (seção 7.2).
- **P3 é a mais volátil** (var/média 61,5) e a que mais "anda de nível" (tendência 0,82) — sobe e
  desce em ondas de semanas.
- **Todas são fortemente superdispersas** (var/média de 30 a 60, contra 1 do Poisson puro): boa
  parte do movimento é **surto genuinamente imprevisível**. Isso é o teto de acerto, e por isso o
  intervalo importa tanto quanto o ponto.
- **P5 é intermitente** (quase sempre 0) e **P1 teve 1 evento no ano inteiro** — não há série;
  tratamos como evento raro.

---

## 5. Como o modelo aprende

**Ideia:** transformar previsão de série temporal em **regressão supervisionada**. Uma linha por
dia; a resposta é o valor de D+1 (ou D+7); as perguntas são pistas conhecidas de antemão.

**Features (as pistas):**

| Grupo | Features |
|---|---|
| Calendário (determinístico) | dia da semana (one-hot), fim de semana, feriado BR, semana da Black Friday, temporada de dezembro |
| Histórico da série | valor do mesmo dia semana passada (`seas_lag7`, `seas_lag14`), último valor, média e desvio dos últimos 7 dias, média dos últimos 28 |
| Exposição | nº de CIs ativos (último e média de 7 dias) — é o que "atravessa" a quebra de regime |
| Tendência | contador de tempo |

**Antivazamento (*data leakage*) — regra inegociável:**
- Split **temporal**: passado treina, futuro testa. **Nunca** aleatório.
- Toda feature de histórico leva `shift(h)`: ao prever D+7, o modelo só enxerga o que se sabia 7
  dias antes.
- O calendário do dia-alvo **pode** ser usado — é determinístico, sabemos hoje que 25/12 é feriado.
- **Proibido** derivar qualquer coisa de `Resolvido`, `Encerrado`, `Duração`, `Código de
  fechamento`, `Solução` — isso só existe *depois* que o incidente acabou.

**Avaliação — backtest walk-forward:** simulamos estar em cada dia sabendo só o passado, o modelo
é **re-treinado**, prevê o próximo, conferimos com o real, e avançamos um dia. Repetido por todo
o período de teste.

---

## 6. Os algoritmos — e por que estes

Filosofia: uma **escada de complexidade**. Só se paga complexidade (e perda de interpretabilidade)
quando ela compra acerto.

| Degrau | Algoritmo | Como funciona | Por que está aqui |
|---|---|---|---|
| 0 | **naive7** | "amanhã = mesmo dia da semana passada" | régua de comparação clássica em série com ciclo semanal |
| 0 | **media7** | média dos últimos 7 dias conhecidos | régua para séries **sem** ciclo semanal |
| 0 | **ultimo** | repete o último valor conhecido | régua de persistência; imbatível em série muito lisa |
| 1 | **Ridge** (linear regularizada) | soma ponderada das pistas; a regularização impede que um peso exploda | é o **interpretável**: dá para ler quanto cada pista pesa. Exigência da disciplina. Estável com poucos dados |
| 2 | **Poisson-offset** | modela a **taxa** (incidentes por CI ativo) e multiplica pela exposição | família **estatisticamente correta** para contagem: nunca prevê negativo, variância cresce com a média. O *offset* é o que atravessa a mudança de monitoramento |
| 3 | **GBR** (gradient boosting, perda Poisson) | centenas de arvorezinhas, cada uma corrigindo o erro da anterior | capta **não-linearidade**; mede o teto de acerto. É caixa-preta, então só entra se ganhar de verdade |

### O que descartamos, e por quê

- **LSTM / redes neurais para volume:** ~122 dias de regime pleno. Rede neural com esse volume de
  dado **decora** (overfit) e não é interpretável. Seria canhão para matar mosca. *(ANN faz
  sentido na frente de risco — Integrante 3 — onde o problema é outro.)*
- **ARIMA / Prophet como carro-chefe:** são bons em série temporal, mas incorporam com menos
  naturalidade as features externas (exposição de CIs, Black Friday) e entregam menos
  interpretabilidade **por variável**, que é o que a disciplina cobra. Cabem como comparação
  futura, não como entregável.
- **Poisson simples (sem offset):** foi testado e **falhou** — o link logarítmico ficou instável
  na quebra de regime (P2 D+1 chegou a **−102%** de skill, ou seja, muito pior que a régua boba).
  Substituído pelo Poisson-offset, que resolveu (+18% na mesma série). **Erro registrado de
  propósito:** mostra que a escolha veio de teste, não de preferência.

---

## 7. Como medimos — e como consertamos a medição

### 7.1 As métricas
- **MAE** — erro médio em nº de incidentes ("erra ~X por dia"). É a métrica principal.
- **RMSE** — pune erro grande mais que erro pequeno.
- **sMAPE** — erro em %, permite comparar séries de tamanhos diferentes.
- **Skill** — quanto **melhor que a régua boba**. É o número que diz se o ML valeu a pena.
- **Cobertura** — % de dias em que o valor real caiu dentro da faixa prevista (meta 80%).

### 7.2 Correção nº 1 — o baseline estava frouxo

Até a v3.1 comparávamos só contra **naive7**. A EDA (4.4) mostrou o furo: **o P4 não tem
sazonalidade semanal** (força 0,03, acf7 0,00). Comparar o P4 contra "mesmo dia da semana passada"
é competir contra um espantalho.

Medimos as três réguas (set22–dez, MAE):

| série | naive7 | media7 | ultimo | melhor régua |
|---|---:|---:|---:|---|
| ALL D+1 | 113,3 | 87,8 | **86,8** | ultimo |
| P2 D+1 | 14,2 | **13,3** | 14,3 | media7 |
| P3 D+1 | 62,1 | **50,7** | 55,1 | media7 |
| P4 D+1 | 86,5 | 63,1 | **54,7** | ultimo |

O naive7 é de **35% a 58% pior** que a melhor régua em ALL e P4. Todo skill medido contra ele
estava inflado. **Correção: o skill agora é sempre contra a melhor das três.**

### 7.3 Correção nº 2 — o modelo era escolhido olhando a prova

A v3.1 escolhia o "melhor modelo" pelo menor MAE **no próprio conjunto de teste**. Isso é
otimista por construção — e a instabilidade era real: rodando por blocos de 3 semanas, o vencedor
alternava entre Ridge, GBR e Poisson-offset a cada bloco.

**Correção — protocolo em três tempos:**

```
set–out/2025 (61 dias)  →  escolhe o preditor    [nunca vira nota]
nov–dez/2025 (61 dias)  →  produz a nota         [nunca participa da escolha]
```

E mais: **as réguas bobas são candidatas de pleno direito**, com regra de Occam ao longo da escada
da seção 6 — fica o preditor **mais simples** que chegar a 5% do melhor. Se a régua simples ganha,
**entregamos a régua simples**. Isso é decisão de engenharia, não fracasso do ML.

### 7.4 Robustez — o ganho se repete?

Antes de confiar em qualquer número, fatiamos o teste em 6 blocos de ~3 semanas
(skill do Ridge vs naive7, D+1):

| série | F1 | F2 | F3 | F4 | F5 | F6 | médio | pior |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | +49 | +10 | +30 | +28 | +30 | +33 | +30 | **+10** |
| P2 | +20 | +23 | +12 | +14 | +31 | +18 | +20 | **+12** |
| P3 | +25 | −0 | +8 | +14 | +39 | +53 | +23 | **−0** |
| P4 | +46 | +7 | +44 | +36 | +0 | +32 | +27 | **+0** |

Em **D+1 o ganho nunca fica negativo** em nenhum dos 6 blocos → é consistente, não foi sorte de
um período. Em **D+7 o Ridge não se sustenta** (fica negativo em vários blocos para ALL e P4) —
ali só o GBR segura, e é por isso que o D+7 acabou majoritariamente com GBR.

---

## 8. Decisões registradas (com a evidência)

### 8.1 Deduplicar cascatas — **SIM**
Evidência: seção 3.3 (acf1 de P2 sai de 0,05 → 0,32; sMAPE 55% → 32%).
Justificativa de negócio: o dicionário exclui incidente-filho do KPI.

### 8.2 Janela de treino: ano inteiro ou só o regime novo? — **ANO INTEIRO**

Hipótese que levantamos: treinar só em set–dez (regime homogêneo) evitaria o degrau e seria
melhor. **Testamos e a hipótese é FALSA** (MAE em nov–dez, mesmo modelo, só muda o treino):

| série | modelo | treino = ano | treino = set–dez | efeito |
|---|---|---:|---:|---:|
| ALL D+1 | Ridge | **74,0** | 89,3 | **−21%** |
| P4 D+1 | Ridge | **56,1** | 69,6 | **−24%** |
| P4 D+7 | Poisson-offset | **91,8** | 146,5 | **−60%** |
| P3 D+1 | Poisson-offset | 67,7 | **57,3** | +15% |
| P3 D+7 | Poisson-offset | 69,8 | **62,1** | +11% |
| ALL D+7 | GBR | 91,6 | 91,6 | 0% |

**Leitura:** perder dado machuca mais do que a heterogeneidade de regime atrapalha. A exceção é o
Poisson-offset, que já normaliza pela exposição e por isso prefere a janela curta.
**Decisão: treino no ano inteiro.** *(Hipótese minha, refutada pelo dado — fica registrada.)*

### 8.3 Escopo de avaliação: por que a nota é só no regime novo
Ver 4.1. O modelo vai operar num mundo de ~766/dia; medir acerto no mundo de ~117/dia daria um
número bonito e inútil. Os dois períodos **não são comparáveis em escala absoluta**.

### 8.4 Escolha do preditor — Occam sobre a escada
Ver 7.3. Preferência declarada *a priori*: régua boba < Ridge < Poisson-offset < GBR, tolerância
de 5%.

---

## 9. A faixa de incerteza (intervalo conformal adaptativo)

**Por que uma faixa, e não só um número.** "Amanhã abrem 395 incidentes" é quase sempre errado no
detalhe. O útil para operação é "**entre 302 e 605, com 80% de confiança**" — dá para dimensionar
plantão.

**Como era, e por que desafinava.** Usávamos a mesma largura todo dia, tirada dos quantis dos
erros passados. Mas o erro não tem o mesmo tamanho todo dia: em dia cheio erra-se mais. Resultado:
faixa **faltando** nos dias movimentados e **sobrando** nos calmos.

**Como é agora.** Duas ideias somadas:

1. **A largura acompanha o tamanho do dia:** proporcional a **√(previsto)**. Não é chute — em
   dados de contagem o desvio típico cresce com a raiz da média. *Analogia: a margem de erro de
   uma pesquisa depende do tamanho da amostra; não é um número fixo.*
2. **A faixa se auto-corrige todo dia** (*ACI — Adaptive Conformal Inference*): caiu fora → alarga
   amanhã; sobrou folga demais → aperta amanhã. É um termostato perseguindo os 80%.

**Honestidade:** cada dia usa **só erros de dias anteriores** (janela de 60 dias), nunca o futuro.
Os 28 primeiros dias são aquecimento e não entram na conta.

**Resultado:** cobertura entre **75% e 84%** em todas as séries (meta 80%).

---

## 10. Resultados

**Protocolo:** escolha em set–out/2025 · nota em **nov–dez/2025 (61 dias nunca vistos na escolha)**
· skill contra a **melhor** das três réguas bobas.

| série | hor | preditor escolhido | tipo | MAE | sMAPE | **skill** | (vs naive7) | cobertura |
|---|---|---|---|---:|---:|---:|---:|---:|
| ALL | D+1 | `ultimo` | régua simples | 76,6 | 10,3% | −4% | +27% | 77% |
| ALL | D+7 | GBR | modelo | 91,6 | 12,7% | **+13%** | +13% | 80% |
| P1 | D+1/D+7 | `naive7` | régua simples | 0,0 | — | n/a | n/a | 100% |
| P2 | D+1 | **Ridge** | modelo | 9,8 | 30,0% | **+16%** | +23% | 79% |
| P2 | D+7 | GBR | modelo | 10,0 | 30,9% | **+15%** | +22% | 79% |
| P3 | D+1 | GBR | modelo | 58,9 | 29,4% | −7% | +22% | 82% |
| P3 | D+7 | GBR | modelo | 62,1 | 30,8% | **+18%** | +18% | 79% |
| P4 | D+1 | `ultimo` | régua simples | 49,5 | 10,5% | +0% | +37% | 75% |
| P4 | D+7 | GBR | modelo | 66,2 | 14,3% | **+14%** | +15% | 84% |
| P5 | D+1 | GBR | modelo | 0,3 | 194,5% | −3% | +15% | 79% |
| P5 | D+7 | GBR | modelo | 0,2 | 192,4% | **+30%** | +32% | 82% |

*(O sMAPE do P5 é ~194% porque a série é quase sempre zero e a divisão explode — **é métrica sem
sentido nesse caso**; o número honesto ali é o MAE de 0,2, ou seja "esperar ~0, às vezes 1".)*

### A leitura honesta

**Em D+7 o ML ganha em todas as séries (+13% a +30%).** Faz sentido mecanicamente: a 7 dias de
distância a regra "repete o valor de ontem" perde validade, e é aí que calendário, exposição e
nível recente passam a valer.

**Em D+1 o ML só ganha claramente no P2 (+16%).** Em ALL e P4, séries lisas e persistentes, a
regra trivial é imbatível — e o pipeline **entrega a regra trivial** nesses casos.

**Uma mancha declarada:** no P3 D+1 a seleção escolheu GBR (−7%), mas o **Ridge teria dado +16%**.
A escolha errou porque 61 dias de seleção ainda é pouco. Preferir o Ridge aqui exigiria olhar o
período da nota — que é exatamente o vício que o protocolo elimina. **Fica como limitação, não
maquiada.**

**Nota de honestidade sobre versões anteriores:** o "+35%" que aparecia na v3/v3.1 era
aritmeticamente correto, mas contra a régua fraca (naive7) e com o modelo escolhido olhando o
teste. Os números desta seção são menores e **defensáveis**.

### Previsão futura (a partir de 31/12/2025), no contrato

| série | D+1 (01/01) | D+7 (07/01) |
|---|---|---|
| ALL | 752 (635–900) | 889 (790–1092) |
| P2 | 29 (16–43) | 41 (25–60) |
| P3 | 395 (302–605) | 297 (207–528) |
| P4 | 367 (300–434) | 447 (367–559) |
| P5 | ~0 (0–1) | ~0 (0–1) |
| P1 | 0 | 0 |

---

## 11. Limitações declaradas

1. **Regime pleno tem ~4 meses.** Captamos sazonalidade **semanal**, não anual. Não sabemos o que
   acontece em Carnaval, férias de julho ou fechamento de ano fiscal.
2. **Janela de seleção curta (61 dias).** Foi o que causou a escolha ruim no P3 D+1.
3. **Storms de cascata são imprevisíveis no *timing*.** Vão para o intervalo, não para o ponto.
4. **Previsões para 2026 extrapolam** — o modelo nunca viu janeiro.
5. **Séries superdispersas** (var/média 30–60): há um teto de acerto que nenhum modelo vence.
6. **Avaliação no regime antigo não foi feita.** Um teste de robustez legítimo seria medir jan–ago
   com **erro relativo** (adimensional, imune à diferença de escala). Está identificado como
   próximo passo, não executado.

---

## 12. Ferramentas, arquivos e como rodar

**Stack:** Python 3.14 · pandas (tabelas) · scikit-learn (modelos) · matplotlib (gráficos) ·
`holidays` (feriados BR) · pyarrow (parquet) · streamlit (painel).

```bash
python pipeline_prioridades.py   # treina, faz backtest, gera outputs/ e plots/
python predict.py                # imprime a previsão futura no contrato
streamlit run app_streamlit.py   # painel
```

```python
from predict import prever_volume
prever_volume(scope="P3", horizon="D+1")   # o BI / o app chamam assim
```

| Arquivo | O que é |
|---|---|
| `pipeline_prioridades.py` | pipeline **v3.2** — o entregável |
| `predict.py` | função de inferência (lê o contrato) |
| `app_streamlit.py` | painel |
| `outputs/predictions_volume.csv\|.parquet` | predições no contrato |
| `outputs/metrics.json` | métricas completas, incluindo o MAE de **todos** os candidatos |
| `plots/backtest_v32_D1.png` | previsto vs real com intervalo |
| `data/incidents.parquet` | dado tratado (versionado por decisão do time) |

**Contrato de saída (congelado):** `reference_date, horizon (D+1|D+7), scope (ALL|P1..P5),
predicted_incidents, actual_incidents, lower_bound, upper_bound, model, model_version,
generated_at`.

---

## 13. Histórico de versões

| Versão | O que trouxe |
|---|---|
| v1 | primeira série ALL/P2/P3, série crua |
| v2 | Poisson-**offset** (consertou a instabilidade do Poisson simples), exposição por CIs ativos |
| v3 | **deduplicação de cascatas** + um modelo por prioridade |
| v3.1 | **intervalo conformal adaptativo** (faixa que se ajusta sozinha) |
| **v3.2** | **honestidade metodológica**: baseline justo, janela de treino testada, preditor escolhido fora do período de nota, réguas simples como candidatas |

---

## 14. Guardrails do produto

Ferramenta de **apoio à decisão** — não emite parecer. Toda afirmação deste documento tem número
rastreável ao dado. Declarar incerteza (ou dizer "aqui a régua simples ganha") é comportamento
correto, não falha. Nenhum dado pessoal real nem segredo no repositório; a anonimização já vem do
dataset de origem.
