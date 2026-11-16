# Fase 0 — Núcleo de Dados — plano aprovado conceitualmente

## Objetivo

Disponibilizar uma base local consistente e rastreável para o percurso físico e financeiro da mercadoria, respeitando o [ROADMAP](../../ROADMAP.md) quanto à fase e ao escopo e o [HANDOFF](../../HANDOFF.md) quanto às regras e invariantes de domínio.

Este plano foi aprovado conceitualmente pelo responsável pelo projeto e está alinhado à mudança de domínio de 2026-10-05: ingresso confirmado pela atendente sem aprovação administrativa e cadastro de produto com preço inicial. Esta atualização não autoriza implementação. Distingue a base necessária ao desenvolvimento local das garantias exigidas antes de produção.

## Responsabilidades

- Preservar a integridade de produtos, ingressos, lotes físicos, cortes, tickets, vendas, fechamentos e movimentações.
- Manter os vínculos que permitem explicar origem, quantidade, momento, responsável registrado e destino da mercadoria.
- Garantir coerência entre saldo físico registrado, movimentações e resultado financeiro, sem confundir corte e pagamento.
- Proteger as operações contra acesso indevido e concorrência incompatível, mantendo sua integridade transacional.
- Sustentar os contratos de dados já decididos para as entregas Ingreso / Stock, Corte / Ticket e Caja / Venta, sem definir interfaces ou políticas ainda abertas e sem dependência do módulo administrativo.
- Distinguir a identificação de responsável informada para registro da comprovação confiável de autoria.

## Regras/invariantes já decididas

As regras de domínio abaixo vêm do HANDOFF; seus detalhes vigentes permanecem naquele documento.

- **Produto e quantidade:** atendente pode cadastrar produto e definir preço inicial; alterações posteriores exigem o fluxo protegido de preços com PIN geral. Preço pertence ao produto; quantidades admitem frações com precisão decimal; unidades previstas são metro, quilograma e unidade. Largura do tecido não multiplica o estoque em metro linear.
- **Individualização:** cada rolo físico tem identidade, produto, origem, quantidade inicial própria e quantidade atual. O padrão sugerido do produto não substitui a quantidade do recebimento. Estado operacional e condição física são informações distintas.
- **Ingresso:** atendente encontra ou cadastra produto, informa os rolos, confere e confirma; cada rolo vira lote individual imediatamente disponível, sem aprovação administrativa. Grupos homogêneos não eliminam a individualização: 4 × 30 m + 1 × 45 m produz cinco lotes. A declaração original permanece preservada; confirmação não pode deixar efeitos parciais ou duplicados.
- **Corte e ticket:** ticket representa um atendimento e pode ter vários itens; cada item pode consumir um ou mais lotes. A soma das quantidades alocadas deve corresponder à quantidade do item. A retirada baixa o estoque no corte, sem consumir saldo inexistente.
- **Preço e pagamento:** preço do item é congelado no corte; alteração posterior do produto não modifica o ticket anterior. O banco calcula a venda a partir dos itens; ticket vazio não pode ser pago. Pagamento não baixa estoque novamente.
- **Corte confirmado presencialmente:** o corte só é realizado presencialmente após solicitação/confirmação do cliente. Não existe cancelamento operacional de corte; depois dele, o sistema não oferece fluxo de cancelamento que recomponha, reclassifique ou devolva esse material. A retirada e sua rastreabilidade permanecem registradas. O conceito geral de retalho não é eliminado, mas qualquer uso por outra razão fica para definição posterior em 1B.
- **Livro-razão:** toda alteração física relevante deve ser explicável pelas movimentações; efeito de entrada ou saída deve ser inequívoco; saldo registrado deve ser consistente com o histórico. Material fisicamente cortado não pode ser recomposto no rolo original.
- **Fechamento:** valores esperados são calculados pelo banco; quando houver contagem física, o operador informa o contado e o sistema calcula a divergência. Isso não define o comportamento após o fechamento.
- **Permissões e autoria:** operador não altera diretamente saldo nem preço de produto existente; pode cadastrar produto com preço inicial e confirmar ingresso sem administrador, não acessa hashes e realiza operações por meios controlados. Autorização administrativa não pode se apoiar apenas em uma identidade informada pelo cliente. Registrar um identificador não comprova autoria.
- **Concorrência:** alterações de lotes e tickets são transacionais; operações simultâneas não podem consumir o mesmo saldo indevidamente, encerrar o mesmo ticket de formas incompatíveis, acrescentar itens a um ticket em finalização ou duplicar identificadores.

A implementação atual ainda exige aprovação de ingresso e não permite cadastro de produto pelo operador; esses contratos precisam ser adaptados antes da entrega 1A, sem preservar a aprovação como requisito. A validação do núcleo acompanha cada entrega: 1A não exige concluir 1B, 1C ou o Administrativo. Auditoria avançada e tratamento de divergências não integram seu primeiro aceite.

