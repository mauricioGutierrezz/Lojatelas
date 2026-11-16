# Backup mais frequente e recuperação em um passo (2026-11-16)

Pedido e aprovado pelo responsável em 2026-11-16, depois de a loja passar a ser
usada por mais de um computador com um único servidor. Atualiza o item 2 de
[uso prático no Windows](2026-11-15-uso-pratico-windows.md), que previa um
backup por dia e os 30 mais recentes.

## Quando o backup é feito

- Ao abrir a loja, se o mais recente tiver mais de uma hora.
- A cada hora, enquanto a loja estiver aberta.
- Ao confirmar cada Cierre del día.
- Na hora, por `respaldar.bat`.

Os backups automáticos rodam em segundo plano: não travam as telas e, se
falharem, a loja continua funcionando. Dois backups nunca rodam ao mesmo tempo.

## O que é conservado

- Todos os backups das últimas 48 horas.
- O último de cada dia, até 30 dias.
- O restante é apagado. Só arquivos com o nome de backup da própria base são
  apagados.

Perda máxima esperada com defeito no disco do servidor: até uma hora de
trabalho, desde que a pasta de backups exista fora desse disco.

## Recuperação em outro computador

`recuperar_en_otro_equipo.bat`, em um computador com Python e PostgreSQL
instalados e com acesso à pasta de backups:

1. escolhe o backup mais recente (ou o arquivo/pasta informado);
2. mostra a data do backup e pede a confirmação `recuperar`;
3. cria a base com o nome de sempre a partir do backup;
4. cria a role de conexão com senha nova, aleatória e cifrada pelo Windows;
5. configura o backup automático no computador novo;
6. cria o atalho e pergunta pelo modo servidor.

Nunca substitui uma base existente: se a base já existir, para sem alterar
nada. As senhas de Administrador, Empleado e Cajero vêm do backup e continuam
as mesmas. A senha do `postgres` do computador novo pode ser diferente.

Verificado por teste de ponta a ponta: instalação, backup, restauração em um
segundo PostgreSQL vazio com outra senha administrativa, operação com a role
restrita, login com a senha de papel original e novo backup no destino.

## Continua em aberto

- A cópia fora do equipamento depende de a pasta de backups estar em um
  serviço sincronizado ou ser copiada para outro meio.
- Teste periódico de recuperação pelo responsável.
- A recuperação interativa (`recuperar_en_otro_equipo.bat`) não foi executada
  em um segundo computador físico.
