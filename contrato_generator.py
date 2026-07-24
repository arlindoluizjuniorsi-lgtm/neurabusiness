"""
NeuraBusiness v3 — Gerador de Contrato de Prestação de Serviços
Gera contrato jurídico completo baseado na proposta aprovada
"""
from datetime import datetime, date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, PageBreak
)
from io import BytesIO
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── ESTILOS ──────────────────────────────────────────────────────────────────
def estilos():
    C_DARK  = colors.HexColor('#0f172a')
    C_MUTED = colors.HexColor('#64748b')
    C_ACCENT= colors.HexColor('#00D4FF')
    return {
        'titulo': ParagraphStyle('titulo',
            fontName='Helvetica-Bold', fontSize=14, textColor=C_DARK,
            alignment=TA_CENTER, spaceAfter=6, spaceBefore=8),
        'subtitulo': ParagraphStyle('sub',
            fontName='Helvetica-Bold', fontSize=11, textColor=C_DARK,
            spaceAfter=4, spaceBefore=10),
        'corpo': ParagraphStyle('corpo',
            fontName='Helvetica', fontSize=9.5, textColor=C_DARK,
            alignment=TA_JUSTIFY, leading=15, spaceAfter=6),
        'item': ParagraphStyle('item',
            fontName='Helvetica', fontSize=9.5, textColor=C_DARK,
            leading=14, spaceAfter=3, leftIndent=16),
        'negrito': ParagraphStyle('negrito',
            fontName='Helvetica-Bold', fontSize=9.5, textColor=C_DARK,
            leading=14, spaceAfter=4),
        'rodape': ParagraphStyle('rodape',
            fontName='Helvetica', fontSize=8, textColor=C_MUTED,
            alignment=TA_CENTER),
        'destaque': ParagraphStyle('destaque',
            fontName='Helvetica-Bold', fontSize=10, textColor=C_DARK,
            alignment=TA_CENTER, spaceAfter=4),
        'clausula': ParagraphStyle('clausula',
            fontName='Helvetica-Bold', fontSize=10, textColor=C_DARK,
            spaceAfter=4, spaceBefore=10),
    }

def _extenso_mes(mes):
    meses = ['janeiro','fevereiro','março','abril','maio','junho',
             'julho','agosto','setembro','outubro','novembro','dezembro']
    return meses[mes-1] if 1 <= mes <= 12 else str(mes)

