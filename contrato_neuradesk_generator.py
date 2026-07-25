"""
NeuraBusiness — Gerador do Contrato de Licenciamento NeuraDesk

Independente do contrato_generator.py (que é do negócio de propostas
comerciais/Creative) -- este aqui tem texto próprio, específico do
licenciamento de uso do software NeuraDesk e da prestação dos serviços
de hospedagem/manutenção/suporte que o acompanham.

Gerado sob demanda (a cada download), a partir do estado atual do
registro no banco -- não fica um arquivo estático salvo em disco.
"""
from datetime import datetime
import hashlib

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
)
from io import BytesIO

from config import Config

C_DARK   = colors.HexColor('#1b1f27')
C_MUTED  = colors.HexColor('#5b6472')
C_ACCENT = colors.HexColor('#EA640F')


def _estilos():
    return {
        'titulo': ParagraphStyle('titulo', fontName='Helvetica-Bold', fontSize=14,
            textColor=C_DARK, alignment=TA_CENTER, spaceAfter=6, spaceBefore=4),
        'sub': ParagraphStyle('sub', fontName='Helvetica', fontSize=9.5,
            textColor=C_MUTED, alignment=TA_CENTER, spaceAfter=14),
        'clausula': ParagraphStyle('clausula', fontName='Helvetica-Bold', fontSize=10.5,
            textColor=C_ACCENT, spaceAfter=5, spaceBefore=12),
        'corpo': ParagraphStyle('corpo', fontName='Helvetica', fontSize=9.3,
            textColor=C_DARK, alignment=TA_JUSTIFY, leading=14, spaceAfter=6),
        'item': ParagraphStyle('item', fontName='Helvetica', fontSize=9.3,
            textColor=C_DARK, leading=13, spaceAfter=3, leftIndent=14),
        'rodape': ParagraphStyle('rodape', fontName='Helvetica', fontSize=7.5,
            textColor=C_MUTED, alignment=TA_CENTER),
        'partes_label': ParagraphStyle('pl', fontName='Helvetica-Bold', fontSize=8,
            textColor=C_ACCENT, spaceAfter=2),
        'partes_valor': ParagraphStyle('pv', fontName='Helvetica', fontSize=8.5,
            textColor=C_DARK, spaceAfter=8, leading=11),
    }


