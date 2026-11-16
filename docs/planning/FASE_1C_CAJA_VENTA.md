# Fase 1C — Caja / Venta — plano da entrega

## Objetivo

Entregar o recebimento dos tickets já cortados, em uma interface es-AR simples, rápida e fácil de usar. O [ROADMAP](../../ROADMAP.md) governa fases e escopo; o [HANDOFF](../../HANDOFF.md) governa domínio; este plano registra também as decisões posteriores explicitamente aprovadas pelo responsável na conversa. Não autoriza implementação.

Conteo / Fechamento permanece na Fase 1C como etapa posterior a Caja / Venta. A primeira entrega foca no recebimento do ticket; depois dela haverá o fluxo de fechamento do dia. As regras de Consulta de Caja e Cierre abaixo foram aprovadas; substituem propostas anteriores de múltiplas conferências formais e de vendas após fechamento confirmado.

## Responsabilidades

- Na primeira entrega, localizar o ticket pelo mesmo código gerado em Corte / Ticket, conferir seus vários itens e registrar o recebimento integral com composição entre Efectivo e Otro. Na UX aprovada, a atendente informa Efectivo entregado ou usa Todo en Otro / Todo en efectivo; o sistema calcula a composição persistida e o Vuelto visual, conforme a seção de UX abaixo.
- Apresentar quantidades vendidas, preços congelados, subtotais e total, distinguindo a quantidade cortada preservada para rastreabilidade física.
- Permitir consultar o resultado do recebimento, mantendo seu vínculo com ticket, itens e responsável informado.
- Preservar timestamps dos eventos relevantes: criação do ticket, registro de cada corte e conclusão da venda/pagamento. Esses horários devem permanecer disponíveis para análises futuras, sem implementar relatórios, métricas ou dashboards nesta entrega.
- Na etapa posterior da mesma fase, entregar Consulta de Caja informativa e Cierre del día conforme as regras aprovadas abaixo. Total vendido, efectivo recebido em vendas e Otro devem ser derivados automaticamente dos recebimentos registrados, nunca digitados manualmente.

Fluxo operacional aprovado para o recebimento: localizar código → conferir itens e total → informar Efectivo entregado ou escolher Todo en Otro / Todo en efectivo → conferir Total, Efectivo, Otro e Vuelto na mesma tela → confirmar explicitamente o cobro completo → consultar venda concluída. Não há página intermediária de composição, digitação de total ou de Otro, pagamento parcial ou descontos. Vuelto é apenas auxílio visual transitório.

## Regras/invariantes já decididas

- Existe um único caixa na loja. Interface visível em es-AR; UX simples, rápida e fácil de usar.
- Qualquer funcionário autorizado à operação pode receber.
- Confirmar recebimento significa quitação integral. Não implementar pagamento parcial nem descontos nesta entrega.
- **Composição aprovada do recebimento:** a interface calcula a parcela aplicada em efectivo a partir de Efectivo entregado ou dos atalhos aprovados. O banco calcula o total a partir do ticket e calcula `Otro = total da venda − efectivo`. Total e Otro não são digitados manualmente. Esta decisão substitui o recorte anterior sem registro de composição e o adiamento de pagamento misto entre Efectivo e Otro.
- Suportar venda totalmente em efectivo, totalmente em Otro ou mista entre ambos, sempre com quitação integral. Não detalhar modalidades dentro de Otro por hipótese.
- Efectivo representa a parcela da venda paga em dinheiro, não necessariamente o montante físico entregue pelo cliente. Efectivo entregado e Vuelto são dados transitórios de interface, não persistidos; não modificam o significado da composição financeira.
- Detalhamento futuro de modalidades permanece fora do escopo. O auxílio visual de Vuelto está aprovado somente nos limites da seção de UX abaixo.
- Ticket pode conter vários itens. Quantidade vendida e quantidade cortada são distintas; cobrança usa quantidade vendida × preço unitário congelado.
- Total da venda é calculado pelo banco a partir dos itens, não fornecido arbitrariamente pela interface. Ticket vazio não pode ser pago.
- Estoque já foi baixado no corte pela quantidade cortada. Pagamento não baixa estoque novamente nem modifica as retiradas registradas.
- Não existe cancelamento operacional de corte.
- Recebimento deve preservar rastreabilidade e impedir pagamentos duplicados e operações concorrentes incompatíveis, conforme o HANDOFF.
- Os horários de criação do ticket, registro dos cortes e conclusão da venda/pagamento permanecem preservados e disponíveis para análises futuras. A conclusão da venda não substitui os horários anteriores.
- Fechamento diário pertence à etapa posterior da 1C, pelo calendário operacional de Córdoba, Argentina. Valores esperados são calculados pelo banco; quando houver contagem física, o operador informa o contado e o sistema calcula a divergência. A composição da contagem e o pós-fechamento seguem as decisões consolidadas abaixo.
- No fechamento, o banco deriva total vendido, efectivo recebido em vendas e Otro dos recebimentos abrangidos. Esses totais não são digitados manualmente. Efectivo recebido em vendas não define, por si só, todo o dinheiro físico esperado na gaveta nem a interpretação de uma divergência.
- Não são incluídos agora relatórios, dashboards, métricas ou regras administrativas.

