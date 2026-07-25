"""NeuraBusiness v3.0 — Sistema Comercial Multi-empresa (SQLAlchemy)"""
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, jsonify, send_file, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, date, timedelta
from sqlalchemy import func, or_
import os, json, uuid, base64

from config import Config
import mp_integracao
from models import (db, Empresa, Usuario, UsuarioEmpresa, Produto, Servico,
                    CatalogoServico, MaterialInfra, Cliente, Proposta,
                    ItemProposta, OrdemServico, ProjetoAnexo, Contrato, OsAssinatura,
                    LicencaNeuraDesk, Integracao)

# ─── APP ───────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY']              = Config.SECRET_KEY
app.config['UPLOAD_FOLDER']           = Config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH']      = Config.MAX_CONTENT_LENGTH
app.config['SQLALCHEMY_DATABASE_URI'] = Config.get_db_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

ALLOWED_IMG    = {'png','jpg','jpeg','gif','webp'}
ALLOWED_ANEXOS = {'png','jpg','jpeg','pdf','gif','webp'}
EMPRESAS_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'empresas')
ANEXOS_FOLDER   = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'anexos')

# ─── FILTROS DE TEMPLATE ───────────────────────────────────────────────────────
@app.template_filter('data')
def fmt_data(value, fmt='%d/%m/%Y'):
    if not value: return '—'
    if hasattr(value, 'strftime'): return value.strftime(fmt)
    try:
        return datetime.fromisoformat(str(value)[:19]).strftime(fmt)
    except:
        return str(value)[:10]

# ─── HELPERS ───────────────────────────────────────────────────────────────────
def allowed_file(filename, exts=None):
    exts = exts or ALLOWED_IMG
    return '.' in filename and filename.rsplit('.',1)[1].lower() in exts

def save_upload(file_obj, pasta=None, exts=None):
    if not file_obj or not file_obj.filename: return None
    if not allowed_file(file_obj.filename, exts or ALLOWED_IMG): return None
    ext  = file_obj.filename.rsplit('.',1)[1].lower()
    nome = f"{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(app.config['UPLOAD_FOLDER'], pasta or '')
    os.makedirs(dest, exist_ok=True)
    file_obj.save(os.path.join(dest, nome))
    return nome

def logo_b64(empresa):
    if not empresa: return None
    logo = getattr(empresa, 'logo', None) or (empresa.get('logo') if isinstance(empresa, dict) else None)
    if not logo: return None
    path = os.path.join(EMPRESAS_FOLDER, logo)
    if not os.path.exists(path): return None
    with open(path,'rb') as f: data = f.read()
    ext = logo.rsplit('.',1)[-1]
    return f"data:image/{ext};base64,{base64.b64encode(data).decode()}"

def modelo_para_dict(obj):
    if obj is None: return None
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

# ─── AUTH ──────────────────────────────────────────────────────────────────────
def get_current_user():
    if 'user_id' not in session: return None
    return Usuario.query.filter_by(id=session['user_id'], ativo=True).first()

def get_empresa_atual():
    if 'empresa_id' not in session: return None
    return Empresa.query.filter_by(id=session['empresa_id'], ativa=True).first()

@app.context_processor
def inject_globals():
    return dict(
        current_user=get_current_user(),
        empresa_atual=get_empresa_atual(),
        logo_b64=logo_b64
    )

def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

def empresa_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'empresa_id' not in session:
            return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

def admin_required(f):
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
    return dec

def eid():
    return session.get('empresa_id')

# ─── SEED INICIAL ──────────────────────────────────────────────────────────────
def seed_inicial():
    from seed_servicos import seed_catalogo_sqla
    os.makedirs(EMPRESAS_FOLDER, exist_ok=True)

    logo_fname = None
    logo_src = os.path.join(os.path.dirname(__file__), 'static', 'img', 'logo_creative.png')
    if os.path.exists(logo_src):
        import shutil
        logo_fname = 'logo_creative.png'
        shutil.copy2(logo_src, os.path.join(EMPRESAS_FOLDER, logo_fname))

    emp = Empresa.query.filter_by(cnpj='45.127.220/0001-19').first()
    if not emp:
        emp = Empresa(
            razao_social='Arlindo Luiz da Silva Junior 10674100409',
            fantasia='CREATIVE', cnpj='45.127.220/0001-19',
            telefone='(83) 9 8816-1245',
            endereco='Rua Emidio Vidal de Negreiros, 711, Planalto 2',
            cidade='Mataraca', estado='PB', cep='58.292-000', logo=logo_fname)
        db.session.add(emp)
        db.session.commit()
        print(f"[OK] Empresa CREATIVE criada (id={emp.id})")

    # Seed catálogo completo
    from catalogo_creative import seed_catalogo_completo, CATALOGO
    from models import CatalogoServico
    # Re-seed se catálogo está vazio ou incompleto
    count = CatalogoServico.query.filter_by(empresa_id=emp.id).count()
    if count < len(CATALOGO):
        if count > 0:
            # Remove registros antigos sem as colunas novas
            CatalogoServico.query.filter_by(empresa_id=emp.id).delete()
            db.session.commit()
        inserted = seed_catalogo_completo(emp.id)
        print(f"[OK] Catalogo: {inserted} serviços inseridos")
    else:
        print(f"[OK] Catalogo completo ({count} serviços)")

    if not Usuario.query.filter_by(usuario='admin').first():
        adm = Usuario(
            nome='Administrador', usuario='admin',
            email='admin@neurabusiness.com',
            senha_hash=generate_password_hash('admin123'),
            is_admin=True, is_super_admin=True, empresa_id=emp.id)
        db.session.add(adm)
        db.session.commit()
        print("[OK] Admin criado — usuario: admin | senha: admin123")

# ─── LOGIN (2 etapas) ──────────────────────────────────────────────────────────
@app.route('/login')
def login():
    return render_template('login.html', step=1, usuario_pre='',
                           usuario_nome='', usuario_id=None, empresas=[])

@app.route('/login/step1', methods=['POST'])
def login_step1():
    usuario_str = request.form.get('usuario','').strip()
    senha       = request.form.get('senha','')
    u = Usuario.query.filter_by(usuario=usuario_str, ativo=True).first()
    if not u or not check_password_hash(u.senha_hash, senha):
        flash('Usuário ou senha incorretos.','danger')
        return render_template('login.html', step=1, usuario_pre=usuario_str,
                               usuario_nome='', usuario_id=None, empresas=[])
    if u.is_super_admin:
        empresas = Empresa.query.filter_by(ativa=True).order_by(Empresa.fantasia).all()
    elif u.empresa_id:
        ids_extra = [ue.empresa_id for ue in UsuarioEmpresa.query.filter_by(usuario_id=u.id).all()]
        ids = list(set([u.empresa_id] + ids_extra))
        empresas = Empresa.query.filter(Empresa.id.in_(ids), Empresa.ativa==True)\
            .order_by(Empresa.fantasia).all()
    else:
        empresas = Empresa.query.filter_by(ativa=True).order_by(Empresa.fantasia).all()
    if not empresas:
        flash('Sem acesso a nenhuma empresa.','warning')
        return render_template('login.html', step=1, usuario_pre=usuario_str,
                               usuario_nome='', usuario_id=None, empresas=[])
    if len(empresas) == 1:
        _do_login(u, empresas[0].id)
        return redirect(url_for('dashboard'))
    return render_template('login.html', step=2, usuario_pre=usuario_str,
                           usuario_nome=u.nome, usuario_id=u.id, empresas=empresas)

@app.route('/login/step2', methods=['POST'])
def login_step2():
    uid    = request.form.get('usuario_id','').strip()
    emp_id = request.form.get('empresa_id','').strip()
    if not uid or not emp_id:
        flash('Dados inválidos.','danger')
        return redirect(url_for('login'))
    u = Usuario.query.filter_by(id=int(uid), ativo=True).first()
    if not u:
        flash('Sessão expirada.','warning')
        return redirect(url_for('login'))
    _do_login(u, int(emp_id))
    return redirect(url_for('dashboard'))

def _do_login(u, empresa_id):
    session['user_id']    = u.id
    session['user_nome']  = u.nome
    session['empresa_id'] = empresa_id
    session['is_admin']   = u.is_admin or u.is_super_admin
    flash(f'Bem-vindo, {u.nome}!','success')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/trocar-empresa')
@login_required
def selecionar_empresa():
    session.pop('empresa_id', None)
    return redirect(url_for('login'))

# ─── DASHBOARD ─────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
@empresa_required
def dashboard():
    e = eid()
    receita = db.session.query(
        func.sum(ItemProposta.quantidade * ItemProposta.preco_unitario)
    ).join(Proposta).filter(
        Proposta.empresa_id==e, Proposta.status=='aprovada'
    ).scalar() or 0

    stats = {
        'total_produtos':      Produto.query.filter_by(empresa_id=e, ativo=True).count(),
        'total_clientes':      Cliente.query.filter_by(empresa_id=e).count(),
        'total_propostas':     Proposta.query.filter_by(empresa_id=e).count(),
        'propostas_aprovadas': Proposta.query.filter_by(empresa_id=e, status='aprovada').count(),
        'propostas_enviadas':  Proposta.query.filter_by(empresa_id=e, status='enviada').count(),
        'os_abertas':          OrdemServico.query.filter_by(empresa_id=e, status='aberta').count(),
        'os_andamento':        OrdemServico.query.filter_by(empresa_id=e, status='em_andamento').count(),
        'receita_aprovada':    receita,
    }
    ult_prop = Proposta.query.filter_by(empresa_id=e)\
        .order_by(Proposta.criado_em.desc()).limit(5).all()
    ult_os = OrdemServico.query.filter_by(empresa_id=e)\
        .order_by(OrdemServico.criado_em.desc()).limit(5).all()
    return render_template('dashboard.html', **stats,
                           ultimas_propostas=ult_prop, ultimas_os=ult_os)

