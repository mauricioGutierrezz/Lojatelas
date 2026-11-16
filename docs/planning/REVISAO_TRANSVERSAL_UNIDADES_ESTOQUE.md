# Revisão transversal — unidades, estoque e operação

Data: 2026-10-07. Planejamento técnico; nenhuma implementação nesta tarefa.

ROADMAP governa escopo; HANDOFF governa domínio. As decisões de `m`, `un`, `kg` e ausência de atribuição de origem em `un` foram aprovadas pelo responsável. Este documento define a estrutura e os contratos da nova entrega; não delega escolhas de modelo de dados ao Programador. Mecanismos equivalentes de constraints, índices e organização de funções permanecem liberdade técnica, desde que demonstrem os resultados abaixo.

Os planos anteriores das Fases 0, 1A, 1B e 1C registram seus recortes anteriores. Esta revisão os complementa/supersede somente nos pontos de unidade, origem e estoque aqui definidos; não os reescrever como previsão retroativa. SCHEMA_V3_1 continua proposta subordinada não aprovada, nunca fonte de autoridade.

## 1. Estado de prontidão e evidência da base

Plano pronto para implementação no destino local inspecionado, mediante autorização de implementação. A estratégia é instalação em base nova, sem transformação de registros operacionais. Não há decisão de negócio pendente sobre `m`, `un`, `kg` ou atribuição de origem.

Evidência fornecida pelo responsável em 2026-10-07, por saídas de comandos executados no seu terminal:

| Verificação | Resultado observado |
|---|---|
| Conexão à base `urdimbre` pelo socket local padrão | PostgreSQL informou que a base não existe |
| Bases não template no cluster local | Somente `postgres` |
| Tabelas fora de `pg_catalog`/`information_schema` em `postgres` | Zero linhas |
| `pg_lsclusters` | PostgreSQL 16, cluster `main`, porta 5432, online, proprietário postgres; único cluster listado |

Conclusão delimitada: não há base/tabelas da aplicação no cluster local listado e consultado. Não se trata de uma base operacional existente com contagens zero: a base prevista na configuração padrão ainda não existe. Não há registros operacionais a converter nesse destino.

As saídas foram examinadas nesta conversa; a inspeção não foi executada diretamente pelo agente, cujo acesso sudo exigiu autenticação interativa. Não foram inspecionados containers, servidores remotos, clusters não registrados no `pg_lsclusters` ou backups. A conclusão não afirma ausência de dados em outros destinos. Senhas não foram expostas nem documentadas.

Antes da implantação, comparar a conexão efetiva da aplicação com o destino acima e repetir a checagem de existência da base/tabelas. Encontrar outra base ou dados novos invalida o caminho de instalação limpa e exige inspeção específica, sem conversão automática. Essa guarda de implantação não bloqueia implementar e testar o modelo definido neste plano.

## 2. Recorte final e invariantes de domínio

Correção aprovada em 2026-10-07: igualdade obrigatória apenas para `un`. Esta seção substitui a formulação anterior de independência nas três unidades, sem reescrever planos anteriores.

| Unidade | Estoque | Ingresso | Retirada | Linguagem es-AR |
|---|---|---|---|---|
| m | Um saldo por rolo | Grupos: quantidade de rolos × metros por rolo | Uma ou várias origens físicas obrigatórias | Rollo, metros, cantidad cortada |
| un | Agregado por produto | Quantidade inteira direta | Quantidade única: vendida = retirada; nenhuma origem física | Unidades, stock disponible, cantidad (un) |
| kg | Um saldo por peça | Grupos: quantidade de peças × peso por peça | Peso distribuído em uma ou várias peças | Pieza, peso por pieza, peso retirado |

