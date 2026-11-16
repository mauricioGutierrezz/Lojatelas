# HANDOFF — Urdimbre

## 1. Objetivo do projeto

Sistema local-first para gestão operacional e auditoria de uma loja de tecidos e mercadorias relacionadas.

O sistema deve acompanhar a trajetória física e financeira da mercadoria:

`categoria -> produto -> ingresso -> estoque físico individualizado (m/kg) ou agregado (un) -> corte/retirada -> ticket -> pagamento/venda -> auditoria`

A operação da loja deve funcionar localmente mesmo sem internet e sem depender do módulo administrativo. A sequência de entregas é Ingreso / Stock, Corte / Ticket, Caja / Venta e Administrativo separado sobre o mesmo núcleo de dados. Acesso remoto e VPN permanecem posteriores.

---

## 2. Princípio central de rastreabilidade

O sistema não deve apenas saber quanto existe em estoque.

Ele deve conseguir explicar:

- de onde veio;
- em qual rolo/peça estava, para `m`/`kg`; para `un`, quais ingressos e retiradas compõem o saldo agregado do produto, sem atribuir cada saída a um ingresso;
- quando foi movimentado;
- qual responsável foi registrado, sem presumir autoria individual pela sessão compartilhada;
- quanto foi retirado;
- qual é o vínculo da retirada com o ticket, o pagamento e as movimentações registradas, sem presumir tratamento para material cortado que não seja pago.

### Invariante física fundamental

> Nenhuma operação posterior pode aumentar o comprimento restante de um rolo depois que material foi fisicamente cortado dele.

O saldo resultante do corte não pode ser recomposto por operação posterior. Essa invariante não impede novos ingressos legítimos no agregado de `un`: eles são novas entradas documentadas, nunca desfazem a retirada anterior.

---

## 3. Decisões de domínio já fechadas

### 3.1 Produto e categoria

- `tipos_tela`/categoria serve para classificação, filtros e relatórios.
- `produtos` representa o item vendível específico.
- O preço pertence ao produto, não à categoria.
- A atendente pode cadastrar um produto novo e definir seu preço inicial. Alterações posteriores de preço ocorrem pela área protegida de preços com PIN geral; o cadastro inicial não autoriza alterar preços existentes fora desse fluxo.
- Produtos podem usar diferentes unidades de medida, atualmente previstas:
  - `m`
  - `kg`
  - `un`
- Quantidades de `m` e `kg` podem ser fracionárias; `un` admite somente inteiros, tanto no ingresso quanto nas quantidades vendida e retirada.
- Usar `NUMERIC`, não `FLOAT`.
- `largura_metros` é uma característica física de produtos têxteis; pode ser usada em `m` e não aparece na operação de `un`. Não apagar dados históricos por ocultar um campo.
- A largura não participa do cálculo de estoque em metro linear.

---

### Fotos de produto — extensão aprovada

- Produto pode ter uma foto principal para identificação rápida do tecido. Adicionar/substituir no cadastro por seleção/upload de arquivo ou colagem de imagem da área de transferência, inclusive imagem copiada do WhatsApp Web ou captura de tela.
- Mostrar miniatura no cadastro/stock e nas buscas/listas operacionais em que ajude a identificar o produto; obrigatória na futura lista protegida de preços. Clicar/tocar abre visualização maior.
- Preferir estrutura separada para fotos, preparada para evolução; a regra atual permanece uma única foto principal por produto, não uma galeria.
- Não implementar múltiplas fotos, galeria, crop, edição, câmera, organização de fotos ou histórico avançado de imagens.

### 3.2 Estoque conforme unidade — revisão transversal aprovada em 2026-10-07

Esta decisão substitui a individualização universal e a linguagem universal de rolo dos recortes anteriores. Não altera retroativamente a descrição dos registros existentes.

