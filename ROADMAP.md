# ROADMAP — fases e escopo vigentes

Referência vigente de organização do projeto; não autoriza implementação nem resolve as questões abertas. O ROADMAP governa fases e escopo. O [HANDOFF](HANDOFF.md) governa regras e invariantes de domínio. Planos de módulo devem respeitar ambos; propostas não substituem decisões aprovadas.

As regras abaixo são resumos necessários à compreensão do escopo. Consulte o HANDOFF para os detalhes vigentes de domínio. Confirmações posteriores do responsável pelo projeto estão explicitadas onde se aplicam; não representam uma ampliação da autoridade do ROADMAP sobre o domínio. Questões abertas indicam o módulo ou fase em que precisam estar resolvidas, sem definir uma sequência de implementação.

Este documento está separado de `docs/history/roadmap.md`, que permanece como histórico. `docs/planning/SCHEMA_V3_1.md` é uma proposta técnica não aprovada, não o plano da Fase 0. Seus detalhes, recomendações e critérios adicionais não se tornam decisões por referência neste ROADMAP.

Princípios aprovados para a futura interface da aplicação:

- Toda interface visível ao usuário da loja deve estar em espanhol da Argentina (`es-AR`).
- A UX deve priorizar simplicidade, rapidez e facilidade de uso.

Sequência de entregas utilizáveis: **1A Ingreso / Stock → 1B Corte / Ticket → 1C Caja / Venta → Administrativo separado**, sobre o mesmo núcleo de dados. A primeira entrega permite começar a preencher a base real sem aguardar o Administrativo. A adaptação necessária do núcleo acompanha cada entrega.

**Decisão de acesso vigente (2026-11-15):** três contas fixas por papel — Administrador (tudo), Empleado (Productos / Stock e Corte / Ticket) e Cajero (Corte / Ticket, Caja / Venta, Consulta, Cierre e Fondo) — sem PIN geral; o papel autoriza e não identifica a pessoa. Detalhes no HANDOFF §8 e em `docs/decisions/2026-11-15-papeis-sem-pin.md`. Onde este ROADMAP mencionar PIN geral ou sessão compartilhada, vale esta decisão. Próximas entregas: vários computadores na rede local e acesso remoto do Administrador por VPN (`docs/planning/PAPEIS_REDE_ACESSO_REMOTO.md`).

Registro da decisão anterior, substituída: sessão operacional compartilhada, sem login/logout individual por atendimento; Cierre e correção do Fondo inicial exigem PIN geral compartilhado. O PIN não comprova autoria individual. A nova área protegida de preços também exige o mesmo PIN geral, conforme a decisão posterior registrada no HANDOFF. A autorização dura apenas no fluxo protegido: navegar entre suas etapas não pede novo PIN; sair encerra a autorização e novo acesso exige PIN. Valor real configurado localmente fora do repositório, nunca documentado ou incluído em código; verificação no servidor e sem armazenamento em texto puro, conforme HANDOFF. Gestão/troca amigável e controle granular ficam para o Administrativo futuro; não criar usuários individuais ou sessão administrativa. Campos de responsáveis são preservados.

## Fase 0 — Núcleo de Dados

