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

print("Rodando migracoes (emissao de NFS-e Nacional)...")

add_column('empresas', 'nfse_codigo_municipio',           'VARCHAR(7)')
add_column('empresas', 'nfse_inscricao_municipal',        'VARCHAR(30)')
add_column('empresas', 'nfse_codigo_tributacao_nacional', 'VARCHAR(10)')
add_column('empresas', 'nfse_cnbs',                       'VARCHAR(15)')
add_column('empresas', 'nfse_regime_tributario',          "VARCHAR(20) DEFAULT 'mei'")
add_column('empresas', 'nfse_aliquota_iss',               'FLOAT DEFAULT 0')
add_column('empresas', 'nfse_ambiente',                   "VARCHAR(20) DEFAULT 'homologacao'")
add_column('empresas', 'nfse_serie_dps',                  "VARCHAR(5) DEFAULT '1'")
add_column('empresas', 'nfse_ultimo_numero_dps',          'INTEGER DEFAULT 0')

add_column('clientes', 'codigo_municipio_ibge', 'VARCHAR(7)')

add_column('propostas', 'nfse_chave_acesso', 'VARCHAR(60)')
add_column('propostas', 'nfse_numero_dps',   'INTEGER')
add_column('propostas', 'nfse_serie_dps',    'VARCHAR(5)')
add_column('propostas', 'nfse_status',       "VARCHAR(20) DEFAULT 'nao_emitida'")
add_column('propostas', 'nfse_emitido_em',   'TIMESTAMP')
add_column('propostas', 'nfse_erro',         'TEXT')

# Pre-preenche a config fiscal da Creative (empresa id=1) com os dados reais
# extraidos do CNPJ, cadastro estadual e de uma NFS-e ja emitida manualmente
# pelo Arlindo -- Mamanguape/PB, MEI, codigo de tributacao 01.07.01 (suporte
# tecnico/instalacao, o mais usado). So preenche se ainda estiver vazio, pra
# nao sobrescrever se alguem ja tiver configurado por outra via.
cur.execute("""
    UPDATE empresas SET
        nfse_codigo_municipio = COALESCE(nfse_codigo_municipio, '2508901'),
        nfse_codigo_tributacao_nacional = COALESCE(nfse_codigo_tributacao_nacional, '010701'),
        nfse_cnbs = COALESCE(nfse_cnbs, '115013000'),
        nfse_regime_tributario = COALESCE(nfse_regime_tributario, 'mei'),
        nfse_aliquota_iss = COALESCE(nfse_aliquota_iss, 0),
        nfse_ambiente = COALESCE(nfse_ambiente, 'homologacao'),
        nfse_serie_dps = COALESCE(nfse_serie_dps, '1'),
        nfse_ultimo_numero_dps = COALESCE(nfse_ultimo_numero_dps, 0)
    WHERE id = 1
""")
conn.commit()
print("  [OK] config fiscal padrao da empresa 1 (Mamanguape/PB, MEI, cod. 01.07.01)")

cur.close()
conn.close()
print('[OK] Migracao concluida!')