- `m`: cada rolo físico é individualizado, com saldo decimal próprio e estados fechado/aberto/esgotado. Origem física obrigatória no corte; preservar MAX, distribuição e revisão.
- `kg`: cada peça física é individualizada, com saldo decimal próprio. Ingresso por quantidade de peças × peso por peça; retirada por peso de uma ou várias peças. Uma peça parcialmente retirada fica aberta, intacta permanece fechada e zerada fica esgotada. A interface usa linguagem de peça/peso, sem obrigar o termo rolo.
- `un`: estoque agregado por produto, somente inteiros. Ingressos somam ao montante existente; retiradas diminuem esse montante. Não criar lote físico por peça, rolo fictício, estados aberto/fechado, maior rolo ou distribuição física.
- Auditoria de `un` preserva ingressos, tickets/retiradas e saldo resultante. Não exige vínculo da retirada a um ingresso específico; não implementar FIFO, LIFO ou atribuição artificial de origem. Exemplo: ingresso A +30, ingresso B +20, ticket X −7, saldo 43 un.
- A revisão alcança cadastro, ingresso, consultas, detalhe, retirada, ticket/resumo, Caja, Precios, históricos, erros, confirmações, JavaScript, testes e documentação.
- Quantidade vendida e fisicamente retirada permanecem independentes em `m` e `kg`. Para `un`, existe uma única quantidade operacional inteira: vendida = retirada obrigatoriamente, com um campo na interface e divergência impedida pelo backend/banco, inclusive com payload forjado. Preço congelado, baixa única, pagamento sem baixa, atomicidade, idempotência, concorrência e histórico permanecem obrigatórios.

O desenho técnico desta nova entrega fica em [REVISAO_TRANSVERSAL_UNIDADES_ESTOQUE.md](docs/planning/REVISAO_TRANSVERSAL_UNIDADES_ESTOQUE.md). Os planos anteriores registram os respectivos recortes e não devem ser reescritos como se já previssem essa mudança.

Para `m` e `kg`, cada rolo/peça física recebida deve ser individualizada.

Cada lote físico (rolo em `m`, peça em `kg`) possui:

- produto;
- quantidade inicial real;
- quantidade atual;
- código interno;
- estado operacional;
- condição física;
- origem do ingresso.

`quantidade_padrao_lote` em `produtos` é apenas uma sugestão para a interface.

Exemplo:

```text
Produto: Linho Azul
Quantidade padrão sugerida: 30 m

Rolo 001 -> 30 m
Rolo 002 -> 30 m
Rolo 003 -> 45 m
```

O rolo de 45 m não altera o padrão do produto.

Estados operacionais físicos previstos (não se aplicam ao estoque agregado de `un`):

```text
fechado
aberto
esgotado
descartado
```

Condição física prevista:

```text
normal
retalho
```

---

### 3.3 Seleção de lote no balcão

Para `m` e `kg`, a interface deve:

1. preferir lotes físicos já abertos;
2. entre os lotes capazes de atender o pedido, sugerir o menor saldo suficiente;
3. mostrar lotes fechados depois;
4. permitir ao atendente escolher outro lote manualmente.

A regra de melhor escolha depende da quantidade fisicamente necessária ao corte/retirada e deve ser aplicada na consulta/serviço, não apenas pela ordenação genérica da view. A capacidade do lote e a distribuição das retiradas são verificadas pela quantidade cortada, sem presumir que ela seja igual à quantidade vendida.

Para produtos em rolo, mostrar:

```text
estoque_total
maior_lote_disponivel
rolos_abertos
rolos_fechados
```

Em `m`, o estoque total não substitui a informação de maior trecho contínuo. Em `kg`, mostrar saldos por peça, sem falar em trechos. Em `un`, não oferecer sugestão física nem contagens de abertos/fechados.

---

### 3.4 Ingresso de estoque — confirmação operacional

Mudança de domínio aprovada em 2026-10-05: o ingresso operacional não exige aprovação administrativa. Esta regra substitui o fluxo anterior pendente/aprovado e a exceção de aprovação imediata para implantação.

```text
mercadoria chega
-> atendente encontra ou cadastra o produto, definindo o preço inicial se novo
-> informa rolos em m, peças/pesos em kg ou quantidade inteira em un
-> confere
-> confirma o ingresso
-> rolos/peças viram lotes físicos individuais; unidades somam ao estoque agregado do produto
-> estoque fica disponível imediatamente
```

A entrada física de `m`/`kg` pode ser agrupada por produto e quantidade homogêneos. O exemplo 4 × 30 m + 1 × 45 m resulta em cinco lotes individualmente identificáveis: quatro de 30 m e um de 45 m. O agrupamento não transforma os rolos em um único lote.

