"""
NeuraBusiness v3 — Seed de serviços e materiais da Creative
Executado automaticamente na primeira inicialização
"""

CATALOGO_SERVICOS = [
    # ── IMPRESSORA JATO DE TINTA ──────────────────────────────────────────────
    ("Impressora Jato de Tinta", "Geral",          "Troca do Pickup Roller",                  "Substituição do rolo de alimentação de papel", "un", 0, 0.5),
    ("Impressora Jato de Tinta", "Limpeza",        "Limpeza Geral",                            "Limpeza completa interna e externa da impressora", "un", 0, 1.0),
    ("Impressora Jato de Tinta", "Cabeça",         "Limpeza/Desobstrução da Cabeça de Impressão","Limpeza profunda da cabeça de impressão com kit próprio", "un", 0, 1.0),
    ("Impressora Jato de Tinta", "Reset",          "Reset do Contador de Páginas",             "Reset do contador de manutenção via software", "un", 0, 0.5),
    ("Impressora Jato de Tinta", "Almofadas",      "Troca das Almofadas",                      "Substituição das almofadas de absorção de tinta", "un", 0, 1.0),
    ("Impressora Jato de Tinta", "Encoder",        "Substituição do Disco Encoder",            "Troca do disco encoder de posicionamento do carro", "un", 0, 1.5),
    ("Impressora Jato de Tinta", "Encoder",        "Substituição da Fita Encoder",             "Troca da fita encoder de posicionamento linear", "un", 0, 1.0),
    ("Impressora Jato de Tinta", "Elétrica",       "Substituição da Fonte",                    "Troca da fonte de alimentação interna", "un", 0, 1.5),
    ("Impressora Jato de Tinta", "Cabo",           "Substituição de Cabo Flat",                "Substituição de qualquer cabo flat danificado", "un", 0, 1.0),
    ("Impressora Jato de Tinta", "Kit",            "Substituição do Kit de Limpeza",           "Troca completa do kit de limpeza de cabeça", "un", 0, 1.0),
    ("Impressora Jato de Tinta", "Preventiva",     "Manutenção Preventiva",                    "Revisão completa, limpeza, calibração e testes de qualidade", "un", 0, 2.0),

    # ── IMPRESSORA LASER ─────────────────────────────────────────────────────
    ("Impressora Laser", "Geral",       "Troca do Pickup Roller",           "Substituição do rolo de alimentação", "un", 0, 0.5),
    ("Impressora Laser", "Preventiva",  "Manutenção Preventiva na Unidade Fusora","Revisão e limpeza da unidade fusora, verificação de temperatura", "un", 0, 1.5),
    ("Impressora Laser", "Mecânica",    "Troca de Engrenagem",              "Substituição de engrenagem danificada ou desgastada", "un", 0, 1.0),
    ("Impressora Laser", "Elétrica",    "Troca da Fonte",                   "Substituição da fonte de alimentação", "un", 0, 1.5),
    ("Impressora Laser", "Mecânica",    "Troca do Solenoide",               "Substituição do solenoide de acionamento", "un", 0, 1.0),
    ("Impressora Laser", "Mecânica",    "Troca do Motor",                   "Substituição do motor de acionamento principal", "un", 0, 2.0),
    ("Impressora Laser", "Elétrica",    "Troca da Placa",                   "Substituição da placa controladora/lógica", "un", 0, 2.0),

    # ── COMPUTADOR DESKTOP ───────────────────────────────────────────────────
    ("Computador Desktop", "Térmica",   "Troca de Pasta Térmica",           "Aplicação de pasta térmica de qualidade no processador", "un", 0, 0.5),
    ("Computador Desktop", "Elétrica",  "Troca de Fonte",                   "Substituição da fonte de alimentação ATX", "un", 0, 0.5),
    ("Computador Desktop", "Memória",   "Troca de Memória RAM",             "Instalação/substituição de módulos de memória RAM", "un", 0, 0.5),
    ("Computador Desktop", "CPU",       "Troca de Processador",             "Substituição do processador e reaplicação de pasta térmica", "un", 0, 1.0),
    ("Computador Desktop", "Placa",     "Troca de Placa Mãe",              "Substituição da placa mãe com reinstalação do sistema se necessário", "un", 0, 2.0),
    ("Computador Desktop", "BIOS",      "Troca da Pilha da BIOS",           "Substituição da pilha CR2032 da BIOS", "un", 0, 0.25),
    ("Computador Desktop", "Armazenamento","Troca do HD/SSD",              "Substituição do disco rígido ou SSD com migração de dados", "un", 0, 1.5),
    ("Computador Desktop", "Montagem",  "Montagem de PC Comum",             "Montagem completa de computador para uso geral, configuração de sistema", "un", 0, 3.0),
    ("Computador Desktop", "Montagem",  "Montagem de PC Gamer",             "Montagem de PC gamer com gerenciamento de cabos e configuração de sistema", "un", 0, 4.0),

    # ── NOTEBOOK ─────────────────────────────────────────────────────────────
    ("Notebook", "Térmica",     "Troca de Pasta Térmica",       "Desmontagem completa e aplicação de pasta térmica de alta performance", "un", 0, 1.5),
    ("Notebook", "Armazenamento","Troca de HD/SSD",             "Substituição do disco com migração de dados e instalação do sistema", "un", 0, 2.0),
    ("Notebook", "Memória",     "Upgrade de Memória RAM",       "Instalação de módulo de RAM adicional ou substituição", "un", 0, 0.5),
    ("Notebook", "Elétrica",    "Troca do Conector de Carga",   "Substituição do conector DC Jack ou USB-C de carregamento", "un", 0, 2.0),
    ("Notebook", "Tela",        "Troca de Tela",                "Substituição do display LCD/LED", "un", 0, 2.5),
    ("Notebook", "Teclado",     "Troca de Teclado",             "Substituição do teclado danificado", "un", 0, 1.5),
    ("Notebook", "Preventiva",  "Manutenção Preventiva",        "Limpeza interna, troca de pasta térmica, verificação geral", "un", 0, 2.0),

    # ── REDES E INFRAESTRUTURA ───────────────────────────────────────────────
    ("Redes e Infraestrutura", "Cabeamento",  "Cabeamento Estruturado",       "Passagem e certificação de cabos Cat5e/Cat6 com teste de sinal", "ponto", 0, 1.0),
    ("Redes e Infraestrutura", "Ponto",       "Instalação de Ponto de Rede",  "Instalação de ponto de rede com tomada keystone e patch panel", "ponto", 0, 0.75),
    ("Redes e Infraestrutura", "Firewall",    "Instalação de Firewall",       "Instalação, configuração e regras de segurança em firewall dedicado", "un", 0, 4.0),
    ("Redes e Infraestrutura", "Mikrotik",    "Instalação de Mikrotik",       "Configuração de roteador Mikrotik com DHCP, firewall e QoS", "un", 0, 3.0),
    ("Redes e Infraestrutura", "Projeto",     "Montagem de Rede Completa",    "Projeto completo: cablamento, switches, roteador, firewall e documentação", "projeto", 0, 0),

    # ── CÂMERAS / CFTV ───────────────────────────────────────────────────────
    ("Sistema de Câmeras (CFTV)", "Instalação", "Instalação de Câmera",        "Instalação e configuração de câmera IP ou analógica com ajuste de visão", "ponto", 0, 1.0),
    ("Sistema de Câmeras (CFTV)", "DVR/NVR",   "Configuração de DVR/NVR",     "Configuração do gravador, canais, resolução, armazenamento e acesso remoto", "un", 0, 2.0),
    ("Sistema de Câmeras (CFTV)", "Projeto",    "Projeto CFTV Completo",       "Levantamento, projeto, instalação e configuração de sistema CFTV completo", "projeto", 0, 0),
    ("Sistema de Câmeras (CFTV)", "Manutenção", "Manutenção em Sistema CFTV",  "Revisão, limpeza de câmeras, verificação de cabos e configurações", "un", 0, 2.0),

    # ── ALARME ───────────────────────────────────────────────────────────────
    ("Sistema de Alarme", "Instalação", "Instalação de Alarme",          "Instalação de central de alarme com sensores e sirene", "projeto", 0, 0),
    ("Sistema de Alarme", "Sensor",     "Instalação de Sensor",          "Instalação de sensor de presença, abertura ou vibração", "ponto", 0, 0.5),
    ("Sistema de Alarme", "Manutenção", "Manutenção em Sistema de Alarme","Revisão geral, troca de bateria e teste de todos os sensores", "un", 0, 2.0),

    # ── CERCA ELÉTRICA ───────────────────────────────────────────────────────
    ("Cerca Elétrica", "Instalação", "Instalação de Cerca Elétrica",   "Instalação de fios, isoladores, central e testagem", "metro", 0, 0),
    ("Cerca Elétrica", "Central",    "Configuração da Central",         "Configuração de central de cerca com zonas e sirene", "un", 0, 1.0),
    ("Cerca Elétrica", "Manutenção", "Manutenção de Cerca Elétrica",    "Revisão de fios, isoladores, central e teste de descarga", "un", 0, 2.0),
]