## Dependências

- Núcleo da Fase 0 e tickets persistidos pela 1B, com quantidades vendida e cortada distintas, preços congelados, códigos e registros de cortes preservados; lotes e origem provenientes da 1A.
- Preservar os contratos e validações já implementados do recebimento Efectivo/Otro, da quitação integral e da autorização de qualquer funcionário autorizado à operação. Consulta de Caja e Cierre del día também já foram implementados, testados e commitados em `ee40893`.
- Garantias de integridade, permissões, persistência e concorrência pertinentes ao recebimento.
- Para uso real, validar o acesso vigente do HANDOFF: sessão compartilhada na operação normal e PIN geral no Cierre e na correção do fundo. Não exigir autoria individual forte; preservar responsáveis registrados sem tratá-los como prova de identidade.
- Para a revisão UX, preservar as garantias de Conteo / Cierre já implementadas e testadas em `ee40893`; os critérios específicos abaixo permanecem como referência de regressão, não como trabalho de adaptação pendente.

## Questões abertas

**Composição do recebimento decidida:** quitação integral em Efectivo, Otro ou combinação de ambos, com Efectivo entregado ou atalhos informados na interface e composição calculada. Qualquer funcionário autorizado à operação pode receber; pagamento parcial e descontos não integram este recorte; Vuelto integra apenas a interface, sem persistência. Essas definições não permanecem como alternativas a escolher; as regras de fechamento também estão aprovadas no recorte consolidado abaixo.

**Pendências preservadas, sem bloquear a primeira entrega local do fluxo normal de recebimento integral:**

- Controle granular e autoria individual ficam para definição futura do Administrativo; não condicionam a operação normal. Sessão e PIN compartilhados não comprovam autoria individual.
- Extensões futuras: detalhamento de modalidades além da composição Efectivo/Otro. Efectivo entregado e Vuelto transitórios já estão aprovados na seção de UX e não são questões abertas. Pagamento misto entre Efectivo e Otro já está aprovado e não permanece como questão aberta.
- 1C: tratamento excepcional de ticket cortado e não pago, sem presumir destinação do material, novo estado ou solução financeira. Essa pendência não bloqueia o fluxo normal de recebimento integral.
- Conteo / Cierre: nenhuma decisão de negócio bloqueante no recorte aprovado. Contagem obrigatória e restrição de permissões pela Administração ficam para definição futura. Não implementar reabertura, múltiplos fechamentos, movimentos extraordinários, detalhamento de Otro ou redesign visual. O Vuelto aprovado pertence exclusivamente à interface de Caja / Venta.
- Retalho e regras administrativas permanecem fora deste recorte e não são definidos por este plano.

## Critérios de conclusão

