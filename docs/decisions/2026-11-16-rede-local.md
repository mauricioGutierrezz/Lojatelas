# Rede local — vários computadores (2026-11-16)

Entrega B de [PAPEIS_REDE_ACESSO_REMOTO](../planning/PAPEIS_REDE_ACESSO_REMOTO.md),
iniciada com o "pode fazer" do responsável em 2026-11-16.

## Confirmado pelo responsável (plano aprovado em 2026-11-15)

- Um PC servidor roda o PostgreSQL e a aplicação; os demais usam só o
  navegador, sem instalar nada.
- O PostgreSQL continua aceitando conexões apenas do próprio servidor.
- Nova dependência `waitress` como servidor de produção no modo rede.

## Escolhas técnicas desta entrega

- O modo é escolhido no assistente (`instalar.bat`, passo "Varios equipos") e
  fica guardado em `%LOCALAPPDATA%\Urdimbre\modo.txt`. O padrão continua
  sendo servir apenas ao próprio equipamento (`127.0.0.1`).
- No modo servidor a aplicação escuta em todas as interfaces, e há duas
  barreiras: (1) a regra de firewall criada por `permitir_red.bat`, restrita ao
  perfil de rede **privada** e à sub-rede local, porta 5000; (2) a própria
  aplicação recusa qualquer endereço que não seja o próprio equipamento ou rede
  privada, antes de qualquer outro processamento.
- Início automático: atalho na pasta Inicializar da conta Windows, criado só
  se o responsável responder "S" no assistente. Depende de a conta iniciar
  sessão (a senha de conexão é cifrada para essa conta).
- A regra de firewall só é criada por ação do responsável (duplo clique em
  `permitir_red.bat` ou resposta "S" no assistente, com o pedido de permissão
  de administrador do Windows). `quitar_red.bat` desfaz.

## Correções após o primeiro teste com outro computador (2026-11-16)

O primeiro teste real "funcionou por alguns segundos e parou". Achados no PC
servidor e correções:

- O nome do servidor resolve primeiro para endereços IPv6, e a loja só
  escutava em IPv4. Agora escuta em IPv4 e IPv6. Como IPv6 não tem faixa
  "privada" equivalente, a aplicação aceita endereços IPv6 globais apenas do
  mesmo prefixo /64 do próprio servidor (a mesma rede local).
- O Windows suspendia o PC após 15 minutos parado. Com a loja aberta em modo
  servidor, o processo pede ao Windows para não suspender por inatividade; ao
  fechar a loja, vale de novo a configuração do Windows.
- Novo registro de conexões em `%LOCALAPPDATA%\Urdimbre\accesos.log`
  (endereço, método, caminho e resultado; sem parâmetros, corpo ou senhas), só
  no modo servidor, para diagnosticar falhas.

Depois dessas correções e de reabrir a loja, o responsável confirmou em
2026-11-16 que a conexão a partir do outro computador ficou estável.


## HTTP sem cifra na rede da loja — confirmado em 2026-11-16

O responsável confirmou que o Wi-Fi da loja é **exclusivo dela, sem acesso de
clientes**. Com isso, fica aceito usar HTTP sem cifra dentro da rede local: as
senhas dos papéis trafegam sem cifra entre os outros PCs e o servidor.

A decisão vale enquanto essa condição valer. Se a rede passar a ser
compartilhada com clientes ou terceiros, o modo servidor não deve ser usado
até definir HTTPS.

## Em aberto — precisa de resposta do responsável

1. **Qual PC é o servidor.** Deve ficar ligado durante o expediente; os backups
   e a senha de conexão ficam nele.
2. **Endereço estável.** Os outros PCs abrem pelo nome do servidor. Se o nome
   não resolver na rede da loja, usar o IP e reservá-lo no roteador.

Acesso do Administrador de casa (VPN) continua sendo a Entrega C; nesta
entrega, endereços de fora de redes privadas são recusados.
