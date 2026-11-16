"""Qué puede abrir cada rol. Única tabla de permisos de la aplicación.

Las funciones del banco repiten la misma regla como segunda barrera. Las tres
cuentas son compartidas por rol: el rol autoriza, no identifica a la persona.
"""
ADMIN, EMPLEADO, CAJERO = 'admin', 'empleado', 'cajero'
NOMBRES = {ADMIN: 'Administrador', EMPLEADO: 'Empleado', CAJERO: 'Cajero'}
# Logins fijos creados por la instalación, en el orden de la pantalla de ingreso.
CUENTAS = (('administrador', ADMIN), ('empleado', EMPLEADO), ('cajero', CAJERO))

STOCK = frozenset({ADMIN, EMPLEADO})
CORTE = frozenset({ADMIN, EMPLEADO, CAJERO})
CAJA = frozenset({ADMIN, CAJERO})
PRECIOS = frozenset({ADMIN})

# Por blueprint: toda ruta nueva queda cubierta sin tener que recordarla aquí.
AREAS = {'entrada': STOCK, 'ticket': CORTE, 'corte': CORTE, 'caixa': CAJA, 'conteo': CAJA, 'precios': PRECIOS}
# Las fotos se muestran también en Corte y Caja; verlas no modifica nada.
VER_FOTO = frozenset({'entrada.foto', 'entrada.miniatura'})
ABIERTAS = frozenset({'static', 'auth.login', 'auth.logout', 'index'})

MENU = (('entrada.stock', 'Productos y stock', STOCK), ('ticket.index', 'Corte / Ticket', CORTE),
        ('caixa.index', 'Caja / Venta', CAJA), ('precios.index', 'Precios', PRECIOS))


def allowed(endpoint, method, perfil):
    if endpoint is None or endpoint in ABIERTAS:
        return True
    if endpoint in VER_FOTO and method == 'GET':
        return perfil in NOMBRES
    # Blueprint desconocido: denegar hasta que se declare su área.
    return perfil in AREAS.get(endpoint.split('.')[0], frozenset())


def menu(perfil):
    return [(endpoint, label) for endpoint, label, roles in MENU if perfil in roles]


def home(perfil):
    """Primera pantalla del rol."""
    items = menu(perfil)
    return items[0][0] if items else 'auth.login'
