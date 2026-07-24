"""
NeuraBusiness — Gerador de Proposta Inteligente (Estilo Creative)
PDF profissional com capa, seções numeradas, tabelas, quadro comparativo e rodapé
"""
import os
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.platypus import Image as RLImage
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── CORES ─────────────────────────────────────────────────────────────────────
C_DARK    = colors.HexColor('#0A0E1A')
C_DARKER  = colors.HexColor('#070B14')
C_ACCENT  = colors.HexColor('#00D4FF')
C_ACCENT2 = colors.HexColor('#7C3AED')
C_GREEN   = colors.HexColor('#10B981')
C_TEXT    = colors.HexColor('#1e293b')
C_MUTED   = colors.HexColor('#64748b')
C_BORDER  = colors.HexColor('#e2e8f0')
C_ROW_ALT = colors.HexColor('#f8fafc')
C_WHITE   = colors.white
C_ORANGE  = colors.HexColor('#f59e0b')
C_RED     = colors.HexColor('#ef4444')

W, H = A4  # 595 x 842 pts
MARGIN = 20*mm
CONTENT_W = W - 2*MARGIN


# ─── CANVAS COM CABEÇALHO/RODAPÉ ───────────────────────────────────────────────
class CreativeCanvas(canvas.Canvas):
    def __init__(self, *args, empresa=None, proposta=None, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.empresa  = empresa or {}
        self.proposta = proposta or {}
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_header_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_header_footer(self, total_pages):
        page = self._pageNumber
        fantasia = self.empresa.get('fantasia','Creative')
        numero   = self.proposta.get('numero','')

        # ── Cabeçalho (apenas da pág 2 em diante) ──
        if page > 1:
            self.saveState()
            self.setFillColor(C_DARK)
            self.rect(0, H - 16*mm, W, 16*mm, fill=1, stroke=0)
            # Logo ou nome
            logo_path = self._get_logo()
            if logo_path:
                try:
                    self.drawImage(logo_path, MARGIN, H - 13*mm,
                                   width=28*mm, height=9*mm,
                                   preserveAspectRatio=True, mask='auto')
                except:
                    self._draw_brand(fantasia)
            else:
                self._draw_brand(fantasia)
            # Número da proposta
            self.setFont('Helvetica-Bold', 7)
            self.setFillColor(C_ACCENT)
            self.drawRightString(W - MARGIN, H - 10*mm, numero)
            # Linha accent
            self.setStrokeColor(C_ACCENT)
            self.setLineWidth(1)
            self.line(0, H - 16*mm, W, H - 16*mm)
            self.restoreState()

        # ── Rodapé ──
        self.saveState()
        self.setFillColor(C_DARK)
        self.rect(0, 0, W, 12*mm, fill=1, stroke=0)
        self.setFont('Helvetica', 6.5)
        self.setFillColor(colors.HexColor('#64748b'))
        cnpj = self.empresa.get('cnpj','')
        tel  = self.empresa.get('telefone','')
        cid  = f"{self.empresa.get('cidade','')}/{self.empresa.get('estado','')}"
        self.drawString(MARGIN, 7*mm, f"{fantasia}  |  CNPJ: {cnpj}  |  {tel}  |  {cid}")
        self.setFillColor(colors.HexColor('#475569'))
        self.drawRightString(W - MARGIN, 7*mm,
            f"Pág. {page} / {total_pages}  •  {numero}")
        self.setStrokeColor(C_ACCENT)
        self.setLineWidth(0.5)
        self.line(0, 12*mm, W, 12*mm)
        self.restoreState()

    def _draw_brand(self, fantasia):
        self.setFont('Helvetica-Bold', 9)
        self.setFillColor(C_WHITE)
        self.drawString(MARGIN, H - 10*mm, fantasia)

    def _get_logo(self):
        emp = self.empresa
        logo = emp.get('logo')
        if not logo: return None
        path = os.path.join(BASE_DIR, 'static', 'uploads', 'empresas', logo)
        return path if os.path.exists(path) else None


# ─── ESTILOS ───────────────────────────────────────────────────────────────────
def estilos():
    return {
        # Títulos de seção
        'secao_num': ParagraphStyle('secao_num',
            fontName='Helvetica-Bold', fontSize=9, textColor=C_ACCENT,
            spaceAfter=2, leading=11),
        'secao_titulo': ParagraphStyle('secao_titulo',
            fontName='Helvetica-Bold', fontSize=13, textColor=C_DARK,
            spaceAfter=6, leading=16, spaceBefore=4),
        'secao_sub': ParagraphStyle('secao_sub',
            fontName='Helvetica-Bold', fontSize=10, textColor=C_DARK,
            spaceAfter=4, leading=13, spaceBefore=8),
        # Corpo
        'corpo': ParagraphStyle('corpo',
            fontName='Helvetica', fontSize=9, textColor=C_TEXT,
            alignment=TA_JUSTIFY, leading=14, spaceAfter=6),
        'corpo_bold': ParagraphStyle('corpo_bold',
            fontName='Helvetica-Bold', fontSize=9, textColor=C_TEXT,
            leading=13, spaceAfter=4),
        'item_bullet': ParagraphStyle('item_bullet',
            fontName='Helvetica', fontSize=8.5, textColor=C_TEXT,
            leading=13, spaceAfter=3, leftIndent=10),
        # Labels e valores em cards
        'label': ParagraphStyle('label',
            fontName='Helvetica-Bold', fontSize=7, textColor=C_MUTED,
            spaceAfter=1, leading=9),
        'valor': ParagraphStyle('valor',
            fontName='Helvetica', fontSize=9, textColor=C_TEXT,
            leading=12, spaceAfter=3),
        # Tabelas
        'th': ParagraphStyle('th',
            fontName='Helvetica-Bold', fontSize=8, textColor=C_WHITE,
            alignment=TA_CENTER, leading=10),
        'td': ParagraphStyle('td',
            fontName='Helvetica', fontSize=8.5, textColor=C_TEXT,
            leading=12),
        'td_center': ParagraphStyle('td_center',
            fontName='Helvetica', fontSize=8.5, textColor=C_TEXT,
            alignment=TA_CENTER, leading=12),
        'td_bold': ParagraphStyle('td_bold',
            fontName='Helvetica-Bold', fontSize=8.5, textColor=C_TEXT,
            leading=12),
        'td_green': ParagraphStyle('td_green',
            fontName='Helvetica-Bold', fontSize=9, textColor=C_GREEN,
            alignment=TA_RIGHT, leading=12),
        # Capa
        'capa_empresa': ParagraphStyle('capa_empresa',
            fontName='Helvetica-Bold', fontSize=11, textColor=C_WHITE,
            alignment=TA_CENTER, leading=14),
        'capa_sub': ParagraphStyle('capa_sub',
            fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#94a3b8'),
            alignment=TA_CENTER, leading=11),
        'capa_titulo': ParagraphStyle('capa_titulo',
            fontName='Helvetica-Bold', fontSize=22, textColor=C_WHITE,
            alignment=TA_CENTER, leading=28, spaceBefore=8, spaceAfter=6),
        'capa_desc': ParagraphStyle('capa_desc',
            fontName='Helvetica', fontSize=11, textColor=colors.HexColor('#94a3b8'),
            alignment=TA_CENTER, leading=15),
        'capa_meta_lbl': ParagraphStyle('capa_meta_lbl',
            fontName='Helvetica', fontSize=7, textColor=colors.HexColor('#64748b'),
            alignment=TA_CENTER, leading=9),
        'capa_meta_val': ParagraphStyle('capa_meta_val',
            fontName='Helvetica-Bold', fontSize=9, textColor=C_WHITE,
            alignment=TA_CENTER, leading=11),
        'rec': ParagraphStyle('rec',
            fontName='Helvetica-Bold', fontSize=10, textColor=C_WHITE,
            alignment=TA_CENTER, leading=13),
        'rec_sub': ParagraphStyle('rec_sub',
            fontName='Helvetica', fontSize=8.5, textColor=colors.HexColor('#cbd5e1'),
            alignment=TA_CENTER, leading=12),
        'total_lbl': ParagraphStyle('total_lbl',
            fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#94a3b8'),
            leading=11),
        'total_val': ParagraphStyle('total_val',
            fontName='Helvetica-Bold', fontSize=16, textColor=C_ACCENT,
            leading=20),
        'rodape_texto': ParagraphStyle('rodape_texto',
            fontName='Helvetica', fontSize=8.5, textColor=C_MUTED,
            alignment=TA_CENTER, leading=12),
    }


def linha_accent():
    return HRFlowable(width='100%', thickness=2, color=C_ACCENT, spaceAfter=10)

def linha_fina():
    return HRFlowable(width='100%', thickness=0.5, color=C_BORDER, spaceAfter=6)


# ─── CAPA ──────────────────────────────────────────────────────────────────────
def _capa(E, emp, proposta, cliente, S):
    """Gera a capa da proposta no estilo Creative"""

    # Fundo escuro via tabela
    fundo = Table([['']], colWidths=[CONTENT_W])
    fundo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_DARK),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [C_DARK]),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))

    # Logo
    logo_path = None
    logo = emp.get('logo')
    if logo:
        p = os.path.join(BASE_DIR, 'static', 'uploads', 'empresas', logo)
        if os.path.exists(p): logo_path = p

    # Bloco de cabeçalho da capa
    if logo_path:
        try:
            logo_img = RLImage(logo_path, width=40*mm, height=14*mm)
            logo_img.hAlign = 'CENTER'
            E.append(Spacer(1, 10*mm))
            E.append(logo_img)
        except:
            E.append(Spacer(1, 10*mm))
            E.append(Paragraph(emp.get('fantasia','Creative'), S['capa_empresa']))
    else:
        E.append(Spacer(1, 10*mm))
        E.append(Paragraph(emp.get('fantasia','Creative'), S['capa_empresa']))

    E.append(Spacer(1, 2*mm))
    E.append(Paragraph(emp.get('razao_social',''), S['capa_sub']))
    E.append(Paragraph(f"CNPJ: {emp.get('cnpj','')}  |  {emp.get('telefone','')}  |  {emp.get('cidade','')}/{emp.get('estado','')}", S['capa_sub']))

    E.append(Spacer(1, 12*mm))
    E.append(linha_accent())
    E.append(Spacer(1, 6*mm))

    # Título da proposta
    E.append(Paragraph('PROPOSTA COMERCIAL', S['capa_empresa']))
    E.append(Spacer(1, 3*mm))
    titulo = proposta.get('titulo','Proposta Comercial')
    E.append(Paragraph(titulo, S['capa_titulo']))
    E.append(Spacer(1, 4*mm))
    cli_nome = cliente.get('nome','') if cliente else ''
    E.append(Paragraph(f"Preparada exclusivamente para: <b>{cli_nome}</b>", S['capa_desc']))

    E.append(Spacer(1, 10*mm))
    E.append(linha_fina())
    E.append(Spacer(1, 4*mm))

    # Meta info
    hoje = datetime.now().strftime('%d/%m/%Y')
    validade = proposta.get('validade', 15)
    numero   = proposta.get('numero','')
    forma_pag = proposta.get('forma_pagamento','A combinar')

    meta = Table([
        [Paragraph('DATA', S['capa_meta_lbl']),
         Paragraph('VALIDADE', S['capa_meta_lbl']),
         Paragraph('REFERÊNCIA', S['capa_meta_lbl']),
         Paragraph('PAGAMENTO', S['capa_meta_lbl'])],
        [Paragraph(hoje, S['capa_meta_val']),
         Paragraph(f'{validade} dias', S['capa_meta_val']),
         Paragraph(numero, S['capa_meta_val']),
         Paragraph(forma_pag or 'A combinar', S['capa_meta_val'])],
    ], colWidths=[CONTENT_W/4]*4)
    meta.setStyle(TableStyle([
        ('ALIGN',       (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',  (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
    ]))
    E.append(meta)
    E.append(Spacer(1, 8*mm))
    E.append(PageBreak())


# ─── SEÇÃO NUMERADA ────────────────────────────────────────────────────────────
def _secao(E, numero, titulo, S):
    E.append(Spacer(1, 4*mm))
    E.append(Paragraph(f"{numero}.", S['secao_num']))
    E.append(Paragraph(titulo, S['secao_titulo']))
    E.append(linha_accent())


# ─── TABELA DE ITENS ───────────────────────────────────────────────────────────
def _tabela_itens(E, itens, S, titulo='ITENS DA PROPOSTA',
                   custo_loco=0, custo_alim=0, custo_outros=0, descricao_custos=''):
    if not itens:
        return

    # Agrupa por tipo
    produtos  = [i for i in itens if i.get('tipo') in ('produto','material','')]
    servicos  = [i for i in itens if i.get('tipo') == 'servico']
    outros    = [i for i in itens if i not in produtos and i not in servicos]

    def _bloco_itens(lista, subtitulo):
        if not lista: return
        E.append(Paragraph(subtitulo, S['secao_sub']))
        rows = [[
            Paragraph('#',         S['th']),
            Paragraph('Descrição', S['th']),
            Paragraph('Qtd',       S['th']),
            Paragraph('Unit.',     S['th']),
            Paragraph('Total',     S['th']),
        ]]
        subtotal = 0
        for i, item in enumerate(lista):
            sub = (item.get('quantidade',1) or 1) * (item.get('preco_unitario',0) or 0)
            subtotal += sub
            desc_det = item.get('descricao_detalhada','')
            desc_txt = item.get('descricao','')
            if desc_det:
                desc_txt = f"<b>{desc_txt}</b><br/><font size='7.5' color='#64748b'>{desc_det[:120]}</font>"
            rows.append([
                Paragraph(str(i+1), S['td_center']),
                Paragraph(desc_txt, S['td']),
                Paragraph(str(item.get('quantidade',1)), S['td_center']),
                Paragraph(f"R$ {item.get('preco_unitario',0):,.2f}", S['td_center']),
                Paragraph(f"R$ {sub:,.2f}", S['td_green']),
            ])
        # Subtotal row
        rows.append([
            '', '',
            Paragraph('Subtotal', S['corpo_bold']),
            '',
            Paragraph(f"R$ {subtotal:,.2f}", S['td_green']),
        ])
        n = len(rows)
        t = Table(rows, colWidths=[10*mm, CONTENT_W-75*mm, 18*mm, 24*mm, 23*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),  (-1,0),   C_DARK),
            ('ROWBACKGROUNDS',(0,1),  (-1,n-2), [C_WHITE, C_ROW_ALT]),
            ('BACKGROUND',    (0,n-1),(-1,n-1), colors.HexColor('#f0fdf4')),
            ('GRID',          (0,0),  (-1,-1),  0.3, C_BORDER),
            ('TOPPADDING',    (0,0),  (-1,-1),  5),
            ('BOTTOMPADDING', (0,0),  (-1,-1),  5),
            ('LEFTPADDING',   (0,0),  (-1,-1),  6),
            ('RIGHTPADDING',  (0,0),  (-1,-1),  6),
            ('VALIGN',        (0,0),  (-1,-1),  'MIDDLE'),
            ('SPAN',          (0,n-1),(1,n-1)),
            ('SPAN',          (2,n-1),(3,n-1)),
        ]))
        E.append(t)
        E.append(Spacer(1, 4*mm))
        return subtotal

    total_geral = 0
    if produtos:
        st = _bloco_itens(produtos, 'Produtos / Materiais')
        if st: total_geral += st
    if servicos:
        st = _bloco_itens(servicos, 'Serviços')
        if st: total_geral += st
    if outros:
        st = _bloco_itens(outros, 'Outros')
        if st: total_geral += st

    # Custos adicionais
    custo_extra = (custo_loco or 0) + (custo_alim or 0) + (custo_outros or 0)
    if custo_extra > 0:
        E.append(Paragraph('Custos Adicionais', S['secao_sub']))
        rows_c = [[Paragraph('Descrição', S['th']), Paragraph('Valor', S['th'])]]
        if custo_loco:
            rows_c.append([Paragraph('Locomoção', S['td']),
                           Paragraph(f"R$ {custo_loco:,.2f}", S['td_green'])])
        if custo_alim:
            rows_c.append([Paragraph('Alimentação', S['td']),
                           Paragraph(f"R$ {custo_alim:,.2f}", S['td_green'])])
        if custo_outros:
            desc = descricao_custos or 'Outros'
            rows_c.append([Paragraph(desc, S['td']),
                           Paragraph(f"R$ {custo_outros:,.2f}", S['td_green'])])
        tc = Table(rows_c, colWidths=[CONTENT_W-30*mm, 30*mm])
        tc.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0), C_DARK),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [C_WHITE, C_ROW_ALT]),
            ('GRID',          (0,0),(-1,-1), 0.3, C_BORDER),
            ('TOPPADDING',    (0,0),(-1,-1), 5),
            ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ]))
        E.append(tc)
        E.append(Spacer(1, 4*mm))
        total_geral += custo_extra

    # TOTAL FINAL
    total_row = Table([[
        Paragraph('INVESTIMENTO TOTAL', S['total_lbl']),
        Paragraph(f"R$ {total_geral:,.2f}", S['total_val']),
    ]], colWidths=[CONTENT_W*0.55, CONTENT_W*0.45])
    total_row.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), C_DARKER),
        ('TOPPADDING',    (0,0),(-1,-1), 12),
        ('BOTTOMPADDING', (0,0),(-1,-1), 12),
        ('LEFTPADDING',   (0,0),(0,-1),  16),
        ('RIGHTPADDING',  (-1,0),(-1,-1),16),
        ('ALIGN',         (1,0),(1,-1),  'RIGHT'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('ROUNDEDCORNERS',(0,0),(-1,-1), [8,8,8,8]),
    ]))
    E.append(total_row)

    return total_geral


