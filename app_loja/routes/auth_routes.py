from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from .. import permisos
from ..auth import verificar_login
from ..throttle import wait_message

auth_bp = Blueprint('auth', __name__)


def cuentas():
    return [(login, permisos.NOMBRES[perfil]) for login, perfil in permisos.CUENTAS]


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.usuario:
        return redirect(url_for(permisos.home(g.usuario['perfil'])))
    if request.method == 'POST':
        login_name = request.form.get('login', '').strip()
        # Límite por cuenta: errar una contraseña no bloquea los otros roles.
        key = 'login:'+login_name.lower()[:64]
        attempts = current_app.extensions['attempts']
        waiting = attempts.wait_seconds(key)
        if waiting:
            flash(wait_message(waiting), 'erro')
            return render_template('login.html', cuentas=cuentas()), 429
        usuario = verificar_login(login_name, request.form.get('senha', ''))
        if usuario:
            attempts.success(key)
            session.clear()
            session['usuario_id'] = usuario['id']
            return redirect(url_for(permisos.home(usuario['perfil'])))
        attempts.failure(key)
        flash('La contraseña no es correcta para ese rol.', 'erro')
    return render_template('login.html', cuentas=cuentas())


@auth_bp.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