A confirmação precisa preservar origem, responsável registrado, quantidade declarada e movimentações de entrada. Falhas, repetição ou concorrência não podem deixar estoque parcial ou duplicado. Não é uma aprovação administrativa executada automaticamente em nome da atendente.

A quantidade declarada no ingresso não pode ser sobrescrita silenciosamente depois. A representação e o tratamento de divergências físicas posteriores permanecem abertos para definição futura; não bloqueiam a primeira entrega de Ingreso / Stock e não autorizam correções automáticas de saldo.

---

### 3.5 Tickets e corte/retirada

Um ticket representa um atendimento/cliente.

Um ticket pode conter múltiplos itens.

Cada item possui:

- produto;
- quantidade vendida;
- quantidade cortada/retirada;
- preço unitário congelado;
- valor total.

**Distinção aprovada em 2026-10-05, com correção de domínio em 2026-10-07:** em `m` e `kg`, quantidade vendida e fisicamente cortada/retirada permanecem independentes. Em `un`, vendida e retirada são obrigatoriamente iguais e inteiras; a interface apresenta um único campo. Preservar os dois campos internos do item, impondo igualdade para `un`, sem aplicar essa igualdade a `m`/`kg`.

- **Quantidade vendida:** quantidade cobrada do cliente; determina o valor do item com o preço unitário congelado.
- **Quantidade cortada/retirada:** quantidade efetivamente retirada do estoque; determina a baixa e as movimentações. Em `m`, retirada de rolos; em `kg`, peso retirado de peças; em `un`, retirada inteira do saldo agregado, sem origem física individual.
- Em `m`/`kg`, a diferença entre retirado e vendido permanece registrável e auditável, preservando ambas as quantidades. Em `un`, os campos internos têm o mesmo valor e a diferença é necessariamente zero; não pedir duas quantidades nem mostrar uma comparação redundante na operação normal.
- Essa diferença não recebe significado automático de perda, retalho, ajuste ou outra classificação; não autoriza uma movimentação adicional ou correção automática de saldo.
- Em `m`/`kg`, não se presume igualdade, ordem (`cortada >= vendida` ou o inverso), proporção, tolerância ou outra relação. Em `un`, backend e banco rejeitam quantidades divergentes, sem corrigir silenciosamente um payload inconsistente.

Um item de `m`/`kg` pode consumir um ou mais lotes físicos através de `alocacoes_estoque`. Sua soma corresponde à quantidade cortada/retirada do item. Para `un`, não há alocações físicas: o movimento de saída do produto corresponde à quantidade retirada do item.

Para itens de `m`/`kg`, deve sempre valer:

```text
SUM(alocacoes_estoque.quantidade)
=
quantidade cortada do item
```

O valor do item corresponde a:

```text
quantidade vendida × preço unitário congelado
```

Essas expressões descrevem o domínio; não escolhem nomes de colunas nem uma representação técnica para a adaptação futura do schema.

O corte só é realizado presencialmente após solicitação/confirmação do cliente.

A baixa física ocorre no momento do corte/retirada.

Não existe cancelamento operacional de corte, conforme a seção 4.

O pagamento NÃO deve baixar estoque novamente.

---

### 3.6 Preço

O preço atual fica em `produtos.preco_unitario`. A atendente define o preço inicial ao cadastrar produto novo; alterações posteriores usam a área protegida de preços com PIN geral.

No momento do registro do corte/retirada, o preço é copiado para `itens_ticket.preco_unitario`.

Depois disso, alterações futuras no preço do produto não alteram tickets anteriores.

O valor do item usa a quantidade vendida e a baixa usa a quantidade cortada/retirada. Em `m`/`kg`, elas são independentes; em `un`, são obrigatoriamente iguais.

---

### Área protegida de preços — extensão aprovada

> Atualização de 2026-11-15: a área de preços é exclusiva do papel Administrador; o PIN geral foi removido ([docs/decisions/2026-11-15-papeis-sem-pin.md](docs/decisions/2026-11-15-papeis-sem-pin.md)). As demais regras desta seção continuam valendo.

