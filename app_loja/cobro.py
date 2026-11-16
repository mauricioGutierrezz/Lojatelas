"""Entrada monetaria de Caja; dinero entregado y vuelto no son datos de venta."""
from decimal import Decimal

from .validation import money_input


def efectivo_entregado(value):
    text = str(value or '').strip()
    message = 'Ingresá un importe válido, sin negativos y con hasta 2 decimales.'
    if not text:
        raise ValueError('Informá Efectivo entregado o elegí uno de los botones.')
    try:
        return money_input(text, 'Efectivo entregado', precision=14)
    except ValueError:
        raise ValueError(message) from None


def format_money(value):
    return format(Decimal(value), ',.2f').translate(str.maketrans(',.', '.,'))