MATERIAIS_INFRA = [
    # Cabos
    ("Cabo de Rede Cat5e 100% Cobre",    "m",  3.50,  "Cabeamento"),
    ("Cabo de Rede Cat6 100% Cobre",     "m",  5.80,  "Cabeamento"),
    ("Cabo de Rede Cat5e Acobreado",     "m",  1.80,  "Cabeamento"),
    ("Cabo Coaxial RG59",                "m",  2.20,  "Cabeamento"),
    ("Cabo Coaxial RG6",                 "m",  3.00,  "Cabeamento"),
    ("Cabo CFTV 4 vias",                 "m",  4.50,  "Cabeamento"),
    ("Cabo Fibra Óptica Monomodo",       "m", 12.00,  "Cabeamento"),
    # Conectores
    ("Conector RJ45 Cat5e/Cat6",         "un",  0.50,  "Conectores"),
    ("Fast Conector RJ45",               "un",  2.20,  "Conectores"),
    ("Conector BNC Compressão",          "un",  1.80,  "Conectores"),
    ("Conector BNC Mola",                "un",  0.80,  "Conectores"),
    ("Conector P4 Macho",                "un",  0.60,  "Conectores"),
    ("Conector SC/APC Fibra",            "un",  8.00,  "Conectores"),
    # Eletroduto e fixação
    ("Eletroduto Corrugado 3/4",         "m",  1.20,  "Fixação"),
    ("Eletroduto Rígido PVC 3/4",        "m",  2.80,  "Fixação"),
    ("Abraçadeira Nylon P/M/G",          "pct", 8.00, "Fixação"),
    ("Curva 90° Eletroduto 3/4",         "un",  0.90,  "Fixação"),
    ("Luva Eletroduto 3/4",              "un",  0.70,  "Fixação"),
    ("Caixa Passagem 4x2",               "un",  2.50,  "Fixação"),
    ("Caixa Passagem Plástica VBOX",     "un", 12.00,  "Fixação"),
    ("Bucha de Nylon + Parafuso",        "un",  0.30,  "Fixação"),
    ("Fita Isolante Antichama",          "un",  4.50,  "Fixação"),
    # Elétrica
    ("Cabo PP 2x1,5mm",                  "m",  3.80,  "Elétrica"),
    ("Tomada RJ45 Keystone Cat6",        "un",  8.00,  "Elétrica"),
    ("Patch Panel 24 portas",            "un", 85.00,  "Elétrica"),
    ("Switch 8 portas não gerenciável",  "un", 120.00, "Ativos de rede"),
    ("Switch 16 portas não gerenciável", "un", 220.00, "Ativos de rede"),
    ("Injetor PoE",                      "un",  55.00, "Ativos de rede"),
    # Cerca elétrica
    ("Fio Cerca Elétrica Inox 0,5mm",    "m",   1.20,  "Cerca Elétrica"),
    ("Isolador de Canto Plástico",       "un",   0.80,  "Cerca Elétrica"),
    ("Isolador de Linha Plástico",       "un",   0.50,  "Cerca Elétrica"),
    ("Suporte de Cerca Elétrica",        "un",   3.50,  "Cerca Elétrica"),
]

