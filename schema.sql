-- =============================================================
-- SISTEMA "URDIMBRE"
-- schema.sql v3.1 - núcleo + revisão transversal m / un / kg
-- Banco: PostgreSQL
-- =============================================================
-- Inicializa uma base limpa; os dados ficticios anteriores nao migram.
-- usuario_id registra identidade informada, mas ainda nao comprova autoria.

BEGIN;
DO $guard$
BEGIN
 IF EXISTS(SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')) THEN
  RAISE EXCEPTION 'Inicialización rechazada: la base ya tiene estructura. No se modificó ningún dato.';
 END IF;
END; $guard$;
-- 1. Roles e schema
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'loja_owner') THEN
        CREATE ROLE loja_owner NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'loja_operador') THEN
        CREATE ROLE loja_operador NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'loja_admin') THEN
        CREATE ROLE loja_admin NOLOGIN;
    END IF;
END;
$roles$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO loja_owner, loja_operador, loja_admin;

-- 2. Tabelas
CREATE TABLE public.unidades_medida (
    codigo text PRIMARY KEY,
    descricao text NOT NULL,
    decimais smallint NOT NULL CHECK (decimais BETWEEN 0 AND 3)
);
INSERT INTO public.unidades_medida (codigo, descricao, decimais) VALUES
    ('m', 'Metro lineal', 3), ('kg', 'Kilogramo', 3), ('un', 'Unidad', 0);

CREATE TABLE public.tipos_tela (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome text NOT NULL UNIQUE
);

CREATE TABLE public.produtos (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo_id bigint NOT NULL REFERENCES public.tipos_tela(id),
    nome text NOT NULL,
    unidade_medida text NOT NULL DEFAULT 'm' REFERENCES public.unidades_medida(codigo),
    largura_metros numeric(5,2) CHECK (largura_metros > 0),
    quantidade_padrao_lote numeric(12,3) CHECK (quantidade_padrao_lote > 0),
    preco_unitario numeric(12,2) NOT NULL CHECK (preco_unitario >= 0),
    ativo boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT pg_catalog.now()
);

CREATE TABLE public.estoque_agregado (
 produto_id bigint PRIMARY KEY REFERENCES public.produtos(id),
 quantidade_atual numeric NOT NULL DEFAULT 0 CHECK(quantidade_atual>=0 AND quantidade_atual=trunc(quantidade_atual)
   AND quantidade_atual::text NOT IN ('NaN','Infinity','-Infinity'))
);

CREATE TABLE public.usuarios (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome text NOT NULL,
    login text NOT NULL UNIQUE,
    senha_hash text NOT NULL,
    perfil text NOT NULL CHECK (perfil IN ('admin', 'empleado', 'cajero')),
    ativo boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT pg_catalog.now()
);

ALTER TABLE public.produtos ADD COLUMN criado_por bigint REFERENCES public.usuarios(id);

CREATE TABLE public.ingressos (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chave_confirmacao uuid NOT NULL UNIQUE,
    grupos_declarados jsonb NOT NULL,
    registrado_por bigint NOT NULL REFERENCES public.usuarios(id),
    registrado_em timestamptz NOT NULL DEFAULT pg_catalog.now(),
    observacao text
);

-- Cada linha representa uma unidade fisica. A interface pode agrupar a
-- captura, mas quatro rolos sempre produzem quatro linhas e quatro lotes.
CREATE TABLE public.itens_ingresso (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ingresso_id bigint NOT NULL REFERENCES public.ingressos(id) ON DELETE CASCADE,
    produto_id bigint NOT NULL REFERENCES public.produtos(id),
    quantidade numeric NOT NULL CHECK (quantidade > 0 AND quantidade < 1000000000 AND quantidade=round(quantidade,3) AND quantidade::text NOT IN ('NaN','Infinity','-Infinity')),
    codigo_lote text,
    observacao text
);

CREATE SEQUENCE public.estoque_lote_codigo_seq AS bigint;

CREATE TABLE public.estoque_lotes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    produto_id bigint NOT NULL REFERENCES public.produtos(id),
    item_ingresso_id bigint UNIQUE REFERENCES public.itens_ingresso(id),
    codigo_interno text NOT NULL UNIQUE,
    quantidade_inicial numeric(12,3) NOT NULL CHECK (quantidade_inicial > 0),
    quantidade_atual numeric(12,3) NOT NULL
        CHECK (quantidade_atual >= 0 AND quantidade_atual <= quantidade_inicial),
    status_operacional text NOT NULL DEFAULT 'fechado'
        CHECK (status_operacional IN ('fechado', 'aberto', 'esgotado', 'descartado')),
    condicao_fisica text NOT NULL DEFAULT 'normal'
        CHECK (condicao_fisica IN ('normal', 'retalho')),
    aberto_em timestamptz,
    criado_em timestamptz NOT NULL DEFAULT pg_catalog.now(),
    UNIQUE (id, produto_id),
    CHECK (condicao_fisica <> 'normal' OR item_ingresso_id IS NOT NULL),
    CHECK ((quantidade_atual = 0 AND status_operacional IN ('esgotado', 'descartado'))
        OR (quantidade_atual > 0 AND status_operacional IN ('fechado', 'aberto', 'descartado')))
);

CREATE TABLE public.movimentacoes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lote_id bigint,
    item_ingresso_id bigint REFERENCES public.itens_ingresso(id),
    produto_id bigint NOT NULL REFERENCES public.produtos(id),
    tipo text NOT NULL CHECK (tipo IN
        ('ENTRADA', 'CORTE', 'AJUSTE_ENTRADA', 'AJUSTE_SAIDA', 'PERDA')),
    quantidade numeric NOT NULL CHECK (quantidade > 0),
    referencia_tipo text CHECK (referencia_tipo IN ('ingresso', 'ticket', 'manual')),
    referencia_id bigint,
    usuario_id bigint NOT NULL REFERENCES public.usuarios(id),
    criado_em timestamptz NOT NULL DEFAULT pg_catalog.now(),
    observacao text,
    FOREIGN KEY (lote_id, produto_id) REFERENCES public.estoque_lotes(id, produto_id),
    CHECK ((referencia_tipo IS NULL AND referencia_id IS NULL)
        OR (referencia_tipo IS NOT NULL AND referencia_id IS NOT NULL))
);

CREATE TABLE public.tickets (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chave_criacao uuid NOT NULL UNIQUE,
    codigo text NOT NULL UNIQUE,
    atendido_por bigint NOT NULL REFERENCES public.usuarios(id),
    criado_em timestamptz NOT NULL DEFAULT pg_catalog.now(),
    status text NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'pago'))
);

CREATE TABLE public.itens_ticket (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chave_corte uuid NOT NULL UNIQUE,
    alocacoes_declaradas jsonb NOT NULL,
    cortado_por bigint NOT NULL REFERENCES public.usuarios(id),
    ticket_id bigint NOT NULL REFERENCES public.tickets(id),
    produto_id bigint NOT NULL REFERENCES public.produtos(id),
    quantidade_vendida numeric NOT NULL CHECK (quantidade_vendida > 0 AND quantidade_vendida < 1000000000 AND quantidade_vendida=round(quantidade_vendida,3) AND quantidade_vendida::text NOT IN ('NaN','Infinity','-Infinity')),
    quantidade_cortada numeric NOT NULL CHECK (quantidade_cortada > 0 AND quantidade_cortada < 1000000000 AND quantidade_cortada=round(quantidade_cortada,3) AND quantidade_cortada::text NOT IN ('NaN','Infinity','-Infinity')),
    diferenca_quantidade numeric(13,3) GENERATED ALWAYS AS
        (quantidade_cortada - quantidade_vendida) STORED,
    preco_unitario numeric(12,2) NOT NULL CHECK (preco_unitario >= 0),
    valor_total numeric(14,2) GENERATED ALWAYS AS
        (pg_catalog.round(quantidade_vendida * preco_unitario, 2)) STORED,
    cortado_em timestamptz NOT NULL DEFAULT pg_catalog.now()
);

CREATE TABLE public.alocacoes_estoque (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_ticket_id bigint NOT NULL REFERENCES public.itens_ticket(id),
    lote_id bigint NOT NULL REFERENCES public.estoque_lotes(id),
    quantidade numeric NOT NULL CHECK (quantidade > 0 AND quantidade < 1000000000 AND quantidade=round(quantidade,3) AND quantidade::text NOT IN ('NaN','Infinity','-Infinity')),
    UNIQUE (item_ticket_id, lote_id)
);

ALTER TABLE public.movimentacoes ADD COLUMN item_ticket_id bigint REFERENCES public.itens_ticket(id);

CREATE TABLE public.vendas (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id bigint NOT NULL UNIQUE REFERENCES public.tickets(id),
    recebido_por bigint NOT NULL REFERENCES public.usuarios(id),
    recebido_em timestamptz NOT NULL DEFAULT pg_catalog.now(),
    metodo_pagamento text,
    conferencia jsonb NOT NULL,
    valor_total numeric(14,2) NOT NULL CHECK (valor_total >= 0),
    valor_efectivo numeric(14,2) NOT NULL CHECK (
        valor_efectivo >= 0 AND valor_efectivo <= valor_total
        AND valor_efectivo::text NOT IN ('NaN','Infinity','-Infinity')),
    valor_otro numeric(14,2) GENERATED ALWAYS AS (valor_total - valor_efectivo) STORED
);