- Usar o mesmo PIN geral e as regras vigentes de autorização por fluxo, sem criar usuário individual ou sessão administrativa.
- Listar todos os produtos com busca/filtro, foto pequena quando existente, nome e preço atual; permitir editar preço diretamente na lista e marcar visualmente cada mudança pendente.
- A ação de revisão apresenta somente produtos alterados, com preço anterior → novo. A confirmação final aplica todas as mudanças atomicamente: todas as alterações válidas são aplicadas ou nenhuma.
- Preservar histórico de produto, preço anterior, preço novo e data/hora. Não inferir autoria individual da sessão compartilhada nem remover responsáveis existentes.
- Preços congelados nos itens de ticket permanecem inalterados. Esta extensão substitui a reserva exclusiva de alteração de preço ao Administrativo futuro e amplia o conjunto de áreas protegidas pelo PIN; não concede outros privilégios administrativos.
- Plano subordinado e avaliação de impacto: `docs/planning/PRECIOS_FOTOS_PRODUCTO.md`. Registro documental não constitui implementação.

### 3.7 Venda

O ticket nasce:

```text
pendente
```

Após pagamento:

```text
pago
```

O valor da venda deve ser calculado pelo banco:

```text
SUM(itens_ticket.valor_total)
```

A aplicação não deve fornecer um valor total arbitrário como fonte da verdade.

Também não deve ser possível finalizar um ticket sem itens.

---

## 4. Corte confirmado presencialmente — regra vigente

Mudança de domínio aprovada em 2026-10-05: não existe cancelamento operacional de corte. O corte só é realizado presencialmente após solicitação/confirmação do cliente. Depois do corte, o sistema não oferece fluxo de cancelamento que recomponha, reclassifique ou devolva esse material.

Esta decisão substitui integralmente as regras anteriores de cancelamento de ticket e de criação de retalho por cancelamento. Deixam de ser requisitos a operação de cancelamento, o estado de ticket cancelado associado a ela, suas movimentações, seus vínculos exclusivos de origem e seus testes. Comportamentos ainda existentes no código não constituem decisão vigente; esta atualização é documental e não modifica o schema.

A retirada física, seu preço congelado e sua rastreabilidade permanecem registrados. Pagamento não baixa estoque novamente.

O conceito geral de retalho permanece reconhecido, mas qualquer uso por outra razão, sua origem, estado e tratamento ficam para definição posterior em 1B. Não há geração automática de retalho por cancelamento nem autorização de um fluxo alternativo equivalente.

O tratamento excepcional de um ticket já cortado que não seja pago permanece questão aberta de 1C. Não se define aqui destinação do material, novo estado, baixa financeira ou outra solução para esse caso.

---

## 5. Movimentações — livro-razão

`movimentacoes` é o livro-razão do estoque.

Toda alteração física relevante deve ser explicável por movimentações.

Tipos recomendados:

```text
ENTRADA
CORTE
AJUSTE_ENTRADA
AJUSTE_SAIDA
PERDA
```

Movimentações específicas de retalho não são requisitos atuais; dependem da definição de seu uso em 1B.

Evitar um tipo `AJUSTE` ambíguo com quantidade sempre positiva.

O efeito sobre saldo deve ser inequívoco.

`quantidade_atual` pode existir por desempenho, mas deve permanecer consistente com o histórico.

As movimentações de retirada registram o efeito físico: por lote de origem em `m`/`kg`, por produto sem origem física individual em `un`. Sua soma por item corresponde à quantidade cortada/retirada; em `m`/`kg` ela é independente da vendida, enquanto em `un` ambas são obrigatoriamente iguais. A denominação técnica existente `CORTE` não obriga linguagem de corte em todas as unidades. A diferença comercial/física permanece auditável pelas quantidades registradas, sem classificação ou movimentação adicional automática.

---

## 6. Estado atual e diferença para o domínio vigente

O arquivo implementado identifica-se como `schema.sql v3.1`. Já há individualização de lotes, movimentações, consultas de estoque e proteções de integridade. A Fase 1A já foi implementada e versionada: o ingresso usa confirmação operacional com disponibilidade imediata, sem aprovação administrativa, e o operador dispõe de cadastro de produto com preço inicial, conforme as decisões da seção 3. Nenhum código é alterado por esta revisão documental.

Na revisão de código de 2026-10-07, a 1B já mantém quantidades vendida e cortada distintas. A lacuna desta entrega é outra: ingresso, seleção, movimentações e alocações ainda pressupõem lotes físicos para todas as unidades. `un` precisa do modelo agregado; `kg` precisa da apresentação e dos contratos por peça. Estado implementado não substitui as regras aprovadas.