# ─── ADMIN: EMPRESAS ───────────────────────────────────────────────────────────
@app.route('/admin/empresas')
@login_required
@admin_required
def listar_empresas():
    emps = Empresa.query.order_by(Empresa.fantasia).all()
    return render_template('admin/empresas.html', empresas=emps)

@app.route('/admin/empresas/nova', methods=['GET','POST'])
@login_required
@admin_required
def nova_empresa():
    if request.method == 'POST':
        logo = save_upload(request.files.get('logo'), 'empresas')
        emp  = Empresa(
            razao_social=request.form.get('razao_social',''),
            fantasia=request.form.get('fantasia',''),
            cnpj=request.form.get('cnpj',''),
            telefone=request.form.get('telefone',''),
            email=request.form.get('email',''),
            endereco=request.form.get('endereco',''),
            cidade=request.form.get('cidade',''),
            estado=request.form.get('estado',''),
            cep=request.form.get('cep',''), logo=logo)
        db.session.add(emp)
        db.session.commit()
        flash('Empresa criada!','success')
        return redirect(url_for('listar_empresas'))
    return render_template('admin/form_empresa.html', empresa=None)

@app.route('/admin/empresas/<int:id>/editar', methods=['GET','POST'])
@login_required
@admin_required
def editar_empresa(id):
    emp = Empresa.query.get_or_404(id)
    if request.method == 'POST':
        emp.razao_social = request.form.get('razao_social','')
        emp.fantasia     = request.form.get('fantasia','')
        emp.cnpj         = request.form.get('cnpj','')
        emp.telefone     = request.form.get('telefone','')
        emp.email        = request.form.get('email','')
        emp.endereco     = request.form.get('endereco','')
        emp.cidade       = request.form.get('cidade','')
        emp.estado       = request.form.get('estado','')
        emp.cep          = request.form.get('cep','')
        novo_logo = save_upload(request.files.get('logo'), 'empresas')
        if novo_logo: emp.logo = novo_logo
        db.session.commit()
        flash('Empresa atualizada!','success')
        return redirect(url_for('listar_empresas'))
    return render_template('admin/form_empresa.html', empresa=emp)

# ─── ADMIN: USUÁRIOS ───────────────────────────────────────────────────────────
@app.route('/admin/usuarios')
@login_required
@admin_required
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    empresas = Empresa.query.filter_by(ativa=True).order_by(Empresa.fantasia).all()
    return render_template('admin/usuarios.html', usuarios=usuarios, empresas=empresas)

@app.route('/admin/usuarios/novo', methods=['GET','POST'])
@login_required
@admin_required
def novo_usuario():
    if request.method == 'POST':
        if Usuario.query.filter_by(usuario=request.form.get('usuario')).first():
            flash('Usuário já existe!','warning')
            return redirect(url_for('novo_usuario'))
        emp_id = request.form.get('empresa_id')
        u = Usuario(
            nome=request.form.get('nome',''),
            usuario=request.form.get('usuario',''),
            email=request.form.get('email',''),
            senha_hash=generate_password_hash(request.form.get('senha','')),
            empresa_id=int(emp_id) if emp_id else None,
            is_admin=bool(request.form.get('is_admin')))
        db.session.add(u)
        db.session.commit()
        flash('Usuário criado!','success')
        return redirect(url_for('listar_usuarios'))
    empresas = Empresa.query.filter_by(ativa=True).order_by(Empresa.fantasia).all()
    return render_template('admin/form_usuario.html', usuario=None, empresas=empresas)

@app.route('/admin/usuarios/<int:id>/editar', methods=['GET','POST'])
@login_required
@admin_required
def editar_usuario(id):
    u = Usuario.query.get_or_404(id)
    if request.method == 'POST':
        u.nome       = request.form.get('nome','')
        u.email      = request.form.get('email','')
        emp_id       = request.form.get('empresa_id')
        u.empresa_id = int(emp_id) if emp_id else None
        u.is_admin   = bool(request.form.get('is_admin'))
        nova_senha   = request.form.get('senha','')
        if nova_senha: u.senha_hash = generate_password_hash(nova_senha)
        db.session.commit()
        flash('Usuário atualizado!','success')
        return redirect(url_for('listar_usuarios'))
    empresas = Empresa.query.filter_by(ativa=True).order_by(Empresa.fantasia).all()
    return render_template('admin/form_usuario.html', usuario=u, empresas=empresas)

# ─── PRODUTOS ──────────────────────────────────────────────────────────────────
@app.route('/produtos')
@login_required
@empresa_required
def listar_produtos():
    q   = request.args.get('q','')
    cat = request.args.get('categoria','')
    qry = Produto.query.filter_by(empresa_id=eid(), ativo=True)
    if q:   qry = qry.filter(Produto.nome.ilike(f'%{q}%'))
    if cat: qry = qry.filter_by(categoria=cat)
    produtos = qry.order_by(Produto.nome).all()
    for p in produtos:
        p.margem = ((p.preco_venda - p.preco_custo) / p.preco_custo * 100) if p.preco_custo > 0 else 0
    categorias = [c[0] for c in db.session.query(Produto.categoria).filter(
        Produto.empresa_id==eid(), Produto.ativo==True,
        Produto.categoria.isnot(None), Produto.categoria!='').distinct().all()]
    return render_template('produtos.html', produtos=produtos,
                           categorias=categorias, q=q, cat=cat)

@app.route('/produtos/novo', methods=['GET','POST'])
@login_required
@empresa_required
def novo_produto():
    if request.method == 'POST':
        nome = request.form.get('nome','').strip()
        specs = json.dumps({k:v for k,v in zip(
            request.form.getlist('spec_key[]'),
            request.form.getlist('spec_val[]')) if k.strip()})
        foto  = save_upload(request.files.get('foto'))
        custo = float(request.form.get('preco_custo') or 0)
        mkp   = float(request.form.get('markup_padrao') or 0)
        venda = custo*(1+mkp/100) if mkp else float(request.form.get('preco_venda') or 0)
        slug  = f"{nome.lower().replace(' ','-')[:50]}-{uuid.uuid4().hex[:6]}"
        p = Produto(empresa_id=eid(), nome=nome,
            descricao=request.form.get('descricao',''),
            especificacoes=specs, preco_custo=custo,
            preco_venda=venda, markup_padrao=mkp,
            estoque=int(request.form.get('estoque') or 0),
            categoria=request.form.get('categoria',''),
            tipo=request.form.get('tipo','produto'),
            foto=foto, slug=slug)
        db.session.add(p)
        db.session.commit()
        flash(f'Produto "{nome}" criado!','success')
        return redirect(url_for('listar_produtos'))
    return render_template('form_produto.html', produto=None)

@app.route('/produtos/<int:id>/editar', methods=['GET','POST'])
@login_required
@empresa_required
def editar_produto(id):
    p = Produto.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if request.method == 'POST':
        p.nome      = request.form.get('nome','')
        p.descricao = request.form.get('descricao','')
        p.especificacoes = json.dumps({k:v for k,v in zip(
            request.form.getlist('spec_key[]'),
            request.form.getlist('spec_val[]')) if k.strip()})
        p.preco_custo   = float(request.form.get('preco_custo') or 0)
        p.markup_padrao = float(request.form.get('markup_padrao') or 0)
        p.preco_venda   = p.preco_custo*(1+p.markup_padrao/100) if p.markup_padrao else float(request.form.get('preco_venda') or 0)
        p.estoque       = int(request.form.get('estoque') or 0)
        p.categoria     = request.form.get('categoria','')
        p.tipo          = request.form.get('tipo','produto')
        novo_foto = save_upload(request.files.get('foto'))
        if novo_foto: p.foto = novo_foto
        db.session.commit()
        flash('Produto atualizado!','success')
        return redirect(url_for('listar_produtos'))
    try: p.especificacoes_dict = json.loads(p.especificacoes or '{}')
    except: p.especificacoes_dict = {}
    return render_template('form_produto.html', produto=p)

@app.route('/produtos/<int:id>/excluir', methods=['POST'])
@login_required
@empresa_required
def excluir_produto(id):
    p = Produto.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    p.ativo = False
    db.session.commit()
    flash('Produto removido.','success')
    return redirect(url_for('listar_produtos'))

@app.route('/produtos/<int:id>/gerar-link', methods=['POST'])
@login_required
@empresa_required
def gerar_link_produto(id):
    p = Produto.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    dias = int(request.form.get('validade_dias', 7))
    p.token_link     = uuid.uuid4().hex
    p.link_expira_em = datetime.now() + timedelta(days=dias)
    db.session.commit()
    flash(f'Link gerado! Válido por {dias} dias.','success')
    return redirect(url_for('editar_produto', id=id))

@app.route('/p/<token>')
def produto_publico(token):
    p = Produto.query.filter_by(token_link=token, ativo=True).first_or_404()
    if p.link_expira_em and p.link_expira_em < datetime.now():
        return render_template('link_expirado.html'), 410
    try: p.especificacoes_dict = json.loads(p.especificacoes or '{}')
    except: p.especificacoes_dict = {}
    emp = Empresa.query.get(p.empresa_id)
    try: p.especificacoes_dict = json.loads(p.especificacoes or '{}')
    except: p.especificacoes_dict = {}
    return render_template('produto_publico.html', produto=p,
                           empresa=emp, logo_b64=logo_b64)