# ─── QUADRO COMPARATIVO ────────────────────────────────────────────────────────
def _quadro_comparativo(E, opcoes, S):
    """opcoes = lista de dicts com 'nome', 'atributos': [(label, valor), ...]"""
    if not opcoes or len(opcoes) < 2:
        return

    E.append(Spacer(1, 2*mm))
    # Cabeçalho
    header = [Paragraph('Característica', S['th'])]
    for op in opcoes:
        header.append(Paragraph(op.get('nome',''), S['th']))

    # Coleta todos os atributos únicos
    all_attrs = []
    seen = set()
    for op in opcoes:
        for label, _ in op.get('atributos',[]):
            if label not in seen:
                all_attrs.append(label)
                seen.add(label)

    rows = [header]
    for label in all_attrs:
        row = [Paragraph(label, S['td_bold'])]
        for op in opcoes:
            attr_dict = dict(op.get('atributos',[]))
            val = attr_dict.get(label,'—')
            # Ícones visuais
            if val == '✓' or val is True or str(val).lower() in ('sim','yes','✓'):
                cell = Paragraph('<font color="#10B981">✓ Sim</font>', S['td_center'])
            elif val == '✗' or val is False or str(val).lower() in ('não','no','nao','✗'):
                cell = Paragraph('<font color="#ef4444">✗ Não</font>', S['td_center'])
            else:
                cell = Paragraph(str(val), S['td_center'])
            row.append(cell)
        rows.append(row)

    n = len(rows)
    col_w = CONTENT_W / (len(opcoes) + 1)
    t = Table(rows, colWidths=[col_w*1.4] + [col_w*0.6 + (CONTENT_W/(len(opcoes)+1)*0.4/len(opcoes))]*len(opcoes))
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),  (-1,0),  C_DARK),
        ('ROWBACKGROUNDS',(0,1),  (-1,-1), [C_WHITE, C_ROW_ALT]),
        ('GRID',          (0,0),  (-1,-1), 0.3, C_BORDER),
        ('TOPPADDING',    (0,0),  (-1,-1), 5),
        ('BOTTOMPADDING', (0,0),  (-1,-1), 5),
        ('LEFTPADDING',   (0,0),  (-1,-1), 6),
        ('VALIGN',        (0,0),  (-1,-1), 'MIDDLE'),
        # Destaca coluna recomendada (segunda coluna = opcao[0])
        ('BACKGROUND',    (1,1),  (1,-1),  colors.HexColor('#f0fdf4')),
    ]))
    E.append(t)