-- Referência diária versionada; correções acrescentam registros, sem sobrescrever.
CREATE TABLE public.fundos_caixa (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chave_registro uuid NOT NULL UNIQUE,
    data_referencia date NOT NULL,
    valor numeric(14,2) NOT NULL CHECK (valor >= 0 AND valor::text NOT IN ('NaN','Infinity','-Infinity')),
    registrado_por bigint NOT NULL REFERENCES public.usuarios(id),
    registrado_em timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE TABLE public.fechamentos_caixa (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chave_confirmacao uuid NOT NULL UNIQUE,
    data_referencia date NOT NULL UNIQUE,
    conferencia jsonb NOT NULL,
    fundo_id bigint NOT NULL REFERENCES public.fundos_caixa(id),
    fundo_inicial numeric(14,2) NOT NULL CHECK (fundo_inicial >= 0),
    total_vendido numeric NOT NULL CHECK (total_vendido >= 0),
    efectivo_vendas numeric NOT NULL CHECK (efectivo_vendas >= 0),
    valor_otro numeric NOT NULL CHECK (valor_otro >= 0),
    efectivo_segun_fondo_vendas numeric GENERATED ALWAYS AS (fundo_inicial + efectivo_vendas) STORED,
    valor_contado numeric(14,2) CHECK (valor_contado >= 0),
    divergencia numeric GENERATED ALWAYS AS
        (CASE WHEN valor_contado IS NULL THEN NULL ELSE valor_contado - (fundo_inicial + efectivo_vendas) END) STORED,
    fechado_por bigint NOT NULL REFERENCES public.usuarios(id),
    fechado_em timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    CHECK (total_vendido = efectivo_vendas + valor_otro)
);

-- 3. Indices
CREATE INDEX idx_lotes_produto_status_qtd
    ON public.estoque_lotes (produto_id, status_operacional, quantidade_atual);
CREATE INDEX idx_mov_item_ingresso ON public.movimentacoes(item_ingresso_id);
CREATE INDEX idx_mov_item_ticket ON public.movimentacoes(item_ticket_id,lote_id);
CREATE INDEX idx_mov_lote_data ON public.movimentacoes (lote_id, criado_em, id);
CREATE INDEX idx_mov_produto_data ON public.movimentacoes (produto_id, criado_em, id);
CREATE INDEX idx_tickets_status_data ON public.tickets (status, criado_em);
CREATE INDEX idx_itens_ticket_produto ON public.itens_ticket (produto_id);
CREATE INDEX idx_itens_ticket_ticket ON public.itens_ticket (ticket_id, id);
CREATE INDEX idx_vendas_data ON public.vendas (recebido_em);
CREATE INDEX idx_fechamentos_data ON public.fechamentos_caixa (data_referencia, fechado_em);
CREATE INDEX idx_fundos_data ON public.fundos_caixa (data_referencia, id DESC);

-- 4. Invariantes diferidas
CREATE FUNCTION public.fn_validar_item_alocacoes(p_item_id bigint)
RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, public AS $fn$
DECLARE
    v_quantidade numeric(12,3);
    v_produto_id bigint;
    v_alocado numeric;
    v_unidade text;
BEGIN
    SELECT it.quantidade_cortada, it.produto_id INTO v_quantidade, v_produto_id
      FROM public.itens_ticket AS it WHERE it.id = p_item_id;
    IF NOT FOUND THEN RETURN; END IF;

    SELECT unidade_medida INTO v_unidade FROM public.produtos WHERE id=v_produto_id;
    IF v_unidade='un' THEN
      IF EXISTS(SELECT 1 FROM public.alocacoes_estoque WHERE item_ticket_id=p_item_id) THEN
        RAISE EXCEPTION 'Unidades no admiten asignaciones físicas.';
      END IF;
      RETURN;
    END IF;
    SELECT COALESCE(SUM(a.quantidade), 0) INTO v_alocado
      FROM public.alocacoes_estoque AS a WHERE a.item_ticket_id = p_item_id;
    IF v_alocado <> v_quantidade THEN
        RAISE EXCEPTION 'Alocacoes do item % somam %, esperado %.',
            p_item_id, v_alocado, v_quantidade;
    END IF;
    IF (SELECT COALESCE(jsonb_agg(jsonb_build_object('lote_id',a.lote_id,'quantidade',a.quantidade) ORDER BY a.lote_id),'[]')
          FROM public.alocacoes_estoque a WHERE a.item_ticket_id=p_item_id)
      IS DISTINCT FROM (SELECT alocacoes_declaradas FROM public.itens_ticket WHERE id=p_item_id) THEN
        RAISE EXCEPTION 'Las asignaciones no corresponden a la declaración de la retirada.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.alocacoes_estoque AS a
        JOIN public.estoque_lotes AS l ON l.id = a.lote_id
        WHERE a.item_ticket_id = p_item_id AND l.produto_id <> v_produto_id
    ) THEN
        RAISE EXCEPTION 'Item % possui alocacao de produto incompativel.', p_item_id;
    END IF;
END;
$fn$;

CREATE FUNCTION public.fn_trigger_validar_item_alocacoes()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $fn$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM public.fn_validar_item_alocacoes(OLD.item_ticket_id);
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM public.fn_validar_item_alocacoes(NEW.item_ticket_id);
    END IF;
    RETURN NULL;
END;
$fn$;

CREATE FUNCTION public.fn_trigger_validar_item()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $fn$
BEGIN
    PERFORM public.fn_validar_item_alocacoes(NEW.id);
    RETURN NULL;
END;
$fn$;

CREATE CONSTRAINT TRIGGER trg_alocacoes_item_integras
AFTER INSERT OR UPDATE OR DELETE ON public.alocacoes_estoque
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.fn_trigger_validar_item_alocacoes();

CREATE CONSTRAINT TRIGGER trg_item_alocacoes_integras
AFTER INSERT OR UPDATE OF produto_id, quantidade_cortada, alocacoes_declaradas ON public.itens_ticket
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.fn_trigger_validar_item();

CREATE FUNCTION public.fn_validar_saldo_lote(p_lote_id bigint)
RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, public AS $fn$
DECLARE
    v_atual numeric(12,3);
    v_reconstruido numeric(12,3);
BEGIN
    SELECT l.quantidade_atual INTO v_atual
      FROM public.estoque_lotes AS l WHERE l.id = p_lote_id;
    IF NOT FOUND THEN RETURN; END IF;

    SELECT COALESCE(SUM(CASE
        WHEN m.tipo IN ('ENTRADA', 'AJUSTE_ENTRADA') THEN m.quantidade
        WHEN m.tipo IN ('CORTE', 'AJUSTE_SAIDA', 'PERDA') THEN -m.quantidade
    END), 0) INTO v_reconstruido
      FROM public.movimentacoes AS m WHERE m.lote_id = p_lote_id;
    IF v_atual <> v_reconstruido THEN
        RAISE EXCEPTION 'Saldo do lote % e %, mas o livro-razao reconstroi %.',
            p_lote_id, v_atual, v_reconstruido;
    END IF;
END;
$fn$;

CREATE FUNCTION public.fn_trigger_validar_saldo_lote()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $fn$
BEGIN
    IF TG_TABLE_NAME = 'movimentacoes' AND TG_OP IN ('UPDATE', 'DELETE') THEN
        PERFORM public.fn_validar_saldo_lote(OLD.lote_id);
    END IF;
    IF TG_TABLE_NAME = 'movimentacoes' AND TG_OP IN ('INSERT', 'UPDATE') THEN
        PERFORM public.fn_validar_saldo_lote(NEW.lote_id);
    ELSIF TG_TABLE_NAME = 'estoque_lotes' AND TG_OP <> 'DELETE' THEN
        PERFORM public.fn_validar_saldo_lote(NEW.id);
    END IF;
    RETURN NULL;
END;
$fn$;

CREATE CONSTRAINT TRIGGER trg_movimentacoes_saldo_integro
AFTER INSERT OR UPDATE OR DELETE ON public.movimentacoes
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.fn_trigger_validar_saldo_lote();

CREATE CONSTRAINT TRIGGER trg_lotes_saldo_integro
AFTER INSERT OR UPDATE OF quantidade_atual ON public.estoque_lotes
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.fn_trigger_validar_saldo_lote();

CREATE FUNCTION public.fn_preservar_declaracao_ingresso()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $fn$
BEGIN
    RAISE EXCEPTION 'La declaración del ingreso confirmado no se puede modificar.';
END;
$fn$;

CREATE TRIGGER trg_ingresso_declaracao_preservada
BEFORE UPDATE OR DELETE ON public.ingressos
FOR EACH ROW EXECUTE FUNCTION public.fn_preservar_declaracao_ingresso();
CREATE TRIGGER trg_item_ingresso_declaracao_preservada
BEFORE UPDATE OR DELETE ON public.itens_ingresso
FOR EACH ROW EXECUTE FUNCTION public.fn_preservar_declaracao_ingresso();

-- 5. Funcoes de negocio
CREATE FUNCTION public.fn_gerar_codigo_ticket()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public AS $fn$
BEGIN
    NEW.codigo := 'TK-' || pg_catalog.lpad(NEW.id::text, 10, '0');
    RETURN NEW;
END;
$fn$;

CREATE TRIGGER trg_codigo_ticket BEFORE INSERT ON public.tickets
FOR EACH ROW EXECUTE FUNCTION public.fn_gerar_codigo_ticket();

