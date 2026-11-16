# Decisões confirmadas — papéis em vez de PIN geral (2026-11-15)

Confirmadas explicitamente pelo responsável pelo projeto em 2026-11-15 e
implementadas na mesma data (Entrega A de
[PAPEIS_REDE_ACESSO_REMOTO](../planning/PAPEIS_REDE_ACESSO_REMOTO.md)).

**Substituem** no HANDOFF e no ROADMAP: a sessão operacional única compartilhada,
o PIN geral de Precios/Cierre/Fondo, a regra de "autorização só enquanto
permanece no fluxo protegido" e a reserva de controle de acesso granular ao
Administrativo futuro. Não alteram regras de estoque, corte, preço congelado,
venda calculada pelo banco nem as regras do Cierre do dia.

## 1. Três contas fixas, uma por papel

| Conta (login) | Papel | Áreas |
| --- | --- | --- |
| `administrador` | Administrador | Tudo, inclusive Precios |
| `empleado` | Empleado | Productos / Stock; Corte / Ticket |
| `cajero` | Cajero | Corte / Ticket; Caja / Venta; Consulta de Caja; Cierre e Fondo inicial |

- Cada conta tem senha própria, definida na instalação; troca por
  `cambiar_contrasena.bat` (exige a senha do `postgres`).
- As contas são compartilhadas por papel: o papel autoriza, **não identifica
  a pessoa**. Os campos de responsável continuam registrando a conta usada e
  não comprovam autoria individual.
- O preço inicial continua sendo definido no cadastro do produto
  (Administrador ou Empleado). Alterar preço existente: só Administrador.
- Fotos e miniaturas são visíveis a todos os papéis nas telas que cada um abre;
  enviar ou trocar foto pertence a Productos / Stock.

## 2. PIN geral removido

O papel é a única barreira de Precios, Cierre e Fondo. Foram removidos o
arquivo de hash do PIN, sua configuração, a tela de PIN e a autorização por
fluxo. Um arquivo `cierre-pin.hash` de instalações anteriores deixa de ser
lido e pode ser apagado pelo responsável.

## 3. Onde a regra é aplicada

1. Menu: mostra só as áreas do papel.
2. Rotas: tabela única em `app_loja/permisos.py`; área não permitida responde
   403. O papel é relido do banco a cada pedido.
3. Banco: as funções de negócio conferem o papel do usuário informado
   (`SQLSTATE 42501` quando o papel não permite). `fn_guardar_foto` não recebe
   usuário e é protegida só pelas camadas 1 e 2.

Limite conhecido, mantido: o banco confia no identificador de usuário que a
aplicação informa (HANDOFF §7.2 G).

## 4. Categorias

A instalação cria `Accesorios`, `Telas por peso`, `Telas de punto` e
`Telas sintéticas`, em um único nível. Subcategorias e eventual tela de gestão
de categorias seguem em aberto.

## 5. Base da versão anterior

A base anterior só tinha dados de teste. O instalador não a apaga: com
confirmação explícita, renomeia-a para `<nome>_anterior_<data>` e cria a base
nova, conservando a role de conexão e sua senha.

## 6. Limite de tentativas

O limite de tentativas registrado em
[2026-11-15-uso-pratico-windows](2026-11-15-uso-pratico-windows.md) passa a
valer apenas para o login e é contado por conta: errar a senha de um papel não
bloqueia os outros.