@app.route('/api/produtos')
@login_required
@empresa_required
def api_produtos():
    rows = Produto.query.filter_by(empresa_id=eid(), ativo=True).order_by(Produto.nome).all()
    result = []
    for p in rows:
        try: specs = json.loads(p.especificacoes or '{}')
        except: specs = {}
        result.append({'id':p.id,'nome':p.nome,'preco_venda':p.preco_venda,
                       'preco_custo':p.preco_custo,'markup_padrao':p.markup_padrao,
                       'estoque':p.estoque,'categoria':p.categoria,'tipo':p.tipo,
                       'foto':p.foto,'especificacoes_dict':specs})
    return jsonify(result)

# ─── SERVIÇOS ──────────────────────────────────────────────────────────────────
@app.route('/servicos')
@login_required
@empresa_required
def listar_servicos():
    servs = Servico.query.filter_by(empresa_id=eid(), ativo=True).order_by(Servico.nome).all()
    return render_template('servicos.html', servicos=servs)

@app.route('/servicos/novo', methods=['GET','POST'])
@login_required
@empresa_required
def novo_servico():
    if request.method == 'POST':
        s = Servico(empresa_id=eid(),
            nome=request.form.get('nome',''),
            descricao=request.form.get('descricao',''),
            preco_unitario=float(request.form.get('preco_unitario') or 0),
            unidade=request.form.get('unidade','un'))
        db.session.add(s)
        db.session.commit()
        flash('Serviço criado!','success')
        return redirect(url_for('listar_servicos'))
    return render_template('form_servico.html', servico=None)

@app.route('/servicos/<int:id>/editar', methods=['GET','POST'])
@login_required
@empresa_required
def editar_servico(id):
    s = Servico.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if request.method == 'POST':
        s.nome           = request.form.get('nome','')
        s.descricao      = request.form.get('descricao','')
        s.preco_unitario = float(request.form.get('preco_unitario') or 0)
        s.unidade        = request.form.get('unidade','un')
        db.session.commit()
        flash('Serviço atualizado!','success')
        return redirect(url_for('listar_servicos'))
    return render_template('form_servico.html', servico=s)

@app.route('/api/servicos')
@login_required
@empresa_required
def api_servicos():
    servs = Servico.query.filter_by(empresa_id=eid(), ativo=True).order_by(Servico.nome).all()
    return jsonify([{'id':s.id,'nome':s.nome,'preco_unitario':s.preco_unitario,
                     'unidade':s.unidade,'descricao':s.descricao} for s in servs])

# ─── CLIENTES ──────────────────────────────────────────────────────────────────
@app.route('/clientes')
@login_required
@empresa_required
def listar_clientes():
    q = request.args.get('q','')
    qry = Cliente.query.filter_by(empresa_id=eid())
    if q: qry = qry.filter(or_(Cliente.nome.ilike(f'%{q}%'),
                                Cliente.telefone.ilike(f'%{q}%')))
    clientes = qry.order_by(Cliente.nome).all()
    return render_template('clientes.html', clientes=clientes, q=q)

@app.route('/clientes/novo', methods=['GET','POST'])
@login_required
@empresa_required
def novo_cliente():
    if request.method == 'POST':
        c = Cliente(empresa_id=eid(),
            nome=request.form.get('nome',''),
            email=request.form.get('email',''),
            telefone=request.form.get('telefone',''),
            cpf_cnpj=request.form.get('cpf_cnpj',''),
            endereco=request.form.get('endereco',''),
            cidade=request.form.get('cidade',''),
            estado=request.form.get('estado',''),
            cep=request.form.get('cep',''),
            observacoes=request.form.get('observacoes',''))
        db.session.add(c)
        db.session.commit()
        flash('Cliente criado!','success')
        return redirect(url_for('listar_clientes'))
    return render_template('form_cliente.html', cliente=None)

@app.route('/clientes/<int:id>/editar', methods=['GET','POST'])
@login_required
@empresa_required
def editar_cliente(id):
    c = Cliente.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if request.method == 'POST':
        c.nome=request.form.get('nome','')
        c.email=request.form.get('email','')
        c.telefone=request.form.get('telefone','')
        c.cpf_cnpj=request.form.get('cpf_cnpj','')
        c.endereco=request.form.get('endereco','')
        c.cidade=request.form.get('cidade','')
        c.estado=request.form.get('estado','')
        c.cep=request.form.get('cep','')
        c.observacoes=request.form.get('observacoes','')
        db.session.commit()
        flash('Cliente atualizado!','success')
        return redirect(url_for('listar_clientes'))
    ult = Proposta.query.filter_by(cliente_id=id)\
        .order_by(Proposta.criado_em.desc()).limit(5).all()
    return render_template('form_cliente.html', cliente=c, ultimas_propostas=ult)

# ─── PROPOSTAS ─────────────────────────────────────────────────────────────────
@app.route('/propostas')
@login_required
@empresa_required
def listar_propostas():
    status = request.args.get('status','')
    qry = Proposta.query.filter_by(empresa_id=eid())
    if status: qry = qry.filter_by(status=status)
    propostas = qry.order_by(Proposta.criado_em.desc()).all()
    return render_template('propostas.html', propostas=propostas, status=status)

@app.route('/propostas/nova', methods=['GET','POST'])
@login_required
@empresa_required
def nova_proposta():
    if request.method == 'POST':
        count  = Proposta.query.filter_by(empresa_id=eid()).count()
        numero = f"NB-{datetime.now().strftime('%Y%m')}-{count+1:04d}"
        token  = uuid.uuid4().hex
        expira = datetime.now() + timedelta(days=int(request.form.get('validade',15)))
        p = Proposta(
            empresa_id=eid(), numero=numero,
            titulo=request.form.get('titulo',''),
            cliente_id=int(request.form.get('cliente_id')),
            validade=int(request.form.get('validade',15)),
            forma_pagamento=request.form.get('forma_pagamento',''),
            observacoes=request.form.get('observacoes',''),
            condicoes=request.form.get('condicoes',''),
            custo_locomocao=float(request.form.get('custo_locomocao') or 0),
            custo_alimentacao=float(request.form.get('custo_alimentacao') or 0),
            custo_outros=float(request.form.get('custo_outros') or 0),
            descricao_custos=request.form.get('descricao_custos',''),
            analise_ambiente=request.form.get('analise_ambiente',''),
            cronograma=request.form.get('cronograma',''),
            token_publico=token, token_expira_em=expira,
            template_estilo=request.form.get('template_estilo','tech'),
            usuario_id=session.get('user_id'))
        db.session.add(p)
        db.session.flush()
        descs     = request.form.getlist('item_desc[]')
        qtds      = request.form.getlist('item_qtd[]')
        precos    = request.form.getlist('item_preco[]')
        tipos     = request.form.getlist('item_tipo[]')
        det_descs = request.form.getlist('item_desc_detalhada[]')
        for i, desc in enumerate(descs):
            if desc.strip():
                db.session.add(ItemProposta(
                    proposta_id=p.id, descricao=desc,
                    quantidade=float(qtds[i] if i < len(qtds) else 1) or 1,
                    preco_unitario=float(precos[i] if i < len(precos) else 0) or 0,
                    tipo=tipos[i] if i < len(tipos) else 'servico',
                    descricao_detalhada=det_descs[i] if i < len(det_descs) else ''))
        # Salva etapas
        from models import EtapaProposta
        for etapa in EtapaProposta.query.filter_by(proposta_id=p.id).all():
            db.session.delete(etapa)
        db.session.flush()
        for ordem, (titulo, dias, desc_e) in enumerate(zip(
            request.form.getlist('etapa_titulo[]'),
            request.form.getlist('etapa_dias[]'),
            request.form.getlist('etapa_desc[]')), 1):
            if titulo.strip():
                db.session.add(EtapaProposta(proposta_id=p.id, ordem=ordem,
                    titulo=titulo, duracao_dias=int(dias or 1),
                    descricao=desc_e))
        db.session.commit()
        flash(f'Proposta {numero} criada!','success')
        return redirect(url_for('ver_proposta', id=p.id))
    clientes  = Cliente.query.filter_by(empresa_id=eid()).order_by(Cliente.nome).all()
    produtos  = Produto.query.filter_by(empresa_id=eid(), ativo=True).order_by(Produto.nome).all()
    servicos  = Servico.query.filter_by(empresa_id=eid(), ativo=True).order_by(Servico.nome).all()
    catalogo  = CatalogoServico.query.filter_by(empresa_id=eid(), ativo=True).order_by(CatalogoServico.categoria, CatalogoServico.nome).all()
    cats_cat  = sorted(set(s.categoria for s in catalogo))
    return render_template('form_proposta.html', proposta=None,
                           clientes=clientes, produtos=produtos,
                           servicos=servicos,
                           catalogo=catalogo, categorias_catalogo=cats_cat)