CREATE FUNCTION public.fn_cadastrar_produto(
    p_tipo_id bigint, p_nome text, p_unidade text, p_preco numeric,
    p_usuario_id bigint, p_largura numeric DEFAULT NULL,
    p_padrao numeric DEFAULT NULL
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $fn$
DECLARE
    v_id bigint;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.usuarios WHERE id = p_usuario_id AND ativo
        AND perfil IN ('admin','empleado')) THEN
        RAISE EXCEPTION 'El rol no permite cargar productos.' USING ERRCODE='42501';
    END IF;
    IF p_nome IS NULL OR btrim(p_nome) = '' THEN
        RAISE EXCEPTION 'Ingresá el nombre del producto.';
    END IF;
    IF p_preco IS NULL OR p_preco < 0 OR p_preco <> round(p_preco, 2)
       OR p_preco::text IN ('NaN', 'Infinity', '-Infinity') THEN
        RAISE EXCEPTION 'Ingresá un precio inicial válido, con hasta dos decimales.';
    END IF;
    IF p_largura IS NOT NULL AND (p_largura <= 0 OR p_largura <> round(p_largura, 2)
        OR p_largura::text IN ('NaN', 'Infinity', '-Infinity')) THEN
        RAISE EXCEPTION 'Ingresá un ancho válido, con hasta dos decimales.';
    END IF;
    IF p_padrao IS NOT NULL AND (p_padrao <= 0 OR p_padrao <> round(p_padrao, 3)
        OR p_padrao::text IN ('NaN', 'Infinity', '-Infinity')) THEN
        RAISE EXCEPTION 'Ingresá una cantidad sugerida válida, con hasta tres decimales.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.tipos_tela WHERE id = p_tipo_id)
       OR NOT EXISTS (SELECT 1 FROM public.unidades_medida WHERE codigo = p_unidade) THEN
        RAISE EXCEPTION 'Elegí una categoría y unidad válidas.';
    END IF;
    IF p_unidade='un' AND (p_largura IS NOT NULL OR p_padrao IS NOT NULL) THEN
      RAISE EXCEPTION 'Unidades no admiten campos físicos.'; END IF;
    -- Solo INSERT: no existe un camino de actualización del precio existente.
    INSERT INTO public.produtos (tipo_id, nome, unidade_medida, preco_unitario,
        criado_por, largura_metros, quantidade_padrao_lote)
    VALUES (p_tipo_id, btrim(p_nome), p_unidade, p_preco,
        p_usuario_id, p_largura, p_padrao) RETURNING id INTO v_id;
    IF p_unidade='un' THEN INSERT INTO public.estoque_agregado(produto_id) VALUES(v_id); END IF;
    RETURN v_id;
END;
$fn$;

CREATE FUNCTION public.fn_confirmar_ingresso(
 p_chave uuid,p_grupos jsonb,p_usuario_id bigint,p_observacao text DEFAULT NULL
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $fn$
DECLARE antigo public.ingressos%ROWTYPE; doc bigint; item bigint; lote bigint; codigo text;
 g jsonb; normal jsonb:='[]'; unidade text; quantidade numeric; numero numeric; r record; n integer;
BEGIN
 IF p_chave IS NULL OR jsonb_typeof(p_grupos) IS DISTINCT FROM 'array' OR jsonb_array_length(p_grupos)=0 THEN
  RAISE EXCEPTION 'Declaración de ingreso inválida.'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.usuarios WHERE id=p_usuario_id AND ativo AND perfil IN ('admin','empleado')) THEN
  RAISE EXCEPTION 'El rol no permite ingresar stock.' USING ERRCODE='42501'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(p_chave::text,0));
 -- Normaliza representación numérica sin cambiar orden/significado de grupos.
 FOR g IN SELECT value FROM jsonb_array_elements(p_grupos) LOOP
  SELECT unidade_medida INTO unidade FROM public.produtos WHERE id=(g->>'produto_id')::bigint;
  IF unidade IS NULL THEN RAISE EXCEPTION 'Producto inexistente.'; END IF;
  quantidade:=(g->>'quantidade')::numeric;
  IF quantidade IS NULL OR quantidade<=0 OR quantidade>=1000000000 OR quantidade<>round(quantidade,3)
    OR quantidade::text IN ('NaN','Infinity','-Infinity') THEN RAISE EXCEPTION 'Cantidad inválida.'; END IF;
  IF unidade='un' THEN
   IF g ? 'rolos' OR g ? 'pecas' OR quantidade<>trunc(quantidade) THEN RAISE EXCEPTION 'Unidades: informá cantidad entera, sin orígenes físicos.'; END IF;
   normal:=normal||jsonb_build_array(jsonb_build_object('produto_id',(g->>'produto_id')::bigint,'unidade',unidade,'quantidade',quantidade));
  ELSE
   IF (unidade='m' AND (NOT g ? 'rolos' OR g ? 'pecas')) OR (unidade='kg' AND (NOT g ? 'pecas' OR g ? 'rolos')) THEN
    RAISE EXCEPTION 'Declaración física incompatible con la unidad.'; END IF;
   numero:=COALESCE(g->>'rolos',g->>'pecas')::numeric;
   IF numero IS NULL OR numero<=0 OR numero<>trunc(numero) OR numero>2147483647 OR numero::text IN ('NaN','Infinity','-Infinity') THEN RAISE EXCEPTION 'Número de orígenes inválido.'; END IF;
   normal:=normal||jsonb_build_array(jsonb_build_object('produto_id',(g->>'produto_id')::bigint,'unidade',unidade,'quantidade',quantidade,
    CASE WHEN unidade='m' THEN 'rolos' ELSE 'pecas' END,numero));
  END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(normal) a WHERE a->>'unidade'='un' GROUP BY a->>'produto_id' HAVING count(*)>1) THEN RAISE EXCEPTION 'Declaración agregada repetida.'; END IF;
 SELECT * INTO antigo FROM public.ingressos WHERE chave_confirmacao=p_chave;
 IF FOUND THEN
  IF antigo.grupos_declarados IS DISTINCT FROM normal OR antigo.registrado_por<>p_usuario_id OR antigo.observacao IS DISTINCT FROM p_observacao THEN RAISE EXCEPTION 'Esta confirmación ya fue utilizada con otros datos.'; END IF;
  RETURN antigo.id;
 END IF;
 FOR r IN SELECT DISTINCT (a->>'produto_id')::bigint AS id FROM jsonb_array_elements(normal) a ORDER BY id LOOP
  PERFORM 1 FROM public.produtos WHERE id=r.id AND ativo FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Producto no disponible.'; END IF;
 END LOOP;
 INSERT INTO public.ingressos(chave_confirmacao,grupos_declarados,registrado_por,observacao) VALUES(p_chave,normal,p_usuario_id,p_observacao) RETURNING id INTO doc;
 FOR g IN SELECT value FROM jsonb_array_elements(normal) LOOP
  unidade:=g->>'unidade'; quantidade:=(g->>'quantidade')::numeric;
  FOR n IN 1..CASE WHEN unidade='un' THEN 1 ELSE COALESCE(g->>'rolos',g->>'pecas')::integer END LOOP
   INSERT INTO public.itens_ingresso(ingresso_id,produto_id,quantidade) VALUES(doc,(g->>'produto_id')::bigint,quantidade) RETURNING id INTO item;
   lote:=NULL;
   IF unidade='un' THEN
    UPDATE public.estoque_agregado SET quantidade_atual=quantidade_atual+quantidade WHERE produto_id=(g->>'produto_id')::bigint;
    IF NOT FOUND THEN RAISE EXCEPTION 'Falta saldo agregado.'; END IF;
   ELSE
    codigo:='LT-'||lpad(nextval('public.estoque_lote_codigo_seq')::text,12,'0');
    INSERT INTO public.estoque_lotes(produto_id,item_ingresso_id,codigo_interno,quantidade_inicial,quantidade_atual)
      VALUES((g->>'produto_id')::bigint,item,codigo,quantidade,quantidade) RETURNING id INTO lote;
   END IF;
   INSERT INTO public.movimentacoes(lote_id,produto_id,item_ingresso_id,tipo,quantidade,referencia_tipo,referencia_id,usuario_id)
    VALUES(lote,(g->>'produto_id')::bigint,item,'ENTRADA',quantidade,'ingresso',doc,p_usuario_id);
  END LOOP;
 END LOOP;
 RETURN doc;
END; $fn$;

-- Autenticação local preserva o contrato existente de senha. A sessão da
-- aplicação ainda informa usuario_id; isto não resolve autoria forte.
CREATE FUNCTION public.fn_autenticar_usuario(p_login text, p_senha text)
RETURNS TABLE (id bigint, nome text, login text, perfil text)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
    SELECT u.id, u.nome, u.login, u.perfil FROM public.usuarios AS u
    WHERE u.login = p_login AND u.ativo
      AND u.senha_hash = public.crypt(p_senha, u.senha_hash);
$fn$;

COMMENT ON FUNCTION public.fn_confirmar_ingresso(uuid, jsonb, bigint, text) IS
    'Confirmação operacional atômica e idempotente. usuario_id é informado, não prova autoria.';

CREATE FUNCTION public.fn_iniciar_ticket(p_chave uuid, p_usuario_id bigint)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $fn$
DECLARE
    v_ticket public.tickets%ROWTYPE;
BEGIN
    IF p_chave IS NULL OR NOT EXISTS (SELECT 1 FROM public.usuarios
        WHERE id=p_usuario_id AND ativo AND perfil IN ('admin','empleado','cajero')) THEN
        RAISE EXCEPTION 'Falta una identificación válida para iniciar el ticket.' USING ERRCODE='42501';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_chave::text, 1));
    SELECT * INTO v_ticket FROM public.tickets WHERE chave_criacao=p_chave;
    IF FOUND THEN
        IF v_ticket.atendido_por <> p_usuario_id THEN
            RAISE EXCEPTION 'La identificación ya fue utilizada por otra atendente.';
        END IF;
        RETURN v_ticket.id;
    END IF;
    INSERT INTO public.tickets(chave_criacao,atendido_por)
    VALUES(p_chave,p_usuario_id) RETURNING * INTO v_ticket;
    RETURN v_ticket.id;
END;
$fn$;

