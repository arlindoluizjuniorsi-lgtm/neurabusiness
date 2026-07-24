"""
NeuraBusiness - Gerador de PDFs com ReportLab
Proposta comercial e Ordem de Serviço
"""
import os
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.platypus.flowables import HRFlowable

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_NB   = os.path.join(BASE_DIR, 'static', 'img', 'logo_neurabusiness.png')

# ─── CORES ────────────────────────────────────────────────────────────────────
COR_PRIMARIA   = colors.HexColor('#0a0a0a')
COR_ACCENT     = colors.HexColor('#f97316')
COR_ACCENT2    = colors.HexColor('#ea6c0a')
COR_TEXTO      = colors.HexColor('#1e293b')
COR_MUTED      = colors.HexColor('#64748b')
COR_BORDA      = colors.HexColor('#e2e8f0')
COR_LINHA_PAR  = colors.HexColor('#f8fafc')
COR_VERDE      = colors.HexColor('#10B981')
COR_HEADER_TB  = colors.HexColor('#0f172a')

# ─── ESTILOS ──────────────────────────────────────────────────────────────────
def get_styles():
    styles = getSampleStyleSheet()
    return {
        'titulo_doc': ParagraphStyle('titulo_doc',
            fontName='Helvetica-Bold', fontSize=14, textColor=COR_PRIMARIA,
            alignment=TA_CENTER, spaceAfter=4),
        'subtitulo_doc': ParagraphStyle('subtitulo_doc',
            fontName='Helvetica', fontSize=10, textColor=COR_MUTED,
            alignment=TA_CENTER, spaceAfter=12),
        'label': ParagraphStyle('label',
            fontName='Helvetica-Bold', fontSize=8, textColor=COR_MUTED,
            spaceAfter=2, leading=10),
        'valor': ParagraphStyle('valor',
            fontName='Helvetica', fontSize=9, textColor=COR_TEXTO,
            spaceAfter=4, leading=12),
        'valor_bold': ParagraphStyle('valor_bold',
            fontName='Helvetica-Bold', fontSize=9, textColor=COR_TEXTO,
            spaceAfter=4, leading=12),
        'total_label': ParagraphStyle('total_label',
            fontName='Helvetica-Bold', fontSize=11, textColor=COR_PRIMARIA,
            alignment=TA_RIGHT),
        'total_valor': ParagraphStyle('total_valor',
            fontName='Helvetica-Bold', fontSize=16, textColor=COR_VERDE,
            alignment=TA_RIGHT),
        'secao': ParagraphStyle('secao',
            fontName='Helvetica-Bold', fontSize=9, textColor=COR_ACCENT,
            spaceBefore=10, spaceAfter=4),
        'rodape': ParagraphStyle('rodape',
            fontName='Helvetica', fontSize=7, textColor=COR_MUTED,
            alignment=TA_CENTER),
        'normal': ParagraphStyle('normal',
            fontName='Helvetica', fontSize=9, textColor=COR_TEXTO,
            leading=13, spaceAfter=4),
        'numero_proposta': ParagraphStyle('numero_proposta',
            fontName='Helvetica-Bold', fontSize=13, textColor=COR_PRIMARIA,
            alignment=TA_CENTER, spaceAfter=2),
        'empresa_nome': ParagraphStyle('empresa_nome',
            fontName='Helvetica-Bold', fontSize=10, textColor=COR_PRIMARIA,
            alignment=TA_RIGHT),
        'empresa_detalhe': ParagraphStyle('empresa_detalhe',
            fontName='Helvetica', fontSize=8, textColor=COR_MUTED,
            alignment=TA_RIGHT, leading=11),
    }

def _load_logo(path):
    """Carrega logo se existir"""
    if path and os.path.exists(path):
        try:
            return RLImage(path)
        except:
            pass
    return None

def _logo_empresa(empresa):
    """Retorna caminho absoluto para logo da empresa"""
    if empresa and empresa.get('logo'):
        p = os.path.join(BASE_DIR, 'static', 'uploads', 'empresas', empresa['logo'])
        if os.path.exists(p):
            return p
    return None

