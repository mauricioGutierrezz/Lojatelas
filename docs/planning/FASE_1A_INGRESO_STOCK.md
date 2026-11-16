# Fase 1A — Ingreso / Stock — primeira entrega utilizável proposta

## Objetivo

Entregar uma aplicação local simples, rápida e prática para começar a preencher a base real de produtos e estoque e registrar recebimentos sem depender do módulo administrativo. ROADMAP governa escopo; HANDOFF governa domínio. As regras abaixo foram aprovadas pelo responsável; este plano organiza a entrega e não autoriza implementação.

## Responsabilidades

- Encontrar produtos por categoria/produto e permitir à atendente cadastrar produto novo com preço inicial.
- Capturar os rolos individualmente ou em grupos homogêneos, conferir e confirmar o ingresso.
- Disponibilizar cada rolo como lote individual após a confirmação, com origem, quantidade declarada e movimentação de entrada rastreáveis.
- Consultar produtos, lotes, quantidade declarada, saldo atual, estoque total e maior lote disponível.
- Persistir os dados para uso entre sessões da loja, sem depender de internet ou de aprovação administrativa.

Fluxo operacional mínimo: mercadoria chega → atendente encontra ou cadastra produto → informa os rolos → confere → confirma → lotes individuais são criados → estoque fica disponível imediatamente.

## Regras/invariantes já decididas

- Interface visível em es-AR; UX simples, rápida e fácil de usar.
- O ingresso operacional não exige aprovação administrativa nem fila de liberação.
- Cada rolo físico vira lote individual. 4 × 30 m + 1 × 45 m resulta em cinco lotes: quatro de 30 m e um de 45 m. Quantidades diferentes ficam em grupos separados; padrão do produto é apenas sugestão.
- Atendente pode cadastrar produto e definir seu preço inicial. Alterações posteriores de preço usam a área protegida com PIN geral, conforme a extensão aprovada em PRECIOS_FOTOS_PRODUCTO.md; não são permitidas diretamente no cadastro operacional.
- A quantidade declarada não é sobrescrita silenciosamente. Origem e movimentações preservam rastreabilidade; não há ajuste de saldo inventado para tratar divergências.
- Repetição, falha ou concorrência não podem gerar lotes parciais ou duplicados.
- Não fazem parte desta entrega corte/ticket, caixa/venda, auditoria avançada, relatórios, alertas, aprovação de ingresso ou tratamento sofisticado de divergências. A rastreabilidade básica permanece obrigatória.
- As entregas seguintes preservam a baixa única no corte e pagamento sem nova baixa; 1A não precisa implementá-las para ser concluída.

## Dependências

- Adaptar o núcleo implementado: substituir a dependência de aprovação de ingresso pela confirmação operacional e permitir cadastro inicial de produto/preço com proteção contra alteração posterior fora da área protegida de preços.
- Integrar a aplicação de ingresso ao núcleo atual; a rota antiga ainda usa um modelo anterior e não constitui entrega 1A compatível.
- Validar persistência, integridade, permissões e consultas utilizadas por esta entrega. Testes de aprovação administrativa precisam refletir a nova regra.
- Para uso real, validar o acesso vigente do HANDOFF: sessão compartilhada na operação normal e PIN geral no Cierre e na correção do fundo. Não exigir autoria individual forte; preservar responsáveis registrados sem tratá-los como prova de identidade.

## Questões abertas

- Representação, documentação e tratamento de divergências físicas posteriores, inclusive eventual efeito sobre saldo e disponibilidade: definição posterior, fora do aceite desta primeira entrega. A necessidade de registro/auditoria futura permanece; não se presume solução por observação livre, ajuste ou substituição da declaração original.
- Controle granular e autoria individual ficam para definição futura do Administrativo; não condicionam a operação normal. Sessão e PIN compartilhados não comprovam autoria individual.
- Questões de retalhos em 1B e de tickets cortados não pagos, contagem e fechamento em 1C permanecem nos módulos próprios, sem bloquear o recorte de 1A.

Não permanecem abertas a aprovação do ingresso nem a permissão de cadastro com preço inicial: ambas foram decididas. Detalhes técnicos equivalentes podem ser escolhidos pelo Programador sem resolver negócio implicitamente.

## Critérios de conclusão

- Uma atendente encontra ou cadastra um produto com preço inicial, informa os rolos, confere e confirma o ingresso sem intervenção administrativa ou comandos técnicos.
- O exemplo 4 × 30 m + 1 × 45 m cria cinco lotes identificáveis, com quantidades próprias e disponibilidade imediata após confirmação.
- A consulta recupera os produtos e rolos registrados, sua origem, declaração original e saldo; distingue total agregado de maior trecho contínuo.
- Alteração de preço existente fora do fluxo protegido por PIN é impedida, inclusive por caminhos alternativos ao cadastro inicial.
- Repetição, falha e concorrência não duplicam nem deixam estoque parcialmente efetivado; saldo registrado concilia com movimentações.
- Dados confirmados permanecem consultáveis após nova sessão; registros reais não são tratados como dados descartáveis de teste.
- Textos, mensagens e validações visíveis estão em es-AR. As tarefas de consulta, cadastro e ingresso podem ser realizadas pela atendente sem ajuda técnica, em operação local sem internet.
- Validações funcionais e de permissões da entrega são demonstradas. Limitações ainda presentes são informadas; liberação para uso real exige as garantias do núcleo aplicáveis, sem exigir a entrega do Administrativo.
- Recursos adiados não são implementados por hipótese nem usados como condição de conclusão de 1A.

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

A extensão aprovada de foto principal e área protegida de preços está em [PRECIOS_FOTOS_PRODUCTO.md](PRECIOS_FOTOS_PRODUCTO.md). Foto pode ser adicionada/substituída no cadastro por arquivo ou colagem, com miniatura no cadastro/stock e visualização maior; isso não altera ingresso ou saldo. A alteração posterior de preço usa exclusivamente o fluxo protegido aprovado.