- `m` e `kg`: até três casas decimais, sem arredondar entrada inválida; quantidade de rolos/peças é inteira positiva. Preservar fechado/aberto/esgotado e origem do ingresso. Retirada parcial abre a origem, retirada total esgota, origens intactas permanecem fechadas.
- `un`: ingresso inteiro positivo e uma única quantidade operacional inteira positiva no item. Preservar os dois campos internos com `quantidade_vendida = quantidade_cortada`; backend e banco impedem divergência, inclusive com payload forjado. Saldo inteiro não negativo; zero de saldo válido. Valor monetário continua admitindo centavos.
- `un`: ingressos A +30, B +20, ticket X −7 produzem saldo 43, sem FIFO, LIFO, consumo de ingressos ou origem artificial.
- Em `m`/`kg`, quantidade vendida determina cobrança e quantidade cortada/peso retirado determina baixa, mantendo independência: não impor igualdade, ordem, proporção ou classificação da diferença. Em `un`, a mesma quantidade determina cobrança e baixa, com igualdade obrigatória dos dois campos internos.
- Uma retirada registrada baixa estoque uma única vez. Pagamento não baixa estoque. Não há cancelamento operacional nem recomposição posterior do material retirado.
- Repetição, falha e concorrência não geram duplicação, saldo negativo, item parcial ou movimento desacompanhado do efeito correspondente.
- Preço inicial no cadastro; atualização posterior pelo fluxo de preços protegido. Sessão/PIN compartilhados não comprovam autoria individual.
- Retalho, divergências físicas e exceções de ticket não pago não ganham tratamento novo nesta entrega.

## 3. Desenho do schema alvo

### 3.1 Produto e origem física

Preservar `produtos` e `unidades_medida`. O modo de estoque é derivado da unidade: `m`/`kg` físico, `un` agregado. Não adicionar um campo editável de modo que permita combinações contraditórias.

- `largura_metros` continua opcional; não participa dos cálculos. Não mostrar em `un`, não apagar valor histórico. Em `kg`, não exigir largura nem acrescentar um fluxo novo de características nesta entrega.
- `quantidade_padrao_lote` continua sugestão, pertinente a rolos/peças; não usar para ingresso de `un`. Valores existentes não são conversão de unidade nem declaração de recebimento.
- Não oferecer alteração/conversão de unidade de produto existente. O banco deve impedir alteração de unidade quando houver dependências de estoque, ingresso, item ou movimento: as consultas históricas dependem dessa unidade estável. Este plano não cria fluxo de correção de unidade.
- `estoque_lotes` permanece a tabela de origens físicas de `m`/`kg`, com os mesmos identificadores, vínculo único ao item de ingresso, quantidade inicial/atual, estados e condição. Para novos registros, produto `un` não pode ter lote físico.
- Não relaxar globalmente a regra `saldo <= quantidade inicial` dos lotes para acomodar unidades agregadas.
- Estados/condições antigas como descartado/retalho não se tornam novas operações; manter sua indisponibilidade e preservação histórica, sem reclassificar automaticamente.

### 3.2 Estoque agregado

Criar `estoque_agregado` com (não criar tabela de lotes agregados nem vínculo a ingresso):

| Campo | Definição |
|---|---|
| produto_id | Chave primária e estrangeira para produtos; somente produto `un` |
| quantidade_atual | NUMERIC sem escala fixa limitadora do total acumulado; finito, inteiro e >= 0; inicial 0 |

Uma linha por produto `un`, criada atomicamente com seu cadastro. No destino inspecionado não há produtos existentes; outra situação exige a guarda da seção 6. Não armazenar quantidade inicial, origem de ingresso, estado aberto/fechado, condição física ou código de rolo nessa tabela.

O total agregado não deve herdar o limite de capacidade de um único lote. Os limites de entrada de uma operação permanecem os atuais, agora com integralidade para `un`. Evitar conversão dos totais para ponto flutuante ou inteiro JavaScript impreciso.

### 3.3 Ingressos

Preservar `ingressos`, chave de confirmação, responsável, horário, observação e declaração recebida. `grupos_declarados` pode conservar o nome interno, mas seu contrato passa a distinguir entrada agregada de grupos físicos; não fabricar `rolos=1` para `un`.

`itens_ingresso` passa a representar:

- `m`/`kg`: uma origem física recebida por linha, ligada a um único lote;
- `un`: a quantidade declarada daquele produto no ingresso, sem lote físico.

Preservar quantidade e documento originais. Não aumentar itens antigos ao receber mercadoria nova. Na nova versão, entrada agregada gera uma linha por produto declarado, uma entrada no livro-razão e incremento do agregado.