def _fmt_reais(v):
    return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def gerar_contrato_neuradesk_pdf(contrato, licenca):
    """contrato: ContratoNeuraDesk ; licenca: LicencaNeuraDesk"""
    s = _estilos()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Contrato NeuraDesk — {contrato.numero}",
    )
    L = A4[0] - 44 * mm
    E = []

    E.append(Paragraph('CONTRATO DE LICENCIAMENTO DE USO DE SOFTWARE<br/>E PRESTAÇÃO DE SERVIÇOS — NEURADESK', s['titulo']))
    E.append(Paragraph(f"Contrato nº {contrato.numero}", s['sub']))

    partes = Table([[
        Paragraph('CONTRATADA', s['partes_label']),
        Paragraph('CONTRATANTE', s['partes_label']),
    ], [
        Paragraph(
            f"<b>{Config.CONTRATADA_RAZAO_SOCIAL}</b><br/>"
            f"CNPJ: {Config.CONTRATADA_CNPJ}<br/>"
            f"{Config.CONTRATADA_ENDERECO}<br/>"
            f"Repr.: {Config.CONTRATADA_REPRESENTANTE_NOME} — CPF: {Config.CONTRATADA_REPRESENTANTE_CPF}",
            s['partes_valor']),
        Paragraph(
            f"<b>{contrato.empresa_razao_social or ''}</b><br/>"
            f"CNPJ: {licenca.empresa_cnpj or '—'}<br/>"
            f"{contrato.empresa_endereco or '—'}<br/>"
            f"Repr.: {contrato.representante_nome or '—'} — CPF: {contrato.representante_cpf or '—'}",
            s['partes_valor']),
    ]], colWidths=[L / 2, L / 2])
    partes.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    E.append(partes)
    E.append(HRFlowable(width='100%', thickness=0.6, color=colors.HexColor('#dde1e7'), spaceAfter=10))

    def clausula(n, titulo, *paragrafos):
        E.append(Paragraph(f"Cláusula {n}ª — {titulo}", s['clausula']))
        for p in paragrafos:
            E.append(Paragraph(p, s['corpo']))

    clausula('1', 'Do Objeto',
        'O presente contrato tem por objeto o licenciamento, por parte da CONTRATADA, do uso do sistema '
        '<b>NeuraDesk</b> — plataforma de gestão de tecnologia da informação — à CONTRATANTE, em caráter não '
        'exclusivo e intransferível, além da prestação dos serviços de hospedagem, manutenção e suporte técnico '
        'descritos neste instrumento.',
        'A licença ora concedida não inclui a cessão do código-fonte, nem qualquer direito de propriedade '
        'intelectual sobre o software, permanecendo este de titularidade da CONTRATADA (Cláusula 8ª).')

    clausula('2', 'Da Hospedagem',
        'O sistema será instalado em servidor dedicado exclusivamente à CONTRATANTE, isolado de qualquer outra '
        'instalação ou cliente da CONTRATADA, com banco de dados, credenciais e arquivos próprios, incluindo '
        'certificado de segurança (HTTPS) válido e renovado automaticamente.')

    modulos = contrato.get_modulos()
    linhas_mod = [['Módulo', 'Valor mensal']]
    linhas_mod.append(['Núcleo (chamados, equipamentos, insumos, manutenções, wiki)', 'Incluso no plano base'])
    for m in modulos:
        linhas_mod.append([m.get('nome', m.get('chave', '')), _fmt_reais(float(m.get('valor', 0)))])
    clausula('3', 'Dos Módulos Contratados',
        'Fazem parte do plano contratado os módulos abaixo, ativados exclusivamente mediante solicitação da CONTRATANTE:')
    t_mod = Table(linhas_mod, colWidths=[L * 0.7, L * 0.3])
    t_mod.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('TEXTCOLOR', (0, 0), (-1, 0), C_ACCENT),
        ('LINEBELOW', (0, 0), (-1, 0), 0.6, colors.HexColor('#dde1e7')),
        ('LINEBELOW', (0, 1), (-1, -1), 0.4, colors.HexColor('#eef0f3')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    E.append(t_mod)
    E.append(Spacer(1, 6))

    clausula('4', 'Do Prazo e da Vigência',
        'O presente contrato vigora por prazo indeterminado, com início na data de ativação da licença, '
        'renovando-se automaticamente a cada ciclo de cobrança mensal, mediante o pagamento tempestivo da mensalidade.')

    valor_total_modulos = sum(float(m.get('valor', 0)) for m in modulos)
    clausula('5', 'Do Preço e da Forma de Pagamento',
        f'Pela licença de uso e pelos serviços descritos neste contrato, a CONTRATANTE pagará à CONTRATADA o valor '
        f'mensal de <b>{_fmt_reais(contrato.valor_base or 0)}</b> (plano base), referente a até '
        f'<b>{contrato.usuarios_inclusos or 0} usuários</b> ativos, acrescido de '
        f'<b>{_fmt_reais(valor_total_modulos)}</b> em módulos opcionais contratados (Cláusula 3ª), '
        f'totalizando <b>{_fmt_reais((contrato.valor_base or 0) + valor_total_modulos)}/mês</b>.',
        f'Cada usuário ativo adicional além do limite do plano base será cobrado à razão de '
        f'{_fmt_reais(contrato.valor_usuario_adicional or 0)}/mês por usuário.',
        f'O pagamento será processado por cobrança recorrente via Mercado Pago, com vencimento todo dia '
        f'{contrato.dia_vencimento or 10} de cada mês, a partir da data de ativação. '
        f'O valor contratado será reajustado anualmente pela variação acumulada do IPCA.')

    clausula('6', 'Da Inadimplência e Suspensão de Acesso',
        'Constatado o não pagamento na data de vencimento, a licença entra automaticamente em período de carência '
        'de 10 (dez) dias, durante o qual o acesso ao sistema permanece integralmente disponível, com aviso visível '
        'a todos os usuários sobre a pendência.',
        'Expirado o período de carência sem regularização, o acesso ao sistema é automaticamente suspenso para '
        'todos os usuários, com exceção do usuário administrador da CONTRATANTE, que mantém acesso exclusivamente '
        'para fins de regularização financeira. Confirmado o pagamento, o acesso de todos os usuários é '
        'restabelecido automaticamente.')

    clausula('7', 'Das Obrigações da Contratada',
        'Manter o sistema em funcionamento; realizar backup diário automatizado do banco de dados e dos arquivos '
        'da instalação, com retenção mínima de 14 (quatorze) dias; aplicar atualizações de segurança; prestar '
        'suporte técnico em horário comercial; manter as credenciais de infraestrutura do cliente cifradas em '
        'repouso, nunca em texto plano.')

    clausula('8', 'Da Propriedade Intelectual',
        'O sistema NeuraDesk, seu código-fonte, layout, marca e documentação são de propriedade exclusiva da '
        'CONTRATADA, não conferindo este contrato à CONTRATANTE qualquer direito sobre eles além da licença de uso '
        'aqui descrita. Os dados operacionais inseridos pela CONTRATANTE permanecem de sua propriedade.')

    clausula('9', 'Da Proteção de Dados Pessoais (LGPD)',
        'Para os fins da Lei nº 13.709/2018, as partes reconhecem que a CONTRATANTE figura como controladora dos '
        'dados pessoais eventualmente inseridos no sistema, e a CONTRATADA figura como operadora, tratando tais '
        'dados exclusivamente conforme as instruções da controladora e para a finalidade de prestação dos serviços '
        'contratados, adotando medidas técnicas de segurança compatíveis, incluindo cifragem de credenciais em '
        'repouso e controle de acesso por usuário.')

    clausula('10', 'Da Confidencialidade',
        'As partes obrigam-se a manter sigilo sobre quaisquer informações técnicas, comerciais ou operacionais da '
        'outra parte a que tenham acesso em razão deste contrato.')

    clausula('11', 'Da Limitação de Responsabilidade',
        'A responsabilidade da CONTRATADA por eventuais danos decorrentes da prestação dos serviços fica limitada '
        'ao valor total pago pela CONTRATANTE nos 6 (seis) meses anteriores ao evento, não respondendo a '
        'CONTRATADA por lucros cessantes, danos indiretos ou perda de dados decorrente de uso inadequado do '
        'sistema pela CONTRATANTE.')

    clausula('12', 'Da Rescisão',
        f'Qualquer das partes poderá rescindir este contrato mediante aviso prévio de {contrato.prazo_aviso_previo_dias or 30} '
        f'dias, por escrito. Rescindido o contrato, a CONTRATANTE terá o prazo de 15 (quinze) dias para solicitar a '
        f'exportação de seus dados, findo o qual a CONTRATADA poderá excluí-los definitivamente.')

    clausula('13', 'Do Foro',
        f'Fica eleito o foro da comarca de {contrato.cidade_foro or "[cidade/UF não definida]"} para dirimir '
        f'quaisquer controvérsias decorrentes deste contrato, com renúncia expressa a qualquer outro.')

    E.append(Spacer(1, 6))
    E.append(HRFlowable(width='100%', thickness=0.3, color=colors.HexColor('#dde1e7'), spaceAfter=6))

    # ── Assinatura do cliente ──
    if contrato.assinatura_nome:
        box = Table([[
            Paragraph('<b>ASSINADO DIGITALMENTE</b><br/><font size="7">CONTRATANTE</font>',
                ParagraphStyle('b1', fontName='Helvetica-Bold', fontSize=8,
                    textColor=colors.HexColor('#065f46'), alignment=TA_CENTER)),
            Paragraph(
                f'<b>Assinante:</b> {contrato.assinatura_nome}<br/>'
                f'<b>CPF:</b> {contrato.assinatura_cpf}<br/>'
                f'<b>Data:</b> {str(contrato.assinado_em)[:16]}<br/>'
                f'<b>IP:</b> {contrato.assinatura_ip}',
                ParagraphStyle('v1', fontName='Helvetica', fontSize=7.5, textColor=C_DARK, leading=11)),
        ]], colWidths=[L * 0.3, L * 0.7])
        box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#dcfce7')),
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#f0fdf4')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#10B981')),
            ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        E.append(box)
        E.append(Spacer(1, 3))
        E.append(Paragraph(f'Hash SHA-256 (Contratante): {contrato.assinatura_hash}',
            ParagraphStyle('h1', fontName='Helvetica', fontSize=6, textColor=C_MUTED)))
        E.append(Spacer(1, 8))
    else:
        E.append(Paragraph('Aguardando assinatura da CONTRATANTE.', s['rodape']))
        E.append(Spacer(1, 8))

    # ── Confirmação da contratada ──
    if contrato.confirmado_por:
        box2 = Table([[
            Paragraph('<b>ASSINADO DIGITALMENTE</b><br/><font size="7">CONTRATADA</font>',
                ParagraphStyle('b2', fontName='Helvetica-Bold', fontSize=8,
                    textColor=colors.HexColor('#92400e'), alignment=TA_CENTER)),
            Paragraph(
                f'<b>Confirmado por:</b> {contrato.confirmado_por}<br/>'
                f'<b>Data:</b> {str(contrato.confirmado_em)[:16]}<br/>'
                f'<b>IP:</b> {contrato.confirmado_ip}',
                ParagraphStyle('v2', fontName='Helvetica', fontSize=7.5, textColor=C_DARK, leading=11)),
        ]], colWidths=[L * 0.3, L * 0.7])
        box2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fff7ed')),
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#fffbf5')),
            ('BOX', (0, 0), (-1, -1), 0.5, C_ACCENT),
            ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        E.append(box2)
        E.append(Spacer(1, 3))
        E.append(Paragraph(
            f'Hash SHA-256 (Contratada): {contrato.confirmado_hash} | '
            f'Validade jurídica: Lei nº 14.063/2020 e Marco Civil da Internet (Lei nº 12.965/2014)',
            ParagraphStyle('h2', fontName='Helvetica', fontSize=6, textColor=C_MUTED)))
    else:
        E.append(Paragraph('Aguardando confirmação da CONTRATADA.', s['rodape']))

    E.append(Spacer(1, 10))
    E.append(HRFlowable(width='100%', thickness=0.3, color=colors.HexColor('#dde1e7'), spaceAfter=4))
    E.append(Paragraph(
        f'Contrato gerado automaticamente pelo NeuraBusiness — {contrato.numero} — '
        f'{datetime.now().strftime("%d/%m/%Y às %H:%M")}', s['rodape']))

    doc.build(E)
    buf.seek(0)
    return buf


def calcular_hash(*partes):
    raw = '|'.join(str(p) for p in partes)
    return hashlib.sha256(raw.encode()).hexdigest()
