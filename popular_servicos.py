"""
NeuraBusiness — Popular tabela Servicos a partir do Catálogo Creative
Execute: python popular_servicos.py
Insere todos os 49 serviços na tabela 'servicos' que aparece no menu.
"""
import os, sys

env = {}
if os.path.exists('.env'):
    for linha in open('.env', encoding='utf-8'):
        linha = linha.strip()
        if linha and not linha.startswith('#') and '=' in linha:
            k, v = linha.split('=', 1)
            env[k.strip()] = v.strip()

servidor = env.get('NB_SQL_SERVER',   r'localhost\neura')
banco    = env.get('NB_SQL_DATABASE', 'NEURA')
driver   = env.get('NB_SQL_DRIVER',   'ODBC Driver 17 for SQL Server')
trusted  = env.get('NB_SQL_TRUSTED',  'no')
user     = env.get('NB_SQL_USER',     'administrador')
password = env.get('NB_SQL_PASS',     '')

print("=" * 60)
print("  NeuraBusiness — Popular Serviços")
print(f"  Banco: {banco} @ {servidor}")
print("=" * 60)

try:
    import pyodbc
except ImportError:
    print("❌ pyodbc não instalado.")
    sys.exit(1)

if trusted.lower() == 'yes':
    conn_str = f'DRIVER={{{driver}}};SERVER={servidor};DATABASE={banco};Trusted_Connection=yes;TrustServerCertificate=yes;'
else:
    conn_str = f'DRIVER={{{driver}}};SERVER={servidor};DATABASE={banco};UID={user};PWD={password};TrustServerCertificate=yes;'

try:
    conn = pyodbc.connect(conn_str)
    conn.autocommit = True
    cur = conn.cursor()
    print("✅ Conectado!\n")
except Exception as e:
    print(f"❌ Conexão falhou: {e}")
    sys.exit(1)

# Pega empresa
cur.execute("SELECT id, fantasia FROM empresas WHERE ativa=1")
emp = cur.fetchone()
if not emp:
    print("❌ Nenhuma empresa encontrada.")
    sys.exit(1)
empresa_id, empresa_nome = emp
print(f"Empresa: {empresa_nome} (id={empresa_id})\n")

# Conta existentes
cur.execute("SELECT COUNT(*) FROM servicos WHERE empresa_id=?", empresa_id)
count_antes = cur.fetchone()[0]
print(f"Serviços existentes: {count_antes}")
if count_antes > 0:
    resp = input("Deseja apagar os existentes e reinserir? (s/N): ").strip().lower()
    if resp == 's':
        cur.execute("DELETE FROM servicos WHERE empresa_id=?", empresa_id)
        print(f"✅ {count_antes} registros removidos")
    else:
        print("Operação cancelada.")
        sys.exit(0)

from catalogo_creative import CATALOGO

# Insere agrupando por categoria como nome principal
count = 0
cat_atual = None
for cat, sub, nome, desc, desc_cli, tipo, preco, unidade, horas in CATALOGO:
    # Nome exibe categoria + serviço para ficar organizado
    nome_exibir = nome
    descricao = desc_cli or desc or ''
    
    cur.execute("""
        INSERT INTO servicos (empresa_id, nome, descricao, preco_unitario, unidade, ativo)
        VALUES (?,?,?,?,?,1)
    """, empresa_id, nome_exibir, descricao, preco, unidade)
    count += 1
    if cat != cat_atual:
        cat_atual = cat
        print(f"\n  📂 {cat}")
    print(f"    ✅ {nome}")

conn.close()
print(f"\n{'='*60}")
print(f"  ✅ {count} serviços inseridos com sucesso!")
print(f"  Agora aparecem no menu Serviços e na proposta.")
print(f"{'='*60}")