- Localizar pelo código existente um ticket da 1B e apresentar todos os itens, quantidades vendidas, preços congelados, subtotais e total corretamente, distinguindo a quantidade cortada.
- Demonstrar cobrança correta quando as quantidades vendida e cortada diferirem e preservação do preço congelado após alteração do preço atual do produto.
- Qualquer funcionário autorizado à operação consegue confirmar a quitação integral informando Efectivo entregado ou usando os atalhos aprovados; total vem do ticket e Otro é calculado pelo banco. Demonstrar vendas totalmente em efectivo, totalmente em Otro e mistas entre ambos. Ticket vazio não pode ser pago; não são oferecidos pagamento parcial ou descontos; Vuelto é apenas visual.
- Demonstrar que efectivo corresponde à parcela da venda, sem confundi-lo com dinheiro entregue pelo cliente. Efectivo entregado e Vuelto permanecem separados dos valores persistidos e não alteram fechamento ou auditoria financeira.
- Demonstrar que pagamento não altera saldo ou movimentação física e que reenvios, falhas e concorrência não duplicam vendas nem deixam efeitos parciais.
- Garantir coerência entre o conteúdo conferido e o recebimento confirmado diante de alterações concorrentes do ticket, sem concluir silenciosamente a cobrança de um total diferente.
- Recuperar a venda após nova sessão, preservando vínculo com ticket, dados do recebimento e responsável informado.
- Verificar que horários de criação do ticket, registro de cada corte e conclusão da venda/pagamento continuam registrados e recuperáveis, sem substituição dos eventos anteriores e sem exigir relatórios ou métricas.
- Permitir realizar o fluxo em es-AR, localmente e sem comandos técnicos.
- No aceite da etapa de fechamento, demonstrar que total vendido, efectivo recebido em vendas e Otro são derivados dos recebimentos registrados, sem entrada manual desses totais. Validar a contagem opcional e a diferença matemática conforme o recorte aprovado.
- Aceite da primeira entrega cobre recebimento, não conclusão integral da 1C. A etapa de fechamento tem os critérios específicos abaixo; comportamentos futuros não são declarados concluídos.
- Distinguir validação local de liberação para uso real; demonstrar acesso compartilhado e proteção das operações sensíveis por PIN geral, mantendo explícita a ausência de autoria individual comprovada.

## Conteo / Cierre — consolidação final aprovada

### Fluxo de Consulta de Caja

Abrir Consulta de Caja → visualizar a data operacional de Córdoba e os valores atuais derivados dos recebimentos → atualizar ou sair. A consulta está disponível a qualquer momento, inclusive após Cierre, e não cria registro de fechamento, não representa conferência formal e não bloqueia vendas. Fundo ainda não informado deve ser distinguido de fundo zero; não presumir o valor ausente.

### Fluxo de Cierre del día

Abrir Cierre para a data operacional → definir/conferir o fundo inicial → revisar os totais calculados → opcionalmente informar efectivo contado, incluindo o fundo → revisar a diferença, quando houver contagem → confirmar o encerramento definitivo → consultar o registro preservado.

Até a confirmação, vendas continuam normalmente. Se o movimento ou o fundo conferido mudar, atualizar os valores e exigir nova revisão antes de confirmar; a contagem anteriormente informada não pode ser considerada atual silenciosamente. Depois da confirmação, impedir novos recebimentos da mesma data operacional. Não reabrir nem gerar segundo fechamento; nova tentativa não pode duplicar o Cierre. Consultas continuam disponíveis.

### Valores e invariantes

| Valor | Definição |
|---|---|
| Total vendido | Soma das vendas recebidas na data operacional. |
| Efectivo recibido por ventas | Soma das parcelas efectivo desses recebimentos. |
| Otro | Soma das parcelas Otro desses recebimentos. |
| Fondo inicial | Um valor de referência por dia, sem transporte automático do dia anterior. |
| Efectivo según fondo y ventas | Fondo inicial + Efectivo recibido por ventas. |
| Efectivo contado | Opcional; dinheiro fisicamente presente na gaveta, incluindo o fundo. |
| Diferencia | Contado − Efectivo según fondo y ventas, somente se houver contagem. |