@app.route('/propostas/<int:id>')
@login_required
@empresa_required
def ver_proposta(id):
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    # Garante que o token existe e está válido
    if not p.token_publico:
        p.token_publico   = uuid.uuid4().hex
        p.token_expira_em = datetime.now() + timedelta(days=p.validade or 15)
        db.session.commit()
    elif not p.token_expira_em or p.token_expira_em < datetime.now():
        p.token_expira_em = datetime.now() + timedelta(days=p.validade or 15)
        db.session.commit()
    total_itens = sum(i.quantidade * i.preco_unitario for i in p.itens)
    custo_extra = (p.custo_locomocao or 0)+(p.custo_alimentacao or 0)+(p.custo_outros or 0)
    contrato = Contrato.query.filter_by(proposta_id=id).first()
    from flask import request as req
    host = req.host_url.rstrip('/')
    link_publico    = f"{host}/proposta/view/{p.token_publico}"
    link_premium    = f"{host}/proposta/premium/{p.token_publico}"
    return render_template('ver_proposta.html', proposta=p,
                           total=total_itens+custo_extra,
                           total_itens=total_itens,
                           itens=p.itens,
                           anexos=p.anexos, contrato=contrato,
                           link_publico=link_publico,
                           link_premium=link_premium)
@app.route('/propostas/<int:id>/editar', methods=['GET','POST'])
@login_required
@empresa_required
def editar_proposta(id):
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if request.method == 'POST':
        p.titulo            = request.form.get('titulo','')
        p.cliente_id        = int(request.form.get('cliente_id'))
        p.validade          = int(request.form.get('validade',15))
        p.forma_pagamento   = request.form.get('forma_pagamento','')
        p.observacoes       = request.form.get('observacoes','')
        p.condicoes         = request.form.get('condicoes','')
        p.custo_locomocao   = float(request.form.get('custo_locomocao') or 0)
        p.custo_alimentacao = float(request.form.get('custo_alimentacao') or 0)
        p.custo_outros      = float(request.form.get('custo_outros') or 0)
        p.descricao_custos  = request.form.get('descricao_custos','')
        p.analise_ambiente  = request.form.get('analise_ambiente','')
        p.cronograma        = request.form.get('cronograma','')
        p.template_estilo   = request.form.get('template_estilo','tech')
        # Recalcula token se não tiver
        if not p.token_publico:
            p.token_publico  = uuid.uuid4().hex
            p.token_expira_em = datetime.now() + timedelta(days=p.validade)
        else:
            # Renova expiração
            p.token_expira_em = datetime.now() + timedelta(days=p.validade)
        # Remove itens antigos e recria
        for item in p.itens:
            db.session.delete(item)
        db.session.flush()
        descs     = request.form.getlist('item_desc[]')
        qtds      = request.form.getlist('item_qtd[]')
        precos    = request.form.getlist('item_preco[]')
        tipos     = request.form.getlist('item_tipo[]')
        det_descs = request.form.getlist('item_desc_detalhada[]')
        for i, desc in enumerate(descs):
            if desc.strip():
                db.session.add(ItemProposta(
                    proposta_id=p.id, descricao=desc,
                    quantidade=float(qtds[i] if i < len(qtds) else 1) or 1,
                    preco_unitario=float(precos[i] if i < len(precos) else 0) or 0,
                    tipo=tipos[i] if i < len(tipos) else 'servico',
                    descricao_detalhada=det_descs[i] if i < len(det_descs) else ''))
        # Salva etapas
        from models import EtapaProposta
        for etapa in EtapaProposta.query.filter_by(proposta_id=p.id).all():
            db.session.delete(etapa)
        db.session.flush()
        for ordem, (titulo, dias, desc_e) in enumerate(zip(
            request.form.getlist('etapa_titulo[]'),
            request.form.getlist('etapa_dias[]'),
            request.form.getlist('etapa_desc[]')), 1):
            if titulo.strip():
                db.session.add(EtapaProposta(proposta_id=p.id, ordem=ordem,
                    titulo=titulo, duracao_dias=int(dias or 1),
                    descricao=desc_e))
        db.session.commit()
        flash('Proposta atualizada!','success')
        return redirect(url_for('ver_proposta', id=p.id))
    clientes  = Cliente.query.filter_by(empresa_id=eid()).order_by(Cliente.nome).all()
    produtos  = Produto.query.filter_by(empresa_id=eid(), ativo=True).order_by(Produto.nome).all()
    servicos  = Servico.query.filter_by(empresa_id=eid(), ativo=True).order_by(Servico.nome).all()
    catalogo  = CatalogoServico.query.filter_by(empresa_id=eid(), ativo=True).order_by(CatalogoServico.categoria, CatalogoServico.nome).all()
    cats_cat  = sorted(set(s.categoria for s in catalogo))
    return render_template('form_proposta.html', proposta=p,
                           clientes=clientes, produtos=produtos,
                           servicos=servicos,
                           catalogo=catalogo, categorias_catalogo=cats_cat)




@app.route('/propostas/<int:id>/excluir', methods=['POST'])
@login_required
@empresa_required
def excluir_proposta(id):
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    # Remove itens, etapas, anexos e contrato relacionados
    for item in p.itens:       db.session.delete(item)
    for etapa in p.etapas:     db.session.delete(etapa)
    for anx in p.anexos_projeto: db.session.delete(anx)
    if p.contrato:             db.session.delete(p.contrato)
    db.session.delete(p)
    db.session.commit()
    flash('Proposta excluída.', 'success')
    return redirect(url_for('listar_propostas'))

@app.route('/propostas/<int:id>/status/<novo_status>', methods=['POST'])
@login_required
@empresa_required
def mudar_status_proposta(id, novo_status):
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    p.status = novo_status
    if novo_status == 'aprovada': p.aprovado_em = datetime.now()
    if novo_status == 'enviada':  p.enviado_em  = datetime.now()
    db.session.commit()
    flash(f'Status alterado para {novo_status}.','success')
    return redirect(url_for('ver_proposta', id=id))

@app.route('/propostas/<int:id>/pdf')
@login_required
@empresa_required
def proposta_pdf(id):
    from pdf_generator import gerar_proposta_pdf
    p   = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    emp = Empresa.query.get(eid())
    itens = [{'descricao':i.descricao,'quantidade':i.quantidade,
              'preco_unitario':i.preco_unitario,'tipo':i.tipo} for i in p.itens]
    etapas = [{'titulo':e.titulo,'descricao':e.descricao,'duracao_dias':e.duracao_dias}
              for e in sorted(p.etapas, key=lambda x: x.ordem)] if p.etapas else []
    buf = gerar_proposta_pdf(modelo_para_dict(p), modelo_para_dict(emp),
                             modelo_para_dict(p.cliente), itens, etapas=etapas)
    return send_file(buf, mimetype='application/pdf',
                     download_name=f"Proposta_{p.numero.replace('-','_')}.pdf")


@app.route('/propostas/<int:id>/pdf-inteligente')
@login_required
@empresa_required
def proposta_pdf_inteligente(id):
    from proposta_inteligente import gerar_proposta_inteligente
    p   = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    emp = Empresa.query.get(eid())
    itens = [{'descricao':i.descricao,'quantidade':i.quantidade,
              'preco_unitario':i.preco_unitario,'tipo':i.tipo,
              'descricao_detalhada': i.descricao_detalhada or '',
              'markup': i.markup or 0} for i in p.itens]
    p_dict   = modelo_para_dict(p)
    emp_dict = modelo_para_dict(emp)
    cli_dict = modelo_para_dict(p.cliente) if p.cliente else {}
    # Inclui dados de assinatura se existirem
    p_dict['assinatura_nome'] = p.assinatura_nome
    p_dict['assinatura_cpf']  = p.assinatura_cpf
    p_dict['assinatura_ip']   = p.assinatura_ip
    p_dict['assinatura_hash'] = p.assinatura_hash
    p_dict['aprovado_em']     = p.aprovado_em
    buf = gerar_proposta_inteligente(p_dict, emp_dict, cli_dict, itens)
    return send_file(buf, mimetype='application/pdf', as_attachment=False,
                     download_name=f"Proposta_{p.numero.replace('-','_')}.pdf")

@app.route('/proposta/view/<token>')
def proposta_publica(token):
    p = Proposta.query.filter_by(token_publico=token).first_or_404()
    # Token expirado só bloqueia se a proposta ainda não foi aprovada
    if p.token_expira_em and p.token_expira_em < datetime.now() and p.status not in ('aprovada',):
        return render_template('link_expirado.html'), 410
    emp = Empresa.query.get(p.empresa_id)
    total_itens = sum(i.quantidade * i.preco_unitario for i in p.itens)
    custo_extra = (p.custo_locomocao or 0)+(p.custo_alimentacao or 0)+(p.custo_outros or 0)
    return render_template('proposta_publica.html', proposta=p, empresa=emp,
                           itens=p.itens, total=total_itens+custo_extra,
                           total_itens=total_itens, logo_b64=logo_b64)

@app.route('/proposta/premium/<token>')
def proposta_premium_pub(token):
    p = Proposta.query.filter_by(token_publico=token).first_or_404()
    if p.token_expira_em and p.token_expira_em < datetime.now():
        return render_template('link_expirado.html'), 410
    emp = Empresa.query.get(p.empresa_id)
    total_itens = sum(i.quantidade * i.preco_unitario for i in p.itens)
    custo_extra = (p.custo_locomocao or 0)+(p.custo_alimentacao or 0)+(p.custo_outros or 0)
    return render_template('proposta_premium.html', proposta=p, empresa=emp,
                           itens=p.itens, total=total_itens+custo_extra,
                           total_itens=total_itens, anexos=p.anexos, logo_b64=logo_b64)