CREATE FUNCTION public.fn_adicionar_item_corte(
    p_ticket_id bigint, p_produto_id bigint, p_quantidade_vendida numeric,
    p_quantidade_cortada numeric,
    p_alocacoes jsonb, p_usuario_id bigint, p_chave uuid
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $fn$
DECLARE
    v_status text;
    v_unidade text;
    v_agregado numeric;
    v_preco numeric(12,2);
    v_item_id bigint;
    v_vendida numeric(12,3);
    v_cortada numeric(12,3);
    v_soma numeric;
    v_total_lotes integer;
    v_lotes_validos integer := 0;
    v_lote record;
    v_aloc record;
    v_existente public.itens_ticket%ROWTYPE;
BEGIN
    IF p_chave IS NULL THEN
        RAISE EXCEPTION 'Falta la identificación del corte.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.usuarios WHERE id=p_usuario_id AND ativo
        AND perfil IN ('admin','empleado','cajero')) THEN
        RAISE EXCEPTION 'La atendente no está autorizada.' USING ERRCODE='42501';
    END IF;
    IF jsonb_typeof(p_alocacoes) IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Asignaciones inválidas.'; END IF;
    SELECT COALESCE(jsonb_agg(jsonb_build_object('lote_id',a.lote_id,'quantidade',a.quantidade) ORDER BY a.lote_id),'[]')
      INTO p_alocacoes FROM jsonb_to_recordset(p_alocacoes) AS a(lote_id bigint,quantidade numeric);
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_chave::text, 2));
    SELECT * INTO v_existente FROM public.itens_ticket WHERE chave_corte=p_chave;
    IF FOUND THEN
        IF v_existente.ticket_id IS DISTINCT FROM p_ticket_id
           OR v_existente.produto_id IS DISTINCT FROM p_produto_id
           OR v_existente.quantidade_vendida IS DISTINCT FROM p_quantidade_vendida
           OR v_existente.quantidade_cortada IS DISTINCT FROM p_quantidade_cortada
           OR v_existente.alocacoes_declaradas IS DISTINCT FROM p_alocacoes
           OR v_existente.cortado_por IS DISTINCT FROM p_usuario_id THEN
            RAISE EXCEPTION 'Esta identificación de corte ya fue utilizada con otros datos.';
        END IF;
        RETURN v_existente.id;
    END IF;
    SELECT t.status INTO v_status FROM public.tickets AS t
      WHERE t.id = p_ticket_id FOR UPDATE;
    IF NOT FOUND OR v_status <> 'pendente' THEN
        RAISE EXCEPTION 'Ticket % no existe o no esta pendiente.', p_ticket_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.usuarios AS u WHERE u.id = p_usuario_id
        AND u.ativo AND u.perfil IN ('admin','empleado','cajero')) THEN
        RAISE EXCEPTION 'Usuario informado e invalido ou inativo.' USING ERRCODE='42501';
    END IF;
    IF p_quantidade_vendida IS NULL OR p_quantidade_vendida <= 0
       OR p_quantidade_vendida <> pg_catalog.round(p_quantidade_vendida, 3)
       OR p_quantidade_vendida::text IN ('NaN','Infinity','-Infinity')
       OR p_quantidade_cortada IS NULL OR p_quantidade_cortada <= 0
       OR p_quantidade_cortada <> pg_catalog.round(p_quantidade_cortada, 3)
       OR p_quantidade_cortada::text IN ('NaN','Infinity','-Infinity') THEN
        RAISE EXCEPTION 'Cantidad invalida: se admite un maximo de tres decimales.';
    END IF;
    v_vendida := p_quantidade_vendida::numeric(12,3);
    v_cortada := p_quantidade_cortada::numeric(12,3);
    SELECT p.preco_unitario,p.unidade_medida INTO v_preco,v_unidade FROM public.produtos p
      WHERE p.id=p_produto_id AND p.ativo FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Producto inexistente o inactivo.'; END IF;
    IF v_unidade='un' THEN
      IF p_quantidade_vendida<>p_quantidade_cortada OR p_quantidade_vendida<>trunc(p_quantidade_vendida) OR p_quantidade_cortada<>trunc(p_quantidade_cortada)
        OR p_alocacoes<>'[]'::jsonb THEN RAISE EXCEPTION 'Unidades: cantidades enteras y ninguna asignación física.'; END IF;
      SELECT quantidade_atual INTO v_agregado FROM public.estoque_agregado WHERE produto_id=p_produto_id FOR UPDATE;
      IF v_agregado IS NULL OR v_agregado<v_cortada THEN RAISE EXCEPTION 'Stock disponible insuficiente.'; END IF;
      INSERT INTO public.itens_ticket(ticket_id,produto_id,quantidade_vendida,quantidade_cortada,preco_unitario,chave_corte,alocacoes_declaradas,cortado_por)
       VALUES(p_ticket_id,p_produto_id,v_vendida,v_cortada,v_preco,p_chave,'[]',p_usuario_id) RETURNING id INTO v_item_id;
      UPDATE public.estoque_agregado SET quantidade_atual=quantidade_atual-v_cortada WHERE produto_id=p_produto_id;
      INSERT INTO public.movimentacoes(produto_id,tipo,quantidade,referencia_tipo,referencia_id,usuario_id,item_ticket_id)
       VALUES(p_produto_id,'CORTE',v_cortada,'ticket',p_ticket_id,p_usuario_id,v_item_id);
      RETURN v_item_id;
    END IF;
    IF p_alocacoes IS NULL OR pg_catalog.jsonb_typeof(p_alocacoes) <> 'array'
       OR pg_catalog.jsonb_array_length(p_alocacoes) = 0 THEN
        RAISE EXCEPTION 'Las asignaciones deben formar un arreglo no vacio.';
    END IF;

    SELECT COUNT(*), SUM(a.quantidade)
      INTO v_total_lotes, v_soma
      FROM pg_catalog.jsonb_to_recordset(p_alocacoes)
           AS a(lote_id bigint, quantidade numeric);
    IF EXISTS (SELECT 1 FROM pg_catalog.jsonb_to_recordset(p_alocacoes)
        AS a(lote_id bigint, quantidade numeric)
        WHERE a.lote_id IS NULL OR a.quantidade IS NULL OR a.quantidade <= 0
           OR a.quantidade <> pg_catalog.round(a.quantidade, 3)
           OR a.quantidade::text IN ('NaN','Infinity','-Infinity')) THEN
        RAISE EXCEPTION 'Asignacion invalida: lote y cantidad positiva son obligatorios.';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.jsonb_to_recordset(p_alocacoes)
        AS a(lote_id bigint, quantidade numeric)
        GROUP BY a.lote_id HAVING COUNT(*) > 1) THEN
        RAISE EXCEPTION 'Un lote no puede repetirse en el mismo item.';
    END IF;
    IF v_soma <> v_cortada THEN
        RAISE EXCEPTION 'Las asignaciones suman %, pero la cantidad cortada es %.', v_soma, v_cortada;
    END IF;

    -- Bloqueio em ordem crescente, independente da ordem do JSON.
    FOR v_lote IN
        SELECT l.id, l.codigo_interno, l.produto_id, l.quantidade_atual,
               l.status_operacional,l.condicao_fisica, a.quantidade::numeric(12,3) AS solicitado
        FROM public.estoque_lotes AS l
        JOIN pg_catalog.jsonb_to_recordset(p_alocacoes)
             AS a(lote_id bigint, quantidade numeric) ON a.lote_id = l.id
        ORDER BY l.id FOR UPDATE OF l
    LOOP
        v_lotes_validos := v_lotes_validos + 1;
        IF v_lote.produto_id <> p_produto_id
           OR v_lote.status_operacional NOT IN ('fechado', 'aberto') OR v_lote.condicao_fisica<>'normal' THEN
            RAISE EXCEPTION 'Lote % no disponible para el producto %.', v_lote.id, p_produto_id;
        END IF;
        IF v_lote.quantidade_atual < v_lote.solicitado THEN
            RAISE EXCEPTION 'Saldo insuficiente en el lote %: disponible %, solicitado %.',
                v_lote.codigo_interno, v_lote.quantidade_atual, v_lote.solicitado;
        END IF;
    END LOOP;
    IF v_lotes_validos <> v_total_lotes THEN
        RAISE EXCEPTION 'Una o mas asignaciones hacen referencia a lotes inexistentes.';
    END IF;

    INSERT INTO public.itens_ticket (ticket_id, produto_id, quantidade_vendida, quantidade_cortada, preco_unitario,
        chave_corte,alocacoes_declaradas,cortado_por)
      VALUES (p_ticket_id, p_produto_id, v_vendida, v_cortada, v_preco,
        p_chave,p_alocacoes,p_usuario_id)
      RETURNING id INTO v_item_id;
    FOR v_aloc IN SELECT a.lote_id, a.quantidade::numeric(12,3) AS quantidade
        FROM pg_catalog.jsonb_to_recordset(p_alocacoes)
             AS a(lote_id bigint, quantidade numeric) ORDER BY a.lote_id
    LOOP
        INSERT INTO public.alocacoes_estoque (item_ticket_id, lote_id, quantidade)
          VALUES (v_item_id, v_aloc.lote_id, v_aloc.quantidade);
        UPDATE public.estoque_lotes
          SET quantidade_atual = quantidade_atual - v_aloc.quantidade,
              status_operacional = CASE
                  WHEN quantidade_atual - v_aloc.quantidade = 0 THEN 'esgotado'
                  WHEN status_operacional = 'fechado' THEN 'aberto'
                  ELSE status_operacional END,
              aberto_em = COALESCE(aberto_em, pg_catalog.now())
          WHERE id = v_aloc.lote_id;
        INSERT INTO public.movimentacoes (
            lote_id, produto_id, tipo, quantidade, referencia_tipo,
            referencia_id, usuario_id, item_ticket_id
        ) VALUES (
            v_aloc.lote_id, p_produto_id, 'CORTE', v_aloc.quantidade,
            'ticket', p_ticket_id, p_usuario_id, v_item_id
        );
    END LOOP;
    RETURN v_item_id;
END;
$fn$;

