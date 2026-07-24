"""NeuraBusiness — Configuracao (Linux + PostgreSQL)"""
import os
from urllib.parse import quote_plus

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _env(key, default=''):
    path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                if k.strip() == key:
                    return v.strip()
    return os.environ.get(key, default)

class Config:
    SECRET_KEY         = _env('FLASK_SECRET', 'neurabusiness-creative-2026-secret')
    UPLOAD_FOLDER      = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    DB_TYPE     = _env('NB_DB_TYPE',     'postgresql')
    PG_HOST     = _env('NB_PG_HOST',     'localhost')
    PG_PORT     = _env('NB_PG_PORT',     '5432')
    PG_DATABASE = _env('NB_PG_DATABASE', 'neura')
    PG_USER     = _env('NB_PG_USER',     'nbuser')
    PG_PASS     = _env('NB_PG_PASS',     '***REMOVED_DB_PASSWORD***')

    @classmethod
    def get_db_uri(cls):
        if cls.DB_TYPE == 'postgresql':
            return (f"postgresql+psycopg2://{quote_plus(cls.PG_USER)}:{quote_plus(cls.PG_PASS)}"
                    f"@{cls.PG_HOST}:{cls.PG_PORT}/{cls.PG_DATABASE}")
        else:
            return f"sqlite:///{os.path.join(BASE_DIR, 'neurabusiness.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
