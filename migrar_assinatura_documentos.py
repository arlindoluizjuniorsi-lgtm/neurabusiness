import psycopg2
from config import Config

conn = psycopg2.connect(
    host=Config.PG_HOST, port=Config.PG_PORT,
    dbname=Config.PG_DATABASE, user=Config.PG_USER,
    password=Config.PG_PASS
)
cur = conn.cursor()

print("Rodando migracao (Assinatura de Documentos, migrado do NeuraDesk)...")

try:
    cur.execute("""
        ALTER TABLE usuarios
        ADD COLUMN IF NOT EXISTS assinatura_salva BYTEA,
        ADD COLUMN IF NOT EXISTS assinatura_salva_mimetype VARCHAR(20)
    """)
    conn.commit()
    print("  [OK] usuarios.assinatura_salva / assinatura_salva_mimetype")
except Exception as e:
    conn.rollback()
    print(f"  [--] usuarios.assinatura_salva: {e}")

try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS certificados_digitais_usuario (
            id                SERIAL PRIMARY KEY,
            usuario_id        INTEGER NOT NULL UNIQUE REFERENCES usuarios(id),
            nome_arquivo      VARCHAR(200),
            arquivo_cifrado   TEXT NOT NULL,
            titular_nome      VARCHAR(200),
            titular_documento VARCHAR(30),
            emissor           VARCHAR(200),
            valido_de         TIMESTAMP,
            valido_ate        TIMESTAMP,
            criado_em         TIMESTAMP
        )
    """)
    conn.commit()
    print("  [OK] tabela certificados_digitais_usuario")
except Exception as e:
    conn.rollback()
    print(f"  [--] certificados_digitais_usuario: {e}")

try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documentos_assinatura (
            id                   SERIAL PRIMARY KEY,
            usuario_id           INTEGER REFERENCES usuarios(id),
            token_publico        VARCHAR(64) UNIQUE,
            nome_arquivo         VARCHAR(200) NOT NULL,
            metodo               VARCHAR(20),
            status               VARCHAR(20) DEFAULT 'pendente',
            arquivo_original     VARCHAR(300),
            arquivo_assinado     VARCHAR(300),
            num_paginas          INTEGER,
            pagina               INTEGER DEFAULT 1,
            pos_x_pct            FLOAT,
            pos_y_pct            FLOAT,
            largura_pct          FLOAT DEFAULT 25.0,
            assinante_nome       VARCHAR(200),
            assinante_cpf        VARCHAR(20),
            assinante_ip         VARCHAR(45),
            hash_sha256          VARCHAR(64),
            certificado_titular  VARCHAR(200),
            certificado_validade TIMESTAMP,
            erro_msg             TEXT,
            criado_em            TIMESTAMP,
            assinado_em          TIMESTAMP
        )
    """)
    conn.commit()
    print("  [OK] tabela documentos_assinatura")
except Exception as e:
    conn.rollback()
    print(f"  [--] documentos_assinatura: {e}")

cur.close()
conn.close()
print('[OK] Migracao concluida!')
