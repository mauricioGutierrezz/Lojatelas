# Fase 1B — Corte / Ticket — primeira entrega utilizável proposta

## Objetivo

Permitir à atendente registrar cortes sobre o estoque carregado pela 1A e reunir os itens de um atendimento em um ticket identificável, com operação simples, rápida e fácil de usar. O [ROADMAP](../../ROADMAP.md) governa fases e escopo; o [HANDOFF](../../HANDOFF.md) governa regras e invariantes. Este plano incorpora as decisões explicitamente aprovadas pelo responsável na conversa e não autoriza implementação.

## Responsabilidades

- Buscar produtos por nome ou categoria e consultar preço, unidade, rolos identificados, saldos, estoque total e maior trecho disponível.
- Registrar separadamente a quantidade vendida e a quantidade fisicamente cortada; selecionar os lotes e as quantidades de cada retirada, registrar o corte e apresentar os itens já registrados e o saldo atualizado.
- Reunir vários itens/produtos em um ticket e permitir localizar e continuar um ticket pendente por outra atendente autorizada a cortar.
- Apresentar código e resumo do ticket na tela, com itens, quantidades vendidas e cortadas, preços congelados, valores pela quantidade vendida, total e indicação de pagamento pendente. Preservar a diferença entre cortado e vendido de forma registrável/auditável, sem classificação automática. Não incluir impressão nesta entrega.
- Preservar o identificador pelo qual Caja / Venta localizará posteriormente o mesmo ticket, sem implementar pagamento nesta fase.

Fluxo operacional proposto: iniciar ou localizar atendimento pendente → buscar produto → informar quantidade vendida e preparar a retirada física do(s) rolo(s) → conferir as duas quantidades e a distribuição por lote → realizar e registrar a quantidade efetivamente cortada após solicitação/confirmação presencial do cliente → repetir para outros itens → consultar código e resumo do ticket. A preparação da seleção não representa corte registrado; sair da tela não desfaz retiradas registradas.

## Regras/invariantes já decididas

Os detalhes de domínio permanecem no HANDOFF e no plano da Fase 0. As confirmações adicionais do responsável para esta entrega estão explicitadas abaixo.

- Interface visível em es-AR; UX simples, rápida e fácil de usar.
- O corte físico ocorre antes do pagamento e reduz o estoque uma única vez pela quantidade efetivamente cortada. Pagamento posterior não reduz estoque novamente.
- **Distinção aprovada em 2026-10-05:** quantidade vendida é a quantidade cobrada do cliente; quantidade cortada é a quantidade efetivamente retirada fisicamente do(s) rolo(s). São grandezas distintas e ambas devem permanecer registráveis/auditáveis.
- **Valor do item:** quantidade vendida × preço unitário congelado. A quantidade cortada determina a baixa de estoque e a movimentação de `CORTE`, não o valor cobrado.
- **Diferença entre cortado e vendido:** deve permanecer registrável/auditável, sem atribuição automática de significado como perda, retalho, ajuste ou outra classificação e sem gerar movimentação adicional ou correção automática. Não impor igualdade, ordem entre as quantidades, proporção, tolerância ou relação adicional sem decisão expressa.
- Ticket representa um atendimento e pode conter vários itens/produtos. Um item pode consumir um ou mais lotes; a soma das quantidades retiradas dos lotes corresponde à quantidade cortada do item, não à quantidade vendida. Lotes físicos permanecem individualizados e rastreáveis; estoque agregado não representa um único trecho contínuo.
- Seleção de rolos segue o HANDOFF: preferir abertos, sugerir o menor saldo suficiente entre os capazes de atender à retirada física e permitir escolha manual; mostrar fechados depois. Verificação de saldo e distribuição por lote consideram a quantidade cortada, sem equipará-la automaticamente à vendida.
- Preço do item fica congelado no corte. Alterações posteriores de preço do produto não modificam itens já cortados; a atendente não altera preços existentes no fluxo de corte; alterações usam a área protegida por PIN.
- Não existe cancelamento operacional de corte, nem fluxo que recomponha, reclassifique ou devolva o material depois do corte.
- **Continuidade aprovada:** qualquer atendente autorizada a cortar pode acrescentar cortes a um ticket pendente iniciado por outra atendente. A operação considera bancada compartilhada e caixa único; os responsáveis existentes permanecem registrados, sem comprovar autoria individual na sessão compartilhada.
- **Responsável por retirada:** cada corte preserva seu responsável informado e os campos existentes, sem presumir que o usuário da sessão compartilhada identifica a pessoa que realizou a retirada. Não remover nem reatribuir registros existentes nesta etapa.
- **Apresentação aprovada:** ticket por código e resumo na tela, sem impressão nesta entrega. Caja / Venta localizará posteriormente o ticket por seu identificador.
- Falhas, repetição de envio e concorrência não podem duplicar a baixa, consumir saldo inexistente ou deixar efeitos parciais. Movimentações devem explicar os saldos e as retiradas registradas.

## Dependências

