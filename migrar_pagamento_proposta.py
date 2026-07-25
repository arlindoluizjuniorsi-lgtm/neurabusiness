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

print("Rodando migracoes (link de pagamento na proposta)...")
add_column('propostas', 'mp_preference_id', 'VARCHAR(100)')
add_column('propostas', 'mp_init_point', 'VARCHAR(500)')
add_column('propostas', 'infinitypay_link', 'VARCHAR(500)')
add_column('propostas', 'link_pagamento_gerado_em', 'TIMESTAMP')

cur.close()
conn.close()
print('[OK] Migracao concluida!')
