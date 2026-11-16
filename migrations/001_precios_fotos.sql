-- Extensão aditiva: não modifica estoque, tickets, vendas ou Cierres existentes.
BEGIN;
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