- **Objetivo:** garantir uma base local consistente e rastreável para o percurso físico e financeiro da mercadoria.
- **Responsabilidades:** integridade de produtos, ingressos, lotes, cortes, tickets, vendas e movimentações; autoria, permissões e proteção contra operações concorrentes incompatíveis.
- **Regras já decididas:** estoque físico por rolo em `m`, por peça em `kg` e agregado inteiro por produto em `un`, conforme revisão transversal de 2026-10-07; movimentações rastreáveis; integridade física, financeira e de acesso conforme o HANDOFF. Dados anteriores fictícios não exigem migração; essa condição não se aplica à futura base real. Confirmação de ingresso pela atendente disponibiliza estoque imediatamente; cadastro de produto permite preço inicial, com alterações posteriores pelo fluxo protegido de preços com PIN geral.
- **Dependências:** HANDOFF e decisões confirmadas; adaptação dos contratos de ingresso e cadastro às regras vigentes. As entregas dependem somente das garantias do núcleo que utilizam.
- **Questões abertas:** controle de acesso granular e autoria individual — definição futura do Administrativo, sem condicionar a operação normal à autoria forte; documentação e tratamento de divergência física — resolver em 1A; efeitos do fechamento — decididos no recorte de 1C, conforme HANDOFF.
- **Critérios de conclusão:** base inicializável sem migração dos dados fictícios; validação das invariantes físicas e financeiras, rastreabilidade, permissões e concorrência; saldo explicável pelas movimentações; retirada preservada sem recomposição do saldo; pagamento sem segunda baixa; contratos afetados por decisões abertas aprovados antes de serem considerados concluídos. Operação normal usa sessão compartilhada; validar PIN geral para acesso ao Cierre e correção de fundo, sem apresentar esse PIN como autoria individual.

## Fase 1 — Operação da Loja

- **Objetivo:** chegar rapidamente a uma aplicação local simples, rápida e utilizável pela loja, começando pelo preenchimento da base real e pelo estoque.
- **Responsabilidades:** entregar separadamente 1A Ingreso / Stock, 1B Corte / Ticket e 1C Caja / Venta, nessa ordem.
- **Regras já decididas:** funcionamento local sem internet nem dependência do Administrativo; interface es-AR; calendário de Córdoba, Argentina; corte e pagamento separados. Caixa único e fechamento diário permanecem no escopo de 1C.
- **Dependências:** núcleo validado para as operações de cada entrega; condições necessárias ao uso real preservadas, sem exigir o módulo administrativo.
- **Questões abertas:** representação e tratamento de divergências ficam para definição posterior; retalhos em 1B e exceções/fechamento em 1C não bloqueiam a primeira entrega.
- **Critérios de conclusão:** cada entrega tem aceite próprio; 1A permite cadastrar e receber estoque real, 1B registrar cortes e tickets, e 1C concluir vendas. Conclusão de 1A não depende das duas seguintes nem de recursos gerenciais.

### 1A — Ingreso / Stock

- **Objetivo:** primeira aplicação utilizável para começar a preencher a base real e controlar os recebimentos e o estoque da loja.
- **Responsabilidades:** encontrar ou cadastrar produto com preço inicial; informar rolos, peças/pesos ou unidades, conferir e confirmar ingresso; consultar declaração, saldo e origem física ou movimentos agregados, conforme a revisão transversal.
- **Regras já decididas:** atendente confirma ingresso sem aprovação administrativa; cada rolo vira lote individual e imediatamente disponível. Entrada agrupada só reúne rolos homogêneos; 4 × 30 m + 1 × 45 m resulta em cinco lotes. Atendente define preço inicial de produto novo; alterações posteriores usam a área protegida de preços por PIN. Dado original não é sobrescrito silenciosamente. Interface es-AR; UX simples, rápida e fácil de usar.
- **Dependências:** adaptação e validação do núcleo para confirmação operacional, cadastro inicial e limites de preço; condições de uso real do núcleo. Não depende do Administrativo, de auditoria avançada ou do tratamento de divergências.
- **Questões abertas:** representação, documentação e tratamento de divergências físicas posteriores, incluindo efeitos sobre saldo e disponibilidade — definição posterior de 1A, fora do aceite desta primeira entrega. Não há decisão pendente de aprovação administrativa do ingresso: ela foi removida.
- **Critérios de conclusão:** atendente encontra/cadastra produto, informa e confere os grupos e confirma sem administrador; cinco lotes individuais disponíveis no exemplo; repetição/falha não duplica nem deixa lotes parciais; consulta distingue total e maior lote nos produtos físicos e apresenta agregado inteiro para `un`; origem e declaração original preservadas; preço existente protegido; dados persistem entre sessões; tarefas locais verificadas em es-AR. Plano de referência: `docs/planning/FASE_1A_INGRESO_STOCK.md`.

