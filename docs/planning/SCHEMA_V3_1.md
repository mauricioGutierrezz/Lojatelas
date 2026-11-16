# Proposta técnica — Núcleo de Dados / schema v3.1

## Status, autoridade e autonomia técnica

Este documento é uma proposta técnica subordinada ao [ROADMAP](../../ROADMAP.md), ao [HANDOFF](../../HANDOFF.md) e ao [plano conceitual aprovado da Fase 0](FASE_0_NUCLEO_DE_DADOS.md). Não constitui autorização de implementação.

- ROADMAP governa fases e escopo.
- HANDOFF governa regras e invariantes de domínio.
- O plano da Fase 0 respeita ambos e está aprovado conceitualmente, sem autorização de implementação.
- Esta proposta define resultados e evidências verificáveis; não altera decisões nem impõe sequência de construção.

Requisitos aprovados permanecem obrigatórios. O Programador pode escolher mecanismos concretos, índices, sequences/UUIDs, organização interna das funções, implementação de constraints e detalhes equivalentes de PostgreSQL, sem aprovação individual dessas escolhas, desde que preserve comportamento, invariantes, limites de segurança e contratos aprovados e demonstre os critérios de aceite.

Uma escolha deixa de ser apenas técnica quando altera comportamento ou contrato de módulo, redefine um limite de segurança ou resolve questão aberta. Nesse caso, exige decisão explícita antes da implementação do comportamento afetado. Recomendação técnica, valor padrão, cardinalidade ou teste não pode decidir domínio implicitamente.

## Objetivo e limites do escopo

Sustentar o desenvolvimento local com um núcleo inicializável, íntegro e rastreável, corrigindo os problemas descritos pelo HANDOFF e preservando as entidades principais. Os dados anteriores fictícios não exigem migração; a futura base real não é descartável.

As adaptações do núcleo acompanham as entregas Ingreso / Stock, Corte / Ticket e Caja / Venta. A primeira depende dos critérios de ingresso, cadastro inicial, consulta e proteção dos dados que utiliza; não exige concluir os critérios de corte, venda ou fechamento nem desenvolver o Administrativo.

O escopo abrange integridade de produtos, ingressos, lotes, cortes, tickets, vendas e movimentações; garantias já decididas de fechamento; permissões e concorrência; distinção entre autoria informada e comprovada.

Não abrange interfaces operacionais, reforma geral da aplicação legada, qualquer uso de retalho ainda não definido em 1B, fluxo de tratamento de divergência física, políticas posteriores ao fechamento, relatórios gerenciais completos, alertas, implantação ou rede. Os comportamentos dependentes de decisões de 1A, 1B e 1C estão fora do escopo implementável desta proposta enquanto essas decisões permanecerem abertas.

A existência de uma dependência não impede trabalhar no restante já definido, mas impede apresentar o comportamento dependente como concluído. Também não autoriza criar um comportamento provisório de negócio para preencher a lacuna.

## Resultados obrigatórios e critérios verificáveis

### Inicialização, produtos e lotes

**Resultado obrigatório:** o schema aplica sem erro em PostgreSQL local limpo; cada unidade física tem identidade, produto, origem e quantidades próprias. Unidades e precisão decimal seguem o HANDOFF; largura não multiplica o estoque em metro linear. Identificadores não se repetem sob concorrência.

O padrão do produto é apenas sugestão. O agrupamento confirmado para 1A não elimina unidades físicas: um recebimento de 4 × 30 m + 1 × 45 m corresponde a cinco lotes identificáveis, quatro de 30 m e um de 45 m. Grupos de quantidades diferentes não podem ser confundidos. Isso não determina a representação interna de grupo ou item, nem antecipa sua interface.

**Evidências de aceite:** inicialização completa sem erro; recebimentos com quantidades próprias preservadas; individualização dos cinco rolos no exemplo; ausência de identificadores duplicados em operações concorrentes. Não é obrigatório um mecanismo específico de geração de código.

### Ingresso por confirmação operacional

**Resultado obrigatório:** atendente encontra ou cadastra produto com preço inicial, informa rolos, confere e confirma. A confirmação produz os lotes individuais e suas entradas rastreáveis, imediatamente disponíveis, sem aprovação administrativa. O exemplo 4 × 30 m + 1 × 45 m resulta em cinco lotes; repetição, falha e concorrência não podem duplicar estoque nem deixar efeitos parciais.

**Evidências de aceite:** cadastro de produto novo com preço inicial pela atendente; confirmação e disponibilidade sem administrador; cinco lotes com quantidades próprias e origem recuperável; repetição e concorrência sem duplicação; falha sem ingresso parcialmente efetivado. Alteração posterior do preço fora da área protegida por PIN é impedida. Não se exige teste de pendência/aprovação administrativa.