def seed_catalogo(empresa_id, execute_fn, query_fn):
    """Insere serviços e materiais se ainda não existirem para a empresa"""
    existe = query_fn(
        "SELECT COUNT(*) as c FROM catalogo_servicos WHERE empresa_id=?",
        (empresa_id,), one=True
    )
    if existe and existe['c'] > 0:
        return  # Já foi inserido

    for cat, sub, nome, desc, unid, preco, tempo in CATALOGO_SERVICOS:
        execute_fn(
            "INSERT INTO catalogo_servicos (empresa_id,categoria,subcategoria,nome,descricao,unidade,preco_base,tempo_horas) VALUES (?,?,?,?,?,?,?,?)",
            (empresa_id, cat, sub, nome, desc, unid, preco, tempo)
        )

    existe_mat = query_fn(
        "SELECT COUNT(*) as c FROM materiais_infra WHERE empresa_id=?",
        (empresa_id,), one=True
    )
    if not existe_mat or existe_mat['c'] == 0:
        for nome, unid, preco, cat in MATERIAIS_INFRA:
            execute_fn(
                "INSERT INTO materiais_infra (empresa_id,nome,unidade,preco_unitario,categoria) VALUES (?,?,?,?,?)",
                (empresa_id, nome, unid, preco, cat)
            )

    print(f"✅ Catálogo de serviços e materiais inseridos para empresa {empresa_id}")


def seed_catalogo_sqla(empresa_id):
    """Versão SQLAlchemy do seed de catálogo"""
    from models import db, CatalogoServico, MaterialInfra
    
    if CatalogoServico.query.filter_by(empresa_id=empresa_id).count() > 0:
        return
    
    for cat, sub, nome, desc, unid, preco, tempo in CATALOGO_SERVICOS:
        db.session.add(CatalogoServico(
            empresa_id=empresa_id, categoria=cat, subcategoria=sub,
            nome=nome, descricao=desc, unidade=unid, preco_base=preco, tempo_horas=tempo))
    
    if MaterialInfra.query.filter_by(empresa_id=empresa_id).count() == 0:
        for nome, unid, preco, cat in MATERIAIS_INFRA:
            db.session.add(MaterialInfra(
                empresa_id=empresa_id, nome=nome, unidade=unid,
                preco_unitario=preco, categoria=cat))
    
    db.session.commit()
    print(f"✅ Catálogo inserido para empresa {empresa_id}")
