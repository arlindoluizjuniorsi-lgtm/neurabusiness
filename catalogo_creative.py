"""NeuraBusiness — Catálogo Creative + Motor de Precificação MEI"""

CATALOGO = [
    # (categoria, subcategoria, nome, desc_tecnica, desc_cliente, tipo_preco, preco_base, unidade, tempo_horas)
    ('Impressora Jato de Tinta','Mecânica','Troca do Pickup Roller','Substituição do rolo de alimentação de papel.','Troca do rolo de alimentação — resolve papel não entrando ou travando.','fixo',0,'serviço',0.5),
    ('Impressora Jato de Tinta','Limpeza','Limpeza Geral','Limpeza interna completa: pó, tinta acumulada, rolos e guias.','Limpeza completa interna, aumentando vida útil e qualidade de impressão.','fixo',0,'serviço',1.0),
    ('Impressora Jato de Tinta','Limpeza','Limpeza e Desobstrução da Cabeça de Impressão','Limpeza profunda dos bicos com solvente específico e ciclos de purga.','Resolve listras, falhas ou ausência de cor. Recupera a qualidade original.','fixo',0,'serviço',1.0),
    ('Impressora Jato de Tinta','Software','Reset do Contador de Páginas','Reset do contador interno via software específico.','Elimina o bloqueio por absorvedores cheios sem trocar peças.','fixo',0,'serviço',0.5),
    ('Impressora Jato de Tinta','Mecânica','Troca das Almofadas','Substituição física das almofadas de absorção + reset do contador.','Solução definitiva para o bloqueio por absorvedores cheios.','fixo',0,'serviço',1.0),
    ('Impressora Jato de Tinta','Mecânica','Substituição do Disco Encoder','Troca do disco encoder de posicionamento do cabeçote.','Resolve erros de alinhamento e travamentos do cabeçote.','fixo',0,'serviço',1.5),
    ('Impressora Jato de Tinta','Mecânica','Substituição da Fita Encoder','Troca da fita encoder linear de posicionamento.','Elimina erros de impressão e traços deslocados.','fixo',0,'serviço',1.0),
    ('Impressora Jato de Tinta','Elétrica','Substituição da Fonte','Troca da fonte de alimentação interna com medição de tensões.','Resolve desligamentos, falhas de ligação e erro de voltagem.','fixo',0,'serviço',1.5),
    ('Impressora Jato de Tinta','Mecânica','Substituição de Cabo Flat','Troca de qualquer cabo flat danificado com teste funcional.','Resolve erros de comunicação entre componentes.','fixo',0,'serviço',1.0),
    ('Impressora Jato de Tinta','Mecânica','Substituição do Kit de Limpeza','Troca completa: absorvedores, bomba e tubos com reset.','Manutenção abrangente do sistema de tinta.','fixo',0,'serviço',1.5),
    ('Impressora Jato de Tinta','Preventiva','Manutenção Preventiva Completa','Revisão completa: limpeza, mecânica, elétrica, lubrificação e testes.','Revisão completa para prevenir problemas e maximizar a vida útil.','fixo',0,'serviço',2.0),
    ('Impressora Laser','Mecânica','Troca do Pickup Roller','Substituição do rolo de alimentação de papel.','Resolve papel não entrando ou atolamentos frequentes.','fixo',0,'serviço',0.5),
    ('Impressora Laser','Preventiva','Manutenção Preventiva na Unidade Fusora','Revisão da unidade fusora: limpeza, temperatura, fusão e lubrificação.','Previne manchas e falhas na impressão.','fixo',0,'serviço',1.5),
    ('Impressora Laser','Mecânica','Troca de Engrenagem','Substituição de engrenagem danificada do conjunto mecânico.','Elimina ruídos e problemas de alimentação de papel.','fixo',0,'serviço',1.0),
    ('Impressora Laser','Elétrica','Troca da Fonte','Substituição da fonte com medição e teste completo de tensões.','Resolve problemas de ligação, desligamentos e erros elétricos.','fixo',0,'serviço',1.5),
    ('Impressora Laser','Mecânica','Troca do Solenoide','Substituição do solenoide de acionamento.','Resolve problemas de alimentação e separação de papel.','fixo',0,'serviço',1.0),
    ('Impressora Laser','Mecânica','Troca do Motor','Substituição do motor com alinhamento e teste.','Resolve travamentos, ruídos e falhas de movimentação.','fixo',0,'serviço',2.0),
    ('Impressora Laser','Elétrica','Troca da Placa Principal','Substituição da placa controladora com reprogramação de firmware.','Resolve erros de comunicação e falhas permanentes.','fixo',0,'serviço',2.0),
    ('Computador Desktop','Térmica','Troca de Pasta Térmica','Remoção da pasta antiga, limpeza e aplicação de pasta de alta condutividade.','Reduz temperatura, evita travamentos e aumenta desempenho.','fixo',0,'serviço',0.5),
    ('Computador Desktop','Elétrica','Troca de Fonte','Substituição da fonte ATX com teste de potência e compatibilidade.','Resolve desligamentos, instabilidades e computador que não liga.','fixo',0,'serviço',0.5),
    ('Computador Desktop','Memória','Upgrade de Memória RAM','Instalação ou substituição de módulos RAM com teste de estabilidade.','Computador mais rápido e com mais capacidade multitarefa.','fixo',0,'serviço',0.5),
    ('Computador Desktop','Processador','Troca de Processador','Substituição com verificação de compatibilidade e teste de estabilidade.','Upgrade de processador — desempenho significativamente superior.','fixo',0,'serviço',1.0),
    ('Computador Desktop','Placa-mãe','Troca de Placa-mãe','Substituição com reinstalação de componentes e configuração de BIOS.','Solução para falhas críticas que impedem o funcionamento.','fixo',0,'serviço',2.0),
    ('Computador Desktop','BIOS','Troca da Pilha da BIOS','Substituição da pilha CR2032 com reconfiguração de data e hora.','Resolve data incorreta e configurações que resetam.','fixo',0,'serviço',0.25),
    ('Computador Desktop','Armazenamento','Troca de HD / Instalação de SSD','Substituição com clonagem de dados e reinstalação do sistema.','Computador mais rápido (SSD) ou substituição de HD com defeito.','fixo',0,'serviço',1.5),
    ('Computador Desktop','Montagem','Montagem de PC Completo','Montagem completa: instalação de componentes, cabos, BIOS e SO.','Montagem profissional — hardware correto, sistema configurado e pronto.','fixo',0,'serviço',3.0),
    ('Computador Desktop','Montagem','Montagem de PC Gamer','Montagem gamer: cabos premium, RGB, overclock seguro, drivers.','PC gamer profissional — performance máxima e estabilidade garantida.','fixo',0,'serviço',4.0),
    ('Notebook','Térmica','Troca de Pasta Térmica','Desmontagem completa, limpeza de pó e troca da pasta térmica.','Notebook mais frio, silencioso e sem travamentos.','fixo',0,'serviço',1.5),
    ('Notebook','Armazenamento','Troca de HD / Instalação de SSD','Substituição com clonagem ou instalação limpa do sistema.','Notebook muito mais rápido ou substituição de HD com defeito.','fixo',0,'serviço',2.0),
    ('Notebook','Memória','Upgrade de Memória RAM','Verificação de slots e instalação de módulo adicional.','Mais memória — roda mais programas sem lentidão.','fixo',0,'serviço',0.5),
    ('Notebook','Elétrica','Troca do Conector de Carga','Substituição do conector DC Jack ou USB-C com solda profissional.','Notebook volta a carregar normalmente.','fixo',0,'serviço',2.0),
    ('Notebook','Display','Troca de Tela','Substituição do display LCD/LED verificando resolução e conectores.','Elimina rachaduras, linhas, manchas ou ausência de imagem.','fixo',0,'serviço',2.5),
    ('Notebook','Teclado','Troca de Teclado','Substituição com desmontagem e teste de todas as teclas.','Resolve teclas travadas, faltando ou não respondendo.','fixo',0,'serviço',1.5),
    ('Notebook','Preventiva','Manutenção Preventiva Completa','Limpeza interna, pasta térmica, bateria e testes de hardware.','Revisão completa — mais frio, mais rápido, vida útil prolongada.','fixo',0,'serviço',2.5),
    ('Redes e Infraestrutura','Cabeamento','Cabeamento Estruturado (por metro)','Passagem de cabo Cat5e/Cat6 100% cobre em eletroduto com certificação.','Cabeamento organizado e certificado — conexão estável em todo o ambiente.','metro',0,'metro',0),
    ('Redes e Infraestrutura','Cabeamento','Instalação de Ponto de Rede','Ponto completo: cabo, tomada keystone, patch panel, teste e certificação.','Ponto de rede instalado e certificado.','ponto',0,'ponto',0.75),
    ('Redes e Infraestrutura','Firewall','Instalação e Configuração de Firewall','Instalação de pfSense/OPNsense com regras, VLANs, VPN e relatórios.','Proteção completa da rede — controle de acesso e bloqueio de ameaças.','fixo',0,'serviço',4.0),
    ('Redes e Infraestrutura','Roteadores','Instalação e Configuração de Mikrotik','Configuração de Mikrotik: DHCP, firewall, QoS, hotspot e acesso remoto.','Rede profissional — controle total de tráfego e qualidade de sinal.','fixo',0,'serviço',3.0),
    ('Redes e Infraestrutura','Projeto','Rede Completa — sob Orçamento','Levantamento, projeto completo, materiais, execução e documentação.','Rede completa projetada e executada — tudo documentado e certificado.','orcamento',0,'projeto',0),
    ('Sistema de Câmeras (CFTV)','Instalação','Instalação de Câmera (por ponto)','Fixação, passagem de cabo, ajuste de visão e configuração no gravador.','Câmera instalada e configurada — monitoramento no celular e gravador.','ponto',0,'câmera',1.0),
    ('Sistema de Câmeras (CFTV)','Configuração','Configuração de DVR/NVR','Configuração: canais, resolução, gravação, motion detection e acesso remoto.','Gravador configurado com acesso pelo celular de qualquer lugar.','fixo',0,'serviço',2.0),
    ('Sistema de Câmeras (CFTV)','Projeto','Projeto Completo CFTV — sob Orçamento','Levantamento de campo, projeto, materiais, instalação e configuração.','Sistema CFTV completo projetado para o seu ambiente — cobertura total.','orcamento',0,'projeto',0),
    ('Sistema de Câmeras (CFTV)','Manutenção','Manutenção em Sistema CFTV','Limpeza de câmeras, verificação de cabos, firmware e backup de config.','Câmeras limpas, cabos verificados e sistema funcionando.','fixo',0,'serviço',2.0),
    ('Sistema de Alarme','Instalação','Instalação de Sistema de Alarme — sob Orçamento','Instalação de central, sensores, sirene e configuração de zonas.','Alarme completo instalado e programado com notificação no celular.','orcamento',0,'projeto',0),
    ('Sistema de Alarme','Instalação','Instalação de Sensor (por ponto)','Instalação de sensor de presença, abertura ou vibração com programação.','Sensor instalado e programado na central.','ponto',0,'sensor',0.5),
    ('Sistema de Alarme','Manutenção','Manutenção em Sistema de Alarme','Revisão da central, bateria, teste de sensores e sirene, senhas.','Revisão completa do alarme — tudo testado e bateria nova.','fixo',0,'serviço',2.0),
    ('Cerca Elétrica','Instalação','Instalação de Cerca Elétrica — sob Orçamento','Instalação de central, fios, isoladores, suportes e testagem.','Cerca elétrica instalada e testada — barreira ativa de segurança.','orcamento',0,'projeto',0),
    ('Cerca Elétrica','Configuração','Configuração de Central de Cerca','Configuração: zonas, sirene, sensores e integração com alarme.','Central programada com zonas e integração ao alarme.','fixo',0,'serviço',1.0),
    ('Cerca Elétrica','Manutenção','Manutenção de Cerca Elétrica','Verificação de fios, isoladores, tensão e reparo de pontos danificados.','Fios, isoladores e central verificados — descarga testada.','fixo',0,'serviço',2.0),
]