### 3.4 Livro-razão comum

Preservar `movimentacoes` como fonte auditável dos dois modelos:

- tornar `lote_id` opcional estruturalmente; obrigatório para movimentos físicos de `m`/`kg`, nulo para novos movimentos agregados de `un`;
- manter `produto_id` obrigatório em todos os movimentos;
- acrescentar `item_ingresso_id` opcional com FK para `itens_ingresso`; obrigatório para uma nova ENTRADA, com produto, quantidade e documento coerentes;
- manter `item_ticket_id` para saída de ticket, obrigatório em uma nova retirada registrada;
- entrada aponta ao seu ingresso, saída aponta ao seu item/ticket. A saída de `un` NÃO contém referência ao item de ingresso;
- produto do lote, do item de ingresso/ticket e do movimento deve coincidir;
- responsável informado, horário, IDs, referências e valores históricos são preservados;
- manter o tipo técnico `CORTE` para retirada, inclusive de `un`/`kg`, evitando reescrever histórico apenas por nomenclatura; traduzir a operação adequadamente na UI;
- manter os tipos legados existentes sem abrir novas operações de ajuste/perda. Todos os efeitos permitidos devem continuar reconciliáveis.

Novas entradas: exatamente um movimento ENTRADA por item de ingresso; nas físicas, corresponde ao lote criado. Novas retiradas de `un`: exatamente um movimento CORTE por item, sem lote. Novas retiradas físicas: exatamente um movimento CORTE por alocação do item/lote, com a mesma quantidade. Validar cardinalidade e correspondência, não apenas a soma geral.

### 3.5 Ticket e alocações

Preservar `itens_ticket`, `quantidade_vendida`, `quantidade_cortada`, diferença, preço congelado, valor calculado, responsável e timestamp. O nome interno `quantidade_cortada` representa retirada/peso conforme a unidade. Preservar os dois campos nas três unidades: independentes em `m`/`kg`, obrigatoriamente iguais e inteiros em `un`. A diferença calculada de `un` é zero; não remover nem alterar a fórmula geral da diferença.

- `m`/`kg`: alocações físicas não vazias, origens distintas, positivas, do mesmo produto; soma = quantidade retirada; efeitos e movimentos correspondentes.
- `un`: nenhuma linha em `alocacoes_estoque`; `alocacoes_declaradas` contém lista vazia, sem origem oculta; movimento agregado = quantidade retirada = quantidade vendida. A igualdade é invariante do banco baseada na unidade efetiva do produto; deve valer em inserção e atualização do item, não somente no formulário ou em uma função de entrada.
- Nenhum produto `un` pode contornar esse contrato enviando lote ou alocação física.
- Preservar cálculo monetário atual: arredondamento financeiro no banco de quantidade vendida × preço congelado. Não alterar precisão financeira nem Cierre.

### 3.6 Integridade no banco e acesso

A unidade e o tipo de estoque são obtidos do produto no banco, não aceitos como verdade enviada pelo navegador. Validar integralidade também em acessos diretos autorizados aos contratos, inclusive tentativa de fraude em payload.

As validações transacionais devem demonstrar simultaneamente:

1. lote físico reconciliado com seus movimentos;
2. agregado reconciliado com movimentos do produto;
3. ingresso e retirada com efeitos completos, cardinalidades e referências válidas;
4. item físico com alocações; item agregado sem alocações;
5. quantidades e produtos compatíveis em todos os vínculos; igualdade integral entre vendida e retirada exclusivamente para `un`, sem restringir diferenças em `m`/`kg`.

Operador continua sem escrita direta em saldos, movimentos, alocações ou preços. Nova tabela e consultas recebem somente os privilégios necessários, com mesma proteção das operações atuais. Não adicionar permissões individuais nem alterar PIN.

## 4. Contratos operacionais fechados

### Cadastro

Receber nome, categoria, unidade, preço inicial e campos pertinentes opcionais, além da foto existente. Criar produto e, para `un`, saldo agregado zero na mesma transação. Campos físicos ocultos não podem determinar cálculos de `un`. Regras de foto e preço protegido permanecem.

### Confirmação de ingresso

Contrato recebe chave de idempotência, responsável informado, produto(s) e declaração discriminada:

- física: lista de grupos com número de rolos/peças e quantidade real por origem;
- agregada: quantidade inteira por produto, sem número de origens.

Conferência não reserva nem grava estoque. Confirmar registra documento, itens, lote(s) ou agregado e movimentos em uma transação. Retorna o mesmo identificador/documento no reenvio idêntico. Recusar produto inativo/inexistente, quantidade inválida ou estrutura incompatível, sem efeitos parciais.

### Preparação e confirmação de retirada

Contrato interno preserva chave de idempotência, ticket, produto, os dois campos de quantidade, responsável informado e alocações físicas somente quando aplicáveis.

Contrato da interface: `m`/`kg` enviam duas quantidades independentes. Para `un`, o formulário envia apenas `quantidade`; o backend valida esse inteiro e preenche ambos os campos internos com o mesmo valor. Não depender de campo oculto nem de cópia por JavaScript. Campos alternativos de vendida/retirada não fazem parte do payload público de `un`: rejeitá-los, em vez de ignorar uma tentativa de divergência. No contrato interno/banco que recebe os dois campos, rejeitar valores diferentes, sem escolher um deles ou normalizar a divergência silenciosamente.

- Preparação/revisão é leitura; apresenta ambas as quantidades para `m`/`kg` e uma única `Cantidad (un)` para `un`, além de valor indicativo e saldo previsto. Distribuição física somente em `m`/`kg`.
- Confirmar exige confirmação explícita da retirada/corte já realizado, ticket pendente, produto disponível e saldo suficiente para a retirada.
- `un`: conferir igualdade/integralidade dos campos internos e saldo agregado; debitar a quantidade única diretamente, sem inferir ingresso de origem.
- `m`/`kg`: conferir cada origem e alocação, debitar e atualizar estados; preservar seleção manual, sugestão atual e MAX.
- Congelar preço no registro usando a regra atual; registrar item, baixa e movimentos atomicamente. Pagamento usa o item já congelado.
- Erro mantém dados e identificação para revisão/reenvio, sem orientar repetir retirada física. Se estoque não comporta a solicitação, não inventar ajuste.
- Concorrência continua revalidada no banco. Saldo suficiente não é reserva; não inventar bloqueio de venda durante preparação.

### Consultas, Caja e Precios

A consulta de estoque por produto deve expor unidade, modo derivado e total disponível. Em listagens mistas, não somar metros, quilos e unidades em um único total de mercadoria. Para físicos, expor maior saldo e contagens abertas/fechadas. Para agregado, retornar esses atributos como não aplicáveis, não como rolos de valor zero.

- `vw_lotes_disponiveis`: somente origens físicas; agregado não gera lote sintético.
- `vw_historico_lote`: permanece para físicos; acrescentar consulta de movimentos por produto para agregado com documento, entrada/saída, horário, responsável informado e saldo após movimento.
- Ordem de auditoria: sequência estável dos movimentos confirmados por produto, não somente timestamp. Como mutações do produto são serializadas, usar identificador crescente de movimento para desempatar/ordenar efeitos; não mudar horários originais.
- Reconciliação deve expor produto/modo e origem física quando aplicável, saldo registrado, reconstruído e diferença; agregado não pode ser somado novamente aos lotes antigos.
- Consulta de ingresso não pode depender de INNER JOIN obrigatório com lote: deve recuperar também itens agregados sem lote.
- Ticket completo/resumo e Caja apresentam unidade e linguagem por item, inclusive tickets mistos. Caixa não seleciona origem nem altera stock.
- Precios apresenta preço por m/un/kg também na revisão e mantém confirmação atômica/histórico e PIN atuais. Fotos, busca e filtros são preservados.
- Consulta de Caja/Cierre continuam exclusivamente com seus contratos financeiros, sem somar quantidades de unidades distintas.

## 5. Concorrência e idempotência

Ordem obrigatória de recursos nas operações de estoque: chave da operação → ticket, se retirada → produtos em ordem crescente → agregado ou lotes físicos em ordem crescente. Nunca adquirir ticket depois de saldo/produto em um caminho concorrente inverso. Ingressos com vários produtos bloqueiam todos na mesma ordem. Alteração de preços usa produtos em ordem estável e não passa a adquirir tickets.