def gerar_contrato_pdf(proposta, empresa, cliente, itens, contrato=None):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=25*mm, rightMargin=25*mm,
        topMargin=20*mm, bottomMargin=20*mm,
        title=f"Contrato de Prestação de Serviços — {proposta.get('numero','')}"
    )
    L = A4[0] - 50*mm
    s = estilos()
    E = []

    # ── DATA ──
    hoje = date.today()
    data_ext = f"{hoje.day} de {_extenso_mes(hoje.month)} de {hoje.year}"

    # ── DADOS DAS PARTES ──
    emp_nome  = empresa.get('razao_social','') if empresa else ''
    emp_cnpj  = empresa.get('cnpj','') if empresa else ''
    emp_end   = empresa.get('endereco','') if empresa else ''
    emp_cid   = f"{empresa.get('cidade','')}-{empresa.get('estado','')}" if empresa else ''
    emp_tel   = empresa.get('telefone','') if empresa else ''
    cli_nome  = cliente.get('nome','') if cliente else ''
    cli_cpf   = cliente.get('cpf_cnpj','') if cliente else ''
    cli_end   = cliente.get('endereco','') if cliente else ''
    cli_cid   = f"{cliente.get('cidade','')}-{cliente.get('estado','')}" if cliente else ''
    cli_tel   = cliente.get('telefone','') if cliente else ''
    total_itens = sum(i.get('quantidade',1)*i.get('preco_unitario',0) for i in itens)
    custo_extra = (proposta.get('custo_locomocao') or 0) + (proposta.get('custo_alimentacao') or 0) + (proposta.get('custo_outros') or 0)
    total     = total_itens + custo_extra
    forma_pag = proposta.get('forma_pagamento','a combinar')
    num_prop  = proposta.get('numero','')

    # ── CABEÇALHO ──
    logo_path = None
    if empresa and empresa.get('logo'):
        p = os.path.join(BASE_DIR, 'static', 'uploads', 'empresas', empresa['logo'])
        if os.path.exists(p):
            logo_path = p

    if logo_path:
        from reportlab.platypus import Image as RLImage
        logo = RLImage(logo_path)
        logo.drawWidth = 100; logo.drawHeight = 32
        cab = Table([[logo, Paragraph(f'<b>{emp_nome}</b><br/>{emp_cnpj}<br/>{emp_tel}',
            ParagraphStyle('cb', fontName='Helvetica', fontSize=8,
                textColor=colors.HexColor('#64748b'), alignment=TA_LEFT))]], 
            colWidths=[L*0.45, L*0.55])
        cab.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('ALIGN',(1,0),(1,0),'RIGHT'),
        ]))
        E.append(cab)
    else:
        E.append(Paragraph(f'<b>{emp_nome}</b>', s['destaque']))

    E.append(HRFlowable(width='100%', thickness=2,
        color=colors.HexColor('#00D4FF'), spaceAfter=8))

    # ── TÍTULO ──
    E.append(Paragraph('CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE TECNOLOGIA', s['titulo']))
    E.append(Paragraph(f'Ref. Proposta {num_prop}', s['subtitulo']))
    E.append(Spacer(1, 6))

    # ── PREÂMBULO ──
    E.append(Paragraph(
        f'Pelo presente instrumento particular, as partes abaixo qualificadas celebram entre si '
        f'o presente <b>Contrato de Prestação de Serviços de Tecnologia da Informação</b>, que '
        f'se regerá pelas cláusulas e condições a seguir estipuladas, em conformidade com o '
        f'Código Civil Brasileiro (Lei nº 10.406/2002) e demais legislações aplicáveis.', s['corpo']))
    E.append(Spacer(1, 4))

    # ── PARTES ──
    E.append(Paragraph('DAS PARTES', s['clausula']))
    E.append(Paragraph(
        f'<b>CONTRATADO:</b> {emp_nome}, inscrita no CNPJ/CPF sob nº {emp_cnpj}, '
        f'com sede em {emp_end}, {emp_cid}, telefone {emp_tel}, '
        f'doravante denominada simplesmente <b>CONTRATADO</b>.', s['corpo']))
    E.append(Paragraph(
        f'<b>CONTRATANTE:</b> {cli_nome}, inscrito no CPF/CNPJ sob nº {cli_cpf}, '
        f'residente/domiciliado em {cli_end}, {cli_cid}, telefone {cli_tel}, '
        f'doravante denominado simplesmente <b>CONTRATANTE</b>.', s['corpo']))

    E.append(HRFlowable(width='100%', thickness=0.5,
        color=colors.HexColor('#e2e8f0'), spaceAfter=4))

    # ── CLÁUSULA 1: OBJETO ──
    E.append(Paragraph('CLÁUSULA 1ª — DO OBJETO', s['clausula']))
    E.append(Paragraph(
        f'O presente contrato tem como objeto a prestação dos serviços de tecnologia '
        f'descritos na Proposta Comercial nº <b>{num_prop}</b>, conforme especificações '
        f'abaixo detalhadas:', s['corpo']))

    # Tabela de itens
    cab_tb = [
        [Paragraph('<b>Item</b>', ParagraphStyle('tbh', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)),
         Paragraph('<b>Descrição</b>', ParagraphStyle('tbh', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)),
         Paragraph('<b>Qtd</b>', ParagraphStyle('tbh', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
         Paragraph('<b>Tipo</b>', ParagraphStyle('tbh', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white, alignment=TA_CENTER)),
        ]
    ]
    rows_tb = list(cab_tb)
    for i, it in enumerate(itens):
        rows_tb.append([
            Paragraph(str(i+1), ParagraphStyle('tbd', fontName='Helvetica', fontSize=8)),
            Paragraph(str(it.get('descricao','')), ParagraphStyle('tbd', fontName='Helvetica', fontSize=8)),
            Paragraph(str(it.get('quantidade',1)), ParagraphStyle('tbd', fontName='Helvetica', fontSize=8, alignment=TA_CENTER)),
            Paragraph(str(it.get('tipo','')), ParagraphStyle('tbd', fontName='Helvetica', fontSize=8, alignment=TA_CENTER)),
        ])
    rows_tb.append([
        '',
        Paragraph('<b>VALOR TOTAL DO CONTRATO</b>', ParagraphStyle('tbf', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#f97316'), alignment=TA_RIGHT)),
        '',
        Paragraph(f'<b>R$ {total:,.2f}</b>', ParagraphStyle('tbf', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#f97316'), alignment=TA_CENTER)),
    ])
    t_obj = Table(rows_tb, colWidths=[12*mm, L-50*mm, 14*mm, 24*mm])
    n = len(rows_tb)
    t_obj.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,0),  colors.HexColor('#0f172a')),
        ('ROWBACKGROUNDS',(0,1),(-1,n-2),[colors.white, colors.HexColor('#f8fafc')]),
        ('BACKGROUND',   (0,n-1),(-1,n-1), colors.HexColor('#1a1a1a')),
        ('GRID',         (0,0), (-1,-1), 0.3, colors.HexColor('#e2e8f0')),
        ('TOPPADDING',   (0,0), (-1,-1), 5),
        ('BOTTOMPADDING',(0,0), (-1,-1), 5),
        ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('LINEABOVE',    (0,n-1),(-1,n-1), 1.5, colors.HexColor('#f97316')),
        ('SPAN',         (0,n-1),(1,n-1)),
    ]))
    E.append(t_obj)
    E.append(Spacer(1, 6))

    # ── CLÁUSULA 2: PRAZO ──
    E.append(Paragraph('CLÁUSULA 2ª — DO PRAZO DE EXECUÇÃO', s['clausula']))
    E.append(Paragraph(
        'O prazo para execução dos serviços será definido de comum acordo entre as partes '
        'após assinatura deste contrato e confirmação do pagamento da entrada, podendo variar '
        'conforme a complexidade técnica e disponibilidade de materiais. Qualquer alteração no '
        'prazo deverá ser comunicada com antecedência mínima de 24 horas.', s['corpo']))

    # ── CLÁUSULA 3: VALOR E PAGAMENTO ──
    E.append(Paragraph('CLÁUSULA 3ª — DO VALOR E FORMA DE PAGAMENTO', s['clausula']))
    E.append(Paragraph(
        f'O valor total dos serviços e materiais objeto deste contrato é de '
        f'<b>R$ {total:,.2f} ({_valor_extenso(total)})</b>, '
        f'a ser pago mediante: <b>{forma_pag or "a combinar entre as partes"}</b>.', s['corpo']))
    E.append(Paragraph(
        'Parágrafo Único: O não pagamento nos prazos acordados sujeitará o CONTRATANTE à '
        'multa de 2% sobre o valor em atraso, acrescida de juros moratórios de 1% ao mês, '
        'calculados pro rata die, além de correção monetária pelo IPCA.', s['corpo']))

    # ── CLÁUSULA 4: OBRIGAÇÕES DO CONTRATADO ──
    E.append(Paragraph('CLÁUSULA 4ª — DAS OBRIGAÇÕES DO CONTRATADO', s['clausula']))
    obrig_cont = [
        'Executar os serviços com qualidade técnica e dentro das normas aplicáveis (ABNT, NR-10 e demais);',
        'Fornecer todos os materiais e equipamentos necessários à execução dos serviços, '
            'salvo quando expressamente pactuado que o CONTRATANTE fornecerá os materiais;',
        'Comunicar ao CONTRATANTE quaisquer imprevistos que possam afetar o prazo ou valor acordado;',
        'Manter sigilo sobre informações confidenciais do CONTRATANTE obtidas durante a prestação de serviços;',
        'Apresentar relatório técnico ao término dos serviços, com descrição das atividades realizadas;',
        'Prestar suporte técnico relativo aos serviços executados durante o prazo de garantia.',
    ]
    for ob in obrig_cont:
        E.append(Paragraph(f'• {ob}', s['item']))

    # ── CLÁUSULA 5: OBRIGAÇÕES DO CONTRATANTE ──
    E.append(Paragraph('CLÁUSULA 5ª — DAS OBRIGAÇÕES DO CONTRATANTE', s['clausula']))
    obrig_cli = [
        'Efetuar os pagamentos nos prazos e condições acordadas;',
        'Fornecer acesso ao local onde os serviços serão prestados, bem como às informações e '
            'equipamentos necessários à execução dos trabalhos;',
        'Notificar imediatamente o CONTRATADO sobre qualquer irregularidade verificada nos serviços;',
        'Não realizar alterações nos serviços executados sem prévia comunicação ao CONTRATADO;',
        'Fazer backup dos dados antes do início dos serviços, quando aplicável, sendo o CONTRATANTE '
            'responsável pela guarda e segurança das suas informações.',
    ]
    for ob in obrig_cli:
        E.append(Paragraph(f'• {ob}', s['item']))

    # ── CLÁUSULA 6: GARANTIA ──
    E.append(Paragraph('CLÁUSULA 6ª — DA GARANTIA', s['clausula']))
    E.append(Paragraph(
        'Os serviços de mão de obra executados pelo CONTRATADO terão garantia de <b>90 (noventa) dias</b>, '
        'contados da data de conclusão e aceite pelo CONTRATANTE. Os materiais fornecidos possuem '
        'garantia conforme especificação do fabricante.', s['corpo']))
    E.append(Paragraph('<b>A garantia NÃO abrange:</b>', s['negrito']))
    nao_garante = [
        'Danos causados por mau uso, acidentes, quedas, líquidos ou agentes externos;',
        'Danos causados por instabilidade ou ausência de energia elétrica (surtos, raios, falhas de rede);',
        'Defeitos decorrentes de intervenções realizadas por terceiros após a prestação dos serviços;',
        'Desgaste natural de peças e componentes sujeitos à depreciação;',
        'Ataques cibernéticos, vírus, malwares ou invasões externas aos sistemas.',
    ]
    for ng in nao_garante:
        E.append(Paragraph(f'• {ng}', s['item']))

    # ── CLÁUSULA 7: RESCISÃO ──
    E.append(Paragraph('CLÁUSULA 7ª — DA RESCISÃO', s['clausula']))
    E.append(Paragraph(
        'O presente contrato poderá ser rescindido por qualquer das partes mediante notificação '
        'prévia de <b>5 (cinco) dias úteis</b>, respondendo a parte que der causa à rescisão '
        'pelos danos e prejuízos causados à outra. Em caso de rescisão imotivada pelo CONTRATANTE '
        'após o início da execução, serão devidos ao CONTRATADO os valores proporcionais aos '
        'serviços já executados, acrescidos de multa de 10% sobre o valor total do contrato.', s['corpo']))

    # ── CLÁUSULA 8: RESPONSABILIDADE ──
    E.append(Paragraph('CLÁUSULA 8ª — DA RESPONSABILIDADE', s['clausula']))
    E.append(Paragraph(
        'O CONTRATADO não se responsabiliza por danos pré-existentes nos equipamentos ou '
        'instalações do CONTRATANTE não informados previamente, nem por perdas de dados não '
        'assegurados por backup realizado pelo CONTRATANTE. '
        'O CONTRATANTE reconhece que serviços de tecnologia podem apresentar limitações '
        'inerentes às condições do ambiente, equipamentos e infraestrutura disponíveis.', s['corpo']))

    # ── CLÁUSULA 9: CONFIDENCIALIDADE ──
    E.append(Paragraph('CLÁUSULA 9ª — DA CONFIDENCIALIDADE', s['clausula']))
    E.append(Paragraph(
        'Ambas as partes comprometem-se a manter em sigilo todas as informações confidenciais '
        'obtidas em razão deste contrato, não podendo divulgá-las a terceiros sem autorização '
        'expressa da outra parte, sob pena de responder por perdas e danos, pelo prazo de '
        '<b>2 (dois) anos</b> após o encerramento deste contrato.', s['corpo']))

    # ── CLÁUSULA 10: FORO ──
    cid_foro = (empresa.get('cidade','') + '/' + empresa.get('estado','')) if empresa else 'Mataraca/PB'
    E.append(Paragraph('CLÁUSULA 10ª — DO FORO', s['clausula']))
    E.append(Paragraph(
        f'As partes elegem o Foro da Comarca de <b>{cid_foro}</b> para dirimir quaisquer '
        f'dúvidas ou litígios decorrentes do presente contrato, renunciando a qualquer outro, '
        f'por mais privilegiado que seja.', s['corpo']))

    # ── ASSINATURAS ──
    E.append(Spacer(1, 14))
    E.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceAfter=8))
    E.append(Paragraph(
        f'E por estarem assim justos e contratados, firmam o presente instrumento em duas vias '
        f'de igual teor e valor, na cidade de {cid_foro}, em {data_ext}.', s['corpo']))

    E.append(Spacer(1, 24))
    ass_data = [
        [
            Paragraph('_______________________________', s['corpo']),
            Paragraph('_______________________________', s['corpo']),
        ],
        [
            Paragraph(f'<b>{emp_nome}</b>', ParagraphStyle('an', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#0f172a'), alignment=TA_CENTER)),
            Paragraph(f'<b>{cli_nome}</b>', ParagraphStyle('an', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#0f172a'), alignment=TA_CENTER)),
        ],
        [
            Paragraph(f'CNPJ: {emp_cnpj}', ParagraphStyle('ad', fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#64748b'), alignment=TA_CENTER)),
            Paragraph(f'CPF/CNPJ: {cli_cpf}', ParagraphStyle('ad', fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#64748b'), alignment=TA_CENTER)),
        ],
        [
            Paragraph('CONTRATADO', ParagraphStyle('at', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#64748b'), alignment=TA_CENTER)),
            Paragraph('CONTRATANTE', ParagraphStyle('at', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#64748b'), alignment=TA_CENTER)),
        ],
    ]
    t_ass = Table(ass_data, colWidths=[L/2, L/2])
    t_ass.setStyle(TableStyle([
        ('ALIGN',   (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    E.append(t_ass)

    E.append(Spacer(1, 10))
    E.append(Paragraph(
        f'Testemunhas: ___________________________ CPF: __________________ | '
        f'___________________________ CPF: __________________', s['rodape']))

    # ── ASSINATURA DIGITAL (se existir) ──
    if contrato and contrato.get('assinatura_nome'):
        E.append(Spacer(1, 8))
        E.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#10B981'), spaceAfter=6))
        ass_box = Table([[
            Paragraph('<b>ASSINADO DIGITALMENTE</b><br/><font size="7">CONTRATANTE</font>',
                ParagraphStyle('ab', fontName='Helvetica-Bold', fontSize=8,
                    textColor=colors.HexColor('#065f46'), alignment=TA_CENTER)),
            Paragraph(
                f'<b>Assinante:</b> {contrato.get("assinatura_nome","")}<br/>'
                f'<b>CPF:</b> {contrato.get("assinatura_cpf","")}<br/>'
                f'<b>Data:</b> {str(contrato.get("assinado_em",""))[:16]}<br/>'
                f'<b>IP:</b> {contrato.get("assinatura_ip","")}',
                ParagraphStyle('av', fontName='Helvetica', fontSize=7.5,
                    textColor=colors.HexColor('#1e293b'), leading=11)),
        ]], colWidths=[L*0.3, L*0.7])
        ass_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#dcfce7')),
            ('BACKGROUND', (1,0), (1,-1), colors.HexColor('#f0fdf4')),
            ('BOX',        (0,0), (-1,-1), 0.5, colors.HexColor('#10B981')),
            ('TOPPADDING',    (0,0),(-1,-1), 8),
            ('BOTTOMPADDING', (0,0),(-1,-1), 8),
            ('LEFTPADDING',   (0,0),(-1,-1), 10),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
        E.append(ass_box)
        if contrato.get('assinatura_hash'):
            E.append(Spacer(1, 4))
            E.append(Paragraph(
                f'Hash SHA-256 (Cliente): {contrato.get("assinatura_hash","")}',
                ParagraphStyle('hh', fontName='Helvetica', fontSize=6,
                    textColor=colors.HexColor('#94a3b8'), leading=8)))

    # Assinatura da empresa
    if contrato and contrato.get('empresa_assinatura_nome'):
        E.append(Spacer(1, 6))
        emp_box = Table([[
            Paragraph('<b>ASSINADO DIGITALMENTE</b><br/><font size="7">CONTRATADA</font>',
                ParagraphStyle('ab2', fontName='Helvetica-Bold', fontSize=8,
                    textColor=colors.HexColor('#92400e'), alignment=TA_CENTER)),
            Paragraph(
                f'<b>Empresa:</b> {contrato.get("empresa_assinatura_nome","")}<br/>'
                f'<b>CNPJ:</b> 45.127.220/0001-19<br/>'
                f'<b>Representante:</b> Arlindo Luiz da Silva Junior<br/>'
                f'<b>CPF:</b> 106.741.004-09<br/>'
                f'<b>Data:</b> {str(contrato.get("empresa_assinado_em",""))[:16]}<br/>'
                f'<b>IP:</b> {contrato.get("empresa_assinatura_ip","")}',
                ParagraphStyle('av2', fontName='Helvetica', fontSize=7.5,
                    textColor=colors.HexColor('#1e293b'), leading=11)),
        ]], colWidths=[L*0.3, L*0.7])
        emp_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#fff7ed')),
            ('BACKGROUND', (1,0), (1,-1), colors.HexColor('#fffbf5')),
            ('BOX',        (0,0), (-1,-1), 0.5, colors.HexColor('#f97316')),
            ('TOPPADDING',    (0,0),(-1,-1), 8),
            ('BOTTOMPADDING', (0,0),(-1,-1), 8),
            ('LEFTPADDING',   (0,0),(-1,-1), 10),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ]))
        E.append(emp_box)
        if contrato.get('empresa_assinatura_hash'):
            E.append(Spacer(1, 4))
            E.append(Paragraph(
                f'Hash SHA-256 (Empresa): {contrato.get("empresa_assinatura_hash","")} | '
                f'Validade juridica: Lei 14.063/2020 e Marco Civil da Internet (Lei 12.965/2014)',
                ParagraphStyle('hh2', fontName='Helvetica', fontSize=6,
                    textColor=colors.HexColor('#94a3b8'), leading=8)))

    E.append(Spacer(1, 10))
    E.append(HRFlowable(width='100%', thickness=0.3, color=colors.HexColor('#e2e8f0'), spaceAfter=4))
    E.append(Paragraph(
        f'Contrato gerado automaticamente pelo NeuraBusiness Sistema Comercial — '
        f'Proposta {num_prop} — {datetime.now().strftime("%d/%m/%Y às %H:%M")}',
        s['rodape']))

    doc.build(E)
    buf.seek(0)
    return buf

def _valor_extenso(valor):
    """Converte valor numérico para texto simplificado"""
    inteiro = int(valor)
    centavos = round((valor - inteiro) * 100)
    if inteiro == 0:
        return f"zero reais e {centavos:02d} centavos"
    # Simplificado para valores comuns
    if inteiro < 1000:
        return f"aproximadamente {inteiro} reais"
    elif inteiro < 10000:
        return f"R$ {inteiro:,.0f} reais"
    else:
        return f"R$ {inteiro:,.0f} reais"

def gerar_texto_contrato_html(proposta, empresa, cliente, itens):
    """Gera versão HTML do contrato para visualização e assinatura online"""
    total = sum(i.get('quantidade',1)*i.get('preco_unitario',0) for i in itens)
    hoje = date.today()
    data_ext = f"{hoje.day} de {_extenso_mes(hoje.month)} de {hoje.year}"
    emp = empresa or {}
    cli = cliente or {}

    itens_html = ''.join([
        f'<tr><td>{i+1}</td><td>{it.get("descricao","")}</td>'
        f'<td style="text-align:center">{it.get("quantidade",1)}</td>'
        f'<td style="text-align:center">{it.get("tipo","")}</td>'
        f'<td style="text-align:right">R$ {it.get("quantidade",1)*it.get("preco_unitario",0):,.2f}</td></tr>'
        for i, it in enumerate(itens)
    ])

    return f"""
    <h2>CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE TECNOLOGIA</h2>
    <p><strong>Ref. Proposta {proposta.get('numero','')}</strong></p>
    <h3>DAS PARTES</h3>
    <p><strong>CONTRATADO:</strong> {emp.get('razao_social','')} — CNPJ {emp.get('cnpj','')} — {emp.get('cidade','')}/{emp.get('estado','')}</p>
    <p><strong>CONTRATANTE:</strong> {cli.get('nome','')} — CPF/CNPJ {cli.get('cpf_cnpj','')} — {cli.get('cidade','')}/{cli.get('estado','')}</p>
    <h3>OBJETO</h3>
    <table border="1" cellpadding="6" style="width:100%;border-collapse:collapse">
    <tr><th>#</th><th>Descrição</th><th>Qtd</th><th>Tipo</th><th>Total</th></tr>
    {itens_html}
    <tr><td colspan="4"><strong>TOTAL</strong></td><td style="text-align:right"><strong>R$ {total:,.2f}</strong></td></tr>
    </table>
    <p><strong>Forma de pagamento:</strong> {proposta.get('forma_pagamento','a combinar')}</p>
    <p><strong>Garantia:</strong> 90 dias para serviços de mão de obra.</p>
    <p>Data: {data_ext} — {emp.get('cidade','')}/{emp.get('estado','')}</p>
    """

def _extenso_mes(mes):
    meses = ['janeiro','fevereiro','março','abril','maio','junho',
             'julho','agosto','setembro','outubro','novembro','dezembro']
    return meses[mes-1] if 1 <= mes <= 12 else str(mes)
