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

def _env_obrigatoria(key):
    valor = _env(key, '')
    if not valor:
        raise RuntimeError(
            f"{key} não definida. Defina no arquivo .env antes de iniciar o servidor."
        )
    return valor

class Config:
    SECRET_KEY         = _env_obrigatoria('FLASK_SECRET')
    UPLOAD_FOLDER      = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    DB_TYPE     = _env('NB_DB_TYPE',     'postgresql')
    PG_HOST     = _env('NB_PG_HOST',     'localhost')
    PG_PORT     = _env('NB_PG_PORT',     '5432')
    PG_DATABASE = _env('NB_PG_DATABASE', 'neura')
    PG_USER     = _env('NB_PG_USER',     'nbuser')
    PG_PASS     = _env_obrigatoria('NB_PG_PASS')

    # Integração Mercado Pago (renovação automática de licenças NeuraDesk).
    # Opcional: enquanto não configurado, o webhook fica inerte (503).
    MP_ACCESS_TOKEN   = _env('MP_ACCESS_TOKEN', '')
    MP_WEBHOOK_SECRET = _env('MP_WEBHOOK_SECRET', '')
    MP_DIAS_RENOVACAO = int(_env('MP_DIAS_RENOVACAO', '30') or 30)

    # Chave usada pra cifrar tokens de integrações guardados no banco
    # (tela /admin/integracoes) -- ex: token do Mercado Pago.
    INTEGRACOES_FERNET_KEY = _env('INTEGRACOES_FERNET_KEY', '')

    # Dados da CONTRATADA nos contratos de licenciamento do NeuraDesk
    # (não são segredo -- vão impressos no PDF do contrato -- mas ficam
    # no .env em vez de hardcoded no código-fonte).
    CONTRATADA_RAZAO_SOCIAL = _env('CONTRATADA_RAZAO_SOCIAL', '[preencher CONTRATADA_RAZAO_SOCIAL no .env]')
    CONTRATADA_CNPJ         = _env('CONTRATADA_CNPJ', '[preencher CONTRATADA_CNPJ no .env]')
    CONTRATADA_ENDERECO     = _env('CONTRATADA_ENDERECO', '[preencher CONTRATADA_ENDERECO no .env]')
    CONTRATADA_REPRESENTANTE_NOME = _env('CONTRATADA_REPRESENTANTE_NOME', '[preencher CONTRATADA_REPRESENTANTE_NOME no .env]')
    CONTRATADA_REPRESENTANTE_CPF  = _env('CONTRATADA_REPRESENTANTE_CPF', '[preencher CONTRATADA_REPRESENTANTE_CPF no .env]')

    @classmethod
    def get_db_uri(cls):
        if cls.DB_TYPE == 'postgresql':
            return (f"postgresql+psycopg2://{quote_plus(cls.PG_USER)}:{quote_plus(cls.PG_PASS)}"
                    f"@{cls.PG_HOST}:{cls.PG_PORT}/{cls.PG_DATABASE}")
        else:
            return f"sqlite:///{os.path.join(BASE_DIR, 'neurabusiness.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