- Núcleo da Fase 0 e estoque persistido pela 1A, com validação das garantias utilizadas por Corte / Ticket.
- Integração da interface ao modelo de tickets, itens, lotes e movimentações com quantidades vendida e cortada distintas; a existência de telas antigas não comprova essa integração. A implementação atual usa uma única quantidade para valor, alocações e baixa e precisa de correção futura conforme esta regra. Esta atualização documental não altera schema/código nem autoriza implementação.
- Preservação do contrato com a futura 1C: mesmo identificador, itens, quantidades vendidas e preços congelados para cobrança, com pagamento separado do corte e preservação da quantidade cortada para rastreabilidade física. A entrega da 1B não depende de implementar Caja / Venta ou Administrativo.
- Para uso real, validar o acesso vigente do HANDOFF: sessão compartilhada na operação normal e PIN geral no Cierre e na correção do fundo. Não exigir autoria individual forte; preservar responsáveis registrados sem tratá-los como prova de identidade.

## Questões abertas

- Controle granular e autoria individual ficam para definição futura do Administrativo; não condicionam a operação normal. Sessão e PIN compartilhados não comprovam autoria individual.
- **1B, definição posterior:** regras de retalho, incluindo uso, origem, estado, tratamento e prioridade comercial. Não integram esta primeira entrega e não serão presumidas.
- **1C:** tratamento excepcional de ticket já cortado e não pago. Não presumir destino do material, novo estado ou solução financeira; não reintroduzir cancelamento.

Não foram identificadas outras decisões de negócio bloqueantes para o recorte local proposto da 1B. Continuidade por outra atendente autorizada, apresentação sem impressão e distinção entre quantidade vendida e cortada estão decididas. A diferença entre essas quantidades deve ser registrável/auditável nesta entrega; classificá-la ou tratá-la automaticamente não está aprovado. Isso não declara prontidão para uso real nem autoriza implementação. Tratamento de divergências físicas e demais comportamentos de Caja / Venta e Administrativo permanecem nos respectivos escopos.

## Critérios de conclusão

- Atendente busca produtos e registra cortes sobre lotes carregados pela 1A sem comandos técnicos; textos, mensagens e validações estão em es-AR.
- Ticket reúne vários produtos e preserva quantidade vendida e quantidade cortada por item; cortes de um lote e de vários lotes permitem identificar cada rolo utilizado, com soma das retiradas igual à quantidade cortada, distinguindo total agregado de trecho contínuo.
- Outra atendente autorizada localiza um ticket pendente e acrescenta um corte; cada retirada preserva seu responsável registrado, inclusive as anteriores, sem afirmar autoria individual comprovada.
- Saldo e movimentações de `CORTE` refletem uma única baixa pela quantidade cortada; quantidade inválida, lote incompatível e saldo insuficiente são rejeitados sem efeitos parciais. Repetição de envio e concorrência são verificadas sem duplicar itens ou retiradas.
- Valor do item é calculado pela quantidade vendida × preço unitário congelado; quantidade cortada distinta não substitui a vendida no cálculo. Preços congelados e ambas as quantidades são preservados e o mesmo ticket pode ser recuperado após nova sessão.
- Casos com quantidades vendida e cortada distintas demonstram que a diferença permanece registrável/auditável, sem classificação automática e sem relação adicional presumida entre as duas quantidades.
- Código e resumo são apresentados na tela sem impressão, com pagamento pendente explícito. O identificador permite recuperar o mesmo ticket e seus itens para a futura integração de Caja / Venta, sem exigir implementação do caixa neste aceite.
- Nenhum fluxo de cancelamento, ajuste de divergência, política de retalho, pagamento ou administração é introduzido neste recorte.
- Evidências de validação distinguem o que foi demonstrado das limitações existentes, especialmente identidade/autoria; aceite local não equivale a liberação para uso real.

## Acesso operacional — atualização aprovada em 2026-10-06

- Sessão compartilhada do terminal/caixa, sem exigir login/logout individual a cada atendimento. Productos / Stock, Corte / Ticket, Caja / Venta e Consulta de Caja ficam acessíveis na sessão operacional normal.
- Cierre del día exige PIN geral compartilhado; correção do Fondo inicial exige o mesmo PIN. A proteção deve valer também para acesso direto às operações sensíveis.
- Não criar PIN individual, usuários individuais, permissões granulares ou sessão administrativa. O PIN concede autorização de acesso e não comprova identidade/autoria individual.
- Preservar os campos e responsáveis atuais; não inferir autoria forte do usuário mostrado na sessão. Autoria individual confiável deixa de ser pré-requisito da operação normal nesta etapa.
- Administrativo futuro poderá substituir o mecanismo por controle granular. Permanecem as restrições administrativas e a proteção dos registros e segredos.
- Validar acesso normal sem troca individual de sessão, recusa de acesso sensível sem PIN válido e preservação das demais invariantes. Cierre, correção de Fondo inicial e a nova área protegida de preços exigem o mesmo PIN geral; os demais módulos permanecem na sessão operacional compartilhada.
- Autorização válida somente durante a permanência no fluxo protegido. Navegação entre etapas do mesmo fluxo não exige novo PIN; sair da área protegida encerra a autorização e novo acesso exige novo PIN.
- Valor real do PIN configurado localmente fora do repositório, nunca registrado em documentação versionada ou código-fonte. Verificação no servidor e nenhum armazenamento em texto puro. Gestão/troca amigável fica para o Administrativo futuro.
- Critérios de aceite do acesso: proteção também nos acessos diretos, continuidade autorizada entre etapas, encerramento ao sair e novo PIN ao retornar; preservar responsáveis existentes sem afirmar autoria individual. Não testar com um PIN real incorporado ao repositório.
- Esta atualização é documental; não declara o PIN implementado nem autoriza implementação.