-- Conferência exata dos itens, com timestamp canônico independente do fuso da sessão.
CREATE FUNCTION public.fn_conferencia_ticket(p_ticket_id bigint)
RETURNS jsonb LANGUAGE sql STABLE SET search_path = pg_catalog, public AS $fn$
    SELECT COALESCE(pg_catalog.jsonb_agg(
        (pg_catalog.to_jsonb(i) - 'cortado_em') || pg_catalog.jsonb_build_object(
            'cortado_em', i.cortado_em AT TIME ZONE 'UTC') ORDER BY i.id), '[]'::jsonb)
    FROM public.itens_ticket i WHERE i.ticket_id=p_ticket_id;
$fn$;

-- Validação e prévia da composição; nenhuma modalidade de Otro é presumida.
CREATE FUNCTION public.fn_composicao_recebimento(
    p_ticket_id bigint, p_conferencia jsonb, p_efectivo numeric
) RETURNS TABLE (valor_total numeric(14,2), valor_efectivo numeric(14,2), valor_otro numeric(14,2))
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $fn$
DECLARE
    v_total numeric(14,2);
    v_itens integer;
BEGIN
    SELECT COUNT(*), COALESCE(SUM(it.valor_total),0)::numeric(14,2)
      INTO v_itens,v_total FROM public.itens_ticket it WHERE it.ticket_id=p_ticket_id;
    IF v_itens=0 THEN RAISE EXCEPTION 'No se puede cobrar un ticket sin items.'; END IF;
    IF public.fn_conferencia_ticket(p_ticket_id) IS DISTINCT FROM p_conferencia THEN
        RAISE EXCEPTION 'El ticket cambió. Volvé a revisar los items y el total.';
    END IF;
    IF p_efectivo IS NULL OR p_efectivo::text IN ('NaN','Infinity','-Infinity')
       OR p_efectivo < 0 OR p_efectivo > v_total
       OR p_efectivo <> pg_catalog.round(p_efectivo,2) THEN
        RAISE EXCEPTION 'Efectivo debe estar entre cero y el total, con hasta dos decimales.';
    END IF;
    RETURN QUERY SELECT v_total,p_efectivo::numeric(14,2),(v_total-p_efectivo)::numeric(14,2);
END;
$fn$;

CREATE FUNCTION public.fn_data_operacional()
RETURNS date LANGUAGE sql VOLATILE SET search_path = pg_catalog, public AS $fn$
    SELECT (pg_catalog.clock_timestamp() AT TIME ZONE 'America/Argentina/Cordoba')::date;
$fn$;

-- Reavaliar a data depois da espera: a transação pode atravessar meia-noite.
CREATE FUNCTION public.fn_travar_dia_recebimento()
RETURNS timestamptz LANGUAGE plpgsql SET search_path = pg_catalog, public AS $fn$
DECLARE v_data date; v_agora timestamptz;
BEGIN
    LOOP
        v_data := public.fn_data_operacional();
        PERFORM pg_catalog.pg_advisory_xact_lock(3,v_data-DATE '2000-01-01');
        v_agora := pg_catalog.clock_timestamp();
        IF (v_agora AT TIME ZONE 'America/Argentina/Cordoba')::date = v_data THEN RETURN v_agora; END IF;
    END LOOP;
END;
$fn$;

CREATE FUNCTION public.fn_finalizar_venda(
    p_ticket_id bigint, p_usuario_id bigint, p_conferencia jsonb, p_efectivo numeric
) RETURNS TABLE (venda_id bigint, valor_total numeric(14,2))
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    v_status text;
    v_total numeric(14,2);
    v_venda_id bigint;
    v_efectivo numeric(14,2);
    v_otro numeric(14,2);
    v_recebido_em timestamptz;
    v_existente public.vendas%ROWTYPE;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.usuarios AS u WHERE u.id = p_usuario_id
        AND u.ativo AND u.perfil IN ('admin','cajero')) THEN
        RAISE EXCEPTION 'El rol no permite cobrar.' USING ERRCODE='42501';
    END IF;
    SELECT t.status INTO v_status FROM public.tickets AS t
      WHERE t.id = p_ticket_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El ticket no existe.';
    END IF;
    IF p_conferencia IS NULL OR pg_catalog.jsonb_typeof(p_conferencia) <> 'array' THEN
        RAISE EXCEPTION 'Falta la conferencia del ticket.';
    END IF;
    IF v_status = 'pago' THEN
        SELECT * INTO v_existente FROM public.vendas WHERE ticket_id=p_ticket_id;
        IF NOT FOUND OR v_existente.conferencia IS DISTINCT FROM p_conferencia
           OR v_existente.valor_efectivo IS DISTINCT FROM p_efectivo THEN
            RAISE EXCEPTION 'El ticket ya fue recibido con otra conferencia o composición.';
        END IF;
        RETURN QUERY SELECT v_existente.id, v_existente.valor_total;
        RETURN;
    END IF;
    IF v_status <> 'pendente' THEN RAISE EXCEPTION 'El ticket no está pendiente.'; END IF;
    v_recebido_em := public.fn_travar_dia_recebimento();
    IF EXISTS (SELECT 1 FROM public.fechamentos_caixa WHERE data_referencia=
        (v_recebido_em AT TIME ZONE 'America/Argentina/Cordoba')::date) THEN
        RAISE EXCEPTION 'El día ya está cerrado. No se puede registrar un nuevo recibimiento.';
    END IF;
    SELECT c.valor_total,c.valor_efectivo,c.valor_otro INTO v_total,v_efectivo,v_otro
      FROM public.fn_composicao_recebimento(p_ticket_id,p_conferencia,p_efectivo) c;

    INSERT INTO public.vendas (ticket_id, recebido_por, conferencia, valor_total,valor_efectivo,recebido_em)
      VALUES (p_ticket_id, p_usuario_id, p_conferencia, v_total,v_efectivo,v_recebido_em)
      RETURNING id INTO v_venda_id;
    UPDATE public.tickets SET status = 'pago' WHERE id = p_ticket_id;
    RETURN QUERY SELECT v_venda_id, v_total;
END;
$fn$;

CREATE FUNCTION public.fn_consultar_caixa(p_data date)
RETURNS TABLE (total_vendido numeric, efectivo_vendas numeric, valor_otro numeric,
    fundo_id bigint, fundo_inicial numeric, efectivo_segun_fondo_vendas numeric, conferencia jsonb)
LANGUAGE sql STABLE SET search_path = pg_catalog, public AS $fn$
    WITH movimento AS (
        SELECT COALESCE(SUM(v.valor_total),0) AS total,
            COALESCE(SUM(v.valor_efectivo),0) AS efectivo,COALESCE(SUM(v.valor_otro),0) AS otro,
            COALESCE(pg_catalog.jsonb_agg((pg_catalog.to_jsonb(v)-'recebido_em') ||
                pg_catalog.jsonb_build_object('recebido_em',v.recebido_em AT TIME ZONE 'UTC')
                ORDER BY v.id),'[]'::jsonb) AS vendas
        FROM public.vendas v
        WHERE (v.recebido_em AT TIME ZONE 'America/Argentina/Cordoba')::date=p_data
    ), fundo AS (
        SELECT f.* FROM public.fundos_caixa f WHERE f.data_referencia=p_data ORDER BY f.id DESC LIMIT 1
    )
    SELECT m.total,m.efectivo,m.otro,f.id,f.valor,f.valor+m.efectivo,
        pg_catalog.jsonb_build_object('data',p_data,'movimento',
            pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(m.vendas::text,'UTF8')),'hex'),'fundo',
            CASE WHEN f.id IS NULL THEN NULL ELSE (pg_catalog.to_jsonb(f)-'registrado_em') ||
                pg_catalog.jsonb_build_object('registrado_em',f.registrado_em AT TIME ZONE 'UTC') END)
    FROM movimento m LEFT JOIN fundo f ON true;
$fn$;

CREATE FUNCTION public.fn_registrar_fundo(p_data date,p_valor numeric,p_usuario bigint,p_chave uuid)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE v_existente public.fundos_caixa%ROWTYPE; v_id bigint;
BEGIN
    IF p_data IS NULL OR p_chave IS NULL OR p_valor IS NULL OR p_valor < 0
       OR p_valor::text IN ('NaN','Infinity','-Infinity') OR p_valor<>pg_catalog.round(p_valor,2) THEN
        RAISE EXCEPTION 'Informá una fecha y un Fondo inicial válido, con hasta dos decimales.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.usuarios WHERE id=p_usuario AND ativo AND perfil IN ('admin','cajero')) THEN
        RAISE EXCEPTION 'El rol no permite operar la caja.' USING ERRCODE='42501';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(3,p_data-DATE '2000-01-01');
    SELECT * INTO v_existente FROM public.fundos_caixa WHERE chave_registro=p_chave;
    IF FOUND THEN
        IF v_existente.data_referencia IS DISTINCT FROM p_data OR v_existente.valor IS DISTINCT FROM p_valor
           OR v_existente.registrado_por IS DISTINCT FROM p_usuario THEN
            RAISE EXCEPTION 'Esta identificación de fondo ya fue usada con otros datos.';
        END IF;
        RETURN v_existente.id;
    END IF;
    INSERT INTO public.fundos_caixa(chave_registro,data_referencia,valor,registrado_por)
        VALUES(p_chave,p_data,p_valor,p_usuario) RETURNING id INTO v_id;
    RETURN v_id;
END;
$fn$;

