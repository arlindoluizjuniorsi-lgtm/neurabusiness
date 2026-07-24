import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432,
    dbname='neura', user='nbuser',
    password='***REMOVED_DB_PASSWORD***'
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

print("Rodando migracoes...")
add_column('propostas', 'assinatura_nome', 'VARCHAR(200)')
add_column('propostas', 'assinatura_cpf',  'VARCHAR(20)')
add_column('propostas', 'assinatura_ip',   'VARCHAR(45)')
add_column('propostas', 'assinatura_hash', 'VARCHAR(128)')
add_column('contratos', 'empresa_assinado_em',     'TIMESTAMP')
add_column('contratos', 'empresa_assinatura_nome', 'VARCHAR(200)')
add_column('contratos', 'empresa_assinatura_ip',   'VARCHAR(45)')
add_column('contratos', 'empresa_assinatura_hash', 'VARCHAR(128)')

cur.close()
conn.close()
print('[OK] Migracao concluida!')
