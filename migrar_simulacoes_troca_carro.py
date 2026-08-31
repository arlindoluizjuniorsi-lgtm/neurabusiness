import psycopg2
from config import Config

conn = psycopg2.connect(
    host=Config.PG_HOST, port=Config.PG_PORT,
    dbname=Config.PG_DATABASE, user=Config.PG_USER,
    password=Config.PG_PASS
)
cur = conn.cursor()

print("Rodando migracao (Troca de Carro -- simulacoes salvas)...")
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gp_simulacoes_troca_carro (
            id                  SERIAL PRIMARY KEY,
            usuario_id          INTEGER NOT NULL REFERENCES usuarios(id),
            nome_carro_novo     VARCHAR(150) NOT NULL,
            valor_carro_novo    FLOAT NOT NULL DEFAULT 0,
            carro_atual_fipe    VARCHAR(200),
            valor_fipe          FLOAT,
            oferta_loja         FLOAT DEFAULT 0,
            saldo_devedor       FLOAT DEFAULT 0,
            total_itens_venda   FLOAT DEFAULT 0,
            total_entrada       FLOAT DEFAULT 0,
            taxa_juros_am       FLOAT DEFAULT 0,
            parcelas            INTEGER DEFAULT 0,
            valor_parcela       FLOAT DEFAULT 0,
            total_pago          FLOAT DEFAULT 0,
            total_juros         FLOAT DEFAULT 0,
            notas               TEXT,
            criado_em           TIMESTAMP
        )
    """)
    conn.commit()
    print("  [OK] tabela gp_simulacoes_troca_carro")
except Exception as e:
    conn.rollback()
    print(f"  [--] gp_simulacoes_troca_carro: {e}")

cur.close()
conn.close()
print('[OK] Migracao concluida!')
