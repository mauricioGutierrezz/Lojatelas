# Preços protegidos e foto principal de produto — decisões aprovadas

## Objetivo e autoridade

Facilitar atualização controlada de preços e identificação visual rápida dos tecidos, sem construir módulo de mídia ou Administrativo completo. ROADMAP governa escopo; HANDOFF governa domínio. Este documento consolida somente as novas decisões aprovadas e sua avaliação de impacto; não autoriza implementação nem transforma SCHEMA_V3_1 em autoridade.

## Área protegida de preços

- Usar o mesmo PIN geral existente, mantendo autorização apenas durante o fluxo protegido. Navegação entre etapas do mesmo fluxo não pede novamente o PIN; sair encerra a autorização e novo acesso exige PIN.
- Mostrar todos os produtos numa lista com busca/filtro. Cada item mostra foto pequena quando houver foto principal, nome e preço atual; foto é opcional no produto.
- Editar preço diretamente na lista. Item alterado fica visualmente marcado como mudança pendente.
- Ação de revisão apresenta somente os produtos alterados com preço anterior → novo. Confirmação final aplica todas as mudanças.
- Gravação atômica: todas as alterações válidas são aplicadas ou nenhuma. Preços e seu histórico devem permanecer coerentes em caso de falha.
- Histórico preserva produto, preço anterior, preço novo e data/hora. Sessão compartilhada e PIN não comprovam autoria individual; preservar os responsáveis existentes sem inferir identidade pessoal.
- Preços congelados de tickets existentes permanecem inalterados. Não permitir atualização irrestrita de preço pelo cadastro operacional.
- A decisão amplia o acesso protegido antes limitado a Cierre/correção do fundo e substitui a reserva de preços ao Administrativo futuro; não cria permissões granulares ou outros privilégios administrativos.

## Foto principal

- Produto pode ter uma foto principal, destinada à identificação rápida do tecido.
- Adicionar/substituir rapidamente pelo cadastro do produto, por seleção/upload de arquivo ou colagem de imagem da área de transferência, como imagem copiada do WhatsApp Web ou captura de tela.
- Exibir miniatura no cadastro/stock, nas buscas/listas operacionais em que ajude a identificar produto e obrigatoriamente na futura lista protegida de preços. Clique/toque permite visualizar a imagem maior.
- Preferir estrutura separada para fotos, preparada para evolução futura. Essa preferência não autoriza múltiplas fotos nesta versão: no máximo uma principal por produto.
- Fora do escopo: múltiplas fotos, galeria, crop, edição de imagem, câmera, organização de fotos e histórico avançado de imagens.

## Impacto mínimo em dados e aplicação — avaliação, não implementação

- **Dados de preço:** manter o preço atual do produto e acrescentar suporte ao histórico aprovado, vinculado ao produto, com valor anterior/novo e horário. A aplicação precisa de uma operação controlada capaz de confirmar o conjunto revisado atomicamente; nomes e mecanismos técnicos não são definidos aqui.
- **Dados de foto:** prever vínculo opcional de produto com uma imagem principal e metadados/referência suficientes para recuperá-la. Preferência por estrutura separada, com garantia de uma principal por produto. Armazenar bytes no banco ou arquivo local referenciado são alternativas técnicas ainda não selecionadas neste documento; ambas precisam preservar coerência e recuperação.
- **Aplicação de preços:** acesso protegido também nos caminhos diretos, lista filtrável, edição pendente preservada durante a revisão, resumo somente dos alterados e confirmação única. Não implementar imediatamente a partir desta descrição.
- **Aplicação de fotos:** entrada por arquivo e evento de colagem com imagem, validação comum, substituição da principal, miniaturas e ampliação. Não ler clipboard silenciosamente nem importar conversas ou contatos; o recurso recebe a imagem colada pelo funcionário.
- **Integração:** fotos não alteram estoque, quantidades, cálculo financeiro ou fechamento. Área protegida de preços não recalcula tickets cortados anteriormente. Não definir novos nomes SQL, estados de negócio ou sequência de construção.

## Riscos técnicos reais e limites da avaliação

- **Clipboard:** copiar uma mensagem, link ou elemento de WhatsApp Web nem sempre fornece bytes de imagem. Comportamento varia por navegador/contexto e pode depender de permissão. Identificar quando não há imagem colável e manter upload como alternativa; não supor integração com WhatsApp nem download automático de URL.
- **Arquivos não confiáveis:** extensão e tipo declarado não comprovam conteúdo. Validar a imagem no servidor; controlar formatos aceitos, tamanho em bytes e dimensões para evitar conteúdo ativo, arquivos malformados e consumo excessivo de memória/disco. Limites e bibliotecas são escolhas técnicas a justificar, não regras escolhidas por este plano.
- **Miniaturas/desempenho:** imagens grandes não devem ser carregadas integralmente em toda linha da lista. Derivação técnica de miniatura não introduz ferramenta de edição/crop para o usuário. Preservar identificação visual útil e evitar distorção; foto não constitui garantia de fidelidade de cor do tecido.
- **Armazenamento local:** nomes fornecidos pelo usuário não devem determinar caminhos arbitrários ou permitir execução de conteúdo. Manter mídia fora do código versionado, com acesso controlado e estratégia de backup/restauração coerente com os dados do produto. A política de backup geral continua no escopo próprio de implantação.
- **Substituição/falha:** escrita de arquivo e gravação no banco podem falhar separadamente. Evitar referência quebrada, perda da foto anterior antes da nova estar válida e acúmulo de arquivos órfãos. Isso não autoriza histórico avançado de imagens.
- **Metadados:** imagem copiada pode conter dados pessoais, localização ou conteúdo não pretendido. O processamento e a exposição devem se limitar ao necessário para identificação do produto; não introduzir coleta de metadados como funcionalidade.
- **Concorrência de preços:** outra alteração pode ocorrer entre edição, revisão e confirmação. O mecanismo técnico deve preservar a coerência entre valores revisados, preços efetivamente aplicados e histórico, sem atualização parcial. Se a solução exigir decidir sobrescrita silenciosa, fusão ou outro comportamento de negócio não aprovado, expor a decisão antes de implementá-la; este documento não seleciona essa política.

## Resultados verificáveis

- Acesso à lista protegida pelo mesmo PIN, sem atribuição de autoria individual.
- Lista com todos os produtos, busca/filtro, miniatura quando existente, nome e preço; mudanças pendentes distinguíveis.
- Revisão mostra somente produtos alterados e valores anterior/novo; confirmação grava o conjunto e histórico coerentes ou não aplica nenhuma mudança.
- Tickets anteriores conservam preços congelados.
- Upload e colagem de imagem permitem adicionar/substituir a única foto principal; miniaturas e ampliação funcionam nos contextos aprovados.
- Arquivo inválido ou falha de armazenamento não deixa vínculo quebrado nem elimina silenciosamente foto válida; validações e limites técnicos são demonstrados.
- Nenhum recurso de galeria, edição, câmera ou histórico avançado é introduzido.

## Documentos afetados e conflitos

HANDOFF registra as decisões; ROADMAP delimita a extensão; planos ativos e referência técnica recebem somente correções das restrições antigas de preços e da lista de áreas protegidas. Guias distinguem operação já implementada da extensão futura. SCHEMA_V3_1 permanece proposta não aprovada, subordinada às autoridades.

Os conflitos documentais reais eram a exclusividade de preço para Administração e a afirmação de que somente Cierre/correção de fundo usam PIN. São superados pela nova decisão explícita. A implementação atual ainda precisa receber a extensão de preços/fotos mediante autorização; nenhuma mudança em schema.sql é realizada nesta tarefa.