CREATE FUNCTION public.fn_fechar_caixa(
    p_data date,p_usuario bigint,p_conferencia jsonb,p_contado numeric,p_chave uuid
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE v_estado record; v_existente public.fechamentos_caixa%ROWTYPE; v_id bigint;
BEGIN
    IF p_data IS NULL OR p_chave IS NULL OR p_conferencia IS NULL THEN
        RAISE EXCEPTION 'Falta la conferencia del Cierre.';
    END IF;
    IF p_contado IS NOT NULL AND (p_contado<0 OR p_contado<>pg_catalog.round(p_contado,2)
        OR p_contado::text IN ('NaN','Infinity','-Infinity')) THEN
        RAISE EXCEPTION 'Efectivo contado inválido.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.usuarios WHERE id=p_usuario AND ativo AND perfil IN ('admin','cajero')) THEN
        RAISE EXCEPTION 'El rol no permite operar la caja.' USING ERRCODE='42501';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(3,p_data-DATE '2000-01-01');
    SELECT * INTO v_existente FROM public.fechamentos_caixa WHERE data_referencia=p_data;
    IF FOUND THEN
        IF v_existente.chave_confirmacao=p_chave AND v_existente.conferencia=p_conferencia
           AND v_existente.valor_contado IS NOT DISTINCT FROM p_contado THEN RETURN v_existente.id; END IF;
        RAISE EXCEPTION 'El día ya tiene un Cierre definitivo.';
    END IF;
    SELECT * INTO v_estado FROM public.fn_consultar_caixa(p_data);
    IF v_estado.fundo_id IS NULL THEN RAISE EXCEPTION 'Informá el Fondo inicial antes de confirmar el Cierre.'; END IF;
    IF v_estado.conferencia IS DISTINCT FROM p_conferencia THEN
        RAISE EXCEPTION 'El movimiento o el fondo cambió. Volvé a revisar el Cierre y el conteo físico.';
    END IF;
    INSERT INTO public.fechamentos_caixa(chave_confirmacao,data_referencia,conferencia,fundo_id,fundo_inicial,
        total_vendido,efectivo_vendas,valor_otro,valor_contado,fechado_por)
        VALUES(p_chave,p_data,p_conferencia,v_estado.fundo_id,v_estado.fundo_inicial,
            v_estado.total_vendido,v_estado.efectivo_vendas,v_estado.valor_otro,p_contado,p_usuario)
        RETURNING id INTO v_id;
    RETURN v_id;
END;
$fn$;

-- 6. Views seguras e auditoria
CREATE VIEW public.vw_usuarios AS
SELECT u.id, u.nome, u.login, u.perfil, u.ativo, u.criado_em FROM public.usuarios AS u;

CREATE VIEW public.vw_estoque_por_produto AS
SELECT p.id AS produto_id, t.nome AS tipo, p.nome AS produto, p.unidade_medida,
    p.largura_metros, p.preco_unitario,
    CASE WHEN p.unidade_medida='un' THEN a.quantidade_atual ELSE COALESCE(SUM(l.quantidade_atual) FILTER
        (WHERE l.status_operacional IN ('fechado', 'aberto')), 0) END AS estoque_total,
    CASE WHEN p.unidade_medida='un' THEN NULL ELSE COALESCE(MAX(l.quantidade_atual) FILTER
        (WHERE l.status_operacional IN ('fechado', 'aberto')), 0) END AS maior_lote_disponivel,
    CASE WHEN p.unidade_medida='un' THEN NULL ELSE COUNT(l.id) FILTER (WHERE l.status_operacional = 'aberto') END AS rolos_abertos,
    CASE WHEN p.unidade_medida='un' THEN NULL ELSE COUNT(l.id) FILTER (WHERE l.status_operacional = 'fechado') END AS rolos_fechados,
    p.ativo,CASE WHEN p.unidade_medida='un' THEN 'agregado' ELSE 'fisico' END AS modo
FROM public.produtos AS p JOIN public.tipos_tela AS t ON t.id = p.tipo_id
LEFT JOIN public.estoque_lotes AS l ON l.produto_id = p.id LEFT JOIN public.estoque_agregado a ON a.produto_id=p.id GROUP BY p.id, t.nome,a.quantidade_atual;

-- A melhor escolha depende da quantidade pedida e cabe a consulta/servico.
CREATE VIEW public.vw_lotes_disponiveis AS
SELECT l.id AS lote_id, l.codigo_interno, p.id AS produto_id, p.nome AS produto,
    t.nome AS tipo, p.unidade_medida, p.largura_metros, l.quantidade_inicial,
    l.quantidade_atual, l.status_operacional, l.condicao_fisica, l.aberto_em, l.criado_em
FROM public.estoque_lotes AS l JOIN public.produtos AS p ON p.id = l.produto_id
JOIN public.tipos_tela AS t ON t.id = p.tipo_id
WHERE l.status_operacional IN ('fechado', 'aberto');

CREATE VIEW public.vw_historico_lote AS
SELECT l.id AS lote_id, l.codigo_interno AS codigo_lote, p.nome AS produto,
    m.tipo, m.quantidade,
    CASE WHEN m.tipo IN ('ENTRADA', 'AJUSTE_ENTRADA') THEN m.quantidade
         WHEN m.tipo IN ('CORTE', 'AJUSTE_SAIDA', 'PERDA') THEN -m.quantidade END AS efeito_saldo,
    m.referencia_tipo, m.referencia_id, u.nome AS usuario_informado,
    m.criado_em, m.observacao, l.quantidade_atual AS saldo_atual_lote
FROM public.movimentacoes AS m JOIN public.estoque_lotes AS l ON l.id = m.lote_id
JOIN public.produtos AS p ON p.id = m.produto_id
JOIN public.usuarios AS u ON u.id = m.usuario_id;

CREATE VIEW public.vw_reconciliacao_estoque AS
SELECT l.produto_id,'fisico'::text AS modo,l.id AS lote_id,l.codigo_interno,l.quantidade_atual AS saldo_registrado,
    COALESCE(SUM(CASE WHEN m.tipo IN ('ENTRADA', 'AJUSTE_ENTRADA') THEN m.quantidade
        WHEN m.tipo IN ('CORTE', 'AJUSTE_SAIDA', 'PERDA') THEN -m.quantidade END), 0
    )::numeric(12,3) AS saldo_reconstruido,
    (l.quantidade_atual - COALESCE(SUM(CASE
        WHEN m.tipo IN ('ENTRADA', 'AJUSTE_ENTRADA') THEN m.quantidade
        WHEN m.tipo IN ('CORTE', 'AJUSTE_SAIDA', 'PERDA') THEN -m.quantidade END), 0)
    )::numeric(12,3) AS diferenca
FROM public.estoque_lotes AS l LEFT JOIN public.movimentacoes AS m ON m.lote_id = l.id
GROUP BY l.id
UNION ALL
SELECT a.produto_id,'agregado',NULL,NULL,a.quantidade_atual,
 COALESCE(SUM(CASE WHEN m.tipo IN ('ENTRADA','AJUSTE_ENTRADA') THEN m.quantidade ELSE -m.quantidade END),0),
 a.quantidade_atual-COALESCE(SUM(CASE WHEN m.tipo IN ('ENTRADA','AJUSTE_ENTRADA') THEN m.quantidade ELSE -m.quantidade END),0)
FROM public.estoque_agregado a LEFT JOIN public.movimentacoes m ON m.produto_id=a.produto_id AND m.lote_id IS NULL GROUP BY a.produto_id;
CREATE VIEW public.vw_historico_produto AS
SELECT m.*,p.unidade_medida,u.nome AS usuario_informado,
 CASE WHEN m.tipo IN ('ENTRADA','AJUSTE_ENTRADA') THEN m.quantidade ELSE -m.quantidade END AS efeito_saldo,
 SUM(CASE WHEN m.tipo IN ('ENTRADA','AJUSTE_ENTRADA') THEN m.quantidade ELSE -m.quantidade END)
 OVER(PARTITION BY m.produto_id ORDER BY m.id ROWS UNBOUNDED PRECEDING) AS saldo_depois
FROM public.movimentacoes m JOIN public.produtos p ON p.id=m.produto_id JOIN public.usuarios u ON u.id=m.usuario_id;

-- Invariantes comuns aos dois modelos, verificadas ao fim da transação.
CREATE FUNCTION public.fn_integridade_unidades() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $fn$
BEGIN
 IF EXISTS(SELECT 1 FROM public.estoque_lotes l JOIN public.produtos p ON p.id=l.produto_id WHERE p.unidade_medida='un')
 OR EXISTS(SELECT 1 FROM public.estoque_agregado a JOIN public.produtos p ON p.id=a.produto_id WHERE p.unidade_medida<>'un')
 OR EXISTS(SELECT 1 FROM public.produtos p WHERE p.unidade_medida='un' AND NOT EXISTS(SELECT 1 FROM public.estoque_agregado a WHERE a.produto_id=p.id)) THEN
  RAISE EXCEPTION 'Modelo de stock incompatible con la unidad.'; END IF;
 IF EXISTS(
  SELECT 1 FROM (
   SELECT e.id AS doc,(g->>'produto_id')::bigint AS produto,(g->>'quantidade')::numeric AS quantidade,
    sum(CASE WHEN g->>'unidade'='un' THEN 1 ELSE COALESCE(g->>'rolos',g->>'pecas')::numeric END) AS numero
   FROM public.ingressos e CROSS JOIN LATERAL jsonb_array_elements(e.grupos_declarados) g
   GROUP BY e.id,(g->>'produto_id')::bigint,(g->>'quantidade')::numeric
  ) d WHERE d.numero IS NULL OR d.numero<>(SELECT count(*) FROM public.itens_ingresso i
    WHERE i.ingresso_id=d.doc AND i.produto_id=d.produto AND i.quantidade=d.quantidade)
 ) OR EXISTS(SELECT 1 FROM public.itens_ingresso i JOIN public.produtos p ON p.id=i.produto_id JOIN public.ingressos e ON e.id=i.ingresso_id
   WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(e.grupos_declarados) g WHERE (g->>'produto_id')::bigint=i.produto_id
     AND (g->>'quantidade')::numeric=i.quantidade AND g->>'unidade'=p.unidade_medida)) THEN
  RAISE EXCEPTION 'Los items no corresponden a la declaración del ingreso.'; END IF;
 IF EXISTS(SELECT 1 FROM public.itens_ingresso i JOIN public.produtos p ON p.id=i.produto_id
  WHERE (p.unidade_medida='un' AND (i.quantidade<>trunc(i.quantidade) OR EXISTS(SELECT 1 FROM public.estoque_lotes l WHERE l.item_ingresso_id=i.id)))
   OR (p.unidade_medida<>'un' AND (SELECT count(*) FROM public.estoque_lotes l WHERE l.item_ingresso_id=i.id AND l.produto_id=i.produto_id AND l.quantidade_inicial=i.quantidade)<>1)
   OR (SELECT count(*) FROM public.movimentacoes m WHERE m.item_ingresso_id=i.id AND m.tipo='ENTRADA')<>1) THEN
  RAISE EXCEPTION 'Ingreso incompleto o incompatible.'; END IF;
 IF EXISTS(SELECT 1 FROM public.movimentacoes m JOIN public.produtos p ON p.id=m.produto_id
  LEFT JOIN public.itens_ingresso e ON e.id=m.item_ingresso_id LEFT JOIN public.itens_ticket i ON i.id=m.item_ticket_id
  WHERE m.quantidade<=0 OR m.quantidade<>round(m.quantidade,3) OR m.quantidade::text IN ('NaN','Infinity','-Infinity')
   OR (p.unidade_medida='un' AND (m.lote_id IS NOT NULL OR m.quantidade<>trunc(m.quantidade)))
   OR (p.unidade_medida<>'un' AND m.lote_id IS NULL)
   OR (m.tipo='ENTRADA' AND (e.id IS NULL OR e.produto_id<>m.produto_id OR e.quantidade<>m.quantidade OR m.referencia_tipo IS DISTINCT FROM 'ingresso' OR m.referencia_id IS DISTINCT FROM e.ingresso_id
     OR m.item_ticket_id IS NOT NULL OR (p.unidade_medida<>'un' AND NOT EXISTS(SELECT 1 FROM public.estoque_lotes l WHERE l.id=m.lote_id AND l.item_ingresso_id=e.id))))
   OR (m.tipo='CORTE' AND (i.id IS NULL OR i.produto_id<>m.produto_id OR m.item_ingresso_id IS NOT NULL OR m.referencia_tipo IS DISTINCT FROM 'ticket' OR m.referencia_id IS DISTINCT FROM i.ticket_id
    OR (p.unidade_medida='un' AND m.quantidade<>i.quantidade_cortada)
    OR (p.unidade_medida<>'un' AND NOT EXISTS(SELECT 1 FROM public.alocacoes_estoque a WHERE a.item_ticket_id=i.id AND a.lote_id=m.lote_id AND a.quantidade=m.quantidade))))) THEN
  RAISE EXCEPTION 'Movimiento incompatible con su documento o unidad.'; END IF;
 IF EXISTS(SELECT 1 FROM public.itens_ticket i JOIN public.produtos p ON p.id=i.produto_id
  WHERE (p.unidade_medida='un' AND (i.quantidade_vendida<>i.quantidade_cortada OR i.quantidade_vendida<>trunc(i.quantidade_vendida) OR i.quantidade_cortada<>trunc(i.quantidade_cortada)
   OR i.alocacoes_declaradas<>'[]'::jsonb OR EXISTS(SELECT 1 FROM public.alocacoes_estoque a WHERE a.item_ticket_id=i.id)
   OR (SELECT count(*) FROM public.movimentacoes m WHERE m.item_ticket_id=i.id AND m.tipo='CORTE')<>1))
   OR (p.unidade_medida<>'un' AND ((SELECT count(*) FROM public.alocacoes_estoque a WHERE a.item_ticket_id=i.id)=0
    OR EXISTS(SELECT 1 FROM public.alocacoes_estoque a WHERE a.item_ticket_id=i.id AND
      (SELECT count(*) FROM public.movimentacoes m WHERE m.item_ticket_id=i.id AND m.lote_id=a.lote_id AND m.tipo='CORTE' AND m.quantidade=a.quantidade)<>1)))) THEN
  RAISE EXCEPTION 'Retirada incompleta o incompatible.'; END IF;
 IF EXISTS(SELECT 1 FROM public.vw_reconciliacao_estoque WHERE diferenca<>0) THEN RAISE EXCEPTION 'Stock y movimientos no concilian.'; END IF;
 RETURN NULL;
