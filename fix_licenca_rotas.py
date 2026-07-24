# -*- coding: utf-8 -*-
"""
fix_licenca_rotas.py

Adiciona ao app.py do NeuraBusiness:
  - Import do modelo LicencaNeuraDesk
  - Decorator super_admin_required (só quem é super_admin gerencia licenças)
  - Rotas de administração: listar, criar, ver detalhe, bloquear, reativar,
    renovar (registrar pagamento manual)
  - Rotas de API (chamadas pelo NeuraDesk do cliente, sem sessão/login):
    /api/licencas/ativar e /api/licencas/verificar

Pré-requisito: rode fix_licenca_model.py antes deste (precisa da classe
LicencaNeuraDesk já existir em models.py).

Idempotente. Faz backup do app.py antes de alterar.
"""
import shutil
import datetime
import os

APP_PATH = "/opt/neurabusiness/app.py"


def main():
    with open(APP_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'def api_licenca_ativar' in content:
        print('Patch já aplicado. Nada a fazer.')
        return

    models_path = os.path.join(os.path.dirname(APP_PATH), 'models.py')
    if 'class LicencaNeuraDesk' not in open(models_path, encoding='utf-8').read():
        raise SystemExit(
            'ERRO: LicencaNeuraDesk não encontrado em models.py. '
            'Rode primeiro fix_licenca_model.py.'
        )

    backup_path = APP_PATH + f'.bak_{datetime.datetime.now():%Y%m%d_%H%M%S}'
    shutil.copy2(APP_PATH, backup_path)
    print(f'Backup criado em: {backup_path}')

    # --- 1) Import ---
    OLD_IMPORT = '''from models import (db, Empresa, Usuario, UsuarioEmpresa, Produto, Servico,
                    CatalogoServico, MaterialInfra, Cliente, Proposta,
                    ItemProposta, OrdemServico, ProjetoAnexo, Contrato, OsAssinatura)'''
    NEW_IMPORT = '''from models import (db, Empresa, Usuario, UsuarioEmpresa, Produto, Servico,
                    CatalogoServico, MaterialInfra, Cliente, Proposta,
                    ItemProposta, OrdemServico, ProjetoAnexo, Contrato, OsAssinatura,
                    LicencaNeuraDesk)'''
    if content.count(OLD_IMPORT) != 1:
        raise SystemExit('ERRO: âncora do import não encontrada ou duplicada.')
    content = content.replace(OLD_IMPORT, NEW_IMPORT, 1)
    print('1/4 - Import do LicencaNeuraDesk adicionado.')

    # --- 2) Decorator super_admin_required ---
    OLD_DEC = '''def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        u = get_current_user()
        if not u or (not u.is_admin and not u.is_super_admin):
            flash('Acesso negado.','danger')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return dec'''
    NEW_DEC = '''def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        u = get_current_user()
        if not u or (not u.is_admin and not u.is_super_admin):
            flash('Acesso negado.','danger')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return dec

def super_admin_required(f):
    """Só o super_admin (você, dono do NeuraBusiness) pode gerenciar
    licenças do NeuraDesk vendidas para outras empresas."""
    @wraps(f)
    def dec(*a, **kw):
        u = get_current_user()
        if not u or not u.is_super_admin:
            flash('Acesso restrito ao administrador do sistema.','danger')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return dec'''
    if content.count(OLD_DEC) != 1:
        raise SystemExit('ERRO: âncora do decorator admin_required não encontrada ou duplicada.')
    content = content.replace(OLD_DEC, NEW_DEC, 1)
    print('2/4 - Decorator super_admin_required adicionado.')

    # --- 3) Rotas ---
    ANCORA = "# ─── INICIALIZAÇÃO ─────────────────────────────────────────────────────────────\nif __name__ == '__main__':"
    if content.count(ANCORA) != 1:
        raise SystemExit('ERRO: âncora de inicialização não encontrada ou duplicada.')

    ROTAS_LICENCA = '''# ─── LICENÇAS NEURADESK (produto vendido para outras empresas) ────────────────

@app.route('/admin/licencas')
@login_required
@super_admin_required
def listar_licencas_neuradesk():
    licencas = LicencaNeuraDesk.query.order_by(LicencaNeuraDesk.criado_em.desc()).all()
    hoje = datetime.now()
    dias_carencia = 10
    for lic in licencas:
        if lic.status in ('bloqueada', 'cancelada'):
            lic.situacao_calc = lic.status
        elif not lic.data_vencimento:
            lic.situacao_calc = 'pendente'
        elif hoje <= lic.data_vencimento:
            lic.situacao_calc = 'ativa'
        elif lic.data_vencimento < hoje <= lic.data_vencimento + timedelta(days=dias_carencia):
            lic.situacao_calc = 'carencia'
        else:
            lic.situacao_calc = 'bloqueada'
    return render_template('licencas_neuradesk.html', licencas=licencas)


@app.route('/admin/licencas/nova', methods=['GET', 'POST'])
@login_required
@super_admin_required
def nova_licenca_neuradesk():
    if request.method == 'POST':
        chave = LicencaNeuraDesk.gerar_chave()
        while LicencaNeuraDesk.query.filter_by(chave=chave).first():
            chave = LicencaNeuraDesk.gerar_chave()

        lic = LicencaNeuraDesk(
            chave=chave,
            empresa_nome=request.form['empresa_nome'],
            empresa_cnpj=request.form.get('empresa_cnpj'),
            max_usuarios=int(request.form.get('max_usuarios', 5) or 5),
            valor_mensal=float(request.form.get('valor_mensal', 0) or 0),
            status='pendente',
            observacoes=request.form.get('observacoes'),
        )
        empresa_id_nb = request.form.get('empresa_id_nb')
        if empresa_id_nb:
            lic.empresa_id_nb = int(empresa_id_nb)

        db.session.add(lic)
        db.session.commit()
        flash(f'Licença gerada com sucesso: {chave}', 'success')
        return redirect(url_for('detalhe_licenca_neuradesk', id=lic.id))

    empresas = Empresa.query.filter_by(ativa=True).order_by(Empresa.fantasia).all()
    return render_template('form_licenca_neuradesk.html', empresas=empresas)


@app.route('/admin/licencas/<int:id>')
@login_required
@super_admin_required
def detalhe_licenca_neuradesk(id):
    lic = LicencaNeuraDesk.query.get_or_404(id)
    return render_template('detalhe_licenca_neuradesk.html', lic=lic)


@app.route('/admin/licencas/<int:id>/bloquear', methods=['POST'])
@login_required
@super_admin_required
def bloquear_licenca_neuradesk(id):
    lic = LicencaNeuraDesk.query.get_or_404(id)
    lic.status = 'bloqueada'
    db.session.commit()
    flash('Licença bloqueada manualmente.', 'warning')
    return redirect(url_for('detalhe_licenca_neuradesk', id=id))


@app.route('/admin/licencas/<int:id>/reativar', methods=['POST'])
@login_required
@super_admin_required
def reativar_licenca_neuradesk(id):
    lic = LicencaNeuraDesk.query.get_or_404(id)
    lic.status = 'ativa'
    db.session.commit()
    flash('Licença reativada.', 'success')
    return redirect(url_for('detalhe_licenca_neuradesk', id=id))


@app.route('/admin/licencas/<int:id>/renovar', methods=['POST'])
@login_required
@super_admin_required
def renovar_licenca_neuradesk(id):
    """Marca o pagamento do mês como confirmado manualmente (uso enquanto
    a integração automática com o Mercado Pago não está pronta)."""
    lic = LicencaNeuraDesk.query.get_or_404(id)
    base = lic.data_vencimento if (lic.data_vencimento and lic.data_vencimento > datetime.now()) else datetime.now()
    lic.data_ultimo_pagamento = datetime.now()
    lic.data_vencimento = base + timedelta(days=30)
    if lic.status not in ('bloqueada', 'cancelada'):
        lic.status = 'ativa'
    db.session.commit()
    flash(f'Renovação registrada. Novo vencimento: {lic.data_vencimento.strftime("%d/%m/%Y")}', 'success')
    return redirect(url_for('detalhe_licenca_neuradesk', id=id))


@app.route('/api/licencas/ativar', methods=['POST'])
def api_licenca_ativar():
    """Chamado pelo NeuraDesk do cliente na primeira ativação. Trava a
    licença no fingerprint desse servidor — se a mesma chave tentar
    ativar em outro servidor depois, a ativação é recusada."""
    dados = request.get_json(silent=True) or {}
    chave = (dados.get('chave') or '').strip().upper()
    fingerprint = (dados.get('fingerprint') or '').strip()

    if not chave or not fingerprint:
        return jsonify({'ok': False, 'erro': 'chave e fingerprint são obrigatórios'}), 400

    lic = LicencaNeuraDesk.query.filter_by(chave=chave).first()
    if not lic:
        return jsonify({'ok': False, 'erro': 'chave inválida'}), 404

    if lic.status == 'cancelada':
        return jsonify({'ok': False, 'erro': 'licença cancelada'}), 403

    if lic.fingerprint_servidor:
        if lic.fingerprint_servidor != fingerprint:
            return jsonify({'ok': False, 'erro': 'licença já ativada em outro servidor'}), 403
    else:
        lic.fingerprint_servidor = fingerprint
        lic.ativada_em = datetime.now()
        if lic.status == 'pendente':
            lic.status = 'ativa'
        if not lic.data_vencimento:
            lic.data_vencimento = datetime.now() + timedelta(days=30)

    lic.ultima_verificacao = datetime.now()
    lic.ultimo_ip_verificacao = request.remote_addr
    db.session.commit()

    return jsonify({
        'ok': True,
        'empresa_nome': lic.empresa_nome,
        'max_usuarios': lic.max_usuarios,
        'status': lic.status,
        'data_vencimento': lic.data_vencimento.isoformat() if lic.data_vencimento else None,
    })


@app.route('/api/licencas/verificar', methods=['POST'])
def api_licenca_verificar():
    """Chamado uma vez por dia pelo NeuraDesk do cliente pra confirmar
    que a licença continua válida (e por quanto tempo, se estiver em
    carência)."""
    dados = request.get_json(silent=True) or {}
    chave = (dados.get('chave') or '').strip().upper()
    fingerprint = (dados.get('fingerprint') or '').strip()

    lic = LicencaNeuraDesk.query.filter_by(chave=chave).first()
    if not lic:
        return jsonify({'ok': False, 'erro': 'chave inválida'}), 404

    if lic.fingerprint_servidor and lic.fingerprint_servidor != fingerprint:
        return jsonify({'ok': False, 'erro': 'fingerprint não confere'}), 403

    lic.ultima_verificacao = datetime.now()
    lic.ultimo_ip_verificacao = request.remote_addr
    db.session.commit()

    hoje = datetime.now()
    dias_carencia = 10
    em_dia = bool(lic.data_vencimento and hoje <= lic.data_vencimento)
    em_carencia = bool(lic.data_vencimento and
                       lic.data_vencimento < hoje <= lic.data_vencimento + timedelta(days=dias_carencia))

    if lic.status in ('bloqueada', 'cancelada'):
        situacao = lic.status
    elif em_dia:
        situacao = 'ativa'
    elif em_carencia:
        situacao = 'carencia'
    else:
        situacao = 'bloqueada'

    dias_restantes_carencia = None
    if em_carencia:
        dias_restantes_carencia = (lic.data_vencimento + timedelta(days=dias_carencia) - hoje).days

    return jsonify({
        'ok': True,
        'situacao': situacao,
        'max_usuarios': lic.max_usuarios,
        'data_vencimento': lic.data_vencimento.isoformat() if lic.data_vencimento else None,
        'dias_restantes_carencia': dias_restantes_carencia,
    })


'''
    content = content.replace(ANCORA, ROTAS_LICENCA + ANCORA, 1)
    print('3/4 - Rotas de administração e API adicionadas.')

    with open(APP_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    print('4/4 - app.py salvo.')
    print('\napp.py atualizado com sucesso.')
    print('Agora copie os templates e rode fix_menu_licenca.py.')


if __name__ == '__main__':
    main()
