"""Ejecutar desde la raíz: python -m app_loja.run."""
import secrets

import psycopg2
from flask import Flask, abort, g, redirect, request, session, url_for

from . import config, db
from .validation import format_decimal
from .cobro import format_money
from . import permisos, red
from .throttle import AttemptLimiter


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=config.SECRET_KEY, MAX_CONTENT_LENGTH=64 * 1024, REDES_PERMITIDAS=(),
                      REGISTRAR_ACCESOS=False,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    if test_config:
        app.config.update(test_config)

    from .routes.auth_routes import auth_bp
    from .routes.entrada_routes import entrada_bp
    from .routes.ticket_routes import ticket_bp
    from .routes.corte_routes import corte_bp
    from .routes.caixa_routes import caixa_bp
    from .routes.conteo_routes import conteo_bp
    from .routes.precios_routes import precios_bp
    app.register_blueprint(precios_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(entrada_bp)
    app.register_blueprint(ticket_bp)
    app.register_blueprint(corte_bp)
    app.register_blueprint(caixa_bp)
    app.register_blueprint(conteo_bp)
    app.extensions['attempts'] = AttemptLimiter()
    app.jinja_env.filters['cantidad'] = format_decimal
    app.jinja_env.filters['importe'] = format_money

    @app.before_request
    def protect_request():
        # Segunda barrera después del firewall: solo este equipo y la red privada de la tienda.
        if not red.allowed_client(request.remote_addr, app.config['REDES_PERMITIDAS']):
            if app.config['REGISTRAR_ACCESOS']:
                red.log_access(request.remote_addr, request.method, request.path, '403-fuera-de-red')
            return 'Acceso permitido solo desde la red de la tienda.', 403, {'Content-Type': 'text/plain; charset=utf-8'}
        # El ícono no existe: responder sin tocar la sesión ni redirigir al ingreso.
        if request.path == '/favicon.ico':
            return '', 204
        if request.endpoint=='entrada.nuevo_producto' or (request.endpoint=='entrada.foto' and request.method=='POST'):
            request.max_content_length = 5*1024*1024+64*1024
        session.setdefault('csrf', secrets.token_urlsafe(32))
        if request.method == 'POST' and not secrets.compare_digest(
            request.form.get('csrf', ''), session['csrf']
        ):
            abort(400, description='La sesión venció. Volvé a abrir la página e intentá de nuevo.')
        g.usuario = None
        if session.get('usuario_id'):
            g.usuario = db.fetchone(
                'SELECT id,nome,login,perfil FROM public.vw_usuarios WHERE id=%s AND ativo',
                (session['usuario_id'],),
            )
        if request.endpoint not in ('auth.login', 'static') and not g.usuario:
            return redirect(url_for('auth.login'))
        # El rol se vuelve a leer del banco en cada pedido; nunca se confía en la cookie.
        if g.usuario and not permisos.allowed(request.endpoint, request.method, g.usuario['perfil']):
            abort(403)

    @app.after_request
    def prevent_cached_authorization(response):
        if request.endpoint!='static':
            response.headers['Cache-Control'] = 'no-store'
            # Solo en modo servidor: ayuda a diagnosticar conexiones de otros equipos.
            if app.config['REGISTRAR_ACCESOS']:
                red.log_access(request.remote_addr, request.method, request.path, response.status_code)
        return response

    def unidad(code):
        return {
            'm':dict(origem='rollo',desde='del rollo',plural='rollos',titulo='Rollo',estado='Abiertos / Cerrados',retirada='Cantidad cortada',curta='Cortada',operacao='corte',realizada='Corte realizado',registrar='Registrar corte'),
            'kg':dict(origem='pieza',desde='de la pieza',plural='piezas',titulo='Pieza',estado='Abiertas / Cerradas',retirada='Peso retirado',curta='Peso retirado',operacao='retirada',realizada='Retirada realizada',registrar='Registrar retirada'),
            'un':dict(origem='',plural='',titulo='',retirada='Cantidad retirada',curta='Retirada',operacao='retirada',realizada='Retirada realizada',registrar='Registrar retirada'),
        }[code]

    @app.context_processor
    def context():
        usuario = g.get('usuario')
        perfil = usuario['perfil'] if usuario else None
        return {'usuario': usuario, 'csrf': session.get('csrf'), 'unidad': unidad,
                'rol': permisos.NOMBRES.get(perfil), 'menu': permisos.menu(perfil),
                'inicio': permisos.home(perfil),
                'puede': lambda endpoint: permisos.allowed(endpoint, 'GET', perfil)}

    @app.errorhandler(psycopg2.Error)
    def database_error(error):
        # No exponer SQL, roles, conexiones ni detalles de la excepción.
        from flask import render_template
        return render_template('error.html', message=
            'No se pudo guardar o consultar la información. Revisá los datos e intentá de nuevo.'), 503

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def request_error(error):
        from flask import render_template
        messages = {400: 'La solicitud no es válida. Volvé a intentarlo.',
                    403: 'Tu rol no tiene acceso a esta sección.',
                    404: 'No encontramos esta página.',
                    413: 'El formulario es demasiado grande. Cargá menos grupos por ingreso.'}
        if error.code==413 and request.endpoint in ('entrada.nuevo_producto','entrada.foto'):
            messages[413]='La foto supera 5 MB. Elegí una imagen más pequeña.'
        return render_template('error.html', message=messages[error.code]), error.code

    @app.route('/')
    def index():
        return redirect(url_for(permisos.home(g.usuario['perfil'])))

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000, debug=False)