# ─── CAIXA DE RECOMENDAÇÃO ─────────────────────────────────────────────────────
def _caixa_recomendacao(E, texto, S):
    box = Table([[
        Paragraph('★  RECOMENDAÇÃO TÉCNICA', S['rec']),
        Paragraph(texto, S['rec_sub']),
    ]], colWidths=[CONTENT_W*0.32, CONTENT_W*0.68])
    box.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), colors.HexColor('#065f46')),
        ('TOPPADDING',    (0,0),(-1,-1), 12),
        ('BOTTOMPADDING', (0,0),(-1,-1), 12),
        ('LEFTPADDING',   (0,0),(0,-1),  14),
        ('LEFTPADDING',   (1,0),(1,-1),  10),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    E.append(box)


# ─── CONDIÇÕES COMERCIAIS ──────────────────────────────────────────────────────
def _condicoes(E, proposta, S):
    validade = proposta.get('validade', 15)
    forma    = proposta.get('forma_pagamento','A combinar')
    obs      = proposta.get('observacoes','')
    cond     = proposta.get('condicoes','')

    linhas = [
        ('Validade da Proposta', f'{validade} dias a partir da emissão'),
        ('Forma de Pagamento',   forma or 'A combinar'),
        ('Garantia da Instalação', '90 dias para serviços'),
        ('Garantia do Equipamento', 'Conforme fabricante'),
    ]
    if cond:
        for linha in cond.split('\n'):
            if linha.strip() and ':' in linha:
                k, v = linha.split(':', 1)
                linhas.append((k.strip(), v.strip()))

    rows = [[Paragraph('Condição', S['th']), Paragraph('Detalhe', S['th'])]]
    for k, v in linhas:
        rows.append([Paragraph(k, S['td_bold']), Paragraph(v, S['td'])])

    if obs:
        rows.append([Paragraph('Observações', S['td_bold']),
                     Paragraph(obs, S['td'])])

    n = len(rows)
    t = Table(rows, colWidths=[CONTENT_W*0.38, CONTENT_W*0.62])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  C_DARK),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [C_WHITE, C_ROW_ALT]),
        ('GRID',          (0,0),(-1,-1), 0.3, C_BORDER),
        ('TOPPADDING',    (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
    ]))
    E.append(t)


