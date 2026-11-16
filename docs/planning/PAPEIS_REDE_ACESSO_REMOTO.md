# Plano — papéis, vários computadores e acesso remoto

Status: **plano proposto**, com as decisões abaixo confirmadas pelo responsável
em 2026-11-15. Não autoriza implementação por si só; cada entrega começa após
o "pode fazer" do responsável. Quando a Entrega A for implementada, HANDOFF e
ROADMAP devem ser atualizados no mesmo trabalho (ver "Documentos a atualizar").

## Decisões confirmadas (2026-11-15)

1. **Três contas fixas, uma por papel**: `administrador`, `empleado`, `cajero`,
   cada uma com senha própria definida na instalação. Contas compartilhadas:
   não identificam qual pessoa fez cada operação.
2. **Cierre del día e Fondo inicial**: Cajero e Administrador.
3. **PIN geral removido**: o papel passa a ser a única barreira de Precios,
   Cierre e Fondo.
4. **Base atual só tem dados de teste**: pode ser recriada do zero (com backup
   antes). Não é necessária migração preservadora nesta entrega.
5. **Hadoop descartado**: não é exigência externa e não atende ao acesso de
   casa. Relatórios futuros leem o próprio PostgreSQL.
6. **Administrador em casa**: precisa operar a loja (inclusive ingressar
   estoque) e consultar números. Solução: VPN até o servidor da loja.

## Quem vê o quê

| Área | Administrador | Empleado | Cajero |
| --- | :---: | :---: | :---: |
| Productos / Stock (consulta, cadastro, ingresso, foto) | sim | sim | não |
| Corte / Ticket (inclui busca de produto dentro do ticket) | sim | sim | sim |
| Caja / Venta (cobrar ticket) | sim | não | sim |
| Consulta de Caja | sim | não | sim |
| Cierre del día e Fondo inicial | sim | não | sim |
| Precios (alterar preços existentes) | sim | não | não |

O preço inicial continua sendo definido no cadastro do produto (Administrador
ou Empleado). Miniaturas e fotos são visíveis a todos os papéis nas telas que
cada um já pode abrir.

## Entrega A — Papéis e categorias

> **Implementada em 2026-11-15.** Registro: [decisão](../decisions/2026-11-15-papeis-sem-pin.md). Diferença em relação ao texto abaixo: a base anterior não é recriada no lugar; é arquivada com outro nome e uma base nova é criada.

**Objetivo:** cada papel entra com sua senha e só vê e executa o que lhe cabe.

- **Banco:** `usuarios.perfil` passa a aceitar `admin`, `empleado`, `cajero`.
  Cada função de negócio confere o papel do usuário informado, conforme a
  tabela acima (ex.: `fn_finalizar_venda` recusa `empleado`; `fn_alterar_precos`
  só aceita `admin`). A aplicação continua conectando com uma única role
  restrita.
- **Aplicação:** uma tabela única de permissões por rota; o menu mostra só o
  permitido; rota não permitida responde 403 com mensagem em es-AR. Testes
  cobrem a matriz inteira (cada papel × cada área), no HTTP e no banco.
- **PIN:** removidos `pin.py`, `setup_pin.py`, `windows_pin_acl.py`,
  `configurar_pin.bat`, a tela de PIN e seus testes. O limite de tentativas de
  login permanece, agora contado por conta.
- **Instalação:** `instalar.bat` cria as três contas e pede as três senhas;
  deixa de pedir "nombre/login operativo" e PIN. Novo `cambiar_contrasena.bat`
  para trocar a senha de um papel (pede a senha do `postgres`).
- **Categorias:** a instalação cria `Accesorios`, `Telas por peso`,
  `Telas de punto`, `Telas sintéticas` em vez de perguntar. (Subitens e lista
  final: questão aberta abaixo.)
- **Base atual:** backup, depois base nova recriada pelo instalador.

**Limite conhecido, mantido:** o papel é conferido a partir do usuário que a
aplicação informa ao banco; contas compartilhadas não provam autoria individual.

**Aceite:** os três logins funcionam; nenhum papel abre ou executa área fora da
tabela, nem por URL direta nem por formulário forjado; Cajero conclui Cierre
sem PIN; Empleado não cobra nem altera preço existente; suíte completa passa
em `ejecutar_pruebas.bat`.