Serializar as mutações de estoque por produto usando a linha do produto como ponto comum de exclusão, inclusive ingresso contra retirada. A pequena loja aceita serialização por produto para manter um protocolo único e seguro. Manter bloqueios das origens físicas e do agregado para as verificações finais. A consistência das consultas com vários resultados exige a mesma fotografia transacional; não apresentar total e origens obtidos em momentos incompatíveis. Cadastro cria agregado zero atomicamente, sem corrida de criação no primeiro ingresso.

Pagamento mantém bloqueio de ticket e suas verificações de conferência/Cierre; não adquire saldo nem executa baixa. Revalidar compatibilidade com a ordem atual dos locks de data do caixa, sem alterar regras de fechamento. Operações de estoque não adquirem lock de data de caixa.

Idempotência:

- preservar chaves únicas atuais em ingresso e item, sem gerar nova chave ao voltar/repetir envio;
- registrar o conteúdo efetivo da solicitação: produto, unidade validada, ambas as quantidades internas, declaração/grupos ou alocações e responsável informado; em `un`, ambas são derivadas da quantidade única e devem coincidir. Reenvio divergente ou com estrutura pública indevida é rejeitado, não normalizado para recuperar sucesso;
- normalizar números e ordenar alocações por origem; conservar a declaração de grupos sem alterar seu significado;
- mesma chave e mesmo conteúdo retorna resultado já gravado, inclusive após pagamento ou mudança de saldo; consultar reenvio antes de validar estado mutável;
- mesma chave com conteúdo diferente falha sem efeitos;
- duas confirmações simultâneas da mesma chave produzem um documento/efeito; chave revertida por falha não deixa registro parcial;
- tentativas com formato antigo incompatível devem falhar de modo explícito, não ser reinterpretadas silenciosamente como nova operação.

Na implantação, concluir ou invalidar preparações ainda não confirmadas, exigindo nova revisão na versão atual; não alterar tickets já registrados nem converter um resultado técnico incerto em nova retirada.

## 6. Estratégia de instalação e preservação

### Caminho fechado para o destino inspecionado

A base `urdimbre` não existe no cluster local 16/main: não há migração de linhas a executar. Implementar o schema alvo no inicializador e instalar em base nova e vazia. Não criar lotes de transição, saldos de abertura fictícios, movimentos artificiais ou estrutura de legado sem dados que a justifiquem.

- O inicializador deve produzir diretamente os dois modelos, incluindo preços/fotos e os contratos financeiros já implementados.
- A criação/configuração da base na implantação é separada desta tarefa documental. Preservar roles/configurações existentes no servidor e nunca armazenar credenciais no repositório.
- Não usar a base `postgres` para a aplicação nem apagá-la. Não apagar/recriar uma base de mesmo nome se ela passar a existir.
- Confirmar conexão efetiva, versão e destino antes da instalação. Recusar inicialização sobre tabelas existentes; falha não autoriza limpeza destrutiva.
- Validar instalação em base descartável vazia, inicialização transacional e rejeição de repetição sobre estrutura existente sem perda de dados.
- Não exigir `migrations/002_unidades_estoque.sql` nesta entrega para um histórico que não existe no destino inspecionado. O histórico das migrações já versionadas permanece intacto.

### Guarda se o destino real divergir da evidência

Se a aplicação apontar a outro destino, ou forem encontrados dados antes da instalação, interromper somente o trabalho dependente da conversão. Não aplicar automaticamente o inicializador nem uma transformação genérica.

O inventário então necessário, em leitura consistente, inclui produtos por unidade, ingressos/itens, lotes por estado/condição, movimentos, tickets/itens/alocações, vendas e Cierres; frações de `un` em todas essas quantidades e itens de `un` com vendida diferente de retirada; reconciliação de saldos/documentos; origem física real dos registros `kg`; estados indisponíveis; e tickets pendentes. Preservar também largura/sugestão existentes, responsáveis, timestamps e preços congelados.

