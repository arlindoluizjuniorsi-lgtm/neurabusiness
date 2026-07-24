# -*- coding: utf-8 -*-
"""
fix_licenca_model.py

Adiciona ao models.py do NeuraBusiness o modelo LicencaNeuraDesk —
representa cada licença/instalação do NeuraDesk vendida para outras
empresas (separado do modelo Empresa, que é usado pras próprias
propostas/OS/contratos do NeuraBusiness).

Idempotente. Faz backup do models.py antes de alterar.
"""
import shutil
import datetime

MODELS_PATH = "/opt/neurabusiness/models.py"


def main():
    with open(MODELS_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'class LicencaNeuraDesk' in content:
        print('Patch já aplicado. Nada a fazer.')
        return

    backup_path = MODELS_PATH + f'.bak_{datetime.datetime.now():%Y%m%d_%H%M%S}'
    shutil.copy2(MODELS_PATH, backup_path)
    print(f'Backup criado em: {backup_path}')

    OLD_IMPORT = '''"""NeuraBusiness — Modelos de Dados (SQLAlchemy)"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()'''
    NEW_IMPORT = '''"""NeuraBusiness — Modelos de Dados (SQLAlchemy)"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets

db = SQLAlchemy()'''
    if content.count(OLD_IMPORT) != 1:
        raise SystemExit('ERRO: âncora do topo do arquivo não encontrada ou duplicada.')
    content = content.replace(OLD_IMPORT, NEW_IMPORT, 1)

    NOVO_MODELO = '''

class LicencaNeuraDesk(db.Model):
    """Licenças do produto NeuraDesk vendido para outras empresas.
    Cada linha representa UMA instalação do NeuraDesk em algum cliente."""
    __tablename__ = 'licencas_neuradesk'
    id                     = db.Column(db.Integer, primary_key=True)
    chave                  = db.Column(db.String(40), unique=True, nullable=False)
    empresa_nome           = db.Column(db.String(200), nullable=False)
    empresa_cnpj           = db.Column(db.String(30))
    empresa_id_nb          = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=True)
    max_usuarios           = db.Column(db.Integer, default=5)
    fingerprint_servidor   = db.Column(db.String(128))
    ativada_em             = db.Column(db.DateTime)
    status                 = db.Column(db.String(20), default='pendente')  # pendente, ativa, carencia, bloqueada, cancelada
    data_ultimo_pagamento  = db.Column(db.DateTime)
    data_vencimento        = db.Column(db.DateTime)
    valor_mensal           = db.Column(db.Float, default=0)
    mp_preapproval_id      = db.Column(db.String(100))
    mp_status              = db.Column(db.String(30))
    ultima_verificacao     = db.Column(db.DateTime)
    ultimo_ip_verificacao  = db.Column(db.String(45))
    observacoes            = db.Column(db.Text)
    criado_em              = db.Column(db.DateTime, default=datetime.now)

    empresa_nb = db.relationship('Empresa', foreign_keys=[empresa_id_nb], lazy=True)

    @staticmethod
    def gerar_chave():
        grupos = [secrets.token_hex(2).upper() for _ in range(4)]
        return 'NRDK-' + '-'.join(grupos)
'''

    content = content.rstrip('\n') + '\n' + NOVO_MODELO

    with open(MODELS_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    print('models.py atualizado com sucesso.')
    print('Agora rode: python fix_licenca_rotas.py')


if __name__ == '__main__':
    main()