**Impacto na implementação atual:** ingressos e seus itens ainda estão vinculados a pendência/aprovação, e a operação que cria os lotes é restrita ao administrador. O operador também não dispõe de cadastro de produto. Esses contratos, permissões e testes precisam ser alinhados ao resultado vigente; simplesmente conceder acesso à antiga aprovação administrativa não representa a nova regra. O mecanismo equivalente cabe ao Programador, preservando integridade e rastreabilidade.

Registro de divergência posterior e eventual tratamento de saldo continuam abertos; não bloqueiam este fluxo e não autorizam correção silenciosa da declaração original. Auditoria avançada, relatórios, alertas e fluxo sofisticado de divergências não integram a primeira entrega.

### Corte, alocações e ticket

**Resultado obrigatório:** o corte só é realizado presencialmente após solicitação/confirmação do cliente. Ticket pode reunir vários itens; cada item pode consumir um ou mais lotes do produto correspondente. A soma das alocações corresponde à quantidade do item. A retirada baixa o estoque uma única vez, congela o preço e preserva a explicação da movimentação. Não há consumo acima do saldo nem escrita parcial após falha.

**Evidências de aceite:** corte de um lote e corte multilote; soma exata das alocações; rejeição de consumo acima do saldo e de associação a produto incompatível; saldo e histórico coerentes; preço congelado; reversão integral dos efeitos de operação que falha.

Formato JSON, representação de alocações e contrato de erros não são impostos. Alocações devem explicar o consumo de estoque; não originam automaticamente retalhos. O mecanismo de registro da solicitação/confirmação presencial não é fixado por esta proposta.

### Limite de domínio após o corte

Não existe cancelamento operacional de corte. Depois do corte confirmado presencialmente, o sistema não oferece fluxo de cancelamento que recomponha, reclassifique ou devolva esse material. A retirada, seu preço congelado e sua rastreabilidade permanecem registrados.

Não integra a proposta uma operação de cancelamento, geração de retalho por esse motivo, estado de cancelamento associado a esse fluxo, movimentação específica ou vínculo de origem exclusivo para suportá-lo. Referências e contratos do código legado não autorizam manter esse comportamento.

O conceito geral de retalho permanece, mas qualquer uso por outra razão, sua origem, estado e tratamento ficam para definição posterior em 1B. Esta proposta não decide correspondência entre alocação e peça física de retalho nem exige sua implementação. A antiga pendência de geração de retalhos por cancelamento deixa de existir, pois sua operação de origem foi retirada do domínio.

Tratamento excepcional de ticket já cortado que não seja pago permanece aberto em 1C. Não se presume devolução, reclassificação, perda, ajuste, novo estado ou solução financeira para esse caso.

### Pagamento e venda

**Resultado obrigatório:** banco calcula o valor da venda pela soma dos itens; preço permanece o congelado no corte. Ticket vazio não pode ser pago. Finalização válida altera o estado para pago sem nova baixa ou movimentação física. Repetição não gera pagamento duplicado nem permite encerramentos incompatíveis.

**Evidências de aceite:** soma de múltiplos itens calculada no banco; alteração posterior de preço sem efeito no ticket; rejeição de ticket vazio ou encerrado; ausência de alteração do estoque no pagamento; atomicidade da operação.

Valor arbitrário informado pelo cliente não pode ser fonte da verdade. A assinatura técnica e o retorno podem ser escolhidos dentro desse contrato. A prevenção de pagamento duplicado não fixa, por si só, uma cardinalidade física de registros financeiros que antecipe contratos de 1C.

### Livro-razão e reconciliação

**Resultado obrigatório:** toda alteração física relevante é explicável pelas movimentações; seus efeitos de entrada e saída são inequívocos. Saldo registrado corresponde ao saldo reconstruído. Corte permanece registrado como retirada física, sem ser confundido com venda. O livro-razão não oferece meio de recompor material fisicamente cortado.

**Evidências de aceite:** reconciliação sem diferença nos cenários aprovados; histórico do lote preserva entrada e corte; consultas de auditoria distinguem movimento físico de resultado comercial.

Os tipos recomendados pelo HANDOFF podem ser utilizados ou representados de maneira equivalente. Nomes exatos, convenção de sinal e forma da consulta de reconciliação são escolhas técnicas, desde que o efeito físico permaneça inequívoco. Representar ajustes positivos e negativos não autoriza executar uma política de correção de estoque ainda não decidida.

Não integra este escopo um fluxo administrativo de ajustes/perdas para tratar divergências. A regra anterior que permitia ajuste de entrada até a quantidade inicial foi retirada: recompor o saldo reduzido pelo corte viola a invariante, mesmo com movimentação registrada. Nenhuma limitação ao máximo inicial substitui a proibição de recompor material cortado. Documentação de divergência e eventual tratamento do saldo pertencem a 1A.