Os dados anteriores são fictícios e não exigem migração. Isso não autoriza descartar os dados reais que começarem a ser registrados na futura aplicação.

---

## 7. Requisitos do núcleo alinhados às entregas

As garantias já implementadas devem ser preservadas e verificadas. Cada entrega depende do trecho do núcleo que utiliza; não precisa aguardar o Administrativo ou decisões posteriores sem relação com seu fluxo.

### 7.1 Núcleo operacional

#### A. Confirmação de ingresso e cadastro inicial de produto

A confirmação pela atendente cria lotes físicos e entradas para `m`/`kg` ou soma unidades ao agregado do produto, preservando cada ingresso. Disponibilidade imediata, consistência e ausência de aprovação administrativa valem para os dois modelos. O cadastro de produto novo permite informar preço inicial; alterações posteriores exigem a área protegida de preços com PIN geral.

A confirmação operacional já substituiu a aprovação administrativa. A nova revisão deve preservar esse resultado nos dois modelos de estoque, com rastreabilidade, prevenção de duplicidade e integridade transacional; não reintroduzir aprovação.

---

#### B. Respeitar a ausência de cancelamento operacional de corte

O núcleo não deve oferecer uma operação de cancelamento de corte nem gerar retalho ou recompor, reclassificar ou devolver material por esse motivo. Preservar a retirada e sua rastreabilidade. Não substituir esse fluxo por um tratamento inventado de ticket não pago; esse caso depende de 1C.

---

#### C. Preservar a venda calculada pelo banco

Remover o valor total fornecido pela aplicação como fonte de verdade.

Calcular no banco:

```text
SUM(itens_ticket.valor_total)
```

Também impedir ticket vazio.

O valor de cada item deriva da quantidade vendida e do preço congelado; a quantidade retirada permanece como fonte da baixa; alocações físicas são exigidas somente para `m`/`kg`.

---

#### D. Hardening de `SECURITY DEFINER`

Para funções sensíveis:

- `REVOKE EXECUTE ... FROM PUBLIC`;
- conceder `EXECUTE` apenas às roles corretas;
- definir `search_path` seguro;
- revisar owner das funções;
- não assumir que ausência de `GRANT` significa ausência de acesso.

---

#### E. Bloquear ticket nas operações transacionais

Corte e pagamento devem bloquear o ticket com:

```sql
SELECT ... FOR UPDATE
```

antes de validar e mudar estado.

Evitar corrida entre:

- adicionar item;
- pagar.

---

#### F. Consulta de Caja e Cierre del día — regras aprovadas

> Atualização de 2026-11-15: Consulta de Caja, Cierre e Fondo inicial pertencem aos papéis Cajero e Administrador; onde se lê "PIN geral", vale o papel ([docs/decisions/2026-11-15-papeis-sem-pin.md](docs/decisions/2026-11-15-papeis-sem-pin.md)).

- Consulta de Caja é informativa, disponível a qualquer momento, mostra valores atuais calculados pelo banco e não cria fechamento, não é conferência formal nem bloqueia vendas.
- Existe um único Cierre del día por data operacional de Córdoba, Argentina. É definitivo: depois de confirmado, novos recebimentos daquela data ficam bloqueados. Antes da confirmação, vendas continuam normalmente. Não implementar reabertura ou múltiplos fechamentos.
- O Cierre del día pode ser confirmado normalmente mesmo quando não houve vendas na data operacional. Zero vendas não é erro nem condição excepcional. As demais exigências do Cierre continuam valendo, inclusive Fondo inicial obrigatório antes da confirmação.
- Se o movimento mudar entre abertura da tela de Cierre e confirmação, exigir atualização/revisão; não confirmar silenciosamente dados desatualizados. Alteração do fundo usado na conferência também exige revisão.
- Total vendido é a soma das vendas recebidas na data; Efectivo recibido por ventas soma suas parcelas em efectivo; Otro soma suas parcelas Otro. Total vendido = Efectivo + Otro. Esses valores são calculados pelo banco, nunca digitados manualmente.
- Existe um fundo inicial de referência por dia, informável no início do dia, sem bloquear vendas enquanto ausente. Deve estar definido antes do Cierre. Não transportar automaticamente o valor anterior. Correções preservam histórico, responsável e horário e não alteram Cierres registrados.
- Não implementar movimentos extraordinários agora. Usar “Efectivo según fondo y ventas” = fundo inicial + efectivo recebido em vendas, sem chamar esse valor de efectivo teórico en caja.
- Efectivo contado é opcional inicialmente e inclui todo o dinheiro fisicamente presente na gaveta, inclusive fundo inicial. Ausência é diferente de zero. Quando houver contagem, registrar Efectivo contado e calcular e registrar Diferencia = contado − efectivo según fondo y ventas. Permitir concluir o Cierre mesmo com diferença diferente de zero, sem exigir motivo, justificativa ou observação textual. A diferença é apenas um dado numérico auditável do fechamento, sem classificação automática como falta, sobra, perda ou erro. Sem contagem, não presumir diferença zero.
- Acesso ao Cierre exige PIN geral compartilhado; correção do Fondo inicial exige o mesmo PIN. A sessão operacional normal, sozinha, não autoriza essas ações sensíveis. Administração poderá futuramente exigir contagem e substituir o mecanismo por controle mais granular.
- Tickets pendentes podem atravessar dias; quando pagos, compõem a data do recebimento. O fechamento não cancela tickets nem recompõe estoque.