### 1B — Corte / Ticket

- **Objetivo:** registrar a retirada física e reunir os itens de um atendimento em um ticket.
- **Responsabilidades:** seleção de produto e origem física quando aplicável; quantidades vendida/retirada e alocações físicas para `m`/`kg`; corte/retirada presencial após solicitação/confirmação do cliente; ticket com múltiplos itens.
- **Regras já decididas:** o corte só é realizado presencialmente após solicitação/confirmação do cliente; baixa física e congelamento do preço ocorrem no corte. Não existe cancelamento operacional de corte nem fluxo posterior de cancelamento que recomponha, reclassifique ou devolva o material. Seleção de lotes, alocações e estados do ticket seguem o HANDOFF. O conceito geral de retalho permanece para definição posterior em 1B, sem origem por cancelamento.
- **Dependências:** Fase 0; lotes disponíveis por 1A. Qualquer uso futuro de retalho depende de definição em 1B.
- **Questões abertas:** qualquer uso de retalho por outra razão, sua origem, estado e tratamento, inclusive prioridade comercial — resolver em 1B.
- **Critérios de conclusão:** cortes presenciais após solicitação/confirmação do cliente, simples e multilote, rastreáveis e sem saldo insuficiente; preço preservado; ticket com itens e alocações coerentes; ausência de cancelamento operacional de corte. Uso futuro de retalho só pode ser considerado concluído após definição aprovada em 1B.

### 1C — Caja / Venta

- **Objetivo:** receber tickets e, na etapa seguinte da própria 1C, oferecer Consulta de Caja e Cierre del día.
- **Responsabilidades:** recebimento integral; consulta informativa dos valores atuais; fundo inicial diário com histórico; contagem opcional e fechamento formal definitivo.
- **Regras já decididas:** caixa único; calendário de Córdoba; valores derivados pelo banco; pagamento sem nova baixa. Consulta não fecha nem bloqueia. Um único Cierre por data, sem reabertura, bloqueia novos recebimentos daquela data após confirmação; movimento alterado antes dela exige revisão. Fundo definido antes do Cierre, sem bloquear vendas enquanto ausente. Contagem opcional inclui o fundo; diferença apenas matemática contra fundo + efectivo das vendas. Detalhes no HANDOFF.
- **Dependências:** núcleo e recebimento Efectivo/Outro; adaptação e validação dos contratos de consulta, fundo, fechamento e concorrência; sessão compartilhada e proteção por PIN geral do Cierre e da correção de fundo, conforme HANDOFF.
- **Questões abertas:** tratamento excepcional de ticket cortado que não seja pago; futuras políticas administrativas de contagem obrigatória e restrição de permissões. Não bloqueiam o recorte local aprovado. Tickets pendentes podem atravessar dias e entram no movimento da data de recebimento; pós-fechamento e unicidade estão decididos.
- **Critérios de conclusão:** totais conferíveis; consulta sem efeito de fechamento; fundo rastreável; contagem ausente distinta de zero; Cierre único e preservado; recebimentos posteriores da mesma data impedidos; alterações concorrentes exigem revisão sem perda de vendas; sem reabertura, movimentos extraordinários ou redesign visual. Plano: `docs/planning/FASE_1C_CAJA_VENTA.md`.

## Revisão transversal — unidades e estoque (2026-10-07)

