\set ON_ERROR_STOP on
SET ROLE loja_operador;
SELECT public.fn_registrar_fundo(public.fn_data_operacional(),100,2,pg_catalog.gen_random_uuid());
SELECT public.fn_fechar_caixa(public.fn_data_operacional(),2,c.conferencia,
    c.efectivo_segun_fondo_vendas+2,pg_catalog.gen_random_uuid())
    FROM public.fn_consultar_caixa(public.fn_data_operacional()) c;
RESET ROLE;
DO $test$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.fechamentos_caixa f
        JOIN public.fn_consultar_caixa(public.fn_data_operacional()) c ON true
        WHERE f.total_vendido=c.total_vendido AND f.efectivo_vendas=c.efectivo_vendas
        AND f.valor_otro=c.valor_otro AND f.fundo_inicial=100
        AND f.valor_contado=c.efectivo_segun_fondo_vendas+2 AND f.divergencia=2) THEN
        RAISE EXCEPTION 'Cierre nao preservou valores do movimento/fundo e diferenca.';
    END IF;
END;
$test$;
SELECT 'phase0_closing: ok' AS resultado;
