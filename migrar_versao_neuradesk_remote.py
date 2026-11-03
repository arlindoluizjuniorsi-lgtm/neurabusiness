import psycopg2
from config import Config

conn = psycopg2.connect(
    host=Config.PG_HOST, port=Config.PG_PORT,
    dbname=Config.PG_DATABASE, user=Config.PG_USER,
    password=Config.PG_PASS
)
cur = conn.cursor()

print("Rodando migracao (versao NeuraDesk Remote)...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS versao_neuradesk_remote (
        id SERIAL PRIMARY KEY,
        build_date VARCHAR(20) NOT NULL,
        download_url VARCHAR(300) NOT NULL,
        notas TEXT,
        atualizado_em TIMESTAMP DEFAULT NOW(),
        atualizado_por VARCHAR(120)
    )
""")
conn.commit()
print("  [OK] versao_neuradesk_remote")

cur.close()
conn.close()
print("Concluido.")