# ─── PRECIFICAÇÃO MEI ──────────────────────────────────────────────────────────
DAS_SERVICO   = 0.05   # 5% DAS MEI serviço (INSS + ISS)
DAS_COMERCIO  = 0.01   # 1% DAS MEI comércio
RESERVA       = 0.05   # 5% reserva operacional
CONSUMO_EST   = 11.5   # km/l estrada - Linea 1.8
CONSUMO_CID   = 9.5    # km/l cidade
PRECO_GAS     = 6.60   # R$/L gasolina Mataraca-PB

def calcular_preco_servico(custo_materiais=0, horas=0, valor_hora=80,
                            km=0, tipo_via='estrada', refeicoes=0, margem=30):
    consumo = CONSUMO_EST if tipo_via == 'estrada' else CONSUMO_CID
    c_comb  = (km / consumo) * PRECO_GAS if km > 0 else 0
    c_ref   = refeicoes * 25.0
    c_desloc= c_comb + c_ref
    c_mao   = horas * valor_hora
    c_total = custo_materiais + c_mao + c_desloc
    impostos= DAS_SERVICO + RESERVA
    margem_d= margem / 100
    divisor = max(1 - impostos - margem_d, 0.1)
    preco   = c_total / divisor
    return {
        'custo_materiais':    round(custo_materiais, 2),
        'custo_mao_obra':     round(c_mao, 2),
        'custo_deslocamento': round(c_desloc, 2),
        'custo_total':        round(c_total, 2),
        'preco_sugerido':     round(preco, 2),
        'preco_arredondado':  round(preco / 5) * 5,
        'preco_minimo':       round(c_total / max(1 - impostos, 0.1), 2),
        'valor_das':          round(preco * DAS_SERVICO, 2),
        'valor_reserva':      round(preco * RESERVA, 2),
        'valor_lucro':        round(preco * margem_d, 2),
        'margem_pct':         margem,
    }