@app.route('/propostas/<int:id>/aprovar-publico/<token>', methods=['POST'])
def aprovar_proposta_publico(id, token):
    p = Proposta.query.filter_by(id=id, token_publico=token).first_or_404()
    nome = request.form.get('nome_assinatura','').strip()
    cpf  = request.form.get('cpf_assinatura','').strip()
    if not nome or not cpf:
        flash('Preencha seu nome completo e CPF para aprovar.','warning')
        return redirect(url_for('proposta_publica', token=token))
    import hashlib
    from contrato_generator import gerar_texto_contrato_html
    ip  = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr or '')
    ts  = datetime.now().isoformat()
    raw = f"{nome}|{cpf}|{ip}|{ts}|{p.numero}"
    h   = hashlib.sha256(raw.encode()).hexdigest()
    p.status          = 'aprovada'
    p.aprovado_em     = datetime.now()
    p.assinatura_nome = nome
    p.assinatura_cpf  = cpf
    p.assinatura_ip   = ip
    p.assinatura_hash = h
    db.session.commit()

    # Gera contrato automaticamente com assinatura do cliente ja registrada
    if not p.contrato:
        try:
            emp   = Empresa.query.get(p.empresa_id)
            itens = [{'descricao':i.descricao,'quantidade':i.quantidade,
                      'preco_unitario':i.preco_unitario,'tipo':i.tipo} for i in p.itens]
            count  = Contrato.query.filter_by(empresa_id=p.empresa_id).count()
            numero = f"CT-{datetime.now().strftime('%Y%m')}-{count+1:04d}"
            token_ct = uuid.uuid4().hex
            texto  = gerar_texto_contrato_html(modelo_para_dict(p),
                                               modelo_para_dict(emp),
                                               modelo_para_dict(p.cliente), itens)
            raw_ct = f"{nome}|{cpf}|{ip}|{ts}|{numero}"
            h_ct   = hashlib.sha256(raw_ct.encode()).hexdigest()
            ct = Contrato(
                empresa_id=p.empresa_id, proposta_id=p.id,
                numero=numero, cliente_id=p.cliente_id,
                token_assinatura=token_ct, texto_contrato=texto,
                status='assinado_cliente',
                assinado_em=datetime.now(),
                assinatura_nome=nome, assinatura_cpf=cpf,
                assinatura_ip=ip, assinatura_hash=h_ct)
            db.session.add(ct)
            db.session.commit()
        except Exception:
            pass

    flash('Proposta aprovada e assinada! Aguardando assinatura da empresa.','success')
    return redirect(url_for('proposta_publica', token=token))

# ─── ORDENS DE SERVIÇO ─────────────────────────────────────────────────────────
@app.route('/os')
@login_required
@empresa_required
def listar_os():
    status = request.args.get('status','')
    qry = OrdemServico.query.filter_by(empresa_id=eid())
    if status: qry = qry.filter_by(status=status)
    os_list = qry.order_by(OrdemServico.criado_em.desc()).all()
    return render_template('ordens_servico.html', ordens=os_list, status=status)

@app.route('/os/nova', methods=['GET','POST'])
@login_required
@empresa_required
def nova_os():
    if request.method == 'POST':
        count  = OrdemServico.query.filter_by(empresa_id=eid()).count()
        numero = f"OS-{datetime.now().strftime('%Y%m')}-{count+1:04d}"
        dp     = request.form.get('data_prevista')
        os_obj = OrdemServico(
            empresa_id=eid(), numero=numero,
            titulo=request.form.get('titulo',''),
            cliente_id=int(request.form.get('cliente_id')),
            proposta_id=int(request.form.get('proposta_id')) if request.form.get('proposta_id') else None,
            prioridade=request.form.get('prioridade','normal'),
            descricao=request.form.get('descricao',''),
            tecnico=request.form.get('tecnico',''),
            data_prevista=date.fromisoformat(dp) if dp else None,
            usuario_id=session.get('user_id'))
        db.session.add(os_obj)
        db.session.commit()
        flash(f'OS {numero} criada!','success')
        return redirect(url_for('ver_os', id=os_obj.id))
    clientes  = Cliente.query.filter_by(empresa_id=eid()).order_by(Cliente.nome).all()
    propostas = Proposta.query.filter_by(empresa_id=eid()).order_by(Proposta.numero.desc()).all()
    return render_template('form_os.html', os=None, clientes=clientes, propostas=propostas)

@app.route('/os/<int:id>')
@login_required
@empresa_required
def ver_os(id):
    os_obj = OrdemServico.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    link_ass = None
    if os_obj.assinatura and os_obj.assinatura.token:
        link_ass = f"{request.host_url.rstrip('/')}/os/assinar/{os_obj.assinatura.token}"
    return render_template('ver_os.html', os_obj=os_obj, link_assinatura=link_ass)

@app.route('/os/<int:id>/status/<novo_status>', methods=['POST'])
@login_required
@empresa_required
def mudar_status_os(id, novo_status):
    os_obj = OrdemServico.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    os_obj.status = novo_status
    if novo_status == 'concluida': os_obj.data_conclusao = date.today()
    db.session.commit()
    flash('Status da OS alterado.','success')
    return redirect(url_for('ver_os', id=id))


@app.route('/os/<int:id>/editar', methods=['GET','POST'])
@login_required
@empresa_required
def editar_os(id):
    os_obj = OrdemServico.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if request.method == 'POST':
        os_obj.titulo    = request.form.get('titulo','')
        os_obj.cliente_id= int(request.form.get('cliente_id'))
        pid = request.form.get('proposta_id')
        os_obj.proposta_id  = int(pid) if pid else None
        os_obj.prioridade   = request.form.get('prioridade','normal')
        os_obj.tecnico      = request.form.get('tecnico','')
        os_obj.descricao    = request.form.get('descricao','')
        os_obj.solucao      = request.form.get('solucao','')
        dp = request.form.get('data_prevista')
        os_obj.data_prevista= date.fromisoformat(dp) if dp else None
        db.session.commit()
        flash('OS atualizada!','success')
        return redirect(url_for('ver_os', id=id))
    clientes  = Cliente.query.filter_by(empresa_id=eid()).order_by(Cliente.nome).all()
    propostas = Proposta.query.filter_by(empresa_id=eid()).order_by(Proposta.numero.desc()).all()
    return render_template('form_os.html', os=os_obj,
                           clientes=clientes, propostas=propostas)


@app.route('/os/<int:id>/excluir', methods=['POST'])
@login_required
@empresa_required
def excluir_os(id):
    os_obj = OrdemServico.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if os_obj.assinatura:
        db.session.delete(os_obj.assinatura)
    db.session.delete(os_obj)
    db.session.commit()
    flash('OS excluída.','success')
    return redirect(url_for('listar_os'))

@app.route('/os/<int:id>/pdf')
@login_required
@empresa_required
def os_pdf(id):
    from pdf_generator import gerar_os_pdf
    os_obj = OrdemServico.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    emp    = Empresa.query.get(eid())
    os_d   = modelo_para_dict(os_obj)
    os_d['cliente_nome'] = os_obj.cliente.nome
    buf = gerar_os_pdf(os_d, modelo_para_dict(emp), modelo_para_dict(os_obj.cliente))
    return send_file(buf, mimetype='application/pdf',
                     download_name=f"OS_{os_obj.numero.replace('-','_')}.pdf")

# ─── CATÁLOGO DE SERVIÇOS ──────────────────────────────────────────────────────
@app.route('/catalogo')
@login_required
@empresa_required
def catalogo_servicos():
    cat = request.args.get('categoria','')
    qry = CatalogoServico.query.filter_by(empresa_id=eid(), ativo=True)
    if cat: qry = qry.filter_by(categoria=cat)
    servicos = qry.order_by(CatalogoServico.categoria, CatalogoServico.nome).all()
    cats = [c[0] for c in db.session.query(CatalogoServico.categoria).filter_by(
        empresa_id=eid(), ativo=True).distinct().order_by(CatalogoServico.categoria).all()]
    return render_template('catalogo.html', servicos=servicos, categorias=cats, cat_filtro=cat)

@app.route('/catalogo/<int:id>/editar', methods=['GET','POST'])
@login_required
@empresa_required
def editar_catalogo(id):
    s = CatalogoServico.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if request.method == 'POST':
        s.nome=request.form.get('nome','')
        s.descricao=request.form.get('descricao','')
        s.preco_base=float(request.form.get('preco_base') or 0)
        s.tempo_horas=float(request.form.get('tempo_horas') or 0)
        s.unidade=request.form.get('unidade','un')
        db.session.commit()
        flash('Serviço atualizado!','success')
        return redirect(url_for('catalogo_servicos'))
    return render_template('form_catalogo.html', servico=s)

@app.route('/api/catalogo')
@login_required
@empresa_required
def api_catalogo():
    cat = request.args.get('categoria','')
    qry = CatalogoServico.query.filter_by(empresa_id=eid(), ativo=True)
    if cat: qry = qry.filter_by(categoria=cat)
    servicos = qry.order_by(CatalogoServico.categoria, CatalogoServico.nome).all()
    return jsonify([{'id':s.id,'nome':s.nome,'categoria':s.categoria,
                     'preco_base':s.preco_base,'tempo_horas':s.tempo_horas,
                     'unidade':s.unidade,'descricao':s.descricao} for s in servicos])

# ─── MATERIAIS ─────────────────────────────────────────────────────────────────
@app.route('/materiais')
@login_required
@empresa_required
def listar_materiais():
    mats = MaterialInfra.query.filter_by(empresa_id=eid(), ativo=True)\
        .order_by(MaterialInfra.categoria, MaterialInfra.nome).all()
    return render_template('materiais.html', materiais=mats)

