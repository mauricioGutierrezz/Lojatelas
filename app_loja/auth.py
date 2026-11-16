"""Login local existente; usuario_id informado aún no demuestra autoría."""
from .db import fetchone


def verificar_login(login, senha):
    return fetchone('SELECT * FROM public.fn_autenticar_usuario(%s,%s)', (login, senha))