def calcular_preco_produto(preco_custo=0, margem=30):
    if preco_custo <= 0:
        return {'erro': 'Preço de custo inválido'}
    impostos= DAS_COMERCIO + RESERVA
    margem_d= margem / 100
    divisor = max(1 - impostos - margem_d, 0.1)
    preco   = preco_custo / divisor
    return {
        'preco_custo':       round(preco_custo, 2),
        'custo_total':       round(preco_custo, 2),
        'preco_sugerido':    round(preco, 2),
        'preco_arredondado': round(preco / 5) * 5,
        'preco_minimo':      round(preco_custo / max(1 - impostos, 0.1), 2),
        'markup_real_pct':   round(((preco - preco_custo) / preco_custo) * 100, 1),
        'valor_das':         round(preco * DAS_COMERCIO, 2),
        'valor_reserva':     round(preco * RESERVA, 2),
        'valor_lucro':       round(preco * margem_d, 2),
        'margem_pct':        margem,
    }

def seed_catalogo_completo(empresa_id):
    """Insere catálogo completo via SQLAlchemy"""
    from models import db, CatalogoServico
    if CatalogoServico.query.filter_by(empresa_id=empresa_id).count() > 0:
        return 0
    count = 0
    for cat, sub, nome, desc, desc_cli, tipo, preco, unid, horas in CATALOGO:
        db.session.add(CatalogoServico(
            empresa_id=empresa_id, categoria=cat, subcategoria=sub,
            nome=nome, descricao=desc, descricao_cliente=desc_cli,
            tipo_preco=tipo, preco_base=preco, unidade=unid, tempo_horas=horas))
        count += 1
    db.session.commit()
    print(f"✅ {count} serviços inseridos no catálogo")
    return count