- **Objetivo:** tornar a operação já entregue coerente com `m`, `un` e `kg`, do cadastro ao histórico, sem aguardar o Administrativo.
- **Responsabilidades:** adaptar núcleo, ingresso, stock, retirada, ticket/resumo, Caja, Precios, consultas, erros, JavaScript, testes e guias. Esta entrega atualiza os contratos dos recortes anteriores; não reescrever seus planos como previsão retroativa.
- **Regras já decididas:** `m` por rolo físico; `kg` por peça física; `un` agregado inteiro por produto, sem FIFO/LIFO nem vínculo obrigatório da saída a um ingresso. Preservar quantidades vendida/retirada distintas, preço congelado, baixa única, histórico e garantias transacionais. Detalhes no HANDOFF.
- **Dependências:** inspeção efetiva da base operacional antes de definir transformação automática; novo plano técnico [REVISAO_TRANSVERSAL_UNIDADES_ESTOQUE.md](docs/planning/REVISAO_TRANSVERSAL_UNIDADES_ESTOQUE.md). Os exemplos anteriores de maior lote e individualização referem-se a estoque físico, não ao agregado de `un`.
- **Questões abertas:** nenhuma atribuição de origem por ingresso para `un`: ela foi explicitamente dispensada. Exceções reais de dados, se encontradas, exigem resolução específica; não converter frações, significados físicos incertos ou divergências silenciosamente.
- **Critérios de conclusão:** contratos e telas coerentes nas três unidades; saldo agregado e saldos físicos conciliáveis; migração preservadora demonstrada; regressões financeiras, concorrência e idempotência verificadas. Documentação de planejamento não implementa a entrega.

## Extensão aprovada — preços protegidos e foto de produto

- **Objetivo:** facilitar identificação visual dos tecidos e atualização controlada dos preços, sem criar módulo de mídia nem aguardar o Administrativo completo.
- **Responsabilidades:** cadastro/substituição de uma foto principal por arquivo ou colagem; miniaturas e visualização maior; lista protegida de todos os produtos com filtro, edição de preços, revisão e confirmação coletiva.
- **Regras já decididas:** mesmo PIN geral; alterações pendentes marcadas; revisão somente dos alterados; gravação atômica e histórico de preço anterior/novo por produto com horário. Uma foto principal por produto; preferir estrutura separada, sem galeria ou edição de imagens. Detalhes no HANDOFF.
- **Dependências:** catálogo atual, proteção por PIN e contratos de preços congelados; extensão de dados para histórico de preços e foto, sem definir mecanismo concreto neste ROADMAP.
- **Questões abertas:** escolhas técnicas equivalentes de armazenamento e processamento não alteram as decisões aprovadas; riscos e limites constam no plano subordinado.
- **Critérios de conclusão:** resultados aprovados verificáveis conforme `docs/planning/PRECIOS_FOTOS_PRODUCTO.md`; nenhuma alteração parcial de preços, nenhum efeito sobre tickets anteriores, nenhuma autoria individual presumida. Não autoriza implementação.

## Fase 2 — Administrativo separado

- **Objetivo:** desenvolver a área administrativa separadamente sobre o mesmo núcleo de dados, sem bloquear a operação da loja.
- **Responsabilidades:** alterações posteriores de preço, auditoria avançada, relatórios e alertas em escopos próprios.
- **Regras já decididas:** ingresso operacional não exige aprovação administrativa; a primeira definição de preço pertence ao cadastro pela atendente e alterações posteriores usam a área protegida por PIN, sem aguardar o Administrativo completo. Rastreabilidade básica já pertence ao núcleo.
- **Dependências:** mesmo núcleo e dados operacionais das entregas da loja; acesso remoto permanece na Fase 3.
- **Questões abertas:** recorte de auditoria avançada, relatórios e alertas; representação e tratamento de divergências seguem pendentes, sem ampliar a primeira entrega.
- **Critérios de conclusão:** capacidades administrativas validadas no escopo que vier a ser aprovado, sem introduzir aprovação de ingresso nem dependência administrativa nos fluxos operacionais definidos.

### Auditoria

