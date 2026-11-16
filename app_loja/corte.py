"""Selección y preparación sin modificar ni reservar el stock."""
from decimal import Decimal

from flask import abort, current_app, g
from itsdangerous import BadSignature, URLSafeSerializer

from .validation import decimal_input


def seal(data, purpose):
    return URLSafeSerializer(current_app.secret_key, salt=('unidades-stock-v2-' if purpose in ('preparo','corte') else 'corte-ticket-1b-')+purpose).dumps(data)


def unseal(token, purpose):
    try:
        data = URLSafeSerializer(current_app.secret_key, salt=('unidades-stock-v2-' if purpose in ('preparo','corte') else 'corte-ticket-1b-')+purpose).loads(token)
    except BadSignature:
        abort(400)
    if not isinstance(data,dict) or data.get('usuario_id') != g.usuario['id']:
        abort(400)
    return data


def suggestion(lots, quantity):
    capable = [lot for lot in lots if lot['quantidade_atual'] >= quantity]
    if not capable:
        return None
    return min(capable, key=lambda lot:(lot['status_operacional']!='aberto',
                                       lot['quantidade_atual'],lot['lote_id']))['lote_id']


def allocation_input(lot_ids, amounts, quantity, unit='m'):
    origin = 'pieza' if unit=='kg' else 'rollo'
    if len(lot_ids)!=len(amounts) or not lot_ids:
        raise ValueError(f'Elegí los orígenes físicos y cuánto retirar de cada {origin}.')
    allocations = []
    seen = set()
    for raw_id, raw_amount in zip(lot_ids,amounts):
        if not str(raw_amount).strip():
            continue
        amount = decimal_input(raw_amount,f'Cantidad de {origin}',3,allow_zero=True)
        if amount == 0:
            continue
        try:
            lot_id = int(raw_id)
            if lot_id<=0 or lot_id in seen:
                raise ValueError
        except (TypeError,ValueError):
            raise ValueError(f'Cada {origin} debe aparecer una sola vez.') from None
        seen.add(lot_id)
        allocations.append({'lote_id':lot_id,'quantidade':format(amount,'f')})
    if not allocations or sum(Decimal(a['quantidade']) for a in allocations)!=quantity:
        raise ValueError('La suma de las retiradas debe coincidir con la cantidad retirada.')
    return sorted(allocations,key=lambda a:a['lote_id'])
