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

print("Rodando migracao (parcela atual pra comparar com a simulada)...")
add_column('gp_simulacoes_troca_carro', 'parcela_atual', 'FLOAT')

cur.close()
conn.close()
print('[OK] Migracao concluida!')
