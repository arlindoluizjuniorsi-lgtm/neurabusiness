import psycopg2
from config import Config

conn = psycopg2.connect(
    host=Config.PG_HOST, port=Config.PG_PORT,
    dbname=Config.PG_DATABASE, user=Config.PG_USER,
    password=Config.PG_PASS
)
cur = conn.cursor()

print("Rodando migracao (Troca de Carro -- itens pra venda que somam na entrada)...")
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gp_itens_venda_troca (
            id          SERIAL PRIMARY KEY,
            usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
            descricao   VARCHAR(200) NOT NULL,
            valor       FLOAT NOT NULL DEFAULT 0,
            criado_em   TIMESTAMP
        )
    """)
    conn.commit()
    print("  [OK] tabela gp_itens_venda_troca")
except Exception as e:
    conn.rollback()
    print(f"  [--] gp_itens_venda_troca: {e}")

cur.close()
conn.close()
print('[OK] Migracao concluida!')