### Garantias do fechamento

**Resultado obrigatório:** existe caixa único com fechamento diário pelo calendário operacional de Córdoba, Argentina. O banco calcula valores esperados; o operador não fornece totais arbitrários como verdade. Quando houver contagem, o sistema calcula a divergência. Esses requisitos não autorizam definir o comportamento posterior ao fechamento.

**Evidências de aceite do que já está decidido:** impossibilidade de o operador inserir livremente totais esperados; cálculo derivado dos registros, sem duplicação artificial de valores; referência temporal compatível com Córdoba. Cálculos de contagem e divergência só podem ser declarados operacionalmente validados no significado já aprovado para suas grandezas; esta proposta não inventa esse significado.

Ficam fora do recorte implementável os comportamentos dependentes de 1C: composição da contagem e eventual restrição da divergência a dinheiro; tratamento após fechamento; repetição, revisão ou reabertura; tickets pendentes entre datas; tratamento excepcional de ticket cortado que não seja pago. Não são critérios atuais rejeitar sempre o segundo fechamento ou tornar a data imutável. A implementação integral do fechamento permanece condicionada aos contratos de 1C, sem retirar a obrigação de o banco calcular os valores.

### Permissões, segurança e autoria

**Resultado obrigatório:** operador pode cadastrar produto com preço inicial e confirmar ingresso; não altera diretamente saldo nem preço de produto existente, não insere livremente movimentos ou totais de fechamento e não acessa hashes. Operações sensíveis têm concessões explícitas, acesso público revogado conforme o HANDOFF, resolução segura de objetos e ownership revisado. Credenciais e segredos não são expostos.

Autorização administrativa não depende apenas de identificador enviado pelo cliente. Validar existência, atividade ou perfil desse identificador não comprova identidade nem autoria.

**Evidências de aceite:** tentativas do operador de realizar ações proibidas falham; hashes não são acessíveis pelos caminhos expostos; operações sensíveis não ficam executáveis por acesso público indevido; resolução de objetos não permite desvio das operações privilegiadas; fornecer ID de administrador não concede ao operador alteração posterior de preço ou outras ações administrativas. Permitir preço inicial não autoriza atualização de preço existente fora do fluxo protegido por PIN. Os acessos efetivos devem ser demonstrados, não inferidos da ausência de concessão no texto.

**Desenvolvimento local:** pode conservar autoria informada como limitação explicitamente documentada, com permissões efetivas e sem elevar privilégios por ID do cliente. Isso não equivale a autoria comprovada.

