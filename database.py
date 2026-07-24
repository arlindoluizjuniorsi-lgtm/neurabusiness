"""
NeuraBusiness — Camada de Banco de Dados
Banco: NEURA (SQL Server) com fallback SQLite
Cada empresa usa seu próprio SCHEMA dentro do banco NEURA
"""
import os, json, sqlite3, threading
from flask import g

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_env():
    path = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(path): return
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

_load_env()

DB_TYPE   = os.environ.get('NB_DB_TYPE', 'sqlite')
SQL_SERVER= os.environ.get('NB_SQL_SERVER',   r'localhost\SQLEXPRESS')
SQL_DB    = os.environ.get('NB_SQL_DATABASE', 'NEURA')
SQL_DRIVER= os.environ.get('NB_SQL_DRIVER',   'ODBC Driver 17 for SQL Server')
SQL_TRUST = os.environ.get('NB_SQL_TRUSTED',  'yes')
SQL_USER  = os.environ.get('NB_SQL_USER',     'administrador')
SQL_PASS  = os.environ.get('NB_SQL_PASS',     '')
SQLITE_PATH = os.path.join(BASE_DIR, 'neurabusiness.db')

# Cache da verificação de disponibilidade do SQL Server (evita timeout repetido)
_sqlserver_available = None
_sqlserver_lock = threading.Lock()

def _build_conn_string():
    if SQL_TRUST.lower() == 'yes':
        return f'DRIVER={{{SQL_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DB};Trusted_Connection=yes;Connect Timeout=5;'
    else:
        return f'DRIVER={{{SQL_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DB};UID={SQL_USER};PWD={SQL_PASS};Connect Timeout=5;'

def _check_sqlserver():
    """Testa conexão uma vez e cacheia o resultado para evitar timeouts repetidos"""
    global _sqlserver_available
    if _sqlserver_available is not None:
        return _sqlserver_available
    with _sqlserver_lock:
        if _sqlserver_available is not None:
            return _sqlserver_available
        if DB_TYPE != 'sqlserver':
            _sqlserver_available = False
            return False
        try:
            import pyodbc
            conn = pyodbc.connect(_build_conn_string(), timeout=5)
            conn.close()
            _sqlserver_available = True
            print(f"[NeuraBusiness] ✅ SQL Server conectado: {SQL_SERVER} → banco {SQL_DB}")
        except Exception as e:
            _sqlserver_available = False
            print(f"[NeuraBusiness] ⚠️  SQL Server indisponível ({type(e).__name__}), usando SQLite.")
    return _sqlserver_available

# ─── CONEXÃO ──────────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        if _check_sqlserver():
            import pyodbc
            conn = pyodbc.connect(_build_conn_string())
            conn.autocommit = False
            g.db = conn
            g.db_type = 'sqlserver'
        else:
            g.db = _sqlite_connect()
            g.db_type = 'sqlite'
    return g.db, g.get('db_type', 'sqlite')

def _sqlite_connect():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")   # melhor performance
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn

def close_db(e=None):
    db = g.pop('db', None)
    g.pop('db_type', None)
    if db:
        try: db.close()
        except: pass

def query(sql, args=(), one=False):
    conn, dbtype = get_db()
    if dbtype == 'sqlserver':
        sql = _to_sqlserver(sql)
    cur = conn.cursor()
    cur.execute(sql, args)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall()
    if dbtype == 'sqlserver':
        rows = [dict(zip(cols, r)) for r in rows]
    return (rows[0] if rows else None) if one else rows

def execute(sql, args=()):
    conn, dbtype = get_db()
    if dbtype == 'sqlserver':
        sql = _to_sqlserver(sql)
        cur = conn.cursor()
        cur.execute(sql, args)
        cur.execute("SELECT SCOPE_IDENTITY() AS id")
        row = cur.fetchone()
        conn.commit()
        return int(row[0]) if row and row[0] is not None else None
    cur = conn.cursor()
    cur.execute(sql, args)
    lid = cur.lastrowid
    conn.commit()
    return lid

def executemany(sql, args_list):
    conn, dbtype = get_db()
    if dbtype == 'sqlserver':
        sql = _to_sqlserver(sql)
    cur = conn.cursor()
    cur.executemany(sql, args_list)
    try: conn.commit()
    except: pass