@app.route('/materiais/novo', methods=['GET','POST'])
@login_required
@empresa_required
def novo_material():
    if request.method == 'POST':
        m = MaterialInfra(empresa_id=eid(),
            nome=request.form.get('nome',''),
            unidade=request.form.get('unidade','m'),
            preco_unitario=float(request.form.get('preco_unitario') or 0),
            categoria=request.form.get('categoria',''))
        db.session.add(m)
        db.session.commit()
        flash('Material adicionado!','success')
        return redirect(url_for('listar_materiais'))
    return render_template('form_material.html', material=None)

@app.route('/materiais/<int:id>/editar', methods=['GET','POST'])
@login_required
@empresa_required
def editar_material(id):
    m = MaterialInfra.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if request.method == 'POST':
        m.nome=request.form.get('nome','')
        m.unidade=request.form.get('unidade','m')
        m.preco_unitario=float(request.form.get('preco_unitario') or 0)
        m.categoria=request.form.get('categoria','')
        db.session.commit()
        flash('Material atualizado!','success')
        return redirect(url_for('listar_materiais'))
    return render_template('form_material.html', material=m)

@app.route('/api/materiais')
@login_required
@empresa_required
def api_materiais():
    mats = MaterialInfra.query.filter_by(empresa_id=eid(), ativo=True)\
        .order_by(MaterialInfra.categoria, MaterialInfra.nome).all()
    return jsonify([{'id':m.id,'nome':m.nome,'unidade':m.unidade,
                     'preco_unitario':m.preco_unitario,'categoria':m.categoria} for m in mats])

# ─── CALCULADORAS ──────────────────────────────────────────────────────────────
@app.route('/calculadora')
@login_required
@empresa_required
def calculadora():
    return render_template('calculadora.html')

@app.route('/api/calc/mei', methods=['POST'])
@login_required
@empresa_required
def api_calc_mei():
    from precificacao import calcular_preco_mei
    d = request.get_json()
    return jsonify(calcular_preco_mei(
        preco_custo=float(d.get('preco_custo',0)),
        margem_desejada_pct=float(d.get('margem',30)),
        tipo=d.get('tipo','servico'),
        incluir_deslocamento=float(d.get('desloc',0)),
        horas_execucao=float(d.get('horas',0)),
        valor_hora=float(d.get('valor_hora',0))))

@app.route('/api/calc/desloc', methods=['POST'])
@login_required
@empresa_required
def api_calc_desloc():
    from precificacao import calcular_deslocamento
    d = request.get_json()
    return jsonify(calcular_deslocamento(
        distancia_km=float(d.get('km',0)),
        tipo_via=d.get('tipo_via','estrada'),
        refeicoes=int(d.get('refeicoes',0)),
        diaria=float(d.get('diaria',0)),
        pedagios=float(d.get('pedagios',0))))

@app.route('/api/calc/infra-rede', methods=['POST'])
@login_required
@empresa_required
def api_calc_infra_rede():
    from precificacao import calcular_infra_rede
    d = request.get_json()
    return jsonify(calcular_infra_rede(
        n_pontos=int(d.get('pontos',1)),
        tipo_cabo=d.get('cabo','cat6_cobre'),
        metros_por_ponto=int(d.get('metros_ponto',15)),
        incluir_tomadas=d.get('tomadas',True),
        incluir_patch_panel=d.get('patch_panel',True),
        dificuldade=d.get('dificuldade','normal')))

@app.route('/api/calc/infra-cftv', methods=['POST'])
@login_required
@empresa_required
def api_calc_infra_cftv():
    from precificacao import calcular_infra_cftv
    d = request.get_json()
    return jsonify(calcular_infra_cftv(
        n_cameras=int(d.get('cameras',1)),
        tipo_cabo=d.get('cabo','cftv_4vias'),
        metros_por_camera=int(d.get('metros_camera',20)),
        dificuldade=d.get('dificuldade','normal')))

@app.route('/api/calc/cerca', methods=['POST'])
@login_required
@empresa_required
def api_calc_cerca():
    from precificacao import calcular_cerca_eletrica
    d = request.get_json()
    return jsonify(calcular_cerca_eletrica(
        metros_cerca=float(d.get('metros',0)),
        dificuldade=d.get('dificuldade','normal')))

# ─── ANEXOS ────────────────────────────────────────────────────────────────────
@app.route('/propostas/<int:id>/anexos', methods=['POST'])
@login_required
@empresa_required
def upload_anexo(id):
    Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    f = request.files.get('arquivo')
    if not f or not f.filename:
        flash('Nenhum arquivo.','warning')
        return redirect(url_for('ver_proposta', id=id))
    ext = f.filename.rsplit('.',1)[-1].lower()
    if ext not in ALLOWED_ANEXOS:
        flash('Tipo não permitido.','danger')
        return redirect(url_for('ver_proposta', id=id))
    os.makedirs(ANEXOS_FOLDER, exist_ok=True)
    nome = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(ANEXOS_FOLDER, nome))
    anx = ProjetoAnexo(proposta_id=id, nome_original=f.filename,
                       nome_arquivo=nome,
                       tipo=request.form.get('tipo_anexo','outro'),
                       descricao=request.form.get('descricao',''))
    db.session.add(anx)
    db.session.commit()
    flash('Anexo adicionado!','success')
    return redirect(url_for('ver_proposta', id=id))

@app.route('/propostas/<int:id>/anexos/<int:aid>/excluir', methods=['POST'])
@login_required
@empresa_required
def excluir_anexo(id, aid):
    anx = ProjetoAnexo.query.filter_by(id=aid, proposta_id=id).first_or_404()
    try: os.remove(os.path.join(ANEXOS_FOLDER, anx.nome_arquivo))
    except: pass
    db.session.delete(anx)
    db.session.commit()
    flash('Anexo removido.','success')
    return redirect(url_for('ver_proposta', id=id))

# ─── CONTRATOS ─────────────────────────────────────────────────────────────────
@app.route('/contratos')
@login_required
@empresa_required
def listar_contratos():
    contratos = Contrato.query.filter_by(empresa_id=eid())\
        .order_by(Contrato.criado_em.desc()).all()
    return render_template('contratos.html', contratos=contratos)

@app.route('/propostas/<int:id>/gerar-contrato', methods=['POST'])
@login_required
@empresa_required
def gerar_contrato(id):
    from contrato_generator import gerar_texto_contrato_html
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if p.status != 'aprovada':
        flash('Proposta precisa estar aprovada.','warning')
        return redirect(url_for('ver_proposta', id=id))
    if p.contrato:
        flash('Contrato já existe.','info')
        return redirect(url_for('ver_contrato', id=p.contrato.id))
    emp   = Empresa.query.get(eid())
    itens = [{'descricao':i.descricao,'quantidade':i.quantidade,
              'preco_unitario':i.preco_unitario,'tipo':i.tipo} for i in p.itens]
    count  = Contrato.query.filter_by(empresa_id=eid()).count()
    numero = f"CT-{datetime.now().strftime('%Y%m')}-{count+1:04d}"
    token  = uuid.uuid4().hex
    texto  = gerar_texto_contrato_html(modelo_para_dict(p),
                                       modelo_para_dict(emp),
                                       modelo_para_dict(p.cliente), itens)
    ct = Contrato(empresa_id=eid(), proposta_id=id, numero=numero,
                  cliente_id=p.cliente_id, token_assinatura=token,
                  texto_contrato=texto)
    db.session.add(ct)
    db.session.commit()
    flash(f'Contrato {numero} gerado!','success')
    return redirect(url_for('ver_contrato', id=ct.id))

@app.route('/contratos/<int:id>')
@login_required
@empresa_required
def ver_contrato(id):
    ct = Contrato.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    link = f"{request.host_url.rstrip('/')}/contrato/assinar/{ct.token_assinatura}"
    return render_template('ver_contrato.html', contrato=ct, link_assinatura=link)

@app.route('/contratos/<int:id>/assinar-empresa', methods=['POST'])
@login_required
@empresa_required
def assinar_contrato_empresa(id):
    import hashlib
    ct = Contrato.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if ct.status == 'assinado':
        flash('Contrato ja esta totalmente assinado.', 'info')
        return redirect(url_for('ver_contrato', id=id))
    ip  = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr or '')
    ts  = datetime.now().isoformat()
    emp = Empresa.query.get(eid())
    nome_emp = emp.fantasia if emp else 'EMPRESA'
    raw = f"{nome_emp}|{ip}|{ts}|{ct.numero}"
    h   = hashlib.sha256(raw.encode()).hexdigest()
    ct.status                  = 'assinado'
    ct.empresa_assinado_em     = datetime.now()
    ct.empresa_assinatura_nome = nome_emp
    ct.empresa_assinatura_ip   = ip
    ct.empresa_assinatura_hash = h
    db.session.commit()

    # Envia o contrato assinado automaticamente via Telegram
    try:
        from telegram_notify import enviar_mensagem_telegram, enviar_documento_telegram
        from contrato_generator import gerar_contrato_pdf
        itens_ct = [{'descricao':i.descricao,'quantidade':i.quantidade,
                     'preco_unitario':i.preco_unitario,'tipo':i.tipo} for i in ct.proposta.itens]
        ct_dict = modelo_para_dict(ct)
        buf = gerar_contrato_pdf(modelo_para_dict(ct.proposta), modelo_para_dict(emp),
                                 modelo_para_dict(ct.cliente), itens_ct, contrato=ct_dict)
        pdf_bytes = buf.getvalue() if hasattr(buf, 'getvalue') else buf.read()

        cliente_nome = ct.cliente.nome if ct.cliente else ''
        enviar_mensagem_telegram(
            f"✅ *Contrato {ct.numero} totalmente assinado!*\n\n"
            f"👤 Cliente: {cliente_nome}\n\n"
            f"📎 Segue o PDF assinado para você encaminhar ao cliente:"
        )
        enviar_documento_telegram(
            pdf_bytes,
            f"Contrato_{ct.numero.replace('-','_')}_Assinado.pdf",
            caption=f"Contrato {ct.numero} — {cliente_nome}"
        )
    except Exception as e:
        print(f"[ERRO notificacao Telegram] {e}")

    flash(f'Contrato {ct.numero} assinado! PDF liberado para o cliente.', 'success')
    return redirect(url_for('ver_contrato', id=id))

