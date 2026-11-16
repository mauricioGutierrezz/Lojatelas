\set ON_ERROR_STOP on

-- Executar em banco vazio, imediatamente depois de schema.sql.
INSERT INTO public.usuarios (nome, login, senha_hash, perfil) VALUES
    ('Admin de teste', 'admin_teste', 'hash-ficticio-admin', 'admin'),
    ('Operador de teste', 'operador_teste', 'hash-ficticio-operador', 'admin');

INSERT INTO public.tipos_tela (nome) VALUES ('Tipo de teste');
INSERT INTO public.produtos (
    tipo_id, nome, unidade_medida, largura_metros,
    quantidade_padrao_lote, preco_unitario
) VALUES
    (1, 'Produto A', 'm', 1.40, 30, 10.00),
    (1, 'Produto B', 'm', 1.50, 20, 20.00);

SET ROLE loja_operador;
SELECT public.fn_confirmar_ingresso('00000000-0000-0000-0000-000000000001',
    '[{"produto_id":1,"rolos":4,"quantidade":30}]', 2);
RESET ROLE;

DO $test$
BEGIN
    IF (SELECT COUNT(*) FROM public.estoque_lotes WHERE produto_id = 1) <> 4 THEN
        RAISE EXCEPTION 'Confirmacao nao criou quatro lotes individuais.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.estoque_lotes
        WHERE quantidade_inicial <> 30 OR quantidade_atual <> 30
    ) THEN
        RAISE EXCEPTION 'Confirmacao nao preservou a quantidade real dos rolos.';
    END IF;
    IF (SELECT COUNT(*) FROM public.movimentacoes WHERE tipo = 'ENTRADA') <> 4 THEN
        RAISE EXCEPTION 'Entradas do livro-razao incompletas.';
    END IF;
    PERFORM public.fn_confirmar_ingresso('00000000-0000-0000-0000-000000000001',
        '[{"produto_id":1,"rolos":4,"quantidade":30}]', 2);
    IF (SELECT COUNT(*) FROM public.estoque_lotes) <> 4 THEN
        RAISE EXCEPTION 'Repeticao de confirmacao duplicou lotes.';
    END IF;
END;
$test$;

SET ROLE loja_operador;
SELECT public.fn_iniciar_ticket(pg_catalog.gen_random_uuid(),2) FROM generate_series(1,5);

SELECT public.fn_adicionar_item_corte(
    1, 1, 5, 5,
    jsonb_build_array(jsonb_build_object('lote_id', 1, 'quantidade', 5)),
    2, pg_catalog.gen_random_uuid()
);
SELECT public.fn_adicionar_item_corte(
    2, 1, 15, 15,
    jsonb_build_array(
        jsonb_build_object('lote_id', 2, 'quantidade', 10),
        jsonb_build_object('lote_id', 3, 'quantidade', 5)
    ),
    2, pg_catalog.gen_random_uuid()
);

DO $test$
DECLARE v_falhou boolean;
BEGIN
    v_falhou := false;
    BEGIN
        PERFORM public.fn_adicionar_item_corte(
            3, 1, 26, 26,
            jsonb_build_array(jsonb_build_object('lote_id', 1, 'quantidade', 26)),
            2, pg_catalog.gen_random_uuid()
        );
    EXCEPTION WHEN OTHERS THEN
        v_falhou := true;
    END;
    IF NOT v_falhou THEN RAISE EXCEPTION 'Corte acima do saldo deveria falhar.'; END IF;

    v_falhou := false;
    BEGIN
        PERFORM public.fn_adicionar_item_corte(
            4, 2, 1, 1,
            jsonb_build_array(jsonb_build_object('lote_id', 4, 'quantidade', 1)),
            2, pg_catalog.gen_random_uuid()
        );
    EXCEPTION WHEN OTHERS THEN
        v_falhou := true;
    END;
    IF NOT v_falhou THEN RAISE EXCEPTION 'Produto incompatível deveria falhar.'; END IF;

    v_falhou := false;
    BEGIN
        PERFORM * FROM public.fn_finalizar_venda(5, 2, public.fn_conferencia_ticket(5), 0);
    EXCEPTION WHEN OTHERS THEN
        v_falhou := true;
    END;
    IF NOT v_falhou THEN RAISE EXCEPTION 'Ticket vazio deveria falhar.'; END IF;
END;
$test$;
RESET ROLE;

DO $test$
BEGIN
    IF (SELECT quantidade_atual FROM public.estoque_lotes WHERE id = 1) <> 25 THEN
        RAISE EXCEPTION 'Falha de corte deixou efeito parcial ou saldo incorreto.';
    END IF;
    IF EXISTS (SELECT 1 FROM public.itens_ticket WHERE ticket_id IN (3, 4)) THEN
        RAISE EXCEPTION 'Falha de corte deixou item parcial.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.itens_ticket AS it
        LEFT JOIN public.alocacoes_estoque AS a ON a.item_ticket_id = it.id
        GROUP BY it.id, it.quantidade_cortada
        HAVING COALESCE(SUM(a.quantidade), 0) <> it.quantidade_cortada
    ) THEN
        RAISE EXCEPTION 'Soma das alocacoes diverge da quantidade do item.';
    END IF;
