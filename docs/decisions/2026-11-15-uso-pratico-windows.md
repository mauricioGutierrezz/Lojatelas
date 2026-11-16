# Decisões confirmadas — uso prático no Windows (2026-11-15)

Confirmadas explicitamente pelo responsável pelo projeto em 2026-11-15. Não
alteram regras de domínio do HANDOFF (estoque, corte, venda, Cierre, PIN).

## 1. Senha de conexão guardada cifrada pelo Windows

- **Antes:** `iniciar.bat` pedia a senha de conexão da role `loja_app` a cada
  início; nenhuma senha era gravada.
- **Decisão:** a senha é pedida uma única vez e guardada cifrada com DPAPI do
  Windows, legível somente pela mesma conta Windows no mesmo equipamento, em
  `%LOCALAPPDATA%\Urdimbre`, fora do projeto e de pastas sincronizadas.
- **Consequência aceita:** quem usa a mesma conta Windows abre a loja sem
  digitar a senha do banco. O login da tela e o PIN geral continuam exigidos.
- **Preservado:** nenhuma senha em texto puro, em argumentos, em `.env` ou no
  repositório. `iniciar.bat --no-recordar` mantém o modo sempre interativo e
  `iniciar.bat --olvidar` apaga a senha guardada.

## 2. Backup local automático diário

> Atualizado em 2026-11-16: frequência, retenção e recuperação em outro computador mudaram; ver [backup e recuperação](2026-11-16-backup-e-recuperacao.md).

- **Antes:** política de backup era questão aberta da Fase 3, sem rotina.
- **Decisão (provisória, local):** cada início da loja cria no máximo um
  backup por dia em `Documentos\Urdimbre - Respaldos`, mantendo os 30
  mais recentes. `respaldar.bat` cria um backup imediato.
- **Mecanismo:** role própria `loja_backup`, somente leitura
  (`pg_read_all_data`), com senha aleatória guardada cifrada pelo Windows. A
  senha do `postgres` é pedida só na configuração inicial.
- **Restauração:** `restaurar_respaldo.bat` restaura sempre em uma base
  **nova**; nunca substitui nem apaga uma base existente.
- **Continua em aberto na Fase 3:** cópia fora do equipamento (pendrive/nuvem),
  prazo de retenção definitivo e teste periódico de recuperação. O arquivo de
  backup contém os hashes de senha dos usuários e deve ser tratado como
  confidencial.

## 3. Limite de tentativas de PIN e de login

> Atualizado no mesmo dia: o PIN geral foi removido ([papéis em vez de PIN](2026-11-15-papeis-sem-pin.md)); o limite vale só para o login, contado por conta.

Endurecimento técnico, sem novo contrato de acesso: após 5 erros seguidos, novas
tentativas esperam 30 s, dobrando até 5 minutos; um acerto zera a contagem. O
limite do PIN vale para o equipamento (o PIN é compartilhado) e não identifica
pessoas. Reiniciar a aplicação zera a contagem.