@app.route('/contrato/download/<token>')
def contrato_download_publico(token):
    from contrato_generator import gerar_contrato_pdf
    ct = Contrato.query.filter_by(token_assinatura=token).first_or_404()
    if ct.status != 'assinado':
        abort(403)
    emp   = Empresa.query.get(ct.empresa_id)
    itens = [{'descricao':i.descricao,'quantidade':i.quantidade,
              'preco_unitario':i.preco_unitario,'tipo':i.tipo} for i in ct.proposta.itens]
    ct_dict = modelo_para_dict(ct)
    buf = gerar_contrato_pdf(modelo_para_dict(ct.proposta), modelo_para_dict(emp),
                             modelo_para_dict(ct.cliente), itens, contrato=ct_dict)
    return send_file(buf, mimetype='application/pdf',
                     download_name=f"Contrato_{ct.numero.replace('-','_')}_Assinado.pdf")

@app.route('/contratos/<int:id>/pdf')
@login_required
@empresa_required
def contrato_pdf(id):
    from contrato_generator import gerar_contrato_pdf
    ct  = Contrato.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    emp = Empresa.query.get(eid())
    itens = [{'descricao':i.descricao,'quantidade':i.quantidade,
              'preco_unitario':i.preco_unitario,'tipo':i.tipo} for i in ct.proposta.itens]
    ct_dict = modelo_para_dict(ct)
    buf = gerar_contrato_pdf(modelo_para_dict(ct.proposta), modelo_para_dict(emp),
                             modelo_para_dict(ct.cliente), itens, contrato=ct_dict)
    return send_file(buf, mimetype='application/pdf',
                     download_name=f"Contrato_{ct.numero.replace('-','_')}.pdf")

@app.route('/contrato/assinar/<token>', methods=['GET','POST'])
def contrato_publico(token):
    ct  = Contrato.query.filter_by(token_assinatura=token).first_or_404()
    emp = Empresa.query.get(ct.empresa_id)
    if request.method == 'POST':
        nome = request.form.get('nome_assinatura','').strip()
        cpf = request.form.get('cpf_assinatura','').strip()
        if nome and cpf:
            import hashlib
            ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr or '')
            ts = datetime.now().isoformat()
            raw = f"{nome}|{cpf}|{ip}|{ts}|{ct.numero}"
            h   = hashlib.sha256(raw.encode()).hexdigest()
            ct.status          = 'assinado'
            ct.assinado_em     = datetime.now()
            ct.assinatura_nome = nome
            ct.assinatura_cpf  = cpf
            ct.assinatura_ip   = ip
            ct.assinatura_hash = h
            db.session.commit()
            flash('Contrato assinado digitalmente! Guarde o número do hash como comprovante.','success')
        else:
            flash('Preencha nome e CPF para assinar.','warning')
    return render_template('contrato_publico.html', contrato=ct,
                           empresa=emp, logo_b64=logo_b64)

# ─── OS ASSINATURA ─────────────────────────────────────────────────────────────
@app.route('/os/<int:id>/gerar-link-assinatura', methods=['POST'])
@login_required
@empresa_required
def gerar_link_assinatura_os(id):
    os_obj = OrdemServico.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    token  = uuid.uuid4().hex
    if os_obj.assinatura:
        os_obj.assinatura.token = token
    else:
        db.session.add(OsAssinatura(os_id=id, token=token))
    db.session.commit()
    flash('Link gerado!','success')
    return redirect(url_for('ver_os', id=id))

@app.route('/os/assinar/<token>', methods=['GET','POST'])
def os_publica(token):
    ass    = OsAssinatura.query.filter_by(token=token).first_or_404()
    os_obj = ass.os
    emp    = Empresa.query.get(os_obj.empresa_id)
    if request.method == 'POST':
        nome = request.form.get('nome_assinatura','').strip()
        if nome:
            ass.assinado_em = datetime.now()
            ass.assinatura_nome = nome
            os_obj.status = 'concluida'
            os_obj.data_conclusao = date.today()
            db.session.commit()
            flash('OS assinada e concluída!','success')
        else:
            flash('Informe o nome.','warning')
    return render_template('os_publica.html', os_obj=os_obj,
                           assinatura=ass, empresa=emp, logo_b64=logo_b64)


@app.route('/api/calc/preco', methods=['POST'])
@login_required
@empresa_required
def api_calc_preco():
    from catalogo_creative import calcular_preco_servico, calcular_preco_produto
    d = request.get_json()
    tipo = d.get('tipo','servico')
    custo = float(d.get('custo',0))
    margem = float(d.get('margem',30))
    horas = float(d.get('horas',0))
    hora_val = float(d.get('hora_val',80))
    if tipo == 'produto':
        return jsonify(calcular_preco_produto(custo, margem))
    else:
        return jsonify(calcular_preco_servico(custo, horas, hora_val, margem=margem))


@app.route('/propostas/<int:id>/upload-anexo', methods=['POST'])
@login_required
@empresa_required
def upload_anexo_proposta(id):
    from models import AnexoProposta
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    f = request.files.get('arquivo')
    if not f or not f.filename:
        return jsonify({'erro':'Nenhum arquivo'}), 400
    ext = f.filename.rsplit('.',1)[-1].lower()
    if ext not in {'jpg','jpeg','png','gif','webp','pdf'}:
        return jsonify({'erro':'Tipo não permitido'}), 400
    pasta = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'anexos')
    os.makedirs(pasta, exist_ok=True)
    nome = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(pasta, nome))
    anx = AnexoProposta(proposta_id=id, nome_original=f.filename,
                        nome_arquivo=nome,
                        tipo=request.form.get('tipo_anexo','outro'),
                        descricao=request.form.get('descricao',''))
    db.session.add(anx)
    db.session.commit()
    return jsonify({'ok': True, 'nome': nome})


@app.route('/propostas/<int:id>/anexos/<int:aid>/excluir-proj', methods=['POST'])
@login_required
@empresa_required
def excluir_anexo_proposta(id, aid):
    from models import AnexoProposta
    anx = AnexoProposta.query.filter_by(id=aid, proposta_id=id).first_or_404()
    try:
        os.remove(os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'anexos', anx.nome_arquivo))
    except: pass
    db.session.delete(anx)
    db.session.commit()
    flash('Documento removido.', 'success')
    return redirect(url_for('editar_proposta', id=id))

@app.route('/proposta/doc/<token>/<int:aid>')
def download_doc_publico(token, aid):
    from models import AnexoProposta
    # Busca a proposta pelo token — ignora expiração pois download deve sempre funcionar
    p   = Proposta.query.filter_by(token_publico=token).first_or_404()
    anx = AnexoProposta.query.filter_by(id=aid, proposta_id=p.id).first_or_404()
    path = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'anexos', anx.nome_arquivo)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=anx.nome_original)

@app.route('/propostas/<int:id>/clonar', methods=['POST'])
@login_required
@empresa_required
def clonar_proposta(id):
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    count  = Proposta.query.filter_by(empresa_id=eid()).count()
    numero = f"NB-{datetime.now().strftime('%Y%m')}-{count+1:04d}"
    token  = uuid.uuid4().hex
    expira = datetime.now() + timedelta(days=p.validade or 15)
    nova = Proposta(
        empresa_id=eid(), numero=numero,
        titulo=f"{p.titulo} (Copia)",
        cliente_id=p.cliente_id,
        validade=p.validade,
        forma_pagamento=p.forma_pagamento,
        observacoes=p.observacoes,
        condicoes=p.condicoes,
        custo_locomocao=p.custo_locomocao,
        custo_alimentacao=p.custo_alimentacao,
        custo_outros=p.custo_outros,
        descricao_custos=p.descricao_custos,
        analise_ambiente=p.analise_ambiente,
        cronograma=p.cronograma,
        template_estilo=p.template_estilo,
        token_publico=token, token_expira_em=expira,
        status='rascunho',
        usuario_id=session.get('user_id'))
    db.session.add(nova)
    db.session.flush()
    for item in p.itens:
        db.session.add(ItemProposta(
            proposta_id=nova.id,
            descricao=item.descricao,
            quantidade=item.quantidade,
            preco_unitario=item.preco_unitario,
            tipo=item.tipo,
            descricao_detalhada=item.descricao_detalhada or ''))
    from models import EtapaProposta
    for etapa in p.etapas:
        db.session.add(EtapaProposta(
            proposta_id=nova.id,
            ordem=etapa.ordem,
            titulo=etapa.titulo,
            duracao_dias=etapa.duracao_dias,
            descricao=etapa.descricao or ''))
    db.session.commit()
    flash(f'Proposta clonada como {numero}!', 'success')
    return redirect(url_for('ver_proposta', id=nova.id))

# ─── CADASTRO PÚBLICO DE CLIENTE (sem login) ───────────────────────────────────
@app.route('/cadastro')
def cadastro_publico():
    """Página pública — o cliente preenche seus próprios dados via link do WhatsApp."""
    # Usa empresa 1 (Creative) como padrão para cadastros públicos
    empresa_id = session.get('empresa_id', 1)
    return render_template('cadastro_publico.html', empresa_id=empresa_id)

