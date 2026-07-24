"""
Seed de Produtos Completo — Creative Solucoes
Adiciona produtos novos sem duplicar os existentes
Execute: python3 seed_produtos_completo.py
"""
import sys
sys.path.insert(0, '/opt/neurabusiness')
from app import app, db
from models import Empresa, Produto

PRODUTOS = [
    # ─── CÂMERAS INTELBRAS ────────────────────────────────────────
    ('Camera IP Bullet Intelbras VIP 1120 B', 'CFTV', 120.00, 40),
    ('Camera IP Dome Intelbras VIP 1120 D', 'CFTV', 125.00, 40),
    ('Camera IP Bullet Intelbras VIP 1220 B Full Color', 'CFTV', 165.00, 38),
    ('Camera IP Dome Intelbras VIP 1220 D Full Color', 'CFTV', 170.00, 38),
    ('Camera IP VIP 1230 D Intelbras', 'CFTV', 220.00, 35),

    # ─── DVR INTELBRAS ───────────────────────────────────────────
    ('DVR Intelbras MHDX 4 Canais', 'CFTV', 465.00, 25),
    ('DVR Intelbras MHDX 8 Canais', 'CFTV', 656.00, 25),
    ('DVR Intelbras MHDX 16 Canais', 'CFTV', 1078.00, 22),
    ('DVR Intelbras MHDX 32 Canais', 'CFTV', 2100.00, 20),

    # ─── NVR INTELBRAS ───────────────────────────────────────────
    ('NVR Intelbras iNVD 4 Canais', 'CFTV', 580.00, 28),
    ('NVR Intelbras iNVD 8 Canais', 'CFTV', 980.00, 25),
    ('NVR Intelbras iNVD 16 Canais', 'CFTV', 1800.00, 22),
    ('NVR Intelbras iNVD 32 Canais', 'CFTV', 3200.00, 20),

    # ─── HD PARA CFTV ────────────────────────────────────────────
    ('HD 1TB CFTV WD Purple', 'CFTV', 280.00, 25),
    ('HD 2TB CFTV WD Purple', 'CFTV', 420.00, 25),
    ('HD 4TB CFTV WD Purple', 'CFTV', 680.00, 22),

    # ─── ACESSÓRIOS CFTV ─────────────────────────────────────────
    ('Fonte 12V 5A Bivolt', 'CFTV', 35.00, 60),
    ('Fonte 12V 10A Bivolt', 'CFTV', 55.00, 55),
    ('Conector P4 Macho (50un)', 'CFTV', 18.00, 80),
    ('Balun VB 501 Intelbras', 'CFTV', 25.00, 70),
    ('Cabo Coaxial 4 Vias Rolo 100m', 'CFTV', 95.00, 35),
    ('Cabo de Rede CAT6 Rolo 305m', 'REDE', 280.00, 30),
    ('Rack Vertical CFTV Intelbras', 'CFTV', 155.00, 35),
    ('Rack Montado CFTV Intelbras', 'CFTV', 320.00, 30),
    ('Suporte Articulado para Camera', 'CFTV', 28.00, 70),
    ('Caixa Hermetica de Sobrepor VBOX 1100', 'CFTV', 35.00, 65),
    ('Filtro de Linhas 5 Tomadas', 'CFTV', 38.00, 60),
    ('Conector BNC (50un)', 'CFTV', 22.00, 80),
    ('Monitor 21 pol LED', 'CFTV', 480.00, 25),

    # ─── SSD ─────────────────────────────────────────────────────
    ('SSD 256GB', 'Informatica', 95.00, 40),
    ('SSD 480GB', 'Informatica', 145.00, 38),
    ('SSD 960GB', 'Informatica', 230.00, 35),

    # ─── ADAPTADORES ─────────────────────────────────────────────
    ('Adaptador Extensor RJ45 para HDMI', 'Informatica', 85.00, 55),

    # ─── SWITCHES ────────────────────────────────────────────────
    ('Switch 5 Portas Fast TP-Link', 'REDE', 55.00, 50),
    ('Switch 5 Portas Fast Intelbras', 'REDE', 60.00, 48),
    ('Switch 8 Portas Fast TP-Link', 'REDE', 85.00, 45),
    ('Switch 8 Portas Fast Intelbras', 'REDE', 90.00, 45),
    ('Switch 5 Portas Gigabit TP-Link', 'REDE', 80.00, 48),
    ('Switch 5 Portas Gigabit Intelbras', 'REDE', 85.00, 48),
    ('Switch 8 Portas Gigabit TP-Link', 'REDE', 120.00, 42),
    ('Switch 8 Portas Gigabit Intelbras', 'REDE', 125.00, 42),
    ('Switch PoE 8 Portas Gigabit Intelbras Nao Gerenciavel', 'REDE', 320.00, 35),
    ('Patch Panel 24 Portas CAT6', 'REDE', 180.00, 35),
    ('Rack de Parede 12U', 'REDE', 320.00, 30),
    ('Nobreak 1400VA NHS', 'REDE', 480.00, 25),
    ('Nobreak Intelbras Attiv 700VA Bivolt', 'REDE', 320.00, 30),
    ('Nobreak Intelbras Attiv 1500VA Bivolt', 'REDE', 580.00, 28),
    ('Conector RJ45 CAT6 (100un)', 'REDE', 28.00, 60),

    # ─── ALARME ──────────────────────────────────────────────────
    ('Central de Alarme Intelbras AMT 2018 EG', 'Alarme', 280.00, 35),
    ('Sensor de Presenca Intelbras IVP', 'Alarme', 45.00, 55),
    ('Sensor Magnetico de Abertura Intelbras', 'Alarme', 18.00, 80),
    ('Sirene Ativa 120dB', 'Alarme', 35.00, 65),
    ('Teclado de Alarme LCD Intelbras', 'Alarme', 90.00, 40),
    ('Bateria Selada 12V 7Ah', 'Alarme', 55.00, 45),
    ('Cabo 4 Vias Alarme Rolo 100m', 'Alarme', 65.00, 38),
    ('Fechadura Eletronica Intelbras', 'Alarme', 280.00, 35),
    ('Fechadura Eletronica AGL', 'Alarme', 320.00, 32),

    # ─── MOTOR DE PORTÃO ─────────────────────────────────────────
    ('Motor Deslizante Garen KDZ FIT 1/4 HP 500kg', 'Motor de Portao', 580.00, 32),
    ('Motor Deslizante Garen KDZ TSI 1/3 HP 700kg', 'Motor de Portao', 750.00, 30),
    ('Motor Deslizante Garen Durata 1/2 HP 1500kg', 'Motor de Portao', 1100.00, 28),
    ('Motor Deslizante Rossi DZ Nano Nitro 650kg', 'Motor de Portao', 680.00, 30),
    ('Motor Deslizante Rossi DZ4 SK Turbo 800kg', 'Motor de Portao', 850.00, 28),
    ('Motor Deslizante Rossi DZ4 Nitro 850kg', 'Motor de Portao', 950.00, 28),
    ('Motor Deslizante PPA Gatter Steel 1/4', 'Motor de Portao', 650.00, 30),
    ('Motor Deslizante PPA Gatter Steel 1/3', 'Motor de Portao', 850.00, 28),
    ('Capacitor de Motor de Portao', 'Motor de Portao', 22.00, 100),
    ('Cremalheira de Motor de Portao Metro', 'Motor de Portao', 18.00, 65),
    ('Controle Remoto (par)', 'Motor de Portao', 45.00, 65),
    ('Central Motor PPA', 'Motor de Portao', 120.00, 45),

    # ─── CERCA ELÉTRICA ──────────────────────────────────────────
    ('Eletrificador ELC 6012 Net Intelbras', 'Cerca Eletrica', 280.00, 42),
    ('Eletrificador Genno 500m Bivolt', 'Cerca Eletrica', 180.00, 45),
    ('Eletrificador Genno 1000m Bivolt', 'Cerca Eletrica', 280.00, 38),
    ('Fio Aco Inox 0.7mm Bobina 500m', 'Cerca Eletrica', 95.00, 40),
    ('Cabo de Alta Isolacao para Cerca Eletrica Metro', 'Cerca Eletrica', 3.50, 80),
    ('Haste de Cerca 25x25 4 Isoladores', 'Cerca Eletrica', 32.00, 70),
    ('Haste de Cerca 25x25 6 Isoladores', 'Cerca Eletrica', 42.00, 65),
    ('Haste de Canto 28x28 4 Isoladores', 'Cerca Eletrica', 48.00, 65),
    ('Haste de Canto 28x28 6 Isoladores', 'Cerca Eletrica', 58.00, 60),
    ('Isolador para Cerca Eletrica (un)', 'Cerca Eletrica', 0.90, 130),
    ('Placa de Advertencia Cerca Eletrica', 'Cerca Eletrica', 5.00, 100),

    # ─── ENERGIA SOLAR ───────────────────────────────────────────
    ('Painel Solar 400W Monocristalino', 'Energia Solar', 480.00, 25),
    ('Inversor Solar 3kW Growatt', 'Energia Solar', 1800.00, 20),
    ('Inversor Solar 5kW Growatt', 'Energia Solar', 2800.00, 20),
    ('Cabo Solar 6mm Metro', 'Energia Solar', 4.50, 65),
    ('Conector MC4 (par)', 'Energia Solar', 5.50, 80),
    ('Disjuntor CC 32A', 'Energia Solar', 45.00, 55),
    ('String Box 2E/2S', 'Energia Solar', 180.00, 38),
    ('Estrutura de Fixacao Painel Solar (un)', 'Energia Solar', 85.00, 42),

    # ─── MATERIAIS GERAIS ────────────────────────────────────────
    ('Eletroduto Corrugado 3/4 Metro', 'Materiais', 2.50, 80),
    ('Abracadeira Nylon (100un)', 'Materiais', 8.00, 100),
    ('Fita Isolante Rolo', 'Materiais', 4.00, 100),
    ('Bucha e Parafuso (100un)', 'Materiais', 12.00, 80),
    ('Terminal de Aterramento', 'Materiais', 15.00, 80),
]

with app.app_context():
    emp = Empresa.query.filter_by(cnpj='45.127.220/0001-19').first()
    if not emp:
        print('[ERRO] Empresa nao encontrada!')
        exit(1)

    print(f'[OK] Empresa: {emp.fantasia}')
    count = 0
    skip = 0
    for nome, cat, custo, mkp in PRODUTOS:
        existe = Produto.query.filter_by(empresa_id=emp.id, nome=nome).first()
        if not existe:
            venda = round(custo * (1 + mkp / 100), 2)
            db.session.add(Produto(
                empresa_id=emp.id, nome=nome, categoria=cat,
                preco_custo=custo, markup_padrao=mkp,
                preco_venda=venda, tipo='produto', ativo=True
            ))
            count += 1
        else:
            skip += 1

    db.session.commit()
    print(f'[OK] {count} produtos inseridos')
    print(f'[--] {skip} ja existiam (ignorados)')
    print('[OK] Concluido!')
