"""Secretos locales cifrados por Windows (DPAPI) para la cuenta que usa la tienda.

Solo la misma cuenta Windows, en este mismo equipo, puede descifrarlos. Los
archivos viven fuera del proyecto y fuera de carpetas sincronizadas. Nunca se
guardan contraseñas en texto plano ni se imprimen.
"""
import os
from pathlib import Path
import re

WINDOWS = os.name == 'nt'
REPOSITORY = Path(__file__).resolve().parents[1]


def store_dir():
    custom = os.environ.get('LOJA_SECRET_DIR')
    if custom:
        return Path(custom)
    base = os.environ.get('LOCALAPPDATA')
    if not base:
        raise ValueError('No se encontró la carpeta local de la cuenta Windows.')
    return Path(base)/'Urdimbre'


def _path(name):
    if not re.fullmatch(r'[a-z0-9_.-]{1,120}', name):
        raise ValueError('Nombre de secreto inválido.')
    path = (store_dir()/f'{name}.dpapi').absolute()
    if path.resolve().is_relative_to(REPOSITORY):
        raise ValueError('Los secretos deben quedar fuera del proyecto.')
    return path


def _crypt(data, entropy, *, protect):
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_char))]

    def blob(value):
        buffer = ctypes.create_string_buffer(value, len(value))
        return Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer

    source, _keep_source = blob(data)
    salt, _keep_salt = blob(entropy)
    result = Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    # 0x1 = CRYPTPROTECT_UI_FORBIDDEN: nunca abrir ventanas.
    if not function(ctypes.byref(source), None, ctypes.byref(salt), None, None, 0x1, ctypes.byref(result)):
        raise ValueError('Windows no pudo proteger o leer el secreto local.')
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel32.LocalFree(ctypes.cast(result.data, wintypes.HLOCAL))


def available():
    return WINDOWS


def save(name, secret):
    """Guarda el secreto cifrado para la cuenta Windows actual."""
    if not WINDOWS:
        raise ValueError('El guardado protegido solo existe en Windows.')
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    protected = _crypt(secret.encode('utf-8'), name.encode('ascii'), protect=True)
    pending = path.with_name(path.name+'.pending')
    pending.write_bytes(protected)
    os.replace(pending, path)


def load(name):
    """Devuelve el secreto, o None si no existe o no pertenece a esta cuenta."""
    if not WINDOWS:
        return None
    try:
        path = _path(name)
        protected = path.read_bytes()
        if not protected or len(protected) > 16384:
            return None
        return _crypt(protected, name.encode('ascii'), protect=False).decode('utf-8')
    except (OSError, ValueError, UnicodeError):
        return None


def forget(name):
    try:
        _path(name).unlink()
    except (OSError, ValueError):
        pass


def connection_name(kind, user, database, port):
    return f'{kind}-{user}-{database}-{port}'