END; $fn$;
DO $triggers$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['ingressos','produtos','estoque_agregado','estoque_lotes','itens_ingresso','itens_ticket','alocacoes_estoque','movimentacoes'] LOOP
  EXECUTE format('CREATE CONSTRAINT TRIGGER trg_unidades_integras AFTER INSERT OR UPDATE OR DELETE ON public.%I DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.fn_integridade_unidades()',t);
 END LOOP;
END; $triggers$;
CREATE FUNCTION public.fn_unidade_estavel() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $fn$
BEGIN
 IF NEW.unidade_medida IS DISTINCT FROM OLD.unidade_medida AND (
   EXISTS(SELECT 1 FROM public.estoque_agregado WHERE produto_id=OLD.id) OR EXISTS(SELECT 1 FROM public.estoque_lotes WHERE produto_id=OLD.id)
   OR EXISTS(SELECT 1 FROM public.itens_ingresso WHERE produto_id=OLD.id) OR EXISTS(SELECT 1 FROM public.itens_ticket WHERE produto_id=OLD.id)
   OR EXISTS(SELECT 1 FROM public.movimentacoes WHERE produto_id=OLD.id)) THEN RAISE EXCEPTION 'No se puede convertir la unidad de un producto con registros.'; END IF;
 RETURN NEW;
END; $fn$;
CREATE TRIGGER trg_unidade_estavel BEFORE UPDATE OF unidade_medida ON public.produtos FOR EACH ROW EXECUTE FUNCTION public.fn_unidade_estavel();
ALTER FUNCTION public.fn_unidade_estavel() OWNER TO loja_owner;
ALTER FUNCTION public.fn_integridade_unidades() OWNER TO loja_owner;

-- 7. Ownership e permissoes
ALTER TABLE public.unidades_medida OWNER TO loja_owner;
ALTER TABLE public.tipos_tela OWNER TO loja_owner;
ALTER TABLE public.produtos OWNER TO loja_owner;
ALTER TABLE public.estoque_agregado OWNER TO loja_owner;
ALTER VIEW public.vw_historico_produto OWNER TO loja_owner;
ALTER TABLE public.usuarios OWNER TO loja_owner;
ALTER TABLE public.ingressos OWNER TO loja_owner;
ALTER TABLE public.itens_ingresso OWNER TO loja_owner;
ALTER TABLE public.estoque_lotes OWNER TO loja_owner;
ALTER TABLE public.movimentacoes OWNER TO loja_owner;
ALTER TABLE public.tickets OWNER TO loja_owner;
ALTER TABLE public.itens_ticket OWNER TO loja_owner;
ALTER TABLE public.alocacoes_estoque OWNER TO loja_owner;
ALTER TABLE public.vendas OWNER TO loja_owner;
ALTER TABLE public.fechamentos_caixa OWNER TO loja_owner;
ALTER TABLE public.fundos_caixa OWNER TO loja_owner;

-- O ownership das sequences de IDENTITY acompanha automaticamente as tabelas.
ALTER SEQUENCE public.estoque_lote_codigo_seq OWNER TO loja_owner;

ALTER VIEW public.vw_usuarios OWNER TO loja_owner;
ALTER VIEW public.vw_estoque_por_produto OWNER TO loja_owner;
ALTER VIEW public.vw_lotes_disponiveis OWNER TO loja_owner;
ALTER VIEW public.vw_historico_lote OWNER TO loja_owner;
ALTER VIEW public.vw_reconciliacao_estoque OWNER TO loja_owner;

ALTER FUNCTION public.fn_validar_item_alocacoes(bigint) OWNER TO loja_owner;
ALTER FUNCTION public.fn_trigger_validar_item_alocacoes() OWNER TO loja_owner;
ALTER FUNCTION public.fn_trigger_validar_item() OWNER TO loja_owner;
ALTER FUNCTION public.fn_validar_saldo_lote(bigint) OWNER TO loja_owner;
ALTER FUNCTION public.fn_trigger_validar_saldo_lote() OWNER TO loja_owner;
ALTER FUNCTION public.fn_preservar_declaracao_ingresso() OWNER TO loja_owner;
ALTER FUNCTION public.fn_gerar_codigo_ticket() OWNER TO loja_owner;
ALTER FUNCTION public.fn_cadastrar_produto(bigint, text, text, numeric, bigint, numeric, numeric) OWNER TO loja_owner;
ALTER FUNCTION public.fn_confirmar_ingresso(uuid, jsonb, bigint, text) OWNER TO loja_owner;
ALTER FUNCTION public.fn_autenticar_usuario(text, text) OWNER TO loja_owner;
ALTER FUNCTION public.fn_iniciar_ticket(uuid, bigint) OWNER TO loja_owner;
ALTER FUNCTION public.fn_adicionar_item_corte(bigint, bigint, numeric, numeric, jsonb, bigint, uuid) OWNER TO loja_owner;
ALTER FUNCTION public.fn_finalizar_venda(bigint, bigint, jsonb, numeric) OWNER TO loja_owner;
ALTER FUNCTION public.fn_composicao_recebimento(bigint, jsonb, numeric) OWNER TO loja_owner;
ALTER FUNCTION public.fn_conferencia_ticket(bigint) OWNER TO loja_owner;
ALTER FUNCTION public.fn_fechar_caixa(date, bigint, jsonb, numeric, uuid) OWNER TO loja_owner;
ALTER FUNCTION public.fn_consultar_caixa(date) OWNER TO loja_owner;
ALTER FUNCTION public.fn_registrar_fundo(date, numeric, bigint, uuid) OWNER TO loja_owner;
ALTER FUNCTION public.fn_data_operacional() OWNER TO loja_owner;
ALTER FUNCTION public.fn_travar_dia_recebimento() OWNER TO loja_owner;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC, loja_operador, loja_admin;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, loja_operador, loja_admin;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, loja_operador, loja_admin;

