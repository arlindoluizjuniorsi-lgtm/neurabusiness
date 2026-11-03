import psycopg2
from config import Config

conn = psycopg2.connect(
    host=Config.PG_HOST, port=Config.PG_PORT,
    dbname=Config.PG_DATABASE, user=Config.PG_USER,
    password=Config.PG_PASS
)
cur = conn.cursor()

print("Rodando migracoes (licencas NeuraDesk Remote)...")

cur.execute("""
    CREATE TABLE IF NOT EXISTS licencas_neuradesk_remote (
        id SERIAL PRIMARY KEY,
        chave VARCHAR(40) UNIQUE NOT NULL,
        empresa_nome VARCHAR(200) NOT NULL,
        empresa_cnpj VARCHAR(30),
        empresa_id_nb INTEGER REFERENCES empresas(id),
        fingerprint_dispositivo VARCHAR(128),
        ativada_em TIMESTAMP,
        status VARCHAR(20) DEFAULT 'pendente',
        data_vencimento TIMESTAMP,
        ultima_verificacao TIMESTAMP,
        ultimo_ip_verificacao VARCHAR(45),
        observacoes TEXT,
        criado_em TIMESTAMP DEFAULT NOW()
    )
""")
conn.commit()
print("  [OK] licencas_neuradesk_remote")

cur.close()
conn.close()
print("Concluido.")