- Total vendido = Efectivo recibido por ventas + Otro. Totais e diferença são calculados pelo banco, nunca digitados manualmente.
- Fundo pode ser informado no início do dia; sua ausência não bloqueia vendas, mas impede confirmar Cierre. Correções preservam histórico, responsável e horário. O valor usado por um Cierre confirmado permanece preservado mesmo se houver correção posterior do fundo.
- Sem movimentos extraordinários registrados, não usar “efectivo teórico en caja”. A diferença é apenas matemática, sem atribuição automática de falta, sobra, perda ou erro e sem ajuste de estoque ou vendas.
- Quando houver contagem física, registrar Efectivo contado e calcular e registrar Diferencia. Permitir concluir o Cierre mesmo quando a diferença for diferente de zero, sem exigir motivo, justificativa ou observação textual. A diferença é apenas um dado numérico auditável do fechamento.
- Ausência de contagem não significa zero; diferença fica ausente quando não houve contagem.
- Há um único Cierre formal, definitivo por data de Córdoba. Recebimentos e encerramento concorrentes devem respeitar esse limite: venda concluída antes do encerramento precisa estar abrangida e revisada; não pode haver novo recebimento da data já encerrada.
- O Cierre del día pode ser confirmado normalmente mesmo quando não houve vendas na data operacional. Zero vendas não é erro nem condição excepcional. As demais exigências do Cierre continuam valendo, inclusive Fondo inicial obrigatório antes da confirmação.
- O acesso ao Cierre exige PIN geral compartilhado; correção do Fondo inicial exige o mesmo PIN. Contagem obrigatória e controle granular por funcionário são extensões administrativas futuras.
- Pendentes atravessam dias sem cancelamento automático; entram no movimento da data em que forem recebidos. Não alterar datas para contornar um Cierre.
- Preservar horários de ticket, cortes e venda, além de horário e responsável informado pelo Cierre e histórico de correções do fundo.

### Critérios objetivos de conclusão de Conteo / Cierre

- Consulta exibe valores atuais sem criar fechamento ou impedir recebimentos.
- Totais conferem com as vendas da data de recebimento em Córdoba, inclusive tickets criados em dias anteriores e vendas Efectivo, Otro ou mistas.
- Vendas funcionam sem fundo definido; Cierre exige fundo. Não transportar fundo automaticamente. Correção registra histórico e não modifica Cierre anterior.
- Contagem opcional distingue ausência de zero, inclui fundo e registra o contado e a diferença calculada, sem classificação automática. Demonstrar conclusão do Cierre com diferença positiva, negativa ou zero, sem exigir motivo, justificativa ou observação textual, preservando esses dados numéricos para auditoria.
- Uma mudança do movimento ou fundo desde a abertura da conferência impede confirmação desatualizada, inclusive quando totais monetários coincidirem; exige revisão.
- Confirmação produz exatamente um Cierre por data, preservando os valores conferidos, horário e responsável; reenvio e confirmação concorrente não duplicam registros.
- Vendas seguem durante a preparação. Corrida entre recebimento e Cierre não perde venda nem permite recebimento posterior daquela data encerrada. Recebimentos em nova data seguem a regra dessa nova data.
- Registro confirmado permanece consultável e inalterado; não há reabertura ou segundo fechamento.
- Não implementar movimentos extraordinários, detalhamento de Otro, relatórios, dashboards ou redesign visual. Não persistir Vuelto nem incluí-lo nos cálculos do Cierre. Interface es-AR simples, rápida e fácil de usar.

### Compatibilidade e prontidão

Consulta de Caja e Cierre del día foram concluídos, testados e commitados em `ee40893`, conforme as decisões aprovadas. O recorte funcional de Conteo / Cierre não tem adaptação pendente neste planejamento.

A implementação já garante Cierre único por data, bloqueio de novos recebimentos após Cierre, diferença calculada contra fundo mais efectivo recebido em vendas, fundo inicial com histórico e revisão quando o movimento muda. Esses comportamentos e seus testes devem ser preservados.