Frações de `un`, itens antigos de `un` com vendida diferente de retirada, significado físico incerto de `kg`, divergências de saldo ou estados incompatíveis impedem conversão silenciosa. Não sobrescrever uma das quantidades de um item antigo para impor a nova igualdade. Não arredondar, dividir, redistribuir, descartar ou ajustar. Apresentar os casos reais ao responsável antes do trabalho dependente.

Uma migração de base povoada exigiria adendo específico a este plano, com mapeamento dos registros efetivamente encontrados, backup/restauração verificados, ensaio em cópia, reconciliação antes/depois e execução transacional sem escritas concorrentes. Esse caminho não é necessário para a instalação local inspecionada e não está implicitamente autorizado por ela.

## 7. Matriz transversal de interface

| Área | m | un | kg |
|---|---|---|---|
| Cadastro | Metros sugeridos por rolo; largura opcional; preço/m | Sem largura/sugestão física; preço/un | Peso sugerido por peça opcional; preço/kg; sem exigir largura |
| Ingresso | Quantidade de rolos × metros | Quantidade inteira direta | Quantidade de peças × kg |
| Revisão/resultado de ingresso | Grupos, total e rolos identificados | Quantidade declarada, ingresso e agregado; sem código físico | Grupos, peso total e peças identificadas |
| Stock/lista | Total m e maior rolo | Stock disponible inteiro; sem maior origem/estados | Total kg e maior saldo por peça |
| Detalhe | Rolos e histórico físico | Saldo e movimentos do produto | Peças, estados, saldo e histórico físico |
| Seleção de produto | Informações de rolos | Apenas disponibilidade agregada | Informações de peças |
| Preparação | Vendida/cortada independentes; sugestão, MAX, distribuição | Um único campo Cantidad (un), inteiro; revisão direta | Vendida/peso retirado independentes; sugestão, MAX, distribuição por peça |
| Revisão | Origem, vendida, cortada e saldo por rolo | Quantidade única, subtotal e saldo agregado previsto, sem tabela física | Origem, vendida, peso retirado e saldo por peça |
| Confirmação | Corte realizado / Registrar corte | Retirada realizada / Registrar retirada | Retirada realizada / Registrar retirada |
| Resumo/ticket | Vendida/cortada e rolos utilizados | Quantidade única, sem comparação redundante nem distribuição física | Vendida/peso retirado e peças utilizadas |
| Caja | Preço congelado/m e quantidades do item | Quantidade única e preço congelado/un, sem corte/rolo | Preço congelado/kg, linguagem de peso |
| Precios/revisão | Anterior → novo por m | Anterior → novo por un | Anterior → novo por kg |
| Histórico | Movimento por rolo/documento | Movimento por produto/documento, sem origem inventada | Movimento por peça/documento |
| Erros e acessibilidade | Rolo/corte/metros | Unidades/retirada/stock | Peça/peso/retirada |

Ticket misto usa rótulos por item, não uma unidade global. Ações genéricas: `Ingresar stock`, `Agregar producto`, `Ver ticket completo`. Não substituir globalmente rollo por lote. Manter dados decisórios, confirmações explícitas e alertas condicionais; não reintroduzir explicações permanentes de treinamento.

JavaScript de ingresso/cadastro alterna campos e não envia dados físicos indevidos para `un`; servidor valida independentemente. JavaScript de retirada precisa de caminho agregado que não dependa de sugestão/tabela/MAX ausentes. Manter valores após erro/retorno, proteção contra resposta assíncrona antiga e confirmação da operação. Sem redesign visual, mobile, novas permissões ou novas modalidades financeiras.

## 8. Arquivos a alterar na futura implementação

