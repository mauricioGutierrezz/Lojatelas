"""Consultas parametrizadas con transacción, rol restringido y cierre seguro."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_snapshot=ContextVar("stock_snapshot",default=None)

import psycopg2
from psycopg2.extras import RealDictCursor
from .config import DB_CONFIG


@contextmanager
def transaction():
    existing=_snapshot.get()
    if existing is not None:
        yield existing
        return
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        conn.set_client_encoding('UTF8')
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SET LOCAL ROLE loja_operador")
                cursor.execute("SET LOCAL TIME ZONE 'America/Argentina/Cordoba'")
                yield cursor
    finally:
        conn.close()


def read_snapshot(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        with transaction() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            token=_snapshot.set(cursor)
            try:
                return fn(*args,**kwargs)
            finally:
                _snapshot.reset(token)
    return wrapped


def fetchall(sql, params=()):
    with transaction() as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def fetchone(sql, params=()):
    with transaction() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def guardar_foto_cursor(cursor,produto_id,foto):
    cursor.execute('SELECT public.fn_guardar_foto(%s,%s,%s,%s,%s,%s)',
        (produto_id,foto['imagem'],foto['miniatura'],foto['mime'],foto['largura'],foto['altura']))


def guardar_foto(produto_id,foto):
    with transaction() as cursor:
        guardar_foto_cursor(cursor,produto_id,foto)


def cadastrar_produto(data, usuario_id, foto=None):
    with transaction() as cursor:
        cursor.execute("SELECT public.fn_cadastrar_produto(%s,%s,%s,%s,%s,%s,%s) AS id",
            (data['tipo_id'],data['nome'],data['unidade'],data['preco'],usuario_id,data['largura'],data['padrao']))
        produto_id = cursor.fetchone()['id']
        if foto:
            guardar_foto_cursor(cursor,produto_id,foto)
        return produto_id


def alterar_precos(draft,usuario_id):
    from psycopg2.extras import Json
    return fetchone('SELECT public.fn_alterar_precos(%s::uuid,%s::jsonb,%s) AS id',
        (draft['chave'],Json(draft['alteracoes']),usuario_id))['id']


def confirmar_ingresso(chave, grupos, usuario_id):
    from psycopg2.extras import Json
    row = fetchone(
        "SELECT public.fn_confirmar_ingresso(%s::uuid,%s::jsonb,%s) AS id",
        (chave, Json(grupos), usuario_id),
    )
    return row['id']


def iniciar_ticket(chave, usuario_id):
    return fetchone('SELECT public.fn_iniciar_ticket(%s::uuid,%s) AS id', (chave, usuario_id))['id']


def registrar_corte(draft, usuario_id):
    from psycopg2.extras import Json
    return fetchone('SELECT public.fn_adicionar_item_corte(%s,%s,%s,%s,%s::jsonb,%s,%s::uuid) AS id',
        (draft['ticket_id'], draft['produto_id'], draft['quantidade_vendida'],
         draft['quantidade_cortada'], Json(draft['alocacoes']),
         usuario_id, draft['chave']))['id']


def conferir_ticket(ticket_id):
    # Una única instantánea mantiene coherente la pantalla sin reservar el ticket.
    # La confirmación vuelve a validar estos items bajo lock en el banco.
    with transaction() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cursor.execute('''SELECT t.*,u.nome AS iniciado_por FROM public.tickets t
            JOIN public.vw_usuarios u ON u.id=t.atendido_por
            WHERE t.id=%s''', (ticket_id,))
        row = cursor.fetchone()
        if not row:
            return None
        ticket = dict(row)
        cursor.execute('SELECT EXISTS (SELECT 1 FROM public.fechamentos_caixa '
            'WHERE data_referencia=public.fn_data_operacional()) AS dia_fechado')
        ticket.update(dict(cursor.fetchone()))
        cursor.execute('''SELECT i.*,p.nome AS produto,p.unidade_medida,u.nome AS cortado_por_nome,
            EXISTS(SELECT 1 FROM public.fotos_produto f WHERE f.produto_id=p.id) AS tem_foto
            FROM public.itens_ticket i JOIN public.produtos p ON p.id=i.produto_id
            JOIN public.vw_usuarios u ON u.id=i.cortado_por
            WHERE i.ticket_id=%s ORDER BY i.id''', (ticket_id,))
        items = [dict(item) for item in cursor.fetchall()]
        cursor.execute('''SELECT COALESCE(sum(i.valor_total),0) AS total,
            public.fn_conferencia_ticket(%s)::text AS conferencia
            FROM public.itens_ticket i WHERE i.ticket_id=%s''', (ticket_id,ticket_id))
        ticket.update(dict(cursor.fetchone()))
        cursor.execute('''SELECT v.id,v.valor_total,v.valor_efectivo,v.valor_otro,
            v.recebido_em,u.nome AS recebido_por_nome
            FROM public.vendas v JOIN public.vw_usuarios u ON u.id=v.recebido_por
            WHERE v.ticket_id=%s''', (ticket_id,))
        sale = cursor.fetchone()
        return ticket, items, dict(sale) if sale else None


def composicao_recebimento(draft, efectivo):
    with transaction() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cursor.execute('SELECT * FROM public.fn_composicao_recebimento(%s,%s::jsonb,%s)',
            (draft['ticket_id'],draft['conferencia'],efectivo))
        return dict(cursor.fetchone())


def receber_ticket(draft, usuario_id):
    return fetchone('SELECT * FROM public.fn_finalizar_venda(%s,%s,%s::jsonb,%s)',
        (draft['ticket_id'],usuario_id,draft['conferencia'],draft['efectivo']))


def preparar_cobro(draft, entregado, modo):
    # Solo lectura: valida la conferencia y obtiene el total del banco.
    # El mismo snapshot permite preparar la parcela sin modificar la venta.
    with transaction() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cursor.execute('SELECT * FROM public.fn_composicao_recebimento(%s,%s::jsonb,0)',
            (draft['ticket_id'],draft['conferencia']))
        total = cursor.fetchone()['valor_total']
        efectivo = total if modo=='efectivo' else 0 if modo=='otro' else min(entregado,total)
        cursor.execute('SELECT * FROM public.fn_composicao_recebimento(%s,%s::jsonb,%s)',
            (draft['ticket_id'],draft['conferencia'],efectivo))
        return dict(cursor.fetchone())


def consultar_caixa(data=None):
    with transaction() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if data is None:
            cursor.execute('SELECT public.fn_data_operacional() AS data')
            data = cursor.fetchone()['data']
        cursor.execute('SELECT c.*,c.conferencia::text AS conferencia FROM public.fn_consultar_caixa(%s) c',(data,))
        state = dict(cursor.fetchone())
        state['data'] = data
        cursor.execute('''SELECT f.*,u.nome AS responsavel FROM public.fechamentos_caixa f
            JOIN public.vw_usuarios u ON u.id=f.fechado_por WHERE f.data_referencia=%s''',(data,))
        closed = cursor.fetchone()
        cursor.execute('''SELECT f.*,u.nome AS responsavel FROM public.fundos_caixa f
            JOIN public.vw_usuarios u ON u.id=f.registrado_por
            WHERE f.data_referencia=%s ORDER BY f.id DESC''',(data,))
        return state, dict(closed) if closed else None, [dict(r) for r in cursor.fetchall()]


def registrar_fundo(draft,valor,usuario):
    return fetchone('SELECT public.fn_registrar_fundo(%s,%s,%s,%s::uuid) AS id',
        (draft['data'],valor,usuario,draft['chave']))['id']


def preparar_cierre(draft,contado):
    with transaction() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cursor.execute('''SELECT c.*,c.conferencia=%s::jsonb AS atual,
            CASE WHEN %s::numeric IS NULL THEN NULL ELSE %s::numeric-c.efectivo_segun_fondo_vendas END AS diferenca
            FROM public.fn_consultar_caixa(%s) c''',(draft['conferencia'],contado,contado,draft['data']))
        state = dict(cursor.fetchone())
        if state['fundo_id'] is None:
            raise ValueError('Informá el Fondo inicial antes de confirmar el Cierre.')
        if not state['atual']:
            raise ValueError('El movimiento o el fondo cambió. Volvé a revisar y contar si corresponde.')
        return state


def fechar_caixa(draft,usuario):
    return fetchone('SELECT public.fn_fechar_caixa(%s,%s,%s::jsonb,%s,%s::uuid) AS id',
        (draft['data'],usuario,draft['conferencia'],draft['contado'],draft['chave']))['id']
