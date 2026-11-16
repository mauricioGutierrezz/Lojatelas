"""Validación decimal del formulario; no altera cantidades declaradas."""
from decimal import Decimal, InvalidOperation
import re


def decimal_input(value, label, scale, *, optional=False, allow_zero=False, precision=12):
    text = str(value or '').strip().replace(',', '.')
    if not text and optional:
        return None
    try:
        result = Decimal(text)
        if not result.is_finite():
            raise InvalidOperation
        if result < 0 or (not allow_zero and result == 0):
            raise InvalidOperation
        if result != result.quantize(Decimal(1).scaleb(-scale)):
            raise InvalidOperation
        # Rechazar desbordes antes de enviar el formulario al banco.
        if result >= Decimal(10) ** (precision - scale):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label}: ingresá un valor válido con hasta {scale} decimales.') from None
    return result


def money_input(value, label, *, optional=False, precision=12):
    """Milhares es-AR têm precedência; não arredonda nem utiliza float."""
    text = str(value or '').strip()
    if not text and optional:
        return None
    if re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?', text):
        text = text.replace('.', '')
    elif not re.fullmatch(r'[0-9]+(?:[.,][0-9]{1,2})?', text):
        raise ValueError(f'{label}: ingresá un importe válido con hasta 2 decimales.')
    return decimal_input(text, label, 2, allow_zero=True, precision=precision)


def product_input(form):
    name = form.get('nome', '').strip()
    if not name:
        raise ValueError('Ingresá el nombre del producto.')
    try:
        category = int(form.get('tipo_id', ''))
        if category <= 0:
            raise ValueError
    except ValueError:
        raise ValueError('Elegí una categoría.') from None
    unit = form.get('unidade', '')
    if unit not in ('m', 'kg', 'un'):
        raise ValueError('Elegí una unidad válida.')
    return {
        'tipo_id': category, 'nome': name, 'unidade': unit,
        'preco': money_input(form.get('preco'), 'Precio inicial'),
        'largura': None if unit=='un' else decimal_input(form.get('largura'), 'Ancho', 2, optional=True, precision=5),
        'padrao': None if unit=='un' else decimal_input(form.get('padrao'), 'Cantidad sugerida', 3, optional=True),
    }


def quantity_input(value,label,unit):
    return decimal_input(value,label,0 if unit=='un' else 3,precision=9 if unit=='un' else 12)


def groups_input(produto_id, rolls, quantities, unit='m'):
    if unit=='un':
        if rolls or len(quantities)!=1:
            raise ValueError('Informá una cantidad de unidades, sin orígenes físicos.')
        return [{'produto_id':produto_id,'quantidade':format(quantity_input(quantities[0],'Unidades',unit).normalize(),'f')}]
    origin = 'pieza' if unit=='kg' else 'rollo'
    if len(rolls) != len(quantities) or not rolls:
        raise ValueError(f'Agregá al menos un grupo de {origin}s.')
    groups = []
    for raw_rolls, raw_quantity in zip(rolls, quantities):
        try:
            count = int(raw_rolls)
            if count <= 0 or count > 2147483647:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError(f'La cantidad de {origin}s debe ser un número entero positivo.') from None
        quantity = decimal_input(raw_quantity, f'Cantidad por {origin}', 3)
        groups.append({'produto_id': produto_id, ('pecas' if unit=='kg' else 'rolos'): count,
                       'quantidade': format(quantity.normalize(), 'f')})
    return groups


def format_decimal(value):
    if value is None:
        return '—'
    text = format(Decimal(value), 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text.replace('.', ',')