Essas decisões substituem propostas anteriores de vendas após Cierre e conferências formais sucessivas. Recebimento Efectivo/Outro permanece integral; a atendente informa apenas a parcela efectivo e o banco calcula total e Otro. O núcleo atual de fechamento ainda precisa ser adaptado: seu cálculo genérico de divergência, ausência de unicidade por data e ausência de bloqueio de recebimentos após fechamento não representam as regras aprovadas. Esta atualização não implementa nem autoriza código.

---

### 7.2 Corrigir antes de produção, mas não bloqueia desenvolvimento local inicial

#### G. `p_usuario_id` como identidade

IDs enviados pela aplicação não provam quem executou uma ação.

Especialmente para autorização administrativa, não confiar apenas em `p_usuario_id`.

A operação normal usa sessão compartilhada conforme a seção 8. Autoria individual forte não é requisito desta etapa e não é comprovada pelo usuário da sessão nem pelo PIN geral. A limitação deve permanecer explícita, preservando campos e responsáveis existentes. Proteção contra elevação de privilégios por ID continua obrigatória.

---

#### H. Geração de código de lote com `MAX()+1`

Pode colidir sob concorrência.

Trocar por mecanismo seguro:

- sequence;
- identity;
- UUID interno;
- ou outra estratégia concorrente segura.

---

#### I. Ajustes positivos e negativos

Substituir `AJUSTE` ambíguo por:

```text
AJUSTE_ENTRADA
AJUSTE_SAIDA
```

ou estrutura equivalente.

---

#### J. Não expor `senha_hash`

O operador não precisa de `SELECT` direto sobre hashes.

Criar:

- view segura de usuários;
- ou função de autenticação;
- ou grants por coluna.

---

### 7.3 Definições posteriores nos módulos responsáveis

#### K. Estoque mínimo configurável

O alerta atual `< 5` é provisório.

Depois adicionar algo como:

```text
produtos.estoque_minimo
```

respeitando a unidade de cada produto.

---

#### L. Conceito geral de retalho — definição posterior em 1B

A distinção conceitual entre retalho e lote normal permanece. Qualquer uso de retalho por outra razão, sua origem, estado operacional, prioridade e tratamento ficam para definição posterior em 1B. Não fazem parte dos requisitos atuais de cancelamento, pois essa operação não existe no domínio vigente.

---

## 8. Segurança

### Acesso por papéis — decisão aprovada em 2026-11-15 (vigente)

Esta decisão **substitui** a sessão operacional única compartilhada e o PIN geral descritos na subseção de 2026-10-06 abaixo, que permanece apenas como registro. Onde este HANDOFF disser "PIN geral", "área protegida por PIN" ou "sessão compartilhada", vale o que segue. Detalhes e justificativas: [docs/decisions/2026-11-15-papeis-sem-pin.md](docs/decisions/2026-11-15-papeis-sem-pin.md).