O trabalho pendente desta atualização é somente a revisão UX documentada abaixo: Efectivo entregado, Todo en efectivo / Todo en Otro, Vuelto transitório, composição na mesma tela, remoção da página intermediária e limpeza textual aprovada. Esta documentação não autoriza implementação. O acesso operacional passa a seguir a decisão de sessão compartilhada e PIN geral descrita abaixo; autoria individual forte não condiciona a operação normal.

## UX de Caja / Venta e limpeza textual — decisões aprovadas em 2026-10-06

Esta seção documenta aprovação de UX, sem autorização de implementação. Substitui a entrada direta da parcela Efectivo pela interação abaixo; preserva regras de domínio e contratos financeiros persistidos. Não requer schema novo nem alteração de HANDOFF ou ROADMAP.

### Entrada e cálculos na mesma tela

- Campo em es-AR: **Efectivo entregado**. Representa o dinheiro físico entregue pelo cliente e é transitório: não deve ser persistido.
- Total continua calculado pelo banco a partir do ticket. A atendente não digita Total, Efectivo aplicado, Otro ou Vuelto.
- Para D = efectivo entregado e T = total da venda:

| Condição | Efectivo aplicado | Otro | Vuelto |
|---|---|---|---|
| D < T | D | T − D | 0 |
| D = T | T | 0 | 0 |
| D > T | T | 0 | D − T |
| Ação Todo en Otro | 0 | T | 0 |
| Ação Todo en efectivo | T | 0 | 0 |

- Campo vazio não equivale a zero: significa que a forma de pagamento ainda não foi informada. Os atalhos são escolhas explícitas e não confirmam o recebimento automaticamente.
- Mostrar Total, Efectivo, Otro e Vuelto imediatamente na própria tela, antes da confirmação. Remover a página intermediária separada de composição e o passo de navegação usado somente para essa revisão.
- Manter confirmação explícita do recebimento integral: checkbox **Cobro completo recibido** e ação **Confirmar cobro**. Outro calculado não comprova que essa parcela foi recebida.
- Vuelto é somente um número visual/transitório para auxiliar a devolução do troco. Não é persistido, não gera movimento financeiro, não altera venda, fechamento ou auditoria e não exige recuperação na consulta posterior da venda.
- Preservar os significados persistidos: `valor_efectivo` é a parcela efetivamente paga em dinheiro; `valor_otro` é o restante pago por Otro; `Total = valor_efectivo + valor_otro`. Nunca enviar dinheiro entregue excedente como Efectivo aplicado.

### Validação e segurança da interação

- Erros de entrada aparecem junto ao campo na mesma tela, preservando a entrada para correção. D maior que T não é erro: gera Vuelto.
- Campo inválido ou incompleto não deve deixar uma composição antiga aparentando corresponder à nova entrada. Preservar precisão monetária e formatação es-AR, sem arredondamento silencioso.
- Cálculo imediato na interface não substitui validação no servidor nem o total autoritativo do banco. Preservar conferência do ticket, quitação integral, bloqueio por Cierre, permissões, transação e proteção contra duplicidade.
- Ticket alterado ou estado concorrente exige nova revisão; não recalcular e confirmar silenciosamente com outros dados. Alteração da entrada exige reconfirmação da composição.
- Preservar consulta/reenvio do mesmo registro quando a confirmação falhar ou sua resposta se perder; não orientar novo recebimento do dinheiro.
- Nenhum schema novo, campo persistido novo ou contrato financeiro persistido novo. Apenas interação e preparação da confirmação na aplicação são adaptadas.

### Limpeza textual aprovada nas telas operacionais

Aplicar a limpeza conservadora da revisão de UX: retirar explicações rotineiras, treinamento permanente, detalhes internos de banco/reserva/persistência e repetições já evidentes nos campos, títulos ou botões. Preservar dados necessários à decisão, distinções de domínio, avisos condicionais de erro, estados excepcionais e confirmações explícitas de ações irreversíveis. Não remover regras ou validações junto com seus textos explicativos.

