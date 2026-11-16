from uuid import uuid4

from flask import Blueprint, abort, g, redirect, render_template, request, url_for
from .. import db
from ..corte import seal, unseal

ticket_bp = Blueprint('ticket', __name__)


def get_ticket(ticket_id):
    row = db.fetchone('''SELECT t.*,u.nome AS iniciado_por,
        (SELECT COALESCE(sum(i.valor_total),0) FROM public.itens_ticket i
         WHERE i.ticket_id=t.id) AS total
        FROM public.tickets t JOIN public.vw_usuarios u ON u.id=t.atendido_por
        WHERE t.id=%s''', (ticket_id,))
    if not row:
        abort(404)
    return row


@ticket_bp.get('/tickets')
def index():
    code = request.args.get('codigo','').strip().upper()
    tickets = db.fetchall('''SELECT t.id,t.codigo,t.criado_em,u.nome AS iniciado_por,
        COALESCE(sum(i.valor_total),0) AS total,count(i.id) AS itens
        FROM public.tickets t JOIN public.vw_usuarios u ON u.id=t.atendido_por
        LEFT JOIN public.itens_ticket i ON i.ticket_id=t.id
        WHERE t.status='pendente' AND (%s='' OR t.codigo=%s)
        GROUP BY t.id,u.nome ORDER BY t.id DESC''', (code,code))
    return render_template('tickets.html', tickets=tickets, codigo=code,
        novo=seal({'chave':str(uuid4()), 'usuario_id':g.usuario['id']},'ticket'))


@ticket_bp.post('/tickets/nuevo')
def nuevo():
    draft = unseal(request.form.get('envio',''),'ticket')
    ticket_id = db.iniciar_ticket(draft['chave'], g.usuario['id'])
    return redirect(url_for('corte.productos',ticket_id=ticket_id))


@ticket_bp.get('/tickets/<int:ticket_id>')
@db.read_snapshot
def exibir(ticket_id):
    ticket = get_ticket(ticket_id)
    items = get_items(ticket_id)
    lots = db.fetchall('''SELECT a.item_ticket_id,a.quantidade,l.codigo_interno
        FROM public.alocacoes_estoque a JOIN public.estoque_lotes l ON l.id=a.lote_id
        JOIN public.itens_ticket i ON i.id=a.item_ticket_id
        WHERE i.ticket_id=%s ORDER BY a.item_ticket_id,l.id''', (ticket_id,))
    allocations = {}
    for lot in lots:
        allocations.setdefault(lot['item_ticket_id'],[]).append(lot)
    return render_template('ticket.html',ticket=ticket,itens=items,alocacoes=allocations,
        busca={'q':request.args.get('q',''),'categoria':request.args.get('categoria','')})


def get_items(ticket_id):
    return db.fetchall('''SELECT i.*,p.nome AS produto,p.unidade_medida,u.nome AS cortado_por_nome,
            EXISTS(SELECT 1 FROM public.fotos_produto f WHERE f.produto_id=p.id) AS tem_foto
        FROM public.itens_ticket i JOIN public.produtos p ON p.id=i.produto_id
        JOIN public.vw_usuarios u ON u.id=i.cortado_por
        WHERE i.ticket_id=%s ORDER BY i.id''', (ticket_id,))
