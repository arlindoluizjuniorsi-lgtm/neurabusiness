"""
NeuraBusiness v3 — Calculadoras de Precificação
MEI, Serviços, Deslocamento e Infraestrutura
"""

# ─── CONSTANTES MEI ──────────────────────────────────────────────────────────
# Baseado em valores de 2024/2025 para MEI
MEI_DAS_PERCENTUAL  = 0.05    # 5% sobre faturamento bruto (serviços)
MEI_INSS_PERCENTUAL = 0.05    # já incluso no DAS
MEI_FATURAMENTO_MAX = 81000   # teto anual MEI
ISS_PERCENTUAL      = 0.02    # ISS médio municipal (2% a 5%, usando 2%)
RESERVA_PERCENTUAL  = 0.05    # Reserva para imprevistos e reposição

# Combustível — Linea 1.8 Dualogic
CONSUMO_KML_ESTRADA = 11.5    # km/l média estrada
CONSUMO_KML_CIDADE  = 9.5     # km/l média cidade
PRECO_GASOLINA      = 6.60    # R$/litro em Mataraca-PB
CIDADE_BASE         = "Mataraca-PB"

def calcular_preco_mei(preco_custo, margem_desejada_pct, tipo='servico',
                        incluir_deslocamento=0, horas_execucao=0, valor_hora=0):
    """
    Calcula preço de venda recomendado para MEI considerando:
    - DAS 5% sobre receita
    - ISS 2% sobre receita (serviços)
    - Reserva para imprevistos
    - Margem de lucro desejada
    - Custo de deslocamento
    - Custo de mão de obra (tempo)

    Retorna dict com breakdown completo
    """
    # Custo total base
    custo_mao_obra = horas_execucao * valor_hora if horas_execucao and valor_hora else 0
    custo_total    = preco_custo + custo_mao_obra + incluir_deslocamento

    # Fórmula: Preço = Custo / (1 - impostos - reserva - margem)
    if tipo == 'servico':
        deducoes = MEI_DAS_PERCENTUAL + ISS_PERCENTUAL + RESERVA_PERCENTUAL
    else:  # produto/revenda
        deducoes = MEI_DAS_PERCENTUAL + RESERVA_PERCENTUAL

    margem_dec = margem_desejada_pct / 100
    divisor = 1 - deducoes - margem_dec

    if divisor <= 0:
        divisor = 0.3  # proteção contra divisão por zero

    preco_final     = custo_total / divisor
    valor_impostos  = preco_final * (MEI_DAS_PERCENTUAL + (ISS_PERCENTUAL if tipo == 'servico' else 0))
    valor_reserva   = preco_final * RESERVA_PERCENTUAL
    valor_lucro     = preco_final * margem_dec
    markup_real     = ((preco_final - preco_custo) / preco_custo * 100) if preco_custo > 0 else 0

    return {
        'custo_produto':    round(preco_custo, 2),
        'custo_mao_obra':   round(custo_mao_obra, 2),
        'custo_desloc':     round(incluir_deslocamento, 2),
        'custo_total':      round(custo_total, 2),
        'preco_sugerido':   round(preco_final, 2),
        'preco_arredond':   round(preco_final / 5) * 5,  # arredondado para múltiplo de 5
        'valor_impostos':   round(valor_impostos, 2),
        'valor_reserva':    round(valor_reserva, 2),
        'valor_lucro':      round(valor_lucro, 2),
        'markup_real_pct':  round(markup_real, 1),
        'margem_desejada':  margem_desejada_pct,
        'das_pct':          MEI_DAS_PERCENTUAL * 100,
        'iss_pct':          ISS_PERCENTUAL * 100 if tipo == 'servico' else 0,
        'tipo':             tipo,
    }


def calcular_deslocamento(distancia_km, tipo_via='estrada',
                           refeicoes=0, diaria=0, pedagios=0):
    """
    Calcula custo total de deslocamento para Linea 1.8 de Mataraca-PB

    Args:
        distancia_km: distância total ida+volta em km
        tipo_via: 'estrada' ou 'cidade'
        refeicoes: número de refeições estimadas (custo médio R$25/refeição)
        diaria: valor de diária se necessário pernoite
        pedagios: valor total de pedágios estimado

    Returns:
        dict com breakdown detalhado
    """
    consumo = CONSUMO_KML_ESTRADA if tipo_via == 'estrada' else CONSUMO_KML_CIDADE
    litros   = distancia_km / consumo
    custo_combustivel = litros * PRECO_GASOLINA

    custo_refeicoes  = refeicoes * 25.0
    custo_total = custo_combustivel + custo_refeicoes + diaria + pedagios

    # Tempo estimado de viagem (60km/h estrada, 30km/h cidade)
    velocidade = 60 if tipo_via == 'estrada' else 30
    tempo_horas = (distancia_km / velocidade)

    return {
        'distancia_km':       distancia_km,
        'tipo_via':           tipo_via,
        'consumo_kml':        consumo,
        'litros':             round(litros, 2),
        'preco_gasolina':     PRECO_GASOLINA,
        'custo_combustivel':  round(custo_combustivel, 2),
        'refeicoes':          refeicoes,
        'custo_refeicoes':    round(custo_refeicoes, 2),
        'diaria':             round(diaria, 2),
        'pedagios':           round(pedagios, 2),
        'custo_total':        round(custo_total, 2),
        'tempo_viagem_horas': round(tempo_horas, 1),
        'cidade_base':        CIDADE_BASE,
    }


