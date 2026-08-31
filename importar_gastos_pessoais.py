"""Importa a planilha GASTOS.xlsx (controle pessoal de gastos do Arlindo)
pra dentro da Gestão Pessoal do NeuraBusiness. Rodar uma única vez:
    venv/bin/python3 importar_gastos_pessoais.py /tmp/GASTOS.xlsx
"""
import sys, re
from datetime import date
import openpyxl

sys.path.insert(0, '/opt/neurabusiness')
from app import app, db
from models import Usuario, CartaoPessoal, GastoPessoal

ARQUIVO = sys.argv[1] if len(sys.argv) > 1 else '/tmp/GASTOS.xlsx'

# Blocos de cartão: (nome do cartão, col nome, col valor, col data, col parcela)
BLOCOS_CARTAO = [
    ('BB',   0, 1, 2, 3),
    ('MELI', 5, 6, 7, 8),
]
COL_FIXO_NOME, COL_FIXO_VALOR = 10, 11
HEADERS = {'compras à vista': 'avista', 'compras recorrentes': 'recorrente', 'compras parceladas': 'parcelado'}


def primeira_parcela(ref_date, parcela_atual):
    # A data na planilha (ex: 10/07/2026) é o dia em que a fatura fechou
    # descrevendo o "X/Y" -- mas essa fatura só é paga no fim do mês
    # SEGUINTE (confirmado por Arlindo: nada tá quitado "agora" em
    # 03/08/2026, e os itens em X/X só serão pagos no fim de agosto).
    # Por isso a âncora usada aqui é um mês depois da data da planilha.
    ref_date = date(ref_date.year + (ref_date.month // 12), ref_date.month % 12 + 1, 1)
    total_meses = ref_date.year * 12 + (ref_date.month - 1) - (parcela_atual - 1)
    ano, mes = divmod(total_meses, 12)
    return date(ano, mes + 1, 1)


def main():
    wb = openpyxl.load_workbook(ARQUIVO, data_only=True)
    ws = wb.worksheets[0]
    linhas = list(ws.iter_rows(values_only=True))

    with app.app_context():
        u = Usuario.query.filter_by(is_super_admin=True).first()
        if not u:
            print('[ERRO] Nenhum usuário super_admin encontrado!')
            return

        cartoes = {}
        for nome, *_ in BLOCOS_CARTAO:
            c = CartaoPessoal.query.filter_by(usuario_id=u.id, nome=nome).first()
            if not c:
                c = CartaoPessoal(usuario_id=u.id, nome=nome)
                db.session.add(c)
                db.session.flush()
            cartoes[nome] = c

        count = 0

        # -- fixos --
        for row in linhas[1:]:
            nome = row[COL_FIXO_NOME]
            valor = row[COL_FIXO_VALOR]
            if not nome or str(nome).strip().lower() in ('total',):
                continue
            if not isinstance(valor, (int, float)) or valor <= 0:
                continue
            existe = GastoPessoal.query.filter_by(usuario_id=u.id, tipo='fixo', descricao=str(nome).strip(), valor=float(valor)).first()
            if existe:
                continue
            db.session.add(GastoPessoal(usuario_id=u.id, tipo='fixo', descricao=str(nome).strip(),
                                         valor=float(valor), ativo=True))
            count += 1

        # -- cartões (à vista / recorrente / parcelado) --
        for cartao_nome, col_nome, col_valor, col_data, col_parcela in BLOCOS_CARTAO:
            estado = None
            for row in linhas[1:]:
                nome = row[col_nome]
                if nome is None:
                    continue
                chave = str(nome).strip().lower()
                if chave in HEADERS:
                    estado = HEADERS[chave]
                    continue
                if chave == 'total':
                    continue
                valor = row[col_valor]
                if not isinstance(valor, (int, float)) or valor <= 0:
                    continue
                nome = str(nome).strip()
                existe = GastoPessoal.query.filter_by(
                    usuario_id=u.id, cartao_id=cartoes[cartao_nome].id, descricao=nome,
                    valor=float(valor), tipo=estado if estado != 'parcelado' else 'parcelado').first()
                if existe:
                    continue

                if estado == 'parcelado':
                    data_ref = row[col_data]
                    parcela_str = row[col_parcela] or ''
                    m = re.match(r'(\d+)\s*/\s*(\d+)', str(parcela_str))
                    if not (data_ref and m):
                        continue
                    parcela_atual, parcela_total = int(m.group(1)), int(m.group(2))
                    g = GastoPessoal(usuario_id=u.id, tipo='parcelado', cartao_id=cartoes[cartao_nome].id,
                                      descricao=nome, valor=float(valor), ativo=True,
                                      data_primeira_parcela=primeira_parcela(data_ref.date() if hasattr(data_ref, 'date') else data_ref, parcela_atual),
                                      parcela_total=parcela_total)
                elif estado in ('avista', 'recorrente'):
                    g = GastoPessoal(usuario_id=u.id, tipo=estado, cartao_id=cartoes[cartao_nome].id,
                                      descricao=nome, valor=float(valor), ativo=True,
                                      mes_referencia=date.today().strftime('%Y-%m') if estado == 'avista' else None)
                else:
                    continue
                db.session.add(g)
                count += 1

        db.session.commit()
        print(f'[OK] {count} lançamentos importados pra Gestão Pessoal (usuário: {u.nome}).')


if __name__ == '__main__':
    main()