| Tela/fluxo | Limpeza aprovada |
|---|---|
| Stock | Remover “Encontrá el producto para cargar los rollos que llegaron.”; manter Stock total, Mayor rollo disponible e estados condicionais. |
| Cadastro de produto | Remover “Cargá los datos y el precio inicial.” e “Podés recibir rollos de otro tamaño.”; encurtar a restrição do preço para “Cambios posteriores: área protegida de precios.” |
| Ingreso | Remover explicação repetida de unidade/agrupamento e exemplo permanente de dois grupos; manter categoria, unidades nos campos e ações existentes. Usar “Paso 2 de 2” sem repetir revisão/confirmação. Remover “Cada rollo queda identificado y disponible en stock.”; apresentar “Ingreso confirmado” sem duplicar o estado no subtítulo. |
| Seleção de corte | Remover instruções rotineiras de iniciar/continuar ticket, adicionar corte e explicação do algoritmo de sugestão. Usar “Cantidad vendida (…)” e “Cantidad cortada (…)”, preservando campos separados. Remover o parágrafo permanente sobre trecho contínuo/baixa; preservar os valores distintos e o aviso condicional “Ningún rollo alcanza. Distribuí solo si el pedido admite varios tramos.” |
| Confirmação de corte | Remover os parágrafos “Realizá el corte presencialmente…” e “El precio se fija al registrar…”. Preservar checkbox obrigatório com “Corte realizado” e botão “Registrar corte”. A regra de solicitação/confirmação presencial do cliente permanece inalterada. |
| Ticket | Remover o lembrete permanente de baixa de estoque e conservação do código; encurtar estado vazio para “Sin cortes registrados.” Preservar código, estado, quantidades, diferença, preços, lotes, responsáveis e horários. |
| Caja / Venta | Remover explicação permanente de busca e de baixa de estoque. Substituir texto do antigo Efectivo por Efectivo entregado; remover orientação de digitar zero para Otro e explicações redundantes da composição. Usar “Pagado” sem repetir “Recepción integral registrada”. |
| Consulta de Caja | Remover “Solo consulta: no cierra el día ni bloquea ventas.”; encurtar identificação para “Fecha operativa: …”, preservando o calendário de Córdoba. Em dia fechado, manter “No se pueden recibir pagos.” |
| Fondo inicial | Usar rótulo “Fondo inicial”. Remover ajuda rotineira sobre histórico; depois de Cierre, manter o aviso contextual “Esta corrección no modifica el Cierre.” Quando faltar fundo, usar “Falta informar el fondo inicial.” |
| Contagem/Cierre | Usar “Efectivo contado, incluido el fondo (opcional)” e “Vacío si no contaste”. Manter confirmação explícita: “Cerrar definitivamente: no se podrán recibir más pagos en esta fecha.” No registro confirmado, encurtar “Definitivo · Sin reapertura” para “Sin reapertura”. Preservar nomes dos valores e “Sin conteo”. |
| Acesso e erros | Remover slogan do login. Preservar mensagens condicionais específicas. Encurtar aviso de falha de corte para “Consultá el ticket o reintentá el mismo registro. No vuelvas a cortar.” Manter aviso para não receber o importe novamente após falha de confirmação. |

### Critérios de aceite da revisão de UX

- Demonstrar, para Total 25.501,50: D=10.000 produz Efectivo 10.000, Otro 15.501,50, Vuelto 0; D=25.501,50 produz Efectivo igual ao total e demais valores zero; D=30.000 produz Efectivo 25.501,50, Otro 0 e Vuelto 4.498,50.
- Demonstrar ambos os atalhos e distinguir campo vazio de zero, sem confirmação automática.
- Conferir composição e confirmar cobro completo na mesma tela, sem página intermediária; entrada inválida permanece corrigível nessa tela.
- Comprovar que somente composição financeira aprovada é persistida; Efectivo entregado e Vuelto não são persistidos nem alteram os cálculos do Cierre ou auditoria financeira.
- Preservar rejeição de ticket vazio, revisão de ticket alterado, bloqueio após Cierre, proteção de reenvio e concorrência, preço congelado, quantidades e ausência de nova baixa de estoque.
- Limpeza textual não remove dados decisórios, mensagens excepcionais ou confirmações explícitas e não introduz redesign visual ou outras funcionalidades.

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