**Referência subordinada de acesso:** manter o alinhamento desta proposta ao [HANDOFF, seção 8](../../HANDOFF.md#8-segurança) e aos planos vigentes: sessão operacional compartilhada; Cierre, correção do Fondo inicial e a nova área protegida de preços exigem o mesmo PIN geral. Autorização limitada à permanência no fluxo protegido, sem repetição entre etapas; saída encerra a autorização e novo acesso exige PIN. Verificação no servidor, sem armazenamento em texto puro; valor real configurado fora do repositório e nunca registrado em documentação versionada ou código. Preservar responsáveis existentes sem comprovar autoria individual. Gestão/troca amigável e controle granular pertencem ao Administrativo futuro; não criar usuários individuais ou sessão administrativa nesta etapa.

Este alinhamento deve permanecer para evitar que a proposta repita a exigência superada de autoria forte na operação normal. Sua fonte são as decisões aprovadas registradas no HANDOFF, não esta proposta. SCHEMA_V3_1 continua não aprovada, não é autoridade de domínio nem autorização de implementação, e não determina persistência do PIN no banco ou qualquer novo schema.

### Concorrência e integridade transacional

**Resultado obrigatório:** cortes concorrentes não consomem saldo inexistente; pagamento e inclusão de item não produzem estados incompatíveis; pagamentos concorrentes não duplicam a venda; confirmação concorrente não duplica ingresso físico; códigos não colidem; falha não deixa efeitos parciais.

O bloqueio do ticket antes de validar e mudar estado em corte e pagamento permanece exigência expressa do HANDOFF. As demais escolhas de bloqueio e coordenação devem preservar as garantias aprovadas, sem fixar políticas de outros módulos.

**Evidências de aceite:** concorrência efetiva no mesmo lote e ticket, confirmação concorrente e geração concorrente de identificadores; verificação do resultado e dos saldos após as operações; reversão de efeitos parciais em falhas. Cenários que dependam de contratos ainda abertos permanecem identificados como pendentes. Testes sequenciais isolados não demonstram concorrência.

## Liberdade de implementação

São escolhas do Programador, dentro dos limites acima:

- geração concorrente segura de identificadores por mecanismo apropriado;
- índices e organização interna dos objetos e funções;
- implementação das invariantes por constraints e outros mecanismos equivalentes;
- forma de representar a origem dos ingressos e das retiradas e de consultar a reconciliação;
- convenção inequívoca de sinais e tipos de movimentação;
- estratégia de aquisição de bloqueios compatível com as exigências expressas do HANDOFF;
- meios de restringir acesso a dados sensíveis e de configurar ownership e privilégios;
- ferramentas e organização dos testes e das evidências.

Não há obrigação de usar uma sequence específica, índices específicos, um trigger diferido, uma view específica ou uma ordem global de construção. As escolhas precisam ser justificáveis pelos critérios de aceite, não aprovadas individualmente por serem técnicas.

Essa liberdade não abrange uso, origem ou tratamento de retalho, correção de divergências, composição de contagem, pós-fechamento, tratamento excepcional de ticket cortado não pago, limites de confiança da identidade ou permissões de negócio não aprovadas. Também não autoriza defaults, constraints ou formatos que decidam esses assuntos implicitamente.

## Questões pendentes e limites para autorização

| Âmbito responsável | Questão pendente | Limite desta proposta |
|---|---|---|
| Administrativo futuro | Controle granular e eventual autoria individual | Não bloquear operação normal por autoria forte; aplicar sessão compartilhada e PIN geral no Cierre/correção de fundo conforme HANDOFF. |
| 1A, definição posterior | Documentação de divergência física e eventual tratamento do saldo | Fora do aceite da primeira entrega; preservar o dado original, sem correção automática ou silenciosa. |
| 1B | Qualquer uso de retalho por outra razão, sua origem, estado e tratamento | Não gerar retalho automaticamente nem definir correspondência com alocações, cardinalidade, prioridade ou defaults. |
| 1C | Composição da contagem e alcance da divergência financeira | Não fixar contagem de registros como total de itens nem restringir automaticamente a dinheiro. |
| 1C | Comportamento depois do fechamento e tickets entre datas | Não impor imutabilidade, rejeição de novo fechamento ou reabertura. |
| 1C | Tratamento excepcional de ticket já cortado que não seja pago | Não presumir destinação do material, novo estado ou solução financeira; não reintroduzir cancelamento operacional. |

As pendências dos outros módulos não são transferidas para a Fase 0. Permanecem aqui somente para delimitar o que esta proposta não autoriza decidir ou implementar.

## Aceite e evidências da entrega

Os resultados aprovados continuam obrigatórios. A verificação deve apontar sua origem no HANDOFF e no plano da Fase 0, o cenário executado, o resultado e eventuais limitações. Não é exigido testar ou aprovar uma solução técnica específica que tenha sido substituída por equivalente.

Os casos vigentes da seção de testes do HANDOFF são a referência de cobertura: inicialização e ingresso; corte simples e multilote; proteção de saldo; pagamento; preservação da retirada; auditoria e reconciliação; permissões; fechamento; concorrência e identificadores. Não há dispensa de requisito aprovado. Para casos cuja execução integral dependa de decisão aberta, o relatório deve separar a invariante já verificada do comportamento operacional ainda pendente. Uma pendência não conta como teste aprovado.

Não se exigem como condição do recorte local testes de decisões ainda abertas: uso de retalho, sua origem, estado ou prioridade, correção de divergência física, divergência financeira exclusivamente em dinheiro, rejeição de segundo fechamento, reabertura, tratamento excepcional de ticket cortado não pago ou identidade definitiva.

Testes de implementação podem verificar detalhes escolhidos pelo Programador, mas não promovem tais detalhes a novas regras de negócio. Cenários de teste não podem ser usados como defaults operacionais.

A entrega deve informar arquivos alterados, resumo das mudanças, escolhas técnicas relevantes, testes executados, resultados e verificações pendentes. Aceite do recorte local não significa conclusão integral de todos os comportamentos do núcleo nem prontidão para produção.

**Situação para autorização:** proposta alinhada ao recorte da primeira entrega Ingreso / Stock; suas adaptações de núcleo podem ser objeto de autorização delimitada própria. Uso real depende da validação do acesso compartilhado aprovado, incluindo PIN geral nas operações sensíveis e demais garantias de segurança; não exige autoria individual forte nem a construção do Administrativo. Não está pronta para autorização integral dos comportamentos dependentes nem para produção. A revisão deste documento não concede autorização de implementação.

**Extensão posterior aprovada no HANDOFF:** a área protegida de preços usa o PIN geral para alterações coletivas atômicas com histórico; cadastro operacional não concede edição irrestrita de preços existentes. Foto principal por produto e preferência por estrutura separada constam em [PRECIOS_FOTOS_PRODUCTO.md](PRECIOS_FOTOS_PRODUCTO.md). Esta proposta técnica continua não aprovada e não escolhe representação de fotos, histórico ou mecanismo de armazenamento.