def _to_sqlserver(sql):
    sql = sql.replace("datetime('now')", 'GETDATE()')
    sql = sql.replace("date('now')",     "CAST(GETDATE() AS DATE)")
    sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'INT IDENTITY(1,1) PRIMARY KEY')
    sql = sql.replace('AUTOINCREMENT', 'IDENTITY(1,1)')
    sql = sql.replace(' TEXT ', ' NVARCHAR(MAX) ')
    sql = sql.replace(' TEXT\n', ' NVARCHAR(MAX)\n')
    sql = sql.replace(' REAL ', ' FLOAT ')
    return sql

# ─── SCHEMA SQLITE (completo) ─────────────────────────────────────────────────
_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    razao_social TEXT NOT NULL,
    fantasia TEXT NOT NULL,
    cnpj TEXT, telefone TEXT, email TEXT,
    endereco TEXT, cidade TEXT, estado TEXT, cep TEXT,
    logo TEXT, ativa INTEGER DEFAULT 1,
    briefing TEXT,
    criado_em TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL, usuario TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL, senha_hash TEXT NOT NULL,
    empresa_id INTEGER, is_admin INTEGER DEFAULT 0,
    is_super_admin INTEGER DEFAULT 0, ativo INTEGER DEFAULT 1,
    criado_em TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
);
CREATE TABLE IF NOT EXISTS usuario_empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL, empresa_id INTEGER NOT NULL,
    UNIQUE(usuario_id, empresa_id),
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
);
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL, nome TEXT NOT NULL,
    descricao TEXT, especificacoes TEXT,
    preco_custo REAL DEFAULT 0, preco_venda REAL DEFAULT 0,
    markup_padrao REAL DEFAULT 0, markup_sugerido REAL DEFAULT 0,
    margem_minima REAL DEFAULT 0,
    estoque INTEGER DEFAULT 0, categoria TEXT, tipo TEXT DEFAULT 'produto',
    foto TEXT, ativo INTEGER DEFAULT 1,
    token_link TEXT, link_expira_em TEXT, slug TEXT,
    criado_em TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
);
CREATE TABLE IF NOT EXISTS servicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL, nome TEXT NOT NULL,
    descricao TEXT, preco_unitario REAL DEFAULT 0,
    unidade TEXT DEFAULT 'un', ativo INTEGER DEFAULT 1,
    criado_em TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
);
CREATE TABLE IF NOT EXISTS catalogo_servicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL, categoria TEXT NOT NULL,
    subcategoria TEXT, nome TEXT NOT NULL, descricao TEXT,
    unidade TEXT DEFAULT 'un', preco_base REAL DEFAULT 0,
    tempo_horas REAL DEFAULT 0, ativo INTEGER DEFAULT 1,
    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
);
CREATE TABLE IF NOT EXISTS materiais_infra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL, nome TEXT NOT NULL,
    unidade TEXT DEFAULT 'un', preco_unitario REAL DEFAULT 0,
    categoria TEXT, ativo INTEGER DEFAULT 1,
    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
);
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL, nome TEXT NOT NULL,
    email TEXT, telefone TEXT, cpf_cnpj TEXT,
    endereco TEXT, cidade TEXT, estado TEXT, cep TEXT,
    observacoes TEXT, criado_em TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
);
CREATE TABLE IF NOT EXISTS propostas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL, numero TEXT NOT NULL,
    titulo TEXT NOT NULL, cliente_id INTEGER NOT NULL,
    status TEXT DEFAULT 'rascunho',
    tipo_proposta TEXT DEFAULT 'padrao',
    validade INTEGER DEFAULT 15,
    observacoes TEXT, condicoes TEXT, forma_pagamento TEXT,
    custo_locomocao REAL DEFAULT 0, custo_alimentacao REAL DEFAULT 0,
    custo_outros REAL DEFAULT 0, descricao_custos TEXT,
    cronograma TEXT, analise_ambiente TEXT,
    token_publico TEXT UNIQUE, token_expira_em TEXT,
    template_estilo TEXT DEFAULT 'tech',
    criado_em TEXT DEFAULT (datetime('now')),
    enviado_em TEXT, aprovado_em TEXT, usuario_id INTEGER,
    FOREIGN KEY(empresa_id) REFERENCES empresas(id),
    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
);
CREATE TABLE IF NOT EXISTS itens_proposta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposta_id INTEGER NOT NULL, produto_id INTEGER,
    servico_id INTEGER, descricao TEXT NOT NULL,
    quantidade REAL DEFAULT 1, preco_unitario REAL DEFAULT 0,
    markup REAL DEFAULT 0, tipo TEXT DEFAULT 'produto',
    foto TEXT, descricao_detalhada TEXT,
    FOREIGN KEY(proposta_id) REFERENCES propostas(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ordens_servico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL, numero TEXT NOT NULL,
    titulo TEXT NOT NULL, cliente_id INTEGER NOT NULL,
    proposta_id INTEGER, status TEXT DEFAULT 'aberta',
    prioridade TEXT DEFAULT 'normal', descricao TEXT NOT NULL,
    solucao TEXT, tecnico TEXT,
    data_prevista TEXT, data_conclusao TEXT,
    criado_em TEXT DEFAULT (datetime('now')), usuario_id INTEGER,
    FOREIGN KEY(empresa_id) REFERENCES empresas(id),
    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
);
CREATE TABLE IF NOT EXISTS projeto_anexos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposta_id INTEGER NOT NULL, nome_original TEXT NOT NULL,
    nome_arquivo TEXT NOT NULL, tipo TEXT, descricao TEXT,
    criado_em TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(proposta_id) REFERENCES propostas(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS contratos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL, proposta_id INTEGER NOT NULL,
    numero TEXT NOT NULL, cliente_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pendente',
    token_assinatura TEXT UNIQUE,
    assinado_em TEXT, assinatura_nome TEXT,
    texto_contrato TEXT,
    criado_em TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(empresa_id) REFERENCES empresas(id),
    FOREIGN KEY(proposta_id) REFERENCES propostas(id)
);
CREATE TABLE IF NOT EXISTS os_assinaturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    os_id INTEGER NOT NULL, token TEXT UNIQUE,
    assinado_em TEXT, assinatura_nome TEXT,
    FOREIGN KEY(os_id) REFERENCES ordens_servico(id)
);
"""

# ─── SCHEMA SQL SERVER (banco NEURA, tabelas simples) ─────────────────────────
_SCHEMA_SQLSERVER = [
    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='empresas' AND xtype='U')
    CREATE TABLE empresas(id INT IDENTITY(1,1)PRIMARY KEY,razao_social NVARCHAR(200)NOT NULL,
    fantasia NVARCHAR(100)NOT NULL,cnpj NVARCHAR(30),telefone NVARCHAR(30),email NVARCHAR(120),
    endereco NVARCHAR(300),cidade NVARCHAR(100),estado NVARCHAR(2),cep NVARCHAR(10),
    logo NVARCHAR(300),ativa BIT DEFAULT 1,briefing NVARCHAR(MAX),
    criado_em DATETIME DEFAULT GETDATE())""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='usuarios' AND xtype='U')
    CREATE TABLE usuarios(id INT IDENTITY(1,1)PRIMARY KEY,nome NVARCHAR(100)NOT NULL,
    usuario NVARCHAR(50)NOT NULL UNIQUE,email NVARCHAR(120)NOT NULL UNIQUE,
    senha_hash NVARCHAR(300)NOT NULL,empresa_id INT,is_admin BIT DEFAULT 0,
    is_super_admin BIT DEFAULT 0,ativo BIT DEFAULT 1,
    criado_em DATETIME DEFAULT GETDATE(),FOREIGN KEY(empresa_id)REFERENCES empresas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='usuario_empresas' AND xtype='U')
    CREATE TABLE usuario_empresas(id INT IDENTITY(1,1)PRIMARY KEY,
    usuario_id INT NOT NULL,empresa_id INT NOT NULL,
    UNIQUE(usuario_id,empresa_id),
    FOREIGN KEY(usuario_id)REFERENCES usuarios(id),
    FOREIGN KEY(empresa_id)REFERENCES empresas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='produtos' AND xtype='U')
    CREATE TABLE produtos(id INT IDENTITY(1,1)PRIMARY KEY,empresa_id INT NOT NULL,
    nome NVARCHAR(200)NOT NULL,descricao NVARCHAR(MAX),especificacoes NVARCHAR(MAX),
    preco_custo FLOAT DEFAULT 0,preco_venda FLOAT DEFAULT 0,markup_padrao FLOAT DEFAULT 0,
    markup_sugerido FLOAT DEFAULT 0,margem_minima FLOAT DEFAULT 0,
    estoque INT DEFAULT 0,categoria NVARCHAR(100),tipo NVARCHAR(20)DEFAULT 'produto',
    foto NVARCHAR(300),ativo BIT DEFAULT 1,token_link NVARCHAR(64),
    link_expira_em DATETIME,slug NVARCHAR(200),criado_em DATETIME DEFAULT GETDATE(),
    FOREIGN KEY(empresa_id)REFERENCES empresas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='servicos' AND xtype='U')
    CREATE TABLE servicos(id INT IDENTITY(1,1)PRIMARY KEY,empresa_id INT NOT NULL,
    nome NVARCHAR(200)NOT NULL,descricao NVARCHAR(MAX),preco_unitario FLOAT DEFAULT 0,
    unidade NVARCHAR(20)DEFAULT 'un',ativo BIT DEFAULT 1,
    criado_em DATETIME DEFAULT GETDATE(),FOREIGN KEY(empresa_id)REFERENCES empresas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='catalogo_servicos' AND xtype='U')
    CREATE TABLE catalogo_servicos(id INT IDENTITY(1,1)PRIMARY KEY,empresa_id INT NOT NULL,
    categoria NVARCHAR(100)NOT NULL,subcategoria NVARCHAR(100),nome NVARCHAR(200)NOT NULL,
    descricao NVARCHAR(MAX),unidade NVARCHAR(20)DEFAULT 'un',preco_base FLOAT DEFAULT 0,
    tempo_horas FLOAT DEFAULT 0,ativo BIT DEFAULT 1,
    FOREIGN KEY(empresa_id)REFERENCES empresas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='materiais_infra' AND xtype='U')
    CREATE TABLE materiais_infra(id INT IDENTITY(1,1)PRIMARY KEY,empresa_id INT NOT NULL,
    nome NVARCHAR(200)NOT NULL,unidade NVARCHAR(20)DEFAULT 'un',preco_unitario FLOAT DEFAULT 0,
    categoria NVARCHAR(100),ativo BIT DEFAULT 1,
    FOREIGN KEY(empresa_id)REFERENCES empresas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='clientes' AND xtype='U')
    CREATE TABLE clientes(id INT IDENTITY(1,1)PRIMARY KEY,empresa_id INT NOT NULL,
    nome NVARCHAR(200)NOT NULL,email NVARCHAR(120),telefone NVARCHAR(30),
    cpf_cnpj NVARCHAR(30),endereco NVARCHAR(300),cidade NVARCHAR(100),
    estado NVARCHAR(2),cep NVARCHAR(10),observacoes NVARCHAR(MAX),
    criado_em DATETIME DEFAULT GETDATE(),
    FOREIGN KEY(empresa_id)REFERENCES empresas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='propostas' AND xtype='U')
    CREATE TABLE propostas(id INT IDENTITY(1,1)PRIMARY KEY,empresa_id INT NOT NULL,
    numero NVARCHAR(30)NOT NULL,titulo NVARCHAR(200)NOT NULL,cliente_id INT NOT NULL,
    status NVARCHAR(20)DEFAULT 'rascunho',tipo_proposta NVARCHAR(20)DEFAULT 'padrao',
    validade INT DEFAULT 15,observacoes NVARCHAR(MAX),condicoes NVARCHAR(MAX),
    forma_pagamento NVARCHAR(100),
    custo_locomocao FLOAT DEFAULT 0,custo_alimentacao FLOAT DEFAULT 0,
    custo_outros FLOAT DEFAULT 0,descricao_custos NVARCHAR(MAX),
    cronograma NVARCHAR(MAX),analise_ambiente NVARCHAR(MAX),
    token_publico NVARCHAR(64)UNIQUE,token_expira_em DATETIME,
    template_estilo NVARCHAR(20)DEFAULT 'tech',
    criado_em DATETIME DEFAULT GETDATE(),enviado_em DATETIME,aprovado_em DATETIME,
    usuario_id INT,FOREIGN KEY(empresa_id)REFERENCES empresas(id),
    FOREIGN KEY(cliente_id)REFERENCES clientes(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='itens_proposta' AND xtype='U')
    CREATE TABLE itens_proposta(id INT IDENTITY(1,1)PRIMARY KEY,proposta_id INT NOT NULL,
    produto_id INT,servico_id INT,descricao NVARCHAR(300)NOT NULL,
    quantidade FLOAT DEFAULT 1,preco_unitario FLOAT DEFAULT 0,markup FLOAT DEFAULT 0,
    tipo NVARCHAR(20)DEFAULT 'produto',foto NVARCHAR(300),
    descricao_detalhada NVARCHAR(MAX),
    FOREIGN KEY(proposta_id)REFERENCES propostas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='ordens_servico' AND xtype='U')
    CREATE TABLE ordens_servico(id INT IDENTITY(1,1)PRIMARY KEY,empresa_id INT NOT NULL,
    numero NVARCHAR(30)NOT NULL,titulo NVARCHAR(200)NOT NULL,cliente_id INT NOT NULL,
    proposta_id INT,status NVARCHAR(20)DEFAULT 'aberta',
    prioridade NVARCHAR(20)DEFAULT 'normal',descricao NVARCHAR(MAX)NOT NULL,
    solucao NVARCHAR(MAX),tecnico NVARCHAR(100),data_prevista DATE,data_conclusao DATE,
    criado_em DATETIME DEFAULT GETDATE(),usuario_id INT,
    FOREIGN KEY(empresa_id)REFERENCES empresas(id),
    FOREIGN KEY(cliente_id)REFERENCES clientes(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='projeto_anexos' AND xtype='U')
    CREATE TABLE projeto_anexos(id INT IDENTITY(1,1)PRIMARY KEY,proposta_id INT NOT NULL,
    nome_original NVARCHAR(300)NOT NULL,nome_arquivo NVARCHAR(300)NOT NULL,
    tipo NVARCHAR(50),descricao NVARCHAR(200),criado_em DATETIME DEFAULT GETDATE(),
    FOREIGN KEY(proposta_id)REFERENCES propostas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='contratos' AND xtype='U')
    CREATE TABLE contratos(id INT IDENTITY(1,1)PRIMARY KEY,empresa_id INT NOT NULL,
    proposta_id INT NOT NULL,numero NVARCHAR(30)NOT NULL,cliente_id INT NOT NULL,
    status NVARCHAR(20)DEFAULT 'pendente',token_assinatura NVARCHAR(64)UNIQUE,
    assinado_em DATETIME,assinatura_nome NVARCHAR(200),texto_contrato NVARCHAR(MAX),
    criado_em DATETIME DEFAULT GETDATE(),
    FOREIGN KEY(empresa_id)REFERENCES empresas(id),
    FOREIGN KEY(proposta_id)REFERENCES propostas(id))""",

    """IF NOT EXISTS(SELECT*FROM sysobjects WHERE name='os_assinaturas' AND xtype='U')
    CREATE TABLE os_assinaturas(id INT IDENTITY(1,1)PRIMARY KEY,os_id INT NOT NULL,
    token NVARCHAR(64)UNIQUE,assinado_em DATETIME,assinatura_nome NVARCHAR(200),
    FOREIGN KEY(os_id)REFERENCES ordens_servico(id))""",
]