## Entrega B — Vários computadores na loja

> **Implementada em 2026-11-16** e confirmada pelo responsável com um segundo computador real, após a correção de IPv6 e de suspensão. HTTP sem cifra aceito em 2026-11-16 por a rede ser exclusiva da loja. Registro e pontos em aberto (PC servidor, endereço estável): [rede local](../decisions/2026-11-16-rede-local.md).

**Objetivo:** um PC servidor; os demais usam só o navegador.

- Servidor roda PostgreSQL e a aplicação; os outros abrem
  `http://NOME-DO-SERVIDOR:5000`. Nada é instalado neles.
- PostgreSQL continua aceitando conexões só do próprio servidor.
- Aplicação: escutar na rede local (hoje só `127.0.0.1`), servidor de produção
  `waitress` (nova dependência), regra de firewall do Windows restrita à rede
  privada, início automático quando o PC liga, atalho nos outros PCs.
- Backup diário e senha de conexão cifrada continuam no servidor.

**Risco a decidir:** em HTTP simples as senhas trafegam sem cifra dentro da
rede da loja. Aceitável em rede cabeada/Wi-Fi exclusivo da loja; com Wi-Fi
compartilhado com clientes, exigir HTTPS.

**Aceite:** dois PCs operando ao mesmo tempo com papéis diferentes; corte em um
aparece na Caja do outro; servidor reiniciado volta sozinho; porta fechada para
redes públicas.

## Entrega C — Administrador em casa

**Objetivo:** o Administrador abre a mesma loja de casa, com tudo o que o
papel permite, sem expor a loja à internet.

- VPN entre o dispositivo do Administrador e o servidor (recomendado:
  Tailscale; alternativa: WireGuard). Nenhuma porta aberta no roteador.
- Só dispositivos autorizados pelo Administrador entram na VPN.
- O servidor precisa estar ligado e com internet; sem internet a loja continua
  funcionando localmente.
- A criação da conta na VPN e a autorização dos dispositivos são feitas pelo
  responsável; o projeto documenta o passo a passo.

**Aceite:** de fora da rede da loja, com VPN, o Administrador ingressa estoque
e altera preços; sem VPN o endereço não responde; Empleado/Cajero de fora
também dependem da VPN.

## Relatórios

Ficam na Fase 2 (Relatórios) do ROADMAP, lendo o PostgreSQL pela própria
aplicação, visíveis ao Administrador (inclusive de casa, pela VPN). O conjunto
inicial de relatórios ainda não está definido.

## Ordem

A → B → C. Papéis antes da rede: abrir a loja a mais computadores sem papéis
aumenta o risco. VPN por último: depende de a aplicação já escutar na rede.

## Documentos a atualizar junto com a Entrega A

- **HANDOFF §8 (Segurança):** substituir sessão compartilhada única e PIN geral
  por três contas de papel; registrar que não há autoria individual.
- **HANDOFF §3.6 / área protegida de preços e §7.1 F (Cierre):** trocar "PIN
  geral" por papel (Precios: Administrador; Cierre/Fondo: Cajero e
  Administrador).
- **ROADMAP:** decisão de acesso vigente, 1C, extensão de preços, Fase 2
  (controle granular deixa de ser futuro) e Fase 3 (rede local e VPN deixam de
  ser questão aberta nos pontos decididos aqui).
- **docs/decisions:** nova entrada com as seis decisões acima; a de 2026-11-15
  sobre PIN (limite de tentativas) passa a valer só para o login.
- **docs/INSTALACAO_WINDOWS.md e guias USO_LOCAL:** novos passos, sem PIN.

## Questões abertas

1. **Categorias:** as quatro são a lista completa? Os dois-pontos nas anotações
   indicam subitens (subcategorias) a listar? Hoje o modelo tem um único nível.
2. **Rede da loja:** qual PC será o servidor; a rede é exclusiva da loja ou
   compartilhada com clientes (define HTTP ou HTTPS).
3. **Relatórios:** quais números o Administrador quer ver primeiro.
4. **Ticket cortado e não pago:** segue em aberto (1C), fora deste plano.
