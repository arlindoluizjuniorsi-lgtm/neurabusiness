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

print("Rodando migracoes (status de pagamento parcial/total da proposta)...")
add_column('propostas', 'status_pagamento',     "VARCHAR(20) DEFAULT 'pendente'")
add_column('propostas', 'valor_pago',            'FLOAT DEFAULT 0')
add_column('propostas', 'pagamento_percentual',  'INTEGER')
add_column('propostas', 'mp_payment_id',         'VARCHAR(50)')
add_column('propostas', 'pago_em',               'TIMESTAMP')

cur.close()
conn.close()
print('[OK] Migracao concluida!')