@app.route('/cadastro-cliente', methods=['POST'])
def salvar_cadastro_publico():
    """Recebe o formulário público e salva como novo cliente."""
    try:
        nome       = request.form.get('nome', '').strip()
        telefone   = request.form.get('telefone', '').strip()
        endereco   = request.form.get('endereco', '').strip()
        email      = request.form.get('email', '').strip()
        cpf_cnpj   = request.form.get('cpf_cnpj', '').strip()
        tipo       = request.form.get('tipo', 'PF').strip()
        empresa_id = int(request.form.get('empresa_id', 1))

        if not nome or not telefone or not endereco:
            return jsonify({'ok': False, 'erro': 'Campos obrigatórios ausentes.'}), 400

        # Se já existe cliente com mesmo telefone nessa empresa, apenas atualiza
        existente = Cliente.query.filter_by(empresa_id=empresa_id, telefone=telefone).first()
        if existente:
            existente.nome     = nome
            existente.endereco = endereco
            if email:    existente.email    = email
            if cpf_cnpj: existente.cpf_cnpj = cpf_cnpj
            db.session.commit()
            return jsonify({'ok': True, 'cliente_id': existente.id, 'novo': False})

        cliente = Cliente(
            empresa_id=empresa_id, nome=nome, tipo=tipo,
            cpf_cnpj=cpf_cnpj, email=email,
            telefone=telefone, endereco=endereco,
        )
        db.session.add(cliente)
        db.session.commit()
        return jsonify({'ok': True, 'cliente_id': cliente.id, 'novo': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'erro': str(e)}), 500

# ─── LICENÇAS NEURADESK (produto vendido para outras empresas) ────────────────

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


def _renovar_licenca(lic, dias=30):
    """Estende o vencimento da licença por `dias` a partir de hoje (ou do
    vencimento atual, se ainda não venceu) e marca como ativa. Usado tanto
    pela renovação manual (botão no admin) quanto pelo webhook do Mercado
    Pago quando um pagamento é aprovado."""
    base = lic.data_vencimento if (lic.data_vencimento and lic.data_vencimento > datetime.now()) else datetime.now()
    lic.data_ultimo_pagamento = datetime.now()
    lic.data_vencimento = base + timedelta(days=dias)
    if lic.status not in ('bloqueada', 'cancelada'):
        lic.status = 'ativa'


@app.route('/admin/licencas/<int:id>/renovar', methods=['POST'])
@login_required
@super_admin_required
def renovar_licenca_neuradesk(id):
    """Marca o pagamento do mês como confirmado manualmente (uso normal
    enquanto a licença não estiver vinculada a uma assinatura do Mercado
    Pago, ou como fallback se o webhook falhar por algum motivo)."""
    lic = LicencaNeuraDesk.query.get_or_404(id)
    _renovar_licenca(lic, dias=30)
    db.session.commit()
    flash(f'Renovação registrada. Novo vencimento: {lic.data_vencimento.strftime("%d/%m/%Y")}', 'success')
    return redirect(url_for('detalhe_licenca_neuradesk', id=id))


@app.route('/admin/licencas/<int:id>/vincular-mp', methods=['POST'])
@login_required
@super_admin_required
def vincular_mp_licenca_neuradesk(id):
    """Associa manualmente o ID de uma assinatura (preapproval) do
    Mercado Pago, criada direto no painel do MP, a esta licença -- é
    assim que o webhook sabe pra qual licença aplicar a renovação
    automática quando o pagamento cair."""
    lic = LicencaNeuraDesk.query.get_or_404(id)
    preapproval_id = request.form.get('mp_preapproval_id', '').strip()
    lic.mp_preapproval_id = preapproval_id or None
    db.session.commit()
    flash('Vínculo com Mercado Pago atualizado.', 'success')
    return redirect(url_for('detalhe_licenca_neuradesk', id=id))


@app.route('/admin/integracoes', methods=['GET', 'POST'])
@login_required
@super_admin_required
def admin_integracoes():
    """Tela pra configurar tokens de integrações externas (hoje: Mercado
    Pago) sem precisar editar .env no servidor. Valores ficam cifrados
    no banco -- o formulário nunca mostra o valor salvo de volta, só se
    já tem algo configurado ou não."""
    campos = ['MP_ACCESS_TOKEN', 'MP_WEBHOOK_SECRET']

    if request.method == 'POST':
        for chave in campos:
            valor = request.form.get(chave, '').strip()
            if not valor:
                continue  # em branco = mantem o que ja estava salvo
            reg = Integracao.query.filter_by(chave=chave).first()
            if not reg:
                reg = Integracao(chave=chave)
                db.session.add(reg)
            reg.set_valor(valor)
        db.session.commit()
        flash('Integrações atualizadas.', 'success')
        return redirect(url_for('admin_integracoes'))

    status = {}
    for chave in campos:
        reg = Integracao.query.filter_by(chave=chave).first()
        status[chave] = bool(reg and reg.valor_cifrado)
    return render_template('admin_integracoes.html', status=status)


def _mp_config():
    """Config do Mercado Pago: primeiro tenta a tela de admin
    (/admin/integracoes, guardada cifrada no banco), senão cai pro .env
    -- assim dá pra configurar sem precisar de acesso ao servidor."""
    return {
        'access_token':   Integracao.obter('MP_ACCESS_TOKEN', Config.MP_ACCESS_TOKEN),
        'webhook_secret': Integracao.obter('MP_WEBHOOK_SECRET', Config.MP_WEBHOOK_SECRET),
        'dias_renovacao': Config.MP_DIAS_RENOVACAO,
    }


@app.route('/webhook/mercadopago', methods=['POST', 'GET'])
def webhook_mercadopago():
    """Recebe as notificações do Mercado Pago (pagamento aprovado de uma
    assinatura, mudança de status de preapproval) e renova a licença
    correspondente automaticamente.

    Vínculo licença <-> Mercado Pago: o external_reference do pagamento
    (ou da assinatura/preapproval) precisa ser a CHAVE da licença
    (ex: NRDK-XXXX-XXXX-XXXX-XXXX) -- defina isso ao criar a assinatura
    no Mercado Pago.

    Sempre responde 200 pro MP (exceto quando a assinatura da notificação
    não confere, ou a integração não está configurada) -- se devolvermos
    erro por um bug nosso, o MP fica reenviando a mesma notificação sem
    parar. Erros de processamento são só logados, pra revisão manual."""
    mp = _mp_config()
    if not mp['access_token'] or not mp['webhook_secret']:
        return jsonify({'ok': False, 'erro': 'Mercado Pago não configurado nesta instalação'}), 503

    if not mp_integracao.validar_assinatura(request.headers, request.args, mp['webhook_secret']):
        print('[MP-WEBHOOK] assinatura inválida -- notificação recusada')
        return jsonify({'ok': False, 'erro': 'assinatura inválida'}), 401

    body = request.get_json(silent=True) or {}
    tipo = request.args.get('type') or body.get('type') or request.args.get('topic') or ''
    data_id = request.args.get('data.id') or request.args.get('id') or (body.get('data') or {}).get('id')

    if not data_id:
        return jsonify({'ok': True}), 200

    try:
        if tipo == 'payment':
            _mp_processar_pagamento(data_id, mp)
        elif tipo in ('preapproval', 'subscription_preapproval'):
            _mp_processar_preapproval(data_id, mp)
    except Exception as e:
        print(f'[MP-WEBHOOK] erro processando {tipo} {data_id}: {e}')

    return jsonify({'ok': True}), 200


def _mp_processar_pagamento(payment_id, mp):
    pagamento = mp_integracao.buscar_pagamento(payment_id, mp['access_token'])
    if not pagamento:
        print(f'[MP-WEBHOOK] não consegui buscar o pagamento {payment_id} na API do MP')
        return

    chave = (pagamento.get('external_reference') or '').strip().upper()
    status = pagamento.get('status')
    lic = LicencaNeuraDesk.query.filter_by(chave=chave).first()
    if not lic:
        print(f'[MP-WEBHOOK] pagamento {payment_id} aprovado mas referencia licença desconhecida: {chave!r}')
        return

    lic.mp_status = status

    if status == 'approved':
        if lic.mp_ultimo_pagamento_id == str(payment_id):
            # notificação duplicada do mesmo pagamento -- MP reenvia
            # quando não recebe 200 a tempo. Não renova de novo.
            db.session.commit()
            return
        _renovar_licenca(lic, dias=mp['dias_renovacao'])
        lic.mp_ultimo_pagamento_id = str(payment_id)

    db.session.commit()


def _mp_processar_preapproval(preapproval_id, mp):
    preapproval = mp_integracao.buscar_preapproval(preapproval_id, mp['access_token'])
    if not preapproval:
        print(f'[MP-WEBHOOK] não consegui buscar o preapproval {preapproval_id} na API do MP')
        return

    chave = (preapproval.get('external_reference') or '').strip().upper()
    lic = LicencaNeuraDesk.query.filter_by(chave=chave).first()
    if not lic:
        print(f'[MP-WEBHOOK] preapproval {preapproval_id} referencia licença desconhecida: {chave!r}')
        return

    lic.mp_preapproval_id = str(preapproval_id)
    lic.mp_status = preapproval.get('status')
    db.session.commit()


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


# ─── INICIALIZAÇÃO ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("[NeuraBusiness] Tabelas criadas/verificadas")
        seed_inicial()
    print("\n[>>] NeuraBusiness v3.0 — http://localhost:5000\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