| Arquivos/grupo | Escopo |
|---|---|
| `schema.sql` | Estrutura alvo, contratos, constraints, views e grants; somente quando implementação autorizada |
| Migração adicional de dados | Não necessária no destino inspecionado; somente mediante adendo se uma base povoada diferente for encontrada |
| `app_loja/validation.py`, `corte.py`, `db.py` | Precisão por unidade, contratos físicos/agregados, consultas e operações |
| `app_loja/routes/entrada_routes.py`, `corte_routes.py`, `ticket_routes.py` | Cadastro, ingresso, saldo, revisão, confirmação, histórico e ticket |
| `app_loja/routes/caixa_routes.py`, `precios_routes.py` | Dados de unidade/linguagem nas apresentações e revisão, sem mudar finanças/PIN |
| Templates `producto`, `entrada`, `conferir`, `ingreso`, `stock`, `detalle` | Cadastro/ingresso/consultas pelos dois modelos |
| Templates `corte_productos`, `corte`, `corte_lotes`, `corte_conferir`, `corte_error`, `ticket_resumen`, `ticket`, `tickets` | Retirada física/agregada, tickets mistos e erros |
| Templates `venta`, `precios`, `precios_revisar`, `base` | Unidade, links/ações genéricas e nomenclatura consistente |
| `app_loja/static/corte.js`, scripts de cadastro/ingresso (atualmente inline nos templates) e `stock.css` se necessário | Interação por unidade, validação auxiliar e ajustes mínimos de apresentação |
| `tests/test_ingreso_stock.py`, `test_corte_ticket.py`, `test_caja_venta.py`, `test_precios_fotos.py`, `ux_controllers.cjs` | Cobertura dos três percursos completos |
| `tests/sql/phase0_functional.sql`, `tests/phase0_concurrency.py`, `tests/run_phase0_postgres.sh`, testes de instalação e pré-condições | Integridade, concorrência, instalação vazia e recusa de reinicialização destrutiva |
| `docs/USO_LOCAL_1A.md`, `USO_LOCAL_1B.md`, `USO_LOCAL_1C.md`, `USO_LOCAL_PRECIOS_FOTOS.md`, `docs/README.md` | Guias e catálogo atualizados ao comportamento efetivamente entregue |
| `AGENTS.md` | Adequar a síntese futura de estoque físico/agregado para não restaurar regra universal de rolo |

Nesta tarefa, alterar somente HANDOFF, ROADMAP e este plano. Planos anteriores, guias, código e schema permanecem intocados. Alterações locais preexistentes em `corte.js`, `stock.css`, `corte_lotes.html` e `ux_controllers.cjs` devem ser preservadas e integradas, nunca sobrescritas por restauração de versão antiga.

## 9. Sequência de implementação quando autorizada

1. Usar a evidência da seção 1 e o caminho de instalação limpa da seção 6. Antes da implantação, revalidar a conexão efetiva e as pré-condições; outro destino ou registros novos exigem inspeção específica.
2. Em ambiente descartável, implementar schema alvo e contratos de ingresso/retirada/reconciliação; verificar invariantes e concorrência antes de conectar novas telas.
3. Ensaiar instalação do schema alvo em base descartável vazia e a recusa de inicialização sobre base já preenchida. Não construir conversão automática de dados ausentes no destino inspecionado.
4. Integrar consultas, cadastro, ingresso e stock com os contratos dos dois modelos.
5. Integrar preparação/revisão/confirmação, ticket misto, resumo e histórico; manter independência em `m`/`kg`, igualdade em `un` e garantias de reenvio.
6. Adaptar Caja, Precios, mensagens, JavaScript e guias; não considerar a entrega concluída só com cadastro/ingresso.
7. Executar os testes obrigatórios e revisão transversal de linguagem; validar operação local e recuperação de erros. Aplicação e banco atualizados devem ser implantados juntos, sem janela de escrita por clientes antigos incompatíveis.

## 10. Testes obrigatórios e critérios de aceitação