Confirmações do responsável pelo projeto registradas no ROADMAP também delimitam este plano: os dados anteriores fictícios não exigem migração, mas a futura base real deve ser preservada; agrupamento de recebimento não elimina os lotes individuais; divergência física posterior deve ser documentada, nunca corrigida silenciosamente; calendário operacional é Córdoba, Argentina, com caixa único e fechamento diário. Essas confirmações não escolhem a representação técnica dos dados nem resolvem políticas abertas dos demais módulos.

## Dependências

- Escopo da Fase 0 no ROADMAP e regras/invariantes do HANDOFF, respeitando a autoridade própria de cada documento.
- Decisões confirmadas do responsável pelo projeto, sem converter recomendações técnicas em regras.
- Ambiente PostgreSQL local de validação com dados fictícios, necessário para demonstrar os critérios de conclusão quando houver implementação autorizada.
- Acesso conforme HANDOFF: sessão operacional compartilhada e PIN geral para Cierre e correção de fundo, sem exigir autoria individual forte para a operação normal.

O documento [SCHEMA_V3_1.md](SCHEMA_V3_1.md) é apenas referência técnica não aprovada: problemas ali apontados podem orientar análise, mas suas soluções e critérios adicionais não são incorporados automaticamente.

As decisões ainda abertas dos módulos 1A, 1B, 1C, Administrativo e Fase 3 permanecem nesses escopos. Em particular, qualquer uso restante de retalho pertence à definição posterior de 1B, e o tratamento excepcional de ticket já cortado que não seja pago permanece aberto em 1C, sem solução presumida neste plano. Este plano não as converte em escolhas da Fase 0 nem condiciona todo o desenvolvimento local à sua resolução. Qualquer comportamento dependente dessas decisões permanece sem definição e não pode ser declarado validado por este plano.

## Questões abertas

**Acesso operacional decidido:** sessão compartilhada, sem login/logout individual a cada atendimento; Productos / Stock, Corte / Ticket, Caja / Venta e Consulta de Caja acessíveis normalmente. Cierre e correção do Fondo inicial exigem o mesmo PIN geral. Não criar PIN individual nem permissões por funcionário nesta etapa.

Cierre, correção de Fondo inicial e a nova área protegida de preços exigem o mesmo PIN geral. A autorização vale durante o fluxo protegido, sem repetição entre suas etapas; sair encerra a autorização e retornar exige novo PIN. O valor real é configuração local fora do repositório e não aparece em documentos versionados ou código-fonte; verificar no servidor e não armazenar em texto puro. O PIN controla autorização, não autoria. Preservar campos de responsáveis sem tratar o usuário da sessão como prova de quem executou cada ação. Esta decisão substitui a exigência anterior de identidade/autoria individual confiável antes do uso real da operação normal; não reduz as demais garantias de segurança e integridade.

**Futuro Administrativo:** controle granular e eventual garantia de autoria individual dependem de definição futura, sem escolher mecanismo agora. Gestão/troca amigável do PIN fica para o Administrativo futuro; não criar usuários individuais, permissões granulares ou sessão administrativa nesta etapa.

Desenvolvimento e uso real devem demonstrar as proteções do recorte adotado. Atualizar este plano não implementa essas proteções nem declara a aplicação pronta para uso real.

## Critérios de conclusão

- Base inicializável e validável em ambiente local limpo, sem migração dos dados fictícios.
- Invariantes já decididas demonstradas por validação funcional, de permissões e de concorrência, com cobertura dos casos obrigatórios do HANDOFF pertinentes ao núcleo; resultados e limitações registrados.
- Ingressos confirmados pela atendente disponibilizam unidades físicas individualmente identificáveis e de origem rastreável; cadastro inicial com preço é permitido, alteração posterior fora do fluxo protegido de preços é impedida; cortes e alocações preservam quantidades e saldos.
- Retirada física preservada, sem recomposição de saldo e sem fluxo de cancelamento operacional de corte; não presumir geração, origem ou tratamento de retalho ainda não definido em 1B.
- Preço congelado preservado; venda calculada pelos itens; ticket vazio rejeitado; pagamento sem segunda baixa.
- Saldo de cada lote explicável pelo livro-razão; corte permanece reconhecido como retirada física independentemente do pagamento; valores esperados de fechamento derivam dos registros, sem presumir política posterior ao fechamento.
- Restrições do operador e proteção contra operações concorrentes incompatíveis comprovadas, incluindo ausência de exposição de hashes e de duplicação de identificadores.
- **Para desenvolvimento local:** resultados do núcleo decididos e validados permitem sustentar o trabalho local; eventual limitação de autoria permanece explícita. Iniciar desenvolvimento local não equivale a concluir todos estes critérios nem a liberar produção.
- **Antes do uso real:** validar o acesso operacional aprovado, incluindo PIN geral para Cierre e correção do fundo e preservação das restrições administrativas. Não exigir autoria individual forte para a operação normal nem atribuí-la ao PIN ou à sessão. A conclusão do núcleo não substitui os critérios de implantação e dos outros módulos.
- Nenhum comportamento ainda dependente de decisão de outro módulo é apresentado como concluído; evidências de validação distinguem o que foi verificado do que permanece fora do escopo ou pendente.
