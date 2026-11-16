"""Configuración por variables de entorno; sin credenciales versionadas."""
import os
import secrets

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "urdimbre"),
    "user": os.getenv("DB_USER", "loja_app"),
    "password": os.getenv("DB_PASSWORD", ""),
    "connect_timeout": 5,
}
SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