- `m`: 4 × 30 + 1 × 45 = cinco rolos e 165 m; origem individual, sugestão, MAX, distribuição, estados e revisão preservados.
- `kg`: 30 × 10 = trinta peças e 300 kg; retirar 2,5 de uma deixa 7,5 e abre somente ela; retirar restante esgota; retirada de várias peças preserva cada alocação e origem.
- `un`: +30, +20, −7 = 43; dois ingressos e uma saída auditáveis, nenhuma alocação física/FIFO/LIFO; esgotar e receber novamente funciona sem rolo/estado físico.
- `un`: frações em ingresso, vendida e retirada rejeitadas via HTTP e banco; inclusive payload físico forjado. Rejeitar negativo, não finito, precisão excessiva e saldo insuficiente sem arredondamento.
- `m`/`kg`: testar vendida maior, menor e igual à retirada; valor pela vendida e baixa pela retirada, sem impor relação adicional.
- `un`: um campo visível/enviado; informar 7 persiste vendida = retirada = 7, diferença zero, débito 7 e subtotal 7 × preço congelado. Não exibir dois campos ou diferença redundante em preparação, revisão, resumo, ticket e Caja.
- Forjar payload de `un` com vendida/retirada diferentes deve falhar no backend; chamar diretamente o contrato do banco com valores diferentes também deve falhar. Testar ainda a invariante de inserção/atualização direta em ambiente privilegiado descartável, sem conceder escrita ao operador. Nenhuma falha pode deixar item, movimento, saldo ou chave idempotente parcialmente gravados; não corrigir silenciosamente valores divergentes.
- Ticket misto percorrido do ingresso ao pagamento: unidade e origem corretas em revisão, resumo, ticket, Caja e histórico. Preço congelado resiste à alteração posterior por Precios; revisão de preços exibe unidade.
- Pagamento calcula total no banco, não baixa estoque, conserva Efectivo/Otro e Vuelto transitório. Consulta/Cierre, PIN e permissões mantêm seus testes de regressão.
- Reconciliação por origem física e agregado: todo efeito tem movimento correspondente, com produto/documento/quantidade corretos; nenhuma ligação artificial da saída de `un` a ingresso.
- Idempotência sequencial e simultânea de ingresso e retirada: mesmo conteúdo retorna mesmo resultado; alteração com a mesma chave falha; repetição após pagamento não faz segunda retirada.
- Concorrência com conexões reais: duas retiradas do mesmo agregado; ingresso × retirada; duas retiradas de uma peça/rolo; grupos de produtos em ordens opostas; preço × retirada; retirada × pagamento. Demonstrar espera/revalidação e ausência de efeitos parciais/deadlocks decorrentes da ordem de locks.
- Falha injetada depois de escritas reverte item, saldo, estados, alocações e movimentos juntos, tanto no modelo físico quanto agregado.
- JavaScript: ausência de componentes físicos em `un` não quebra revisão; campo vazio não vira zero; não copiar vendida para retirada em `m`/`kg`; em `un`, enviar uma quantidade e derivar os dois campos internos no servidor, nunca depender de sincronização JavaScript; manter distribuição manual de físicos e comportamento atual do MAX; descartar resposta antiga; preservar formulário em erro/retorno.
- Instalação: schema alvo inicializa base vazia; falha reverte efeitos transacionais; tentativa sobre estrutura existente é recusada sem perda. A guarda detecta destino diferente ou registros novos e não inicia conversão automática. Usar fixtures com fração `un`, origem `kg` não confirmada e divergência para demonstrar que não há correção/transformação silenciosa, sem exigir um migrador de base povoada nesta entrega.
- Auditoria textual inclui títulos, tabelas, flash, erros SQL expostos, labels acessíveis, JavaScript, confirmações e guias. `un` não apresenta rolo, maior rolo, aberto/fechado físico ou distribuição.
- Nenhuma tela pede embalagem nova para `un`; nenhum histórico promete origem individual inexistente. Sem cancelamento, redesign, tratamento de divergência ou novas permissões.

A entrega só está concluída com os três percursos completos e instalação limpa/guardas de preservação demonstradas. Testes existentes que supõem lote em todos os produtos precisam de novas expectativas sem apagar a regressão dos rolos. Registrar verificações executadas e limitações; não confundir revisão documental com testes de produção.

## 11. Riscos e limites

Principais riscos: agregado somado duas vezes; históricos perdidos por joins físicos; limite numérico de lote aplicado ao total agregado; uso de float no navegador; frações antigas ocultadas; significado físico de kg inferido sem evidência; cliente antigo escrevendo pelo contrato anterior; lock em ordem inversa; preço atual substituindo congelado; retorno de revisão perdendo a chave idempotente.

Mitigações estão no schema, contratos, guarda de destino e testes acima. Não há decisão de negócio pendente sobre `un`, `m` ou `kg`. Com a evidência recebida, o plano está pronto para implementação no recorte de instalação local nova, sem migração de registros. Isso não autoriza implementação por si só nem permite tratar eventual base diferente como vazia.