END;
$test$;

-- Alteracao posterior de preco nao pode modificar os itens cortados.
UPDATE public.produtos SET preco_unitario = 99.00 WHERE id = 1;

SET ROLE loja_operador;
SELECT * FROM public.fn_finalizar_venda(1, 2, public.fn_conferencia_ticket(1), 0);
RESET ROLE;

DO $test$
BEGIN
    IF (SELECT valor_total FROM public.vendas WHERE ticket_id = 1) <> 50.00 THEN
        RAISE EXCEPTION 'Venda nao usou o preco congelado no corte.';
    END IF;
    IF (SELECT quantidade_atual FROM public.estoque_lotes WHERE id = 1) <> 25 THEN
        RAISE EXCEPTION 'Pagamento baixou estoque novamente.';
    END IF;
    IF (SELECT COUNT(*) FROM public.movimentacoes WHERE referencia_tipo = 'ticket'
        AND referencia_id = 1) <> 1 THEN
        RAISE EXCEPTION 'Pagamento criou ou removeu movimento fisico.';
    END IF;
    IF EXISTS (SELECT 1 FROM public.vw_reconciliacao_estoque WHERE diferenca <> 0) THEN
        RAISE EXCEPTION 'Livro-razao nao reconcilia com o saldo.';
    END IF;
END;
$test$;

-- Permissoes efetivas do operador.
SET ROLE loja_operador;
DO $test$
BEGIN
    BEGIN
        PERFORM senha_hash FROM public.usuarios LIMIT 1;
        RAISE EXCEPTION 'Operador leu senha_hash.';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE public.estoque_lotes SET quantidade_atual = 1 WHERE id = 1;
        RAISE EXCEPTION 'Operador alterou saldo diretamente.';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        UPDATE public.produtos SET preco_unitario = 1 WHERE id = 1;
        RAISE EXCEPTION 'Operador alterou preco diretamente.';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO public.movimentacoes (
            lote_id, produto_id, tipo, quantidade, usuario_id
        ) VALUES (1, 1, 'CORTE', 1, 2);
        RAISE EXCEPTION 'Operador inseriu movimentacao diretamente.';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    BEGIN
        INSERT INTO public.fechamentos_caixa (
            data_referencia, total_vendido, fechado_por
        ) VALUES (CURRENT_DATE, 0, 2);
        RAISE EXCEPTION 'Operador inseriu fechamento diretamente.';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END;
$test$;
RESET ROLE;

DO $test$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_proc AS p
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
        ) AS a
        JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname IN (
              'fn_confirmar_ingresso', 'fn_cadastrar_produto', 'fn_autenticar_usuario', 'fn_iniciar_ticket', 'fn_adicionar_item_corte',
              'fn_composicao_recebimento', 'fn_conferencia_ticket', 'fn_finalizar_venda', 'fn_fechar_caixa', 'fn_consultar_caixa', 'fn_registrar_fundo', 'fn_data_operacional', 'fn_travar_dia_recebimento'
          )
          AND a.grantee = 0
          AND a.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC executa funcao sensivel.';
    END IF;
    IF to_regprocedure('public.fn_aprovar_ingresso(bigint,bigint)') IS NOT NULL THEN
        RAISE EXCEPTION 'Antigo contrato de aprovacao administrativa ainda existe.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc AS p
        JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname IN (
              'fn_confirmar_ingresso', 'fn_cadastrar_produto', 'fn_autenticar_usuario', 'fn_iniciar_ticket', 'fn_adicionar_item_corte',
              'fn_composicao_recebimento', 'fn_conferencia_ticket', 'fn_finalizar_venda', 'fn_fechar_caixa', 'fn_consultar_caixa', 'fn_registrar_fundo', 'fn_data_operacional', 'fn_travar_dia_recebimento'
          )
          AND pg_catalog.pg_get_userbyid(p.proowner) <> 'loja_owner'
    ) THEN
        RAISE EXCEPTION 'Funcao sensivel com owner incorreto.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc AS p
        JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname IN (
              'fn_confirmar_ingresso', 'fn_cadastrar_produto', 'fn_autenticar_usuario', 'fn_iniciar_ticket', 'fn_adicionar_item_corte',
              'fn_composicao_recebimento', 'fn_conferencia_ticket', 'fn_finalizar_venda', 'fn_fechar_caixa', 'fn_consultar_caixa', 'fn_registrar_fundo', 'fn_data_operacional', 'fn_travar_dia_recebimento'
          )
          AND NOT (p.proconfig @> ARRAY['search_path=pg_catalog, public'])
    ) THEN
        RAISE EXCEPTION 'Funcao sensivel sem search_path seguro.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname IN ('loja_owner', 'loja_operador', 'loja_admin') AND rolcanlogin
    ) THEN
        RAISE EXCEPTION 'Role de grupo possui LOGIN.';
    END IF;
    IF to_regprocedure('public.fn_cancelar_ticket(bigint,bigint)') IS NOT NULL THEN
        RAISE EXCEPTION 'Fluxo de cancelamento ainda existe.';
    END IF;
END;
$test$;

SELECT 'phase0_functional: ok' AS resultado;
