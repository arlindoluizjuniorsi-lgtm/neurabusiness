import psycopg2
from config import Config

conn = psycopg2.connect(
    host=Config.PG_HOST, port=Config.PG_PORT,
    dbname=Config.PG_DATABASE, user=Config.PG_USER,
    password=Config.PG_PASS
)
cur = conn.cursor()

def add_column(tabela, coluna, tipo):
    try:
        cur.execute(f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS {coluna} {tipo}")
        conn.commit()
        print(f"  [OK] {tabela}.{coluna}")
    except Exception as e:
        conn.rollback()
        print(f"  [--] {tabela}.{coluna}: {e}")

print("Rodando migracao (serial mestre NeuraDesk Remote)...")
add_column('licencas_neuradesk_remote', 'mestre', 'BOOLEAN DEFAULT FALSE NOT NULL')

cur.close()
conn.close()
print("Concluido.")