- Três contas fixas, uma por papel, cada uma com senha própria definida na instalação: `administrador`, `empleado`, `cajero`. Não há contas por pessoa.
- **Administrador:** tudo, inclusive Precios. **Empleado:** Productos / Stock e Corte / Ticket. **Cajero:** Corte / Ticket, Caja / Venta, Consulta de Caja, Cierre del día e Fondo inicial.
- O PIN geral deixa de existir. O papel é a única barreira de Precios (Administrador) e de Cierre/Fondo (Cajero e Administrador). Não há mais autorização "por fluxo".
- A restrição vale no menu, nas rotas e nas funções do banco; área não permitida é recusada mesmo por URL direta ou formulário forjado. O papel é relido do banco a cada pedido.
- As contas são compartilhadas por papel: o papel autoriza, não identifica a pessoa. Campos de responsável registram a conta usada e não comprovam autoria individual.
- Senhas nunca em texto puro, no repositório ou em documentos. Troca de senha de um papel exige a senha administrativa do PostgreSQL.
- Permanecem obrigatórios: integridade, rastreabilidade, proteção de segredos e a limitação explícita de que o banco confia no identificador de usuário informado pela aplicação (7.2 G).

### Acesso operacional — decisão de 2026-10-06 (substituída em 2026-11-15)

- Terminal/caixa funciona como sessão compartilhada. Não exigir login/logout individual a cada atendimento.
- Productos / Stock, Corte / Ticket, Caja / Venta e Consulta de Caja permanecem acessíveis na sessão operacional normal.
- Cierre del día é a área operacional sensível nesta etapa: seu acesso exige PIN geral compartilhado. Correção do Fondo inicial exige o mesmo PIN, inclusive por acesso direto à operação.
- Cierre del día, correção do Fondo inicial e a nova área protegida de preços exigem o mesmo PIN geral. Não criar PIN individual, usuários individuais, permissões granulares ou sessão administrativa. O PIN é compartilhado e autoriza acesso; não identifica quem realizou a operação.
- Preservar os campos e responsáveis existentes. O usuário mostrado na sessão e os identificadores registrados não comprovam autoria individual e não devem ser apresentados como tal.
- Esta decisão substitui a exigência anterior de autoria individual confiável como pré-requisito da operação normal e o acesso ao Cierre apenas pela autorização operacional comum. Não dispensa integridade, rastreabilidade dos registros, proteção de segredos ou restrições administrativas.
- Administrativo futuro poderá substituir o mecanismo por controle mais granular. Não definir agora identidade individual definitiva nem atribuir privilégio administrativo ao PIN geral.
- A autorização vale somente enquanto a pessoa permanece no fluxo protegido. Navegar entre etapas do mesmo fluxo não exige novo PIN. Ao sair da área protegida, encerrar a autorização; novo acesso exige novo PIN.
- O valor real do PIN é configuração local fora do repositório. Não registrar seu valor em ROADMAP, HANDOFF, planos, guias versionados ou código-fonte, nem incluir um PIN padrão de exemplo utilizável.
- Verificar o PIN no servidor; não armazená-lo em texto puro. A escolha do mecanismo técnico deve respeitar essas garantias, sem introduzir outro contrato de acesso.
- Gestão/troca amigável do PIN pertence ao Administrativo futuro. Esta atualização é documental e não comprova implementação do novo acesso.

O operador:

- não pode alterar diretamente saldo;
- pode cadastrar produto e definir seu preço inicial; alterações posteriores exigem a área protegida de preços com PIN geral, sem alteração direta irrestrita;
- pode confirmar ingresso e disponibilizar estoque físico ou agregado, sem aprovação administrativa;
- não deve ler hashes;
- executa operações de negócio por funções controladas.

Funções `SECURITY DEFINER` devem ter:

- `search_path` controlado;
- grants explícitos;
- `PUBLIC` revogado quando necessário.

Autorização não deve depender apenas de IDs fornecidos pelo cliente.

---

## 9. Concorrência

Operações que alteram lote físico, estoque agregado ou ticket devem ser transacionais.

Usar bloqueios adequados para impedir:

- duas retiradas consumindo indevidamente o mesmo saldo físico ou agregado;
- pagamentos duplicados;
- inclusão de item enquanto ticket está sendo finalizado;
- geração duplicada de identificadores;
- confirmação de ingresso com lotes parciais ou duplicados.

---

## 10. Testes obrigatórios da v3.1

Em ambiente de teste descartável, validar os requisitos do núcleo conforme a entrega que os utiliza. Esta lista não condiciona 1A à conclusão de corte, venda, fechamento ou Administrativo:

1. aplicar `schema.sql` sem erro;
2. criar admin e operador;
3. cadastrar produto como atendente com preço inicial e impedir alteração posterior desse preço fora do fluxo protegido aprovado;
4. conferir e confirmar ingresso como atendente, sem aprovação administrativa;
5. confirmar disponibilidade imediata dos cinco lotes do exemplo 4 × 30 m + 1 × 45 m;
6. confirmar movimentações de entrada;
7. criar ticket;
8. adicionar corte de um único lote;
9. adicionar corte dividido em dois lotes;
10. impedir corte acima do saldo;
11. testar concorrência no mesmo lote;
12. finalizar venda com total calculado pelo banco;
13. impedir ticket vazio;
14. verificar que a retirada permanece registrada sem recomposição do saldo;
15. verificar rastreabilidade básica; auditoria avançada não integra as entregas iniciais;
16. verificar reconstrução do saldo via movimentações;
17. testar permissões do operador;
18. garantir que operador não leia hashes;
19. testar fechamento de caixa;
20. testar concorrência entre inclusão de item e pagamento e entre pagamentos;
21. testar geração concorrente de código de lote e impedir duplicação ou efeitos parciais na confirmação de ingresso.
22. em `m`/`kg`, registrar quantidades vendida e cortada/retirada distintas e verificar valor pela vendida, baixa e alocações pela retirada, sem relação adicional presumida; em `un`, verificar campo operacional único, dois campos internos inteiros iguais e rejeição de divergência no backend e banco, inclusive payload forjado, sem efeitos parciais.

Na revisão transversal, adicionar os testes de agregado inteiro para `un`, individualização de peças para `kg`, ticket misto, migração preservadora e concorrência dos dois modelos previstos no novo plano. Os exemplos de rolo acima continuam cobrindo `m`, não definem o comportamento de todas as unidades.

Os testes não devem pressupor uso de retalho ainda não definido em 1B nem tratamento de ticket cortado não pago, pendente de 1C. O fluxo presencial deve respeitar a solicitação/confirmação do cliente; esta regra não define mecanismo técnico de registro dessa confirmação.

---

## 11. Sequência vigente de entregas

1. **Ingreso / Stock:** aplicação local utilizável para encontrar ou cadastrar produto com preço inicial, informar rolos, peças/pesos ou unidades conforme o produto, conferir e confirmar ingresso com disponibilidade imediata; consultar origens físicas ou agregado, preservando declarações e movimentos. Permite iniciar o preenchimento da base real, após validação para uso real.
2. **Corte / Ticket:** corte/retirada presencial confirmado; em `m`/`kg`, quantidade vendida e retirada permanecem registráveis e independentes; em `un`, existe uma única quantidade operacional inteira, persistida igualmente nos dois campos internos; preço congelado e baixa única permanecem.
3. **Caja / Venta:** conferir ticket e concluir venda; pagamento sem nova baixa. Questões de conteo/fechamento permanecem em 1C, sem bloquear 1A.
4. **Administrativo separado:** mesma base e núcleo, incluindo alterações posteriores de preço e capacidades gerenciais futuras. Não introduz aprovação de ingresso.

Auditoria avançada, relatórios, alertas e tratamento sofisticado de divergências ficam fora das entregas iniciais. Rastreabilidade básica e preservação do dado original continuam obrigatórias. Interface da loja em es-AR; UX simples, rápida e fácil de usar.

---

## 12. Orientação ao próximo agente

Antes de alterar qualquer arquivo:

1. leia este `HANDOFF.md`;
2. leia `schema.sql`;
3. respeite o ROADMAP da raiz para fases e escopo, este HANDOFF para domínio e o plano do módulo subordinado a ambos;
4. documentos em `docs/history/` e `legacy/` são não autoritativos e podem conter decisões superadas;
5. não restaure comportamento antigo sem justificar.

Objetivo da implementação, quando explicitamente autorizada (aprovação conceitual e proposta técnica não concedem essa autorização):

> produzir e validar `schema.sql v3.1` sem alterar silenciosamente as regras de domínio já fechadas.

Ao terminar, informar:

1. alterações feitas;
2. testes executados;
3. resultados;
4. problemas restantes;
5. arquivos modificados.