GRANT SELECT ON public.unidades_medida, public.tipos_tela, public.produtos,
    public.ingressos, public.itens_ingresso, public.estoque_lotes, public.estoque_agregado,public.vw_historico_produto,
    public.movimentacoes, public.tickets, public.itens_ticket,
    public.alocacoes_estoque, public.vendas, public.fechamentos_caixa, public.fundos_caixa,
    public.vw_usuarios, public.vw_estoque_por_produto,
    public.vw_lotes_disponiveis, public.vw_historico_lote,
    public.vw_reconciliacao_estoque
TO loja_operador, loja_admin;

GRANT EXECUTE ON FUNCTION
    public.fn_iniciar_ticket(uuid, bigint),
    public.fn_adicionar_item_corte(bigint, bigint, numeric, numeric, jsonb, bigint, uuid),
    public.fn_finalizar_venda(bigint, bigint, jsonb, numeric),
    public.fn_composicao_recebimento(bigint, jsonb, numeric),
    public.fn_conferencia_ticket(bigint),
    public.fn_fechar_caixa(date, bigint, jsonb, numeric, uuid),
    public.fn_consultar_caixa(date),
    public.fn_registrar_fundo(date, numeric, bigint, uuid),
    public.fn_data_operacional(),
    public.fn_travar_dia_recebimento()
TO loja_operador, loja_admin;
GRANT EXECUTE ON FUNCTION
    public.fn_cadastrar_produto(bigint, text, text, numeric, bigint, numeric, numeric),
    public.fn_confirmar_ingresso(uuid, jsonb, bigint, text),
    public.fn_autenticar_usuario(text, text)
TO loja_operador, loja_admin;
GRANT EXECUTE ON FUNCTION public.crypt(text, text) TO loja_owner;

ALTER DEFAULT PRIVILEGES FOR ROLE loja_owner IN SCHEMA public
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

COMMENT ON COLUMN public.movimentacoes.usuario_id IS
    'Identidade informada para auditoria; nao constitui prova de autoria.';
COMMENT ON COLUMN public.ingressos.registrado_por IS
    'Identidade informada para auditoria; nao constitui prova de autoria.';
COMMENT ON COLUMN public.tickets.atendido_por IS
    'Identidade informada para auditoria; nao constitui prova de autoria.';
COMMENT ON COLUMN public.itens_ticket.cortado_por IS
    'Responsável informado por retirada, independente de quem iniciou o ticket; não prova autoria.';

-- Extensão Precios / foto principal. Mesmo conteúdo da migração aditiva.
-- Instalação única e transacional, incluindo preços e fotos.
CREATE TABLE public.lotes_precos (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 chave uuid NOT NULL UNIQUE,
 alteracoes jsonb NOT NULL,
 registrado_por bigint NOT NULL REFERENCES public.usuarios(id),
 registrado_em timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE public.historico_precos (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 lote_id bigint NOT NULL REFERENCES public.lotes_precos(id),
 produto_id bigint NOT NULL REFERENCES public.produtos(id),
 preco_anterior numeric(12,2) NOT NULL CHECK(preco_anterior>=0),
 preco_novo numeric(12,2) NOT NULL CHECK(preco_novo>=0),
 registrado_em timestamptz NOT NULL,
 UNIQUE(lote_id,produto_id)
);
CREATE TABLE public.fotos_produto (
 produto_id bigint PRIMARY KEY REFERENCES public.produtos(id),
 imagem bytea NOT NULL CHECK(octet_length(imagem) BETWEEN 1 AND 8388608),
 miniatura bytea NOT NULL CHECK(octet_length(miniatura) BETWEEN 1 AND 1048576),
 mime text NOT NULL CHECK(mime IN ('image/jpeg','image/png')),
 largura integer NOT NULL CHECK(largura BETWEEN 1 AND 4096),
 altura integer NOT NULL CHECK(altura BETWEEN 1 AND 4096),
 atualizado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK(largura::bigint*altura<=12000000)
);
CREATE FUNCTION public.fn_alterar_precos(p_chave uuid,p_alteracoes jsonb,p_usuario bigint)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $fn$
DECLARE lote_anterior public.lotes_precos%ROWTYPE; lote bigint; r record; atual numeric; momento timestamptz;
BEGIN
 IF p_chave IS NULL OR jsonb_typeof(p_alteracoes) IS DISTINCT FROM 'array' OR jsonb_array_length(p_alteracoes)=0 THEN
  RAISE EXCEPTION 'Lote inválido'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.usuarios WHERE id=p_usuario AND ativo AND perfil='admin') THEN
  RAISE EXCEPTION 'El rol no permite cambiar precios.' USING ERRCODE='42501'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('precios:'||p_chave::text,0));
 SELECT * INTO lote_anterior FROM public.lotes_precos WHERE chave=p_chave;
 IF FOUND THEN
  IF lote_anterior.alteracoes IS DISTINCT FROM p_alteracoes OR lote_anterior.registrado_por<>p_usuario THEN
   RAISE EXCEPTION 'Reenvio diferente'; END IF;
  RETURN lote_anterior.id;
 END IF;
 IF EXISTS(SELECT 1 FROM jsonb_to_recordset(p_alteracoes) AS a(produto_id bigint,anterior numeric,novo numeric)
   WHERE produto_id IS NULL OR anterior IS NULL OR novo IS NULL OR novo<0 OR anterior<0
     OR novo::text IN ('NaN','Infinity','-Infinity') OR anterior::text IN ('NaN','Infinity','-Infinity')
     OR novo<>round(novo,2) OR anterior<>round(anterior,2) OR novo>=10000000000 OR anterior>=10000000000 OR novo=anterior)
 OR (SELECT count(*)<>count(DISTINCT produto_id) FROM jsonb_to_recordset(p_alteracoes) AS a(produto_id bigint)) THEN
  RAISE EXCEPTION 'Preços inválidos'; END IF;
 -- Ordem estável e valores revisados: não há sobrescrita silenciosa nem merge.
 FOR r IN SELECT * FROM jsonb_to_recordset(p_alteracoes) AS a(produto_id bigint,anterior numeric,novo numeric) ORDER BY produto_id LOOP
  SELECT preco_unitario INTO atual FROM public.produtos WHERE id=r.produto_id FOR UPDATE;
  IF NOT FOUND OR atual IS DISTINCT FROM r.anterior THEN RAISE EXCEPTION 'Revisão desatualizada'; END IF;
 END LOOP;
 momento:=clock_timestamp();
 INSERT INTO public.lotes_precos(chave,alteracoes,registrado_por,registrado_em)
 VALUES(p_chave,p_alteracoes,p_usuario,momento) RETURNING id INTO lote;
 FOR r IN SELECT * FROM jsonb_to_recordset(p_alteracoes) AS a(produto_id bigint,anterior numeric,novo numeric) LOOP
  UPDATE public.produtos SET preco_unitario=r.novo WHERE id=r.produto_id;
  INSERT INTO public.historico_precos(lote_id,produto_id,preco_anterior,preco_novo,registrado_em)
  VALUES(lote,r.produto_id,r.anterior,r.novo,momento);
 END LOOP;
 RETURN lote;
END; $fn$;
CREATE FUNCTION public.fn_guardar_foto(p_produto bigint,p_imagem bytea,p_miniatura bytea,p_mime text,p_largura integer,p_altura integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $fn$
BEGIN
 INSERT INTO public.fotos_produto(produto_id,imagem,miniatura,mime,largura,altura)
 VALUES(p_produto,p_imagem,p_miniatura,p_mime,p_largura,p_altura)
 ON CONFLICT(produto_id) DO UPDATE SET imagem=excluded.imagem,miniatura=excluded.miniatura,
 mime=excluded.mime,largura=excluded.largura,altura=excluded.altura,atualizado_em=clock_timestamp()
 WHERE fotos_produto.imagem IS DISTINCT FROM excluded.imagem;
END; $fn$;
ALTER TABLE public.lotes_precos OWNER TO loja_owner;
ALTER TABLE public.historico_precos OWNER TO loja_owner;
ALTER TABLE public.fotos_produto OWNER TO loja_owner;
ALTER FUNCTION public.fn_alterar_precos(uuid,jsonb,bigint) OWNER TO loja_owner;
ALTER FUNCTION public.fn_guardar_foto(bigint,bytea,bytea,text,integer,integer) OWNER TO loja_owner;
REVOKE ALL ON public.lotes_precos,public.historico_precos,public.fotos_produto FROM PUBLIC,loja_operador,loja_admin;
REVOKE ALL ON FUNCTION public.fn_alterar_precos(uuid,jsonb,bigint),public.fn_guardar_foto(bigint,bytea,bytea,text,integer,integer) FROM PUBLIC,loja_operador,loja_admin;
GRANT SELECT ON public.lotes_precos,public.historico_precos,public.fotos_produto TO loja_operador,loja_admin;
GRANT EXECUTE ON FUNCTION public.fn_alterar_precos(uuid,jsonb,bigint),public.fn_guardar_foto(bigint,bytea,bytea,text,integer,integer) TO loja_operador,loja_admin;
COMMENT ON COLUMN public.lotes_precos.registrado_por IS 'Responsável informado; sessão compartilhada e PIN não comprovam autoria individual.';
COMMIT;