def init_db_schema():
    conn, dbtype = get_db()
    try:
        if dbtype == 'sqlserver':
            cur = conn.cursor()
            for stmt in _SCHEMA_SQLSERVER:
                cur.execute(stmt)
            conn.commit()
        else:
            conn.executescript(_SCHEMA_SQLITE)
        print("[NeuraBusiness] ✅ Schema verificado/criado")
    except Exception as e:
        print(f"[NeuraBusiness] ❌ Erro no schema: {e}")

def init_db_v3():
    """Alias para compatibilidade — init_db_schema já inclui tudo"""
    init_db_schema()

# Script SQL Server para criar banco e usuário (gerado na inicialização)
SETUP_SQL_SERVER_SCRIPT = r"""
-- Execute este script no SSMS como administrador
-- antes de rodar o NeuraBusiness pela primeira vez

-- 1. Criar banco NEURA
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'NEURA')
    CREATE DATABASE NEURA;
GO

USE NEURA;
GO

-- 2. (Opcional) Criar login SQL para o sistema
-- Se você usa autenticação Windows (Trusted_Connection=yes), pode pular este passo
-- CREATE LOGIN neurabusiness_app WITH PASSWORD = 'SuaSenhaAqui@123';
-- CREATE USER neurabusiness_app FOR LOGIN neurabusiness_app;
-- ALTER ROLE db_owner ADD MEMBER neurabusiness_app;

PRINT 'Banco NEURA pronto!';
GO
"""

def gerar_script_setup():
    """Salva script de setup SQL Server na pasta do projeto"""
    path = os.path.join(BASE_DIR, 'setup_sqlserver.sql')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(SETUP_SQL_SERVER_SCRIPT)
    print(f"[NeuraBusiness] Script SQL Server salvo em: {path}")