def _cabecalho_duplo(empresa, styles, largura_util):
    """Cabeçalho com logo NB (esquerda) + dados empresa (direita)"""
    logo_nb_img = _load_logo(LOGO_NB)
    logo_emp_path = _logo_empresa(empresa)
    logo_emp_img = _load_logo(logo_emp_path)

    col_esq_content = []
    if logo_emp_img:
        logo_emp_img.drawWidth = 90
        logo_emp_img.drawHeight = 30
        col_esq_content = [logo_emp_img]
    elif logo_nb_img:
        logo_nb_img.drawWidth = 100
        logo_nb_img.drawHeight = 28
        col_esq_content = [logo_nb_img]
    else:
        col_esq_content = [Paragraph('<b>NeuraBusiness</b>', styles['empresa_nome'])]

    # Dados empresa direita
    emp_nome = empresa.get('razao_social', '') if empresa else 'NeuraBusiness'
    emp_cnpj = empresa.get('cnpj', '') if empresa else ''
    emp_tel  = empresa.get('telefone', '') if empresa else ''
    emp_end  = empresa.get('endereco', '') if empresa else ''
    emp_cid  = f"{empresa.get('cidade','')}/{empresa.get('estado','')}" if empresa else ''
    emp_cep  = empresa.get('cep', '') if empresa else ''

    linhas_dir = [
        Paragraph(f'<b>{emp_nome}</b>', styles['empresa_nome']),
    ]
    if emp_cnpj:   linhas_dir.append(Paragraph(emp_cnpj, styles['empresa_detalhe']))
    if emp_tel:    linhas_dir.append(Paragraph(emp_tel, styles['empresa_detalhe']))
    if emp_end:    linhas_dir.append(Paragraph(emp_end, styles['empresa_detalhe']))
    if emp_cid:    linhas_dir.append(Paragraph(emp_cid, styles['empresa_detalhe']))
    if emp_cep:    linhas_dir.append(Paragraph(emp_cep, styles['empresa_detalhe']))

    from reportlab.platypus import KeepInFrame
    data_cab = [[col_esq_content[0], linhas_dir]]
    t = Table(data_cab, colWidths=[largura_util*0.4, largura_util*0.6])
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN',  (0,0), (0,0),  'LEFT'),
        ('ALIGN',  (1,0), (1,0),  'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    return t

# ─── PROPOSTA PDF ─────────────────────────────────────────────────────────────

def _cabecalho_creative(proposta, empresa, styles, largura_util):
    """Cabecalho estilo Creative: nome empresa + tagline (esquerda), titulo doc (direita)."""
    logo_path = _logo_empresa(empresa)
    logo_img = _load_logo(logo_path)

    emp_nome = (empresa.get('fantasia') or empresa.get('razao_social') or 'CREATIVE') if empresa else 'CREATIVE'
    emp_tel  = empresa.get('telefone', '') if empresa else ''
    emp_email = empresa.get('email', '') if empresa else ''
    emp_cnpj = empresa.get('cnpj', '') if empresa else ''

    if logo_img:
        logo_img.drawWidth = 90
        logo_img.drawHeight = 30
        col_esq = [logo_img]
    else:
        col_esq = [
            Paragraph(f'<font color="#f97316" size="16"><b>{emp_nome.lower()}</b></font>',
                ParagraphStyle('lognome', fontName='Helvetica-Bold', fontSize=16, textColor=colors.HexColor('#f97316'))),
        ]
    col_esq.append(Paragraph('TECNOLOGIA &amp; SEGURANCA ELETRONICA',
        ParagraphStyle('tag', fontName='Helvetica-Bold', fontSize=6.5, textColor=colors.white, spaceBefore=2)))
    contato = []
    if emp_tel: contato.append(emp_tel)
    if emp_email: contato.append(emp_email)
    if contato:
        col_esq.append(Paragraph(' | '.join(contato),
            ParagraphStyle('contato', fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#cbd5e1'), spaceBefore=6)))
    if emp_cnpj:
        col_esq.append(Paragraph(f'CNPJ: {emp_cnpj}',
            ParagraphStyle('cnpj', fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#cbd5e1'))))

    numero = proposta.get('numero', '')
    criado = proposta.get('criado_em', '')
    try:
        dt = datetime.fromisoformat(str(criado)[:19])
        criado_fmt = dt.strftime('%d/%m/%Y')
    except:
        criado_fmt = datetime.now().strftime('%d/%m/%Y')
    validade = proposta.get('validade', 15)

    col_dir = [
        Paragraph('ORCAMENTO DE SERVICO',
            ParagraphStyle('tit', fontName='Helvetica-Bold', fontSize=13, textColor=colors.white, alignment=TA_RIGHT)),
        Paragraph(f'No {numero}',
            ParagraphStyle('num', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#f97316'), alignment=TA_RIGHT, spaceBefore=3)),
        Paragraph(f'Data: {criado_fmt} | Validade: {validade} dias',
            ParagraphStyle('dt', fontName='Helvetica', fontSize=7.5, textColor=colors.HexColor('#cbd5e1'), alignment=TA_RIGHT, spaceBefore=2)),
    ]

    tbl = Table([[col_esq, col_dir]], colWidths=[largura_util*0.55, largura_util*0.45])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0a0a0a')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('LEFTPADDING', (0,0), (0,-1), 16),
        ('RIGHTPADDING', (1,0), (1,-1), 16),
    ]))
    return tbl


def gerar_proposta_pdf(proposta, empresa, cliente, itens, etapas=None):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=0, bottomMargin=16*mm,
        title=f"Proposta {proposta.get('numero','')}"
    )
    largura_util = A4[0] - 36*mm
    styles = get_styles()
    story = []

    # ── CABECALHO (fundo preto) ──
    story.append(_cabecalho_creative(proposta, empresa, styles, largura_util))
    story.append(HRFlowable(width='100%', thickness=3, color=COR_ACCENT, spaceAfter=14))

    # ── CLIENTE ──
    cli_nome = cliente.get('nome', '') if cliente else ''
    cli_cnpj = cliente.get('cpf_cnpj', '') if cliente else ''
    cli_tel  = cliente.get('telefone', '') if cliente else ''
    cli_end  = cliente.get('endereco', '') if cliente else ''
    cli_cid  = cliente.get('cidade', '') if cliente else ''
    cli_uf   = cliente.get('estado', '') if cliente else ''
    cli_cep  = cliente.get('cep', '') if cliente else ''

    linha1 = f'<font color="#f97316" size="7"><b>CLIENTE</b></font><br/><font size="12"><b>{cli_nome}</b></font>'
    linha2_parts = []
    if cli_cnpj: linha2_parts.append(f'CNPJ: {cli_cnpj}')
    linha2_parts.append(f'Aos cuidados de: {cli_nome}')
    linha2 = ' | '.join(linha2_parts)

    end_parts = []
    if cli_end: end_parts.append(cli_end)
    if cli_cid: end_parts.append(f'{cli_cid} - {cli_uf}' if cli_uf else cli_cid)
    if cli_cep: end_parts.append(f'CEP: {cli_cep}')
    linha3 = ', '.join(end_parts)
    if cli_tel: linha3 += (' | ' if linha3 else '') + cli_tel

    cli_html = linha1 + '<br/>' + f'<font size="8" color="#475569">{linha2}</font>'
    if linha3:
        cli_html += '<br/>' + f'<font size="8" color="#475569">{linha3}</font>'

    t_cli = Table([[Paragraph(cli_html, ParagraphStyle('clih', fontName='Helvetica', fontSize=9, leading=13))]],
        colWidths=[largura_util])
    t_cli.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('LINEBEFORE', (0,0), (0,-1), 3, COR_ACCENT),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 14),
    ]))
    story.append(t_cli)
    story.append(Spacer(1, 14))

    # ── TITULO / DESCRICAO ──
    if proposta.get('titulo'):
        story.append(Paragraph(proposta['titulo'], styles['normal']))
        story.append(Spacer(1, 6))

    # ── SECAO: DESCRICAO DO SERVICO ──
    tem_preco = any((i.get('preco_unitario') or 0) > 0 for i in itens)
    titulo_secao = 'DESCRICAO DO SERVICO' if any(i.get('tipo')=='servico' for i in itens) else 'COMPOSICAO DO KIT / MATERIAIS'
    story.append(Paragraph(titulo_secao, ParagraphStyle('secaotit',
        fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0a0a0a'), spaceAfter=6)))
    story.append(HRFlowable(width='100%', thickness=1.2, color=COR_ACCENT, spaceAfter=8))

    cab = [
        Paragraph('<b>ITEM / DESCRICAO</b>', ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)),
        Paragraph('<b>QTD</b>', ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
    ]
    dados = [cab]
    for item in itens:
        qtd = item.get('quantidade', 1)
        qtd_fmt = f'{qtd:.0f}' if qtd == int(qtd) else f'{qtd:.2f}'
        dados.append([
            Paragraph(str(item.get('descricao','')), ParagraphStyle('td', fontName='Helvetica-Bold', fontSize=8.5, textColor=COR_TEXTO)),
            Paragraph(qtd_fmt, ParagraphStyle('td', fontName='Helvetica', fontSize=8.5, textColor=COR_TEXTO, alignment=TA_CENTER)),
        ])
    col_w = [largura_util-24*mm, 24*mm]

    total_itens = sum(i.get('quantidade',1) * i.get('preco_unitario',0) for i in itens)
    custo_extra = (proposta.get('custo_locomocao') or 0) + (proposta.get('custo_alimentacao') or 0) + (proposta.get('custo_outros') or 0)
    total_geral = total_itens + custo_extra

    dados.append([
        Paragraph('TOTAL GERAL', ParagraphStyle('tf', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=TA_RIGHT)),
        Paragraph(f'R$ {total_geral:,.2f}', ParagraphStyle('tf', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#f97316'), alignment=TA_CENTER)),
    ])

    n = len(dados)
    t_itens = Table(dados, colWidths=col_w, repeatRows=1)
    t_itens.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a0a0a')),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('FONTSIZE', (0,1), (-1,-2), 8.5),
        ('TOPPADDING', (0,1), (-1,-2), 6),
        ('BOTTOMPADDING', (0,1), (-1,-2), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, COR_LINHA_PAR]),
        ('BACKGROUND', (0,n-1), (-1,n-1), colors.HexColor('#1a1a1a')),
        ('TOPPADDING', (0,n-1), (-1,n-1), 9),
        ('BOTTOMPADDING', (0,n-1), (-1,n-1), 9),
        ('LINEABOVE', (0,n-1), (-1,n-1), 1.5, COR_ACCENT),
        ('GRID', (0,0), (-1,-1), 0.3, COR_BORDA),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_itens)
    story.append(Spacer(1, 16))

    # ── ETAPAS / CRONOGRAMA DE ENTREGA ──
    if etapas:
        story.append(Paragraph('CRONOGRAMA DE ENTREGA', ParagraphStyle('secaotit2',
            fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0a0a0a'), spaceAfter=6)))
        story.append(HRFlowable(width='100%', thickness=1.2, color=COR_ACCENT, spaceAfter=8))

        for i, et in enumerate(etapas, 1):
            titulo_et = et.get('titulo', '')
            desc_et   = et.get('descricao', '')
            dias_et   = et.get('duracao_dias', '')
            html = f'<font color="#f97316"><b>Etapa {i}</b></font> — <b>{titulo_et}</b>'
            if dias_et:
                html += f' <font color="#64748b" size="7.5">({dias_et} dia(s))</font>'
            if desc_et:
                html += f'<br/><font size="8" color="#64748b">{desc_et}</font>'
            box = Table([[Paragraph(html, ParagraphStyle('etp', fontName='Helvetica', fontSize=9, leading=13))]],
                colWidths=[largura_util])
            box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.white),
                ('BOX', (0,0), (-1,-1), 0.5, COR_BORDA),
                ('LINEBEFORE', (0,0), (0,-1), 2.5, COR_ACCENT),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
            ]))
            story.append(box)
            story.append(Spacer(1, 5))
        story.append(Spacer(1, 10))

    # ── FORMA DE PAGAMENTO + OBSERVACOES (2 colunas) ──
    fp = proposta.get('forma_pagamento', '') or 'A combinar'
    cond = proposta.get('condicoes', '')
    obs  = proposta.get('observacoes', '')

    pag_html = f'<font color="#f97316" size="7.5"><b>FORMA DE PAGAMENTO</b></font><br/>'
    pag_html += f'<font size="8.5">{fp}</font>'
    if cond:
        for linha in cond.split('\n'):
            if linha.strip():
                pag_html += f'<br/><font size="8">{linha}</font>'

    obs_html = f'<font color="#f97316" size="7.5"><b>OBSERVACOES</b></font><br/>'
    if obs:
        linhas_obs = [l for l in obs.split('\n') if l.strip()]
        obs_html += '<br/>'.join(f'<font size="8">{l}</font>' for l in linhas_obs)
    else:
        obs_html += f'<font size="8" color="#94a3b8">—</font>'

    col_pag = Paragraph(pag_html, ParagraphStyle('pagh', fontName='Helvetica', fontSize=8.5, leading=12))
    col_obs = Paragraph(obs_html, ParagraphStyle('obsh', fontName='Helvetica', fontSize=8.5, leading=12))

    t_info2 = Table([[col_pag, col_obs]], colWidths=[largura_util/2-4, largura_util/2-4])
    t_info2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (0,-1), 0.5, COR_BORDA),
        ('BOX', (1,0), (1,-1), 0.5, COR_BORDA),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_info2)
    story.append(Spacer(1, 14))

    # ── QUALIFICACAO TECNICA ──
    qualif_html = (
        '<font color="#0a0a0a" size="7.5"><b>QUALIFICACAO TECNICA DO RESPONSAVEL</b></font><br/>'
        '<font size="7.5" color="#475569">Pos-graduado em Redes | MBA em Gestao de TI | '
        'Certificacoes: ITIL, ISO 27001, PMBOK</font><br/>'
        '<font size="7.5" color="#475569">Expertise: CFTV, Alarmes, Seguranca Eletronica, Redes, '
        'Infraestrutura de TI</font>'
    )
    t_qualif = Table([[Paragraph(qualif_html, ParagraphStyle('qh', fontName='Helvetica', fontSize=8, leading=11))]],
        colWidths=[largura_util])
    t_qualif.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#eff6ff')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#bfdbfe')),
        ('TOPPADDING', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 9),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(t_qualif)
    story.append(Spacer(1, 26))

    # ── ASSINATURA ──
    emp_nome_ass = (empresa.get('fantasia') or empresa.get('razao_social') or '') if empresa else ''
    t_ass = Table([
        [HRFlowable(width=220, thickness=0.7, color=COR_MUTED)],
        [Paragraph('Arlindo Luiz da Silva Junior', ParagraphStyle('assn', fontName='Helvetica-Bold', fontSize=9, textColor=COR_TEXTO))],
        [Paragraph(f'Responsavel Tecnico — {emp_nome_ass} Tecnologia &amp; Seguranca Eletronica',
            ParagraphStyle('assr', fontName='Helvetica', fontSize=7.5, textColor=COR_MUTED))],
    ], colWidths=[largura_util])
    t_ass.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER')]))
    story.append(t_ass)
    story.append(Spacer(1, 20))

    # ── RODAPE (fundo preto) ──
    emp_email_f = empresa.get('email','') if empresa else ''
    emp_tel_f   = empresa.get('telefone','') if empresa else ''
    footer_html = (
        f'<font color="#f97316"><b>{emp_nome_ass.lower()}</b></font> | '
        f'<font color="#cbd5e1">{emp_email_f} | {emp_tel_f}</font><br/>'
        f'<font size="6.5" color="#64748b">Este documento e valido como proposta comercial. '
        f'A execucao implica aceite das condicoes apresentadas.</font>'
    )
    t_foot = Table([[Paragraph(footer_html, ParagraphStyle('foot', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, leading=11))]],
        colWidths=[largura_util])
    t_foot.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0a0a0a')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_foot)

    doc.build(story)
    buf.seek(0)
    return buf


def gerar_os_pdf(os_obj, empresa, cliente):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=f"OS {os_obj.get('numero','')}"
    )
    largura_util = A4[0] - 40*mm
    styles = get_styles()
    story = []

    # ── CABEÇALHO ──
    story.append(_cabecalho_duplo(empresa, styles, largura_util))
    story.append(HRFlowable(width='100%', thickness=2, color=COR_ACCENT2, spaceAfter=10))

    # ── TÍTULO ──
    story.append(Paragraph(f'ORDEM DE SERVIÇO Nº {os_obj.get("numero","")}', styles['titulo_doc']))
    criado = os_obj.get('criado_em', '')
    try:
        dt = datetime.fromisoformat(str(criado)[:19])
        criado_fmt = dt.strftime('%d/%m/%Y às %H:%M')
    except:
        criado_fmt = datetime.now().strftime('%d/%m/%Y às %H:%M')
    story.append(Paragraph(f'Aberta em: {criado_fmt}', styles['subtitulo_doc']))
    story.append(Spacer(1, 8))

    # ── GRID INFO ──
    status_cores = {
        'aberta': '#f97316', 'em_andamento': '#f59e0b',
        'concluida': '#10B981', 'cancelada': '#ef4444'
    }
    cor_status = status_cores.get(os_obj.get('status',''), '#64748b')
    prior_cores = {'urgente': '#ef4444', 'alta': '#f59e0b', 'normal': '#64748b', 'baixa': '#94a3b8'}
    cor_prior = prior_cores.get(os_obj.get('prioridade',''), '#64748b')

    info_data = [
        [
            Paragraph('<b>CLIENTE</b>', styles['label']),
            Paragraph('<b>STATUS</b>', styles['label']),
            Paragraph('<b>PRIORIDADE</b>', styles['label']),
            Paragraph('<b>TÉCNICO</b>', styles['label']),
        ],
        [
            Paragraph(cliente.get('nome','') if cliente else '', styles['valor_bold']),
            Paragraph(f'<font color="{cor_status}"><b>{os_obj.get("status","").upper()}</b></font>', styles['valor_bold']),
            Paragraph(f'<font color="{cor_prior}"><b>{os_obj.get("prioridade","").upper()}</b></font>', styles['valor_bold']),
            Paragraph(os_obj.get('tecnico','—'), styles['valor']),
        ],
        [
            Paragraph(cliente.get('telefone','') or '—' if cliente else '—', styles['valor']),
            Paragraph('', styles['valor']),
            Paragraph('', styles['valor']),
            Paragraph('', styles['valor']),
        ]
    ]
    col_w4 = [largura_util/4] * 4
    t_info = Table(info_data, colWidths=col_w4)
    t_info.setStyle(TableStyle([
        ('BOX',          (0,0), (-1,-1), 0.5, COR_BORDA),
        ('INNERGRID',    (0,0), (-1,-1), 0.3, COR_BORDA),
        ('BACKGROUND',   (0,0), (-1,0),  COR_LINHA_PAR),
        ('TOPPADDING',   (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ('LEFTPADDING',  (0,0), (-1,-1), 8),
        ('VALIGN',       (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 10))

    # ── DATAS ──
    prev = os_obj.get('data_prevista','')
    conc = os_obj.get('data_conclusao','')
    if prev or conc:
        datas = []
        if prev: datas.append(f'<b>Previsão:</b> {prev}')
        if conc: datas.append(f'<b>Conclusão:</b> {conc}')
        story.append(Paragraph('  |  '.join(datas), styles['normal']))
        story.append(Spacer(1, 6))

    # ── DESCRIÇÃO ──
    story.append(Paragraph('DESCRIÇÃO DO SERVIÇO', styles['secao']))
    desc_box = Table([
        [Paragraph(os_obj.get('descricao','').replace('\n','<br/>'), styles['normal'])]
    ], colWidths=[largura_util])
    desc_box.setStyle(TableStyle([
        ('BOX',         (0,0), (-1,-1), 0.5, COR_BORDA),
        ('BACKGROUND',  (0,0), (-1,-1), COR_LINHA_PAR),
        ('TOPPADDING',  (0,0), (-1,-1), 10),
        ('BOTTOMPADDING',(0,0),(-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING',(0,0), (-1,-1), 12),
        ('LINEAFTER',   (0,0), (0,-1),  2, COR_ACCENT2),
    ]))
    story.append(desc_box)

    # ── SOLUÇÃO (se concluída) ──
    if os_obj.get('solucao'):
        story.append(Spacer(1, 10))
        story.append(Paragraph('SOLUÇÃO APLICADA', ParagraphStyle('secao_verde',
            fontName='Helvetica-Bold', fontSize=9, textColor=COR_VERDE, spaceBefore=6, spaceAfter=4)))
        sol_box = Table([
            [Paragraph(os_obj['solucao'].replace('\n','<br/>'), styles['normal'])]
        ], colWidths=[largura_util])
        sol_box.setStyle(TableStyle([
            ('BOX',        (0,0), (-1,-1), 0.5, colors.HexColor('#d1fae5')),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0fdf4')),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING',(0,0),(-1,-1),10),
            ('LEFTPADDING',(0,0), (-1,-1), 12),
            ('LINEAFTER',  (0,0), (0,-1),  2, COR_VERDE),
        ]))
        story.append(sol_box)

    # ── ASSINATURA ──
    story.append(Spacer(1, 30))
    ass_data = [
        [
            Paragraph('_______________________________', styles['normal']),
            Paragraph('_______________________________', styles['normal']),
        ],
        [
            Paragraph('Técnico Responsável', ParagraphStyle('ass', fontName='Helvetica', fontSize=8, textColor=COR_MUTED, alignment=TA_CENTER)),
            Paragraph('Cliente / Aprovação', ParagraphStyle('ass', fontName='Helvetica', fontSize=8, textColor=COR_MUTED, alignment=TA_CENTER)),
        ]
    ]
    t_ass = Table(ass_data, colWidths=[largura_util/2, largura_util/2])
    t_ass.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_ass)

    # ── RODAPÉ ──
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width='100%', thickness=0.3, color=COR_BORDA, spaceAfter=4))
    story.append(Paragraph('Documento gerado por NeuraBusiness — Sistema Comercial', styles['rodape']))

    doc.build(story)
    buf.seek(0)
    return buf
