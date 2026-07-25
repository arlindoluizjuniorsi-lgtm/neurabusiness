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

print("Rodando migracoes (cobranca NeuraDesk)...")
add_column('contratos_neuradesk', 'representante_email', 'VARCHAR(150)')
add_column('contratos_neuradesk', 'endereco_cep',    'VARCHAR(10)')
add_column('contratos_neuradesk', 'endereco_rua',    'VARCHAR(150)')
add_column('contratos_neuradesk', 'endereco_numero', 'VARCHAR(20)')
add_column('contratos_neuradesk', 'endereco_bairro', 'VARCHAR(100)')
add_column('contratos_neuradesk', 'endereco_cidade', 'VARCHAR(100)')
add_column('contratos_neuradesk', 'endereco_uf',     'VARCHAR(2)')

cur.execute("""
    CREATE TABLE IF NOT EXISTS pagamentos_neuradesk (
        id SERIAL PRIMARY KEY,
        licenca_id INTEGER NOT NULL REFERENCES licencas_neuradesk(id),
        tipo VARCHAR(10) NOT NULL,
        mp_payment_id VARCHAR(50),
        status VARCHAR(20) DEFAULT 'pending',
        valor FLOAT DEFAULT 0,
        linha_digitavel VARCHAR(80),
        boleto_url VARCHAR(500),
        pix_qr_base64 TEXT,
        pix_copia_cola TEXT,
        criado_em TIMESTAMP,
        expira_em TIMESTAMP,
        pago_em TIMESTAMP
    )
""")
conn.commit()
print("  [OK] tabela pagamentos_neuradesk")

cur.close()
conn.close()
print('[OK] Migracao concluida!')