# ─── RODAPÉ DE AGRADECIMENTO ───────────────────────────────────────────────────
def _agradecimento(E, emp, S):
    E.append(Spacer(1, 8*mm))
    E.append(linha_fina())
    E.append(Spacer(1, 4*mm))
    fantasia = emp.get('fantasia','Creative')
    tel      = emp.get('telefone','')
    email    = emp.get('email','')
    cid      = f"{emp.get('cidade','')}/{emp.get('estado','')}"

    E.append(Paragraph(
        f'Agradecemos a oportunidade de apresentar nossa proposta.',
        S['rodape_texto']))
    E.append(Paragraph(
        f'Ficamos à disposição para esclarecimentos adicionais.',
        S['rodape_texto']))
    E.append(Spacer(1, 3*mm))
    E.append(Paragraph(
        f'<b>{fantasia}</b>  |  {tel}  |  {email}  |  {cid}',
        S['rodape_texto']))


# ─── FUNÇÃO PRINCIPAL ──────────────────────────────────────────────────────────
def gerar_proposta_inteligente(proposta: dict, empresa: dict,
                                cliente: dict, itens: list,
                                opcoes_comparativo: list = None,
                                recomendacao: str = '') -> BytesIO:
    """
    Gera proposta inteligente em PDF no estilo Creative.

    Args:
        proposta: dict com dados da proposta
        empresa:  dict com dados da empresa
        cliente:  dict com dados do cliente
        itens:    list de dicts com descricao, quantidade, preco_unitario, tipo
        opcoes_comparativo: lista opcional de opções para quadro comparativo
            ex: [{'nome':'Opção 1','atributos':[('Wi-Fi','5'),('Preço','R$900')]}, ...]
        recomendacao: texto da recomendação técnica (opcional)
    """
    buf = BytesIO()

    def make_canvas(filename, **kwargs):
        return CreativeCanvas(filename, pagesize=A4,
                              empresa=empresa, proposta=proposta)

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=20*mm, bottomMargin=18*mm,
        title=f"Proposta {proposta.get('numero','')} — {empresa.get('fantasia','')}",
        author=empresa.get('fantasia','Creative')
    )

    S = estilos()
    E = []

    # ── 1. CAPA ──────────────────────────────────────────────────────────────
    _capa(E, empresa, proposta, cliente, S)

    # ── 2. APRESENTAÇÃO ──────────────────────────────────────────────────────
    _secao(E, 1, 'APRESENTAÇÃO', S)
    cli_nome = cliente.get('nome','') if cliente else ''
    fantasia = empresa.get('fantasia','Creative')
    titulo   = proposta.get('titulo','')
    E.append(Paragraph(
        f'Prezado(a) <b>{cli_nome}</b>,',
        S['corpo']))
    E.append(Paragraph(
        f'Apresentamos nossa proposta para <b>{titulo}</b>. '
        f'Esta proposta foi elaborada exclusivamente para atender às necessidades '
        f'identificadas e apresentar a melhor solução custo-benefício disponível.',
        S['corpo']))
    obs_apres = proposta.get('analise_ambiente','')
    if obs_apres:
        E.append(Spacer(1, 2*mm))
        E.append(Paragraph('<b>Diagnóstico do Ambiente:</b>', S['corpo_bold']))
        for linha in obs_apres.split('\n'):
            if linha.strip():
                E.append(Paragraph(f'• {linha.strip()}', S['item_bullet']))

    # ── 3. PRODUTOS E SERVIÇOS ───────────────────────────────────────────────
    _secao(E, 2, 'PRODUTOS E SERVIÇOS', S)
    _tabela_itens(E, itens, S,
                  custo_loco=proposta.get('custo_locomocao',0),
                  custo_alim=proposta.get('custo_alimentacao',0),
                  custo_outros=proposta.get('custo_outros',0),
                  descricao_custos=proposta.get('descricao_custos',''))

    # ── 4. QUADRO COMPARATIVO (opcional) ─────────────────────────────────────
    if opcoes_comparativo and len(opcoes_comparativo) >= 2:
        _secao(E, 3, 'QUADRO COMPARATIVO', S)
        _quadro_comparativo(E, opcoes_comparativo, S)
        E.append(Spacer(1, 4*mm))
        prox_num = 4
    else:
        prox_num = 3

    # ── 5. RECOMENDAÇÃO ──────────────────────────────────────────────────────
    if recomendacao:
        _secao(E, prox_num, 'NOSSA RECOMENDAÇÃO', S)
        _caixa_recomendacao(E, recomendacao, S)
        E.append(Spacer(1, 4*mm))
        prox_num += 1

    # ── 6. CRONOGRAMA ────────────────────────────────────────────────────────
    cronograma = proposta.get('cronograma','')
    if cronograma:
        _secao(E, prox_num, 'CRONOGRAMA DE EXECUÇÃO', S)
        fases = [f.strip() for f in cronograma.split('\n') if f.strip()]
        rows_c = [[Paragraph('Fase', S['th']), Paragraph('Descrição', S['th'])]]
        for i, fase in enumerate(fases):
            rows_c.append([
                Paragraph(str(i+1), S['td_center']),
                Paragraph(fase, S['td'])
            ])
        tc = Table(rows_c, colWidths=[15*mm, CONTENT_W-15*mm])
        tc.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0),  C_DARK),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [C_WHITE, C_ROW_ALT]),
            ('GRID',          (0,0),(-1,-1), 0.3, C_BORDER),
            ('TOPPADDING',    (0,0),(-1,-1), 5),
            ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING',   (0,0),(-1,-1), 8),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
        E.append(tc)
        E.append(Spacer(1, 4*mm))
        prox_num += 1

    # ── 7. CONDIÇÕES COMERCIAIS ──────────────────────────────────────────────
    _secao(E, prox_num, 'CONDIÇÕES COMERCIAIS', S)
    _condicoes(E, proposta, S)

    # ── ASSINATURA DIGITAL (se existir) ─────────────────────────────────────
    if proposta.get('assinatura_nome'):
        E.append(Spacer(1, 6*mm))
        E.append(linha_fina())
        E.append(Spacer(1, 3*mm))
        nome_ass = proposta.get('assinatura_nome','')
        cpf_ass  = proposta.get('assinatura_cpf','')
        data_ass = proposta.get('aprovado_em','')
        if hasattr(data_ass,'strftime'): data_ass = data_ass.strftime('%d/%m/%Y %H:%M')
        hash_ass = proposta.get('assinatura_hash','')
        ip_ass   = proposta.get('assinatura_ip','')

        ass_data = Table([[
            Paragraph('<b>PROPOSTA ASSINADA DIGITALMENTE</b>', S['rec']),
            Paragraph(
                f'Assinado por: <b>{nome_ass}</b> | CPF: {cpf_ass}<br/>'
                f'Data/Hora: {data_ass} | IP: {ip_ass}',
                S['rec_sub']),
        ]], colWidths=[CONTENT_W*0.35, CONTENT_W*0.65])
        ass_data.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), colors.HexColor('#065f46')),
            ('TOPPADDING',    (0,0),(-1,-1), 10),
            ('BOTTOMPADDING', (0,0),(-1,-1), 10),
            ('LEFTPADDING',   (0,0),(0,-1),  12),
            ('LEFTPADDING',   (1,0),(1,-1),  10),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
        E.append(ass_data)
        if hash_ass:
            E.append(Spacer(1, 2*mm))
            E.append(Paragraph(
                f'<font size="7" color="#64748b">Hash SHA-256: {hash_ass} | '
                f'Validade jurídica: Lei 14.063/2020 e Marco Civil da Internet (Lei 12.965/2014)</font>',
                S['rodape_texto']))

    # ── AGRADECIMENTO ────────────────────────────────────────────────────────
    _agradecimento(E, empresa, S)

    doc.build(E, canvasmaker=make_canvas)
    buf.seek(0)
    return buf