- **Objetivo:** explicar a trajetória física e financeira da mercadoria.
- **Responsabilidades:** consulta de origem, movimentos, responsáveis, cortes, vendas e divergências documentadas. Qualquer inclusão futura de retalhos depende da definição de 1B.
- **Regras já decididas:** distinguir movimento físico de resultado comercial conforme o HANDOFF; divergência física deve permanecer documentada.
- **Dependências:** Fase 0; registros de 1A, 1B e 1C; formato aprovado para divergências físicas.
- **Questões abertas:** apresentação gerencial das divergências — resolver em Auditoria; formato de seu registro — resolver em 1A.
- **Critérios de conclusão:** trajetórias reconstruíveis desde o ingresso, com cortes e pagamentos registrados; saldos e movimentos conciliáveis; divergências visíveis conforme decisão aprovada. A auditoria não presume tratamento do ticket cortado não pago nem uso de retalho ainda não definido.

### Relatórios

- **Objetivo:** oferecer informações gerenciais conferíveis sobre estoque e operação.
- **Responsabilidades:** consolidação de estoque inicial, cortes, vendas e fechamentos; consulta por período operacional.
- **Regras já decididas:** distinguir cortado de vendido e respeitar unidades conforme o HANDOFF; períodos seguem o calendário de Córdoba, Argentina.
- **Dependências:** Fase 0; registros operacionais; conceitos de fechamento aprovados em 1C; rastreabilidade disponível para conferência.
- **Questões abertas:** conjunto inicial de relatórios, comparações entre períodos e necessidade de exportação — resolver em Relatórios.
- **Critérios de conclusão:** conjunto inicial aprovado; números conferíveis com registros de origem; distinção entre estoque, corte e venda; períodos e unidades apresentados sem ambiguidade.

### Alertas

- **Objetivo:** sinalizar necessidades de reposição para acompanhamento administrativo.
- **Responsabilidades:** identificar produtos com estoque abaixo do critério aprovado e apresentar a necessidade ao administrador.
- **Regras já decididas:** estoque mínimo configurável pertence à etapa administrativa; limite atual é provisório e deve respeitar a unidade do produto, conforme o HANDOFF.
- **Dependências:** estoque confiável de 1A; definição dos limiares e da apresentação dos alertas.
- **Questões abertas:** definição dos limiares, apresentação e eventual notificação — resolver em Alertas.
- **Critérios de conclusão:** critérios e apresentação aprovados; alertas coerentes com os saldos e unidades; limite provisório não tratado como política definitiva.

## Fase 3 — Implantação / Rede

- **Objetivo:** ampliar a implantação e disponibilizar acesso administrativo remoto seguro sem comprometer a operação local já entregue. Esta fase não é pré-requisito para começar o uso local de 1A com suas garantias aplicáveis validadas.
- **Responsabilidades:** ambiente da loja, acesso remoto, continuidade operacional, recuperação e preparação da equipe.
- **Regras já decididas:** operação local independe da internet; acesso remoto e VPN pertencem a esta fase. Dados anteriores fictícios não exigem migração; a base real iniciada em 1A deve ser preservada. Ingresso do estoque inicial segue o fluxo operacional de 1A e do HANDOFF.
- **Dependências:** módulos utilizados pela implantação em questão validados; acesso operacional compartilhado protegido conforme HANDOFF e controles próprios do acesso remoto; decisões operacionais aplicáveis aprovadas. A entrega do Administrativo não condiciona o início da operação local de estoque.
- **Questões abertas:** solução de rede privada, dispositivos autorizados e política de backup e recuperação — resolver na Fase 3. O uso por vários computadores na rede local da loja foi implementado em 2026-11-16 (`docs/decisions/2026-11-16-rede-local.md`), com HTTP sem cifra aceito pelo responsável por a rede ser exclusiva da loja; acesso remoto por VPN segue em aberto. Um backup local diário provisório foi confirmado em 2026-11-15 (`docs/decisions/2026-11-15-uso-pratico-windows.md`); cópia fora do equipamento, retenção definitiva e teste periódico de recuperação continuam em aberto.
- **Critérios de conclusão:** operação real validada localmente e sem internet; acesso remoto restrito e validado; recuperação demonstrada segundo política aprovada; equipe preparada; estoque inicial individualizado; nenhuma pendência de segurança ou domínio que bloqueie produção.