def calcular_infra_rede(n_pontos, tipo_cabo='cat6_cobre',
                         metros_por_ponto=15, incluir_tomadas=True,
                         incluir_patch_panel=True, dificuldade='normal'):
    """
    Calcula custo de material de infraestrutura de rede

    Args:
        n_pontos: número de pontos de rede
        tipo_cabo: 'cat5e_cobre', 'cat6_cobre', 'cat5e_acobreado'
        metros_por_ponto: estimativa de metragem por ponto
        incluir_tomadas: incluir tomadas keystone
        incluir_patch_panel: incluir patch panel
        dificuldade: 'facil', 'normal', 'dificil' (afeta estimativa de material)

    Returns:
        dict com lista de materiais e custo total
    """
    PRECOS_CABO = {
        'cat5e_cobre':    3.50,
        'cat6_cobre':     5.80,
        'cat5e_acobreado':1.80,
        'fibra_monomodo': 12.00,
    }
    fator_dif = {'facil': 1.1, 'normal': 1.2, 'dificil': 1.4}.get(dificuldade, 1.2)
    metros_total = n_pontos * metros_por_ponto * fator_dif

    preco_cabo   = PRECOS_CABO.get(tipo_cabo, 5.80)
    custo_cabo   = metros_total * preco_cabo

    # Eletroduto (30% a mais que o cabo de rede como regra geral)
    metros_eletroduto = metros_total * 0.3
    custo_eletroduto  = metros_eletroduto * 1.80  # corrugado 3/4

    # Conectores RJ45 (2 por ponto + 20% reserva)
    qtd_conectores  = int(n_pontos * 2 * 1.2)
    custo_conectores = qtd_conectores * 0.50

    # Abraçadeiras
    qtd_abrac = int(metros_total / 5)
    custo_abrac = (qtd_abrac // 100 + 1) * 8.0

    # Tomadas Keystone
    custo_tomadas = n_pontos * 8.0 if incluir_tomadas else 0

    # Patch Panel
    custo_patch_panel = 85.0 if incluir_patch_panel and n_pontos <= 24 else (
        170.0 if include_patch_panel and n_pontos <= 48 else 0)

    custo_patch_panel = 0
    if incluir_patch_panel:
        custo_patch_panel = 85.0 if n_pontos <= 24 else 170.0

    custo_total_material = (custo_cabo + custo_eletroduto + custo_conectores +
                            custo_abrac + custo_tomadas + custo_patch_panel)

    # Mão de obra estimada (1h por ponto, fator dificuldade)
    horas_estimadas = n_pontos * 1.0 * {'facil':0.8,'normal':1.0,'dificil':1.5}.get(dificuldade,1.0)

    return {
        'n_pontos': n_pontos,
        'tipo_cabo': tipo_cabo,
        'metros_total': round(metros_total, 1),
        'materiais': [
            {'nome': f'Cabo {tipo_cabo.replace("_"," ").title()}', 'qtd': round(metros_total,1), 'un':'m', 'preco_unit':preco_cabo, 'total':round(custo_cabo,2)},
            {'nome': 'Eletroduto Corrugado 3/4', 'qtd': round(metros_eletroduto,1), 'un':'m', 'preco_unit':1.80, 'total':round(custo_eletroduto,2)},
            {'nome': 'Conector RJ45', 'qtd': qtd_conectores, 'un':'un', 'preco_unit':0.50, 'total':round(custo_conectores,2)},
            {'nome': 'Abraçadeiras Nylon', 'qtd': qtd_abrac, 'un':'un', 'preco_unit':0.08, 'total':round(custo_abrac,2)},
            {'nome': 'Tomadas Keystone Cat6', 'qtd': n_pontos if incluir_tomadas else 0, 'un':'un', 'preco_unit':8.00, 'total':round(custo_tomadas,2)},
            {'nome': 'Patch Panel 24 portas', 'qtd': 1 if incluir_patch_panel else 0, 'un':'un', 'preco_unit':85.00, 'total':round(custo_patch_panel,2)},
        ],
        'custo_material': round(custo_total_material, 2),
        'horas_estimadas': round(horas_estimadas, 1),
        'dificuldade': dificuldade,
    }


def calcular_infra_cftv(n_cameras, tipo_cabo='cftv_4vias',
                         metros_por_camera=20, dificuldade='normal'):
    """Calcula material para instalação de sistema CFTV"""
    PRECOS_CABO = {
        'cftv_4vias': 4.50,
        'rg59':        2.20,
        'rg6':         3.00,
        'utp_cat6':    5.80,
    }
    fator_dif = {'facil':1.1,'normal':1.2,'dificil':1.4}.get(dificuldade,1.2)
    metros_total = n_cameras * metros_por_camera * fator_dif
    preco_cabo   = PRECOS_CABO.get(tipo_cabo, 4.50)

    custo_cabo    = metros_total * preco_cabo
    qtd_bnc       = n_cameras * 2
    custo_bnc     = qtd_bnc * 1.80
    qtd_p4        = n_cameras * 2
    custo_p4      = qtd_p4 * 0.60
    metros_eletro = metros_total * 0.25
    custo_eletro  = metros_eletro * 1.80
    qtd_abrac     = int(metros_total / 5)
    custo_abrac   = (qtd_abrac // 100 + 1) * 8.0
    custo_caixas  = n_cameras * 12.0  # VBOX por câmera
    custo_total   = custo_cabo+custo_bnc+custo_p4+custo_eletro+custo_abrac+custo_caixas
    horas_est     = n_cameras * 1.0 * {'facil':0.8,'normal':1.0,'dificil':1.5}.get(dificuldade,1.0)

    return {
        'n_cameras': n_cameras,
        'metros_total': round(metros_total,1),
        'materiais': [
            {'nome': f'Cabo {tipo_cabo.replace("_"," ").title()}','qtd':round(metros_total,1),'un':'m','preco_unit':preco_cabo,'total':round(custo_cabo,2)},
            {'nome':'Conector BNC','qtd':qtd_bnc,'un':'un','preco_unit':1.80,'total':round(custo_bnc,2)},
            {'nome':'Conector P4 Macho','qtd':qtd_p4,'un':'un','preco_unit':0.60,'total':round(custo_p4,2)},
            {'nome':'Eletroduto Corrugado 3/4','qtd':round(metros_eletro,1),'un':'m','preco_unit':1.80,'total':round(custo_eletro,2)},
            {'nome':'Abraçadeiras','qtd':qtd_abrac,'un':'un','preco_unit':0.08,'total':round(custo_abrac,2)},
            {'nome':'Caixa Plástica VBOX','qtd':n_cameras,'un':'un','preco_unit':12.0,'total':round(custo_caixas,2)},
        ],
        'custo_material': round(custo_total,2),
        'horas_estimadas': round(horas_est,1),
    }


def calcular_cerca_eletrica(metros_cerca, dificuldade='normal'):
    """Calcula material para instalação de cerca elétrica"""
    fio_por_metro_fios = 4  # número médio de fios
    metros_fio    = metros_cerca * fio_por_metro_fios
    custo_fio     = metros_fio * 1.20
    isoladores_linha   = int(metros_cerca / 0.5)  # 1 a cada 50cm
    isoladores_canto   = 4  # mínimo 4 cantos
    custo_isol    = (isoladores_linha * 0.50) + (isoladores_canto * 0.80)
    suportes      = int(metros_cerca / 0.5)
    custo_suporte = suportes * 3.50
    custo_total   = custo_fio + custo_isol + custo_suporte + 350  # central estimada
    horas_est     = (metros_cerca / 20) * {'facil':1.0,'normal':1.3,'dificil':1.8}.get(dificuldade,1.3)

    return {
        'metros_cerca': metros_cerca,
        'metros_fio': round(metros_fio,1),
        'materiais': [
            {'nome':'Fio Inox 0,5mm','qtd':round(metros_fio,1),'un':'m','preco_unit':1.20,'total':round(custo_fio,2)},
            {'nome':'Isoladores de Linha','qtd':isoladores_linha,'un':'un','preco_unit':0.50,'total':round(isoladores_linha*0.50,2)},
            {'nome':'Isoladores de Canto','qtd':isoladores_canto,'un':'un','preco_unit':0.80,'total':round(isoladores_canto*0.80,2)},
            {'nome':'Suportes de Cerca','qtd':suportes,'un':'un','preco_unit':3.50,'total':round(custo_suporte,2)},
            {'nome':'Central de Cerca Elétrica','qtd':1,'un':'un','preco_unit':350.0,'total':350.0},
        ],
        'custo_material': round(custo_total,2),
        'horas_estimadas': round(horas_est,1),
    }
