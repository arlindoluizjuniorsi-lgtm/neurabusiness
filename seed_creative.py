import sys
sys.path.insert(0, '/opt/neurabusiness')
from app import app, db
from models import Empresa, Servico, Produto

SERVICOS = [
    ('Servico de Instalacao', 'Instalacao geral de equipamentos', 150.00, 'hr'),
    ('Servico de Instalacao de Cerca Eletrica', 'Instalacao completa de cerca eletrica perimetral', 80.00, 'm'),
    ('Servico de Instalacao de Motor de Portao', 'Instalacao de motor deslizante ou basculante', 350.00, 'un'),
    ('Servico de Instalacao de CFTV', 'Instalacao de cameras com DVR/NVR e cabeamento', 120.00, 'ponto'),
    ('Servico de Instalacao de Alarme', 'Instalacao de central de alarme com sensores', 100.00, 'ponto'),
    ('Servico de Instalacao de Energia Solar', 'Instalacao de sistema fotovoltaico', 500.00, 'un'),
    ('Servico de Manutencao', 'Manutencao preventiva e corretiva de equipamentos', 120.00, 'hr'),
]

PRODUTOS = [
    ('Camera IP VIP 1230 D Intelbras', 'CFTV', 180.00, 35),
    ('Camera Dome Full HD Intelbras', 'CFTV', 120.00, 35),
    ('DVR 4 Canais Full HD Intelbras', 'CFTV', 280.00, 30),
    ('DVR 8 Canais Full HD Intelbras', 'CFTV', 420.00, 30),
    ('NVR 8 Canais Intelbras', 'CFTV', 580.00, 30),
    ('HD 1TB WD Purple CFTV', 'CFTV', 280.00, 25),
    ('Cabo Coaxial 4 Vias Rolo 100m', 'CFTV', 95.00, 30),
    ('Fonte 12V 5A Bivolt', 'CFTV', 35.00, 40),
    ('Conector BNC', 'CFTV', 1.50, 100),
    ('Monitor 21 pol LED', 'CFTV', 480.00, 25),
    ('Central de Alarme Intelbras AMT 2018 EG', 'Alarme', 280.00, 35),
    ('Sensor de Presenca IVP Intelbras', 'Alarme', 45.00, 50),
    ('Sensor Magnetico de Abertura', 'Alarme', 12.00, 80),
    ('Sirene Ativa 120dB', 'Alarme', 35.00, 60),
    ('Teclado de Alarme LCD Intelbras', 'Alarme', 90.00, 40),
    ('Bateria Selada 12V 7Ah', 'Alarme', 55.00, 45),
    ('Cabo 4 Vias Alarme Rolo 100m', 'Alarme', 65.00, 35),
    ('Eletrificador Genno 500m Bivolt', 'Cerca Eletrica', 180.00, 40),
    ('Eletrificador Genno 1000m Bivolt', 'Cerca Eletrica', 280.00, 35),
    ('Fio Aco Inox 0.7mm Rolo 500m', 'Cerca Eletrica', 95.00, 35),
    ('Isolador para Cerca Eletrica', 'Cerca Eletrica', 0.80, 150),
    ('Suporte Lateral para Cerca 20cm', 'Cerca Eletrica', 8.00, 80),
    ('Placa Advertencia Cerca Eletrica', 'Cerca Eletrica', 5.00, 100),
    ('Motor Deslizante PPA Gatter Steel 1/4', 'Motor de Portao', 650.00, 30),
    ('Motor Deslizante PPA Gatter Steel 1/3', 'Motor de Portao', 850.00, 30),
    ('Motor Basculante PPA Home 1/4', 'Motor de Portao', 480.00, 30),
    ('Rack de Nylon Metro', 'Motor de Portao', 18.00, 60),
    ('Controle Remoto PPA par', 'Motor de Portao', 45.00, 60),
    ('Central Motor PPA', 'Motor de Portao', 120.00, 40),
    ('Painel Solar 400W Monocristalino', 'Energia Solar', 480.00, 25),
    ('Inversor Solar 3kW Growatt', 'Energia Solar', 1800.00, 20),
    ('Inversor Solar 5kW Growatt', 'Energia Solar', 2800.00, 20),
    ('Cabo Solar 6mm Metro', 'Energia Solar', 4.50, 60),
    ('Conector MC4 par', 'Energia Solar', 5.00, 80),
    ('Disjuntor CC 32A', 'Energia Solar', 45.00, 50),
    ('String Box 2E 2S', 'Energia Solar', 180.00, 35),
    ('Estrutura de Fixacao Painel Solar', 'Energia Solar', 85.00, 40),
    ('Switch PoE 8 Portas Intelbras', 'Rede', 320.00, 35),
    ('Roteador Wi-Fi Dual Band TP-Link', 'Rede', 180.00, 35),
    ('Cabo de Rede CAT6 Rolo 305m', 'Rede', 280.00, 30),
    ('Conector RJ45 CAT6 100un', 'Rede', 28.00, 60),
    ('Patch Panel 24 Portas CAT6', 'Rede', 180.00, 35),
    ('Rack de Parede 12U', 'Rede', 320.00, 30),
    ('Nobreak 1400VA NHS', 'Rede', 480.00, 25),
    ('Eletroduto Corrugado 3/4 Metro', 'Materiais', 2.50, 80),
    ('Abracadeira Nylon 100un', 'Materiais', 8.00, 100),
    ('Fita Isolante Rolo', 'Materiais', 4.00, 100),
    ('Bucha e Parafuso 100un', 'Materiais', 12.00, 80),
    ('Terminal de Aterramento', 'Materiais', 15.00, 80),
]

with app.app_context():
    emp = Empresa.query.filter_by(cnpj='45.127.220/0001-19').first()
    print(f'Empresa: {emp.fantasia}')
    srv = 0
    for nome, desc, preco, unid in SERVICOS:
        if not Servico.query.filter_by(empresa_id=emp.id, nome=nome).first():
            db.session.add(Servico(empresa_id=emp.id, nome=nome, descricao=desc, preco_unitario=preco, unidade=unid))
            srv += 1
    prod = 0
    for nome, cat, custo, mkp in PRODUTOS:
        if not Produto.query.filter_by(empresa_id=emp.id, nome=nome).first():
            db.session.add(Produto(empresa_id=emp.id, nome=nome, categoria=cat, preco_custo=custo, markup_padrao=mkp, preco_venda=round(custo*(1+mkp/100),2), tipo='produto', ativo=True))
            prod += 1
    db.session.commit()
    print(f'[OK] {srv} servicos inseridos')
    print(f'[OK] {prod} produtos inseridos')
    print('[OK] Concluido!')
