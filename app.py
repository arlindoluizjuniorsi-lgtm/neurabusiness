"""NeuraBusiness v3.0 — Sistema Comercial Multi-empresa (SQLAlchemy)"""
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, jsonify, send_file, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
from datetime import datetime, date, timedelta
from sqlalchemy import func, or_
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os, json, uuid, base64, subprocess, smtplib, logging
import xml.etree.ElementTree as ET
from logging.handlers import RotatingFileHandler

from config import Config
import mp_integracao
import infinitypay_integracao
from models import (db, Empresa, Usuario, UsuarioEmpresa, Produto, Servico,
                    CatalogoServico, MaterialInfra, Cliente, Proposta,
                    ItemProposta, OrdemServico, ItemOs, ProjetoAnexo, Contrato, OsAssinatura,
                    LicencaNeuraDesk, Integracao, ContratoNeuraDesk, PagamentoNeuraDesk,
                    CartaoPessoal, GastoPessoal, RendaPessoal, GastoCarro, GastoCasa,
                    VeiculoPessoal, RevisaoCarro, ManutencaoRecorrente, ItemVendaTroca,
                    SimulacaoTrocaCarro)

# ─── APP ───────────────────────────────────────────────────────────────────────
app = Flask(__name__)
# nginx é o único proxy na frente da app (Cloudflare -> nginx -> app), por
# isso confia num único hop de X-Forwarded-*. Sem isso, request.is_secure
# e url_for(_external=True) sempre acham que a conexão é HTTP, mesmo com
# o site inteiro servido em HTTPS pelo Cloudflare.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config['SECRET_KEY']              = Config.SECRET_KEY
app.config['UPLOAD_FOLDER']           = Config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH']      = Config.MAX_CONTENT_LENGTH
app.config['SQLALCHEMY_DATABASE_URI'] = Config.get_db_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = not Config.DEBUG

db.init_app(app)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, storage_uri='memory://', default_limits=[])

# ─── LOGGING ────────────────────────────────────────────────────────────────────
# Print() continua valendo pra mensagens soltas de debug, mas os caminhos
# criticos (pagamentos, webhooks, email) usam esse logger -- vai pro mesmo
# arquivo de sempre (stdout, redirecionado pelo systemd) e também pra um
# arquivo próprio com rotação, pra não crescer pra sempre.
os.makedirs(os.path.join(os.path.dirname(__file__), 'logs'), exist_ok=True)
logger = logging.getLogger('neurabusiness')
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler(
    os.path.join(os.path.dirname(__file__), 'logs', 'neurabusiness.log'),
    maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(_handler)
logger.addHandler(logging.StreamHandler())

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

@app.template_filter('contraste')
def cor_contraste(hexcolor):
    """Preto ou branco, o que tiver mais contraste com a cor de fundo
    (usado nos badges coloridos dos cartões da Gestão Pessoal)."""
    try:
        h = (hexcolor or '').lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return '#000000' if luminancia > 0.55 else '#ffffff'
    except (ValueError, IndexError):
        return '#ffffff'

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
@limiter.limit('10 per minute')
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
@limiter.limit('10 per minute')
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
        emp.nfse_codigo_municipio           = request.form.get('nfse_codigo_municipio','').strip() or None
        emp.nfse_inscricao_municipal        = request.form.get('nfse_inscricao_municipal','').strip() or None
        emp.nfse_regime_tributario          = request.form.get('nfse_regime_tributario','mei')
        emp.nfse_codigo_tributacao_nacional = request.form.get('nfse_codigo_tributacao_nacional','').strip() or None
        emp.nfse_cnbs                       = request.form.get('nfse_cnbs','').strip() or None
        emp.nfse_serie_dps                  = request.form.get('nfse_serie_dps','1').strip() or '1'
        emp.nfse_ambiente                   = request.form.get('nfse_ambiente','homologacao')
        try:
            emp.nfse_aliquota_iss = float(request.form.get('nfse_aliquota_iss', 0) or 0)
        except ValueError:
            pass
        try:
            emp.nfse_ultimo_numero_dps = int(request.form.get('nfse_ultimo_numero_dps', 0) or 0)
        except ValueError:
            pass
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
        _notificar_proposta_criada_telegram(p)
        flash(f'Proposta {numero} criada!','success')
        return redirect(url_for('ver_proposta', id=p.id))
    clientes  = Cliente.query.filter_by(empresa_id=eid()).order_by(Cliente.nome).all()
    produtos  = Produto.query.filter_by(empresa_id=eid(), ativo=True).order_by(Produto.nome).all()
    servicos  = Servico.query.filter_by(empresa_id=eid(), ativo=True).order_by(Servico.nome).all()
    catalogo  = CatalogoServico.query.filter_by(empresa_id=eid(), ativo=True).order_by(CatalogoServico.categoria, CatalogoServico.nome).all()
    cats_cat  = sorted(set(s.categoria for s in catalogo))
    return render_template('form_proposta.html', proposta=None,
                           clientes=clientes, produtos=produtos,
                           servicos=servicos, form_load_id=uuid.uuid4().hex,
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
    restante = _valor_restante_proposta(p) if p.status == 'aprovada' else None
    os_existente = OrdemServico.query.filter_by(proposta_id=p.id).first()
    return render_template('ver_proposta.html', proposta=p,
                           total=total_itens+custo_extra,
                           total_itens=total_itens,
                           itens=p.itens,
                           anexos=p.anexos, contrato=contrato,
                           link_publico=link_publico,
                           link_premium=link_premium,
                           restante=restante,
                           os_existente=os_existente)
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
                           servicos=servicos, form_load_id=uuid.uuid4().hex,
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

@app.route('/propostas/<int:id>/reenviar-telegram', methods=['POST'])
@login_required
@empresa_required
def reenviar_proposta_telegram(id):
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    _notificar_proposta_criada_telegram(p)
    flash('Proposta reenviada pro Telegram!', 'success')
    return redirect(request.referrer or url_for('ver_proposta', id=id))

@app.route('/propostas/<int:id>/confirmar-pagamento', methods=['POST'])
@login_required
@empresa_required
def confirmar_pagamento_proposta(id):
    """Confirmação manual de pagamento -- pra quando o cliente combina
    "de boca" e paga direto no Pix/dinheiro por fora do MP/InfinitePay.
    Soma o valor informado ao valor_pago da proposta e reaproveita o
    mesmo caminho (status parcial/pago + notificação no Telegram) usado
    pelos webhooks de pagamento."""
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if p.status != 'aprovada':
        flash('Só é possível confirmar pagamento de uma proposta aprovada.', 'warning')
        return redirect(url_for('ver_proposta', id=id))
    try:
        valor = float(request.form.get('valor', '').replace(',', '.'))
    except (TypeError, ValueError):
        valor = 0
    if valor <= 0:
        flash('Informe um valor válido.', 'warning')
        return redirect(url_for('ver_proposta', id=id))
    _registrar_pagamento_proposta(p, valor, f'manual-{uuid.uuid4().hex[:10]}')
    flash('Pagamento confirmado manualmente!', 'success')
    return redirect(url_for('ver_proposta', id=id))

@app.route('/propostas/<int:id>/aprovar-e-pagar', methods=['POST'])
@login_required
@empresa_required
def aprovar_e_pagar_proposta(id):
    """Atalho pra quando o cliente combinou tudo "de boca", nem chegou a
    aprovar pelo link, mas já pagou -- aprova a proposta (igual o botão
    "Aprovar" já existente) e confirma o pagamento do valor total de uma
    vez só. Não mexe no fluxo público de assinatura/contrato -- só marca
    status internamente, igual o botão manual de aprovar já faz."""
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if p.status not in ('rascunho', 'enviada', 'standby'):
        flash('Essa proposta já foi aprovada ou recusada.', 'warning')
        return redirect(url_for('ver_proposta', id=id))
    p.status = 'aprovada'
    p.aprovado_em = datetime.now()
    p.status_pagamento = p.status_pagamento or 'pendente'
    db.session.commit()
    valor = _valor_total_proposta(p)
    _registrar_pagamento_proposta(p, valor, f'manual-{uuid.uuid4().hex[:10]}')
    flash('Proposta aprovada e pagamento confirmado!', 'success')
    return redirect(url_for('ver_proposta', id=id))

@app.route('/propostas/<int:id>/emitir-nfse', methods=['GET', 'POST'])
@login_required
@empresa_required
def emitir_nfse_proposta(id):
    """Emite a NFS-e (Sistema Nacional NFS-e) referente aos itens de uma
    proposta aprovada. GET mostra o formulário (só pede a observação --
    todo o resto vem do cadastro da empresa/cliente/proposta). POST monta
    a DPS, assina com o certificado configurado e envia pra Sefin
    Nacional. Sempre notifica o resultado (sucesso ou erro) via Telegram."""
    p = Proposta.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if p.status != 'aprovada':
        flash('Só é possível emitir nota fiscal de uma proposta aprovada.', 'warning')
        return redirect(url_for('ver_proposta', id=id))

    if request.method == 'GET':
        return render_template('emitir_nfse.html', proposta=p)

    observacao = request.form.get('observacao', '').strip()
    pfx_bytes, senha = _certificado_nfse_configurado()
    if not pfx_bytes:
        flash('Certificado digital da NFS-e não configurado ainda. Configure em /admin/integracoes assim que tiver o certificado renovado.', 'danger')
        return redirect(url_for('ver_proposta', id=id))

    emp = Empresa.query.get(eid())
    import nfse_nacional
    xml_bytes, dps_id, erro = nfse_nacional.montar_dps_xml(
        emp, p.cliente, p.itens, p.numero, p.titulo, observacao, ambiente=emp.nfse_ambiente
    )
    if erro:
        flash(f'Não deu pra montar a nota: {erro}', 'danger')
        return redirect(url_for('ver_proposta', id=id))

    numero_dps_usado = (emp.nfse_ultimo_numero_dps or 0) + 1
    try:
        xml_assinado = nfse_nacional.assinar_dps_xml(xml_bytes, pfx_bytes, senha, dps_id)
    except Exception as e:
        p.nfse_status = 'erro'
        p.nfse_erro = f'Erro ao assinar a DPS: {e}'
        db.session.commit()
        _notificar_nfse_erro(p, p.nfse_erro)
        flash(f'Erro ao assinar a nota: {e}', 'danger')
        return redirect(url_for('ver_proposta', id=id))

    nfse_xml, erro_envio = nfse_nacional.emitir_nfse(xml_assinado, pfx_bytes, senha, ambiente=emp.nfse_ambiente)

    # O número da DPS só é consumido (incrementado) se de fato chegou a ser
    # enviado -- assim uma falha de assinatura/config não "queima" números.
    emp.nfse_ultimo_numero_dps = numero_dps_usado
    db.session.commit()

    if erro_envio:
        p.nfse_status = 'erro'
        p.nfse_numero_dps = numero_dps_usado
        p.nfse_serie_dps = emp.nfse_serie_dps
        p.nfse_erro = str(erro_envio)
        db.session.commit()
        _notificar_nfse_erro(p, str(erro_envio))
        flash(f'A Sefin Nacional recusou a nota: {erro_envio}', 'danger')
        return redirect(url_for('ver_proposta', id=id))

    try:
        from lxml import etree
        root = etree.fromstring(nfse_xml)
        ns = {'n': 'http://www.sped.fazenda.gov.br/nfse'}
        inf_nfse = root.find('.//n:infNFSe', ns)
        id_nfse = inf_nfse.get('Id') if inf_nfse is not None else ''
        chave_acesso = id_nfse[3:] if id_nfse.startswith('NFS') else id_nfse
        n_nfse_el = inf_nfse.find('n:nNFSe', ns) if inf_nfse is not None else None
        numero_nfse = n_nfse_el.text if n_nfse_el is not None else None
    except Exception:
        chave_acesso, numero_nfse = None, None

    p.nfse_status = 'emitida'
    p.nfse_chave_acesso = chave_acesso
    p.nfse_numero_dps = numero_dps_usado
    p.nfse_serie_dps = emp.nfse_serie_dps
    p.nfse_emitido_em = datetime.now()
    p.nfse_erro = None
    db.session.commit()

    _notificar_nfse_sucesso(p, nfse_xml, chave_acesso, numero_nfse)
    flash(f'Nota fiscal emitida! Chave de acesso: {chave_acesso}', 'success')
    return redirect(url_for('ver_proposta', id=id))


def _notificar_nfse_sucesso(p, nfse_xml_bytes, chave_acesso, numero_nfse):
    try:
        from telegram_notify import enviar_mensagem_telegram, enviar_documento_telegram
        cliente_nome = p.cliente.nome if p.cliente else '?'
        enviar_mensagem_telegram(
            f"🧾 *Nota fiscal emitida!*\n\n"
            f"📄 Proposta: {p.numero}\n"
            f"👤 Cliente: {cliente_nome}\n"
            f"🔢 Número NFS-e: {numero_nfse or '?'}\n"
            f"🔑 Chave de acesso:\n`{chave_acesso}`"
        )
        if nfse_xml_bytes:
            enviar_documento_telegram(
                nfse_xml_bytes,
                f"NFSe_{p.numero.replace('-', '_')}.xml",
                caption=f"XML da NFS-e — {p.numero}"
            )
    except Exception as e:
        logger.warning(f'[NFSE] falha ao notificar Telegram da emissão da proposta {p.numero}: {e}')


def _notificar_nfse_erro(p, motivo):
    try:
        from telegram_notify import enviar_mensagem_telegram
        cliente_nome = p.cliente.nome if p.cliente else '?'
        enviar_mensagem_telegram(
            f"⚠️ *Erro ao emitir nota fiscal*\n\n"
            f"📄 Proposta: {p.numero}\n"
            f"👤 Cliente: {cliente_nome}\n"
            f"❌ Motivo: {str(motivo)[:500]}"
        )
    except Exception as e:
        logger.warning(f'[NFSE] falha ao notificar Telegram do erro da proposta {p.numero}: {e}')


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
    # Cliente voltando do checkout da InfinitePay (redirect_url) -- eles não
    # documentam assinatura de webhook, então confirmamos de verdade
    # perguntando pro payment_check deles com os IDs que vieram na URL, em
    # vez de confiar direto nos parâmetros (que o próprio navegador manda e
    # poderiam ser adulterados).
    transaction_nsu = request.args.get('transaction_nsu')
    slug = request.args.get('slug')
    if transaction_nsu and slug and p.infinitypay_link:
        _infinitypay_confirmar_pagamento(p, transaction_nsu, slug)
    emp = Empresa.query.get(p.empresa_id)
    total_itens = sum(i.quantidade * i.preco_unitario for i in p.itens)
    custo_extra = (p.custo_locomocao or 0)+(p.custo_alimentacao or 0)+(p.custo_outros or 0)
    restante = _valor_restante_proposta(p) if p.status == 'aprovada' else None
    return render_template('proposta_publica.html', proposta=p, empresa=emp,
                           itens=p.itens, total=total_itens+custo_extra,
                           total_itens=total_itens, logo_b64=logo_b64, restante=restante)

@app.route('/proposta/premium/<token>')
def proposta_premium_pub(token):
    p = Proposta.query.filter_by(token_publico=token).first_or_404()
    if p.token_expira_em and p.token_expira_em < datetime.now():
        return render_template('link_expirado.html'), 410
    transaction_nsu = request.args.get('transaction_nsu')
    slug = request.args.get('slug')
    if transaction_nsu and slug and p.infinitypay_link:
        _infinitypay_confirmar_pagamento(p, transaction_nsu, slug)
    emp = Empresa.query.get(p.empresa_id)
    total_itens = sum(i.quantidade * i.preco_unitario for i in p.itens)
    custo_extra = (p.custo_locomocao or 0)+(p.custo_alimentacao or 0)+(p.custo_outros or 0)
    restante = _valor_restante_proposta(p) if p.status == 'aprovada' else None
    return render_template('proposta_premium.html', proposta=p, empresa=emp,
                           itens=p.itens, total=total_itens+custo_extra,
                           total_itens=total_itens, anexos=p.anexos, logo_b64=logo_b64, restante=restante)

def _valor_total_proposta(p):
    total_itens = sum(i.quantidade * i.preco_unitario for i in p.itens)
    custo_extra = (p.custo_locomocao or 0) + (p.custo_alimentacao or 0) + (p.custo_outros or 0)
    return round(total_itens + custo_extra, 2)


def _valor_restante_proposta(p):
    """Quanto ainda falta o cliente pagar no total (independente do
    percentual escolhido na assinatura) -- usado na tela pública quando
    ele volta pra pagar o saldo depois de já ter pago o sinal."""
    return max(round(_valor_total_proposta(p) - (p.valor_pago or 0), 2), 0)


def _gerar_link_pagamento_mp(p, forcar_valor=None, descricao=None):
    """Cria uma Preferência de Checkout Pro (Pix+cartão+boleto no mesmo
    link) pra proposta recém-assinada, e salva o link direto nela. Nunca
    levanta exceção -- se o MP falhar ou não estiver configurado, a
    aprovação da proposta segue normalmente, só sem o link de pagamento.

    `forcar_valor`/`descricao`: quando informado, gera o link com um único
    item nesse valor (usado pro sinal de 50% ou pro saldo restante) em vez
    de itemizar a proposta inteira."""
    try:
        mp = _mp_config()
        if not mp['access_token']:
            return
        if forcar_valor is not None:
            if forcar_valor <= 0:
                return
            itens = [{'titulo': descricao or f'Proposta {p.numero}', 'quantidade': 1, 'valor_unitario': forcar_valor}]
        else:
            itens = [{'titulo': i.descricao, 'quantidade': i.quantidade, 'valor_unitario': i.preco_unitario}
                      for i in p.itens]
            custo_extra = (p.custo_locomocao or 0) + (p.custo_alimentacao or 0) + (p.custo_outros or 0)
            if custo_extra:
                itens.append({'titulo': 'Custos adicionais (locomoção/alimentação/outros)',
                               'quantidade': 1, 'valor_unitario': custo_extra})
        if not itens:
            return
        back_url = url_for('proposta_publica', token=p.token_publico, _external=True)
        dados, erro = mp_integracao.criar_preferencia_pagamento(
            mp['access_token'], itens,
            external_reference=p.numero,
            payer_email=p.cliente.email if p.cliente else None,
            payer_nome=p.cliente.nome if p.cliente else None,
            back_url_sucesso=back_url,
        )
        if erro:
            logger.error(f'[PAGAMENTO] erro gerando preferência MP pra proposta {p.numero}: {erro}')
            return
        p.mp_preference_id = dados.get('id')
        p.mp_init_point = dados.get('init_point')
        p.link_pagamento_gerado_em = datetime.now()
        db.session.commit()
    except Exception as e:
        logger.error(f'[PAGAMENTO] erro inesperado gerando link de pagamento pra proposta {p.numero}: {e}')


def _gerar_link_pagamento_infinitypay(p, forcar_valor=None, descricao=None):
    """Mesma ideia da preferência do MP, mas via link de pagamento da
    InfinitePay. Também nunca levanta exceção -- fica inerte enquanto
    INFINITYPAY_HANDLE não estiver configurado em /admin/integracoes.
    O Checkout Integrado da InfinitePay não usa API key/token.

    `forcar_valor`/`descricao`: mesma ideia do MP acima (sinal ou saldo
    restante em vez da proposta itemizada)."""
    try:
        handle = Integracao.obter('INFINITYPAY_HANDLE', '')
        if not handle:
            return
        if forcar_valor is not None:
            if forcar_valor <= 0:
                return
            itens = [{'titulo': descricao or f'Proposta {p.numero}', 'quantidade': 1, 'valor_unitario': forcar_valor}]
        else:
            itens = [{'titulo': i.descricao, 'quantidade': i.quantidade, 'valor_unitario': i.preco_unitario}
                      for i in p.itens]
            custo_extra = (p.custo_locomocao or 0) + (p.custo_alimentacao or 0) + (p.custo_outros or 0)
            if custo_extra:
                itens.append({'titulo': 'Custos adicionais (locomoção/alimentação/outros)',
                               'quantidade': 1, 'valor_unitario': custo_extra})
        if not itens:
            return
        redirect_url = url_for('proposta_publica', token=p.token_publico, _external=True)
        webhook_url = url_for('webhook_infinitypay', _external=True)
        link, erro = infinitypay_integracao.criar_link_pagamento(
            handle, itens,
            order_nsu=p.numero,
            redirect_url=redirect_url,
            webhook_url=webhook_url,
        )
        if erro:
            logger.error(f'[PAGAMENTO] erro gerando link InfinitePay pra proposta {p.numero}: {erro}')
            return
        p.infinitypay_link = link
        p.link_pagamento_gerado_em = datetime.now()
        db.session.commit()
    except Exception as e:
        logger.error(f'[PAGAMENTO] erro inesperado gerando link InfinitePay pra proposta {p.numero}: {e}')


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

    # Gera contrato automaticamente com assinatura do cliente ja registrada,
    # e assina pela empresa na hora tambem -- nao existe mais uma etapa
    # manual de "aguardando assinatura da empresa" nesse fluxo publico.
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
            _assinar_contrato_empresa(ct, emp, ip=ip)
        except Exception as e:
            logger.error(f'[CONTRATO] erro gerando/assinando contrato automatico da proposta {p.numero}: {e}')

    p.pagamento_percentual = 100
    p.status_pagamento = p.status_pagamento or 'pendente'
    db.session.commit()

    _gerar_link_pagamento_mp(p)
    _gerar_link_pagamento_infinitypay(p)

    # Link de pagamento já fica pronto de qualquer forma -- só encaminha
    # direto pra ele agora se o cliente marcou "pagar agora". Se não
    # marcou, ele assina e pode voltar no mesmo link público depois pra
    # escolher pagar (a tela já mostra os botões de pagamento quando ele
    # volta, porque o link já foi gerado aqui).
    pagar_agora = request.form.get('pagar_agora') == 'sim'
    if pagar_agora:
        # prioriza Mercado Pago (integração mais testada) e cai pro
        # InfinitePay se só ele estiver configurado.
        destino_pagamento = p.mp_init_point or p.infinitypay_link
        if destino_pagamento:
            return redirect(destino_pagamento)
        flash('Proposta aprovada e assinada!','success')
    else:
        flash('Proposta aprovada e assinada! Você pode pagar quando quiser voltando neste mesmo link.','success')
    return redirect(url_for('proposta_publica', token=token))


@app.route('/propostas/<int:id>/pagar-restante/<token>/<gateway>')
def pagar_restante_publico(id, token, gateway):
    """Usado quando o cliente pagou só o sinal (50%) e volta no link da
    proposta depois pra quitar o restante -- gera um link novo (MP ou
    InfinitePay) só com o saldo que falta, com base no que o webhook já
    confirmou como pago."""
    p = Proposta.query.filter_by(id=id, token_publico=token).first_or_404()
    if p.status != 'aprovada':
        return redirect(url_for('proposta_publica', token=token))
    restante = _valor_restante_proposta(p)
    if restante <= 0:
        flash('Esta proposta já está totalmente paga.', 'success')
        return redirect(url_for('proposta_publica', token=token))
    p.pagamento_percentual = 100  # a partir de agora o alvo passa a ser o valor total
    db.session.commit()
    descricao = f'Restante — Proposta {p.numero}'
    if gateway == 'mp':
        _gerar_link_pagamento_mp(p, forcar_valor=restante, descricao=descricao)
        destino = p.mp_init_point
    elif gateway == 'infinitypay':
        _gerar_link_pagamento_infinitypay(p, forcar_valor=restante, descricao=descricao)
        destino = p.infinitypay_link
    else:
        destino = None
    if destino:
        return redirect(destino)
    flash('Não consegui gerar o link de pagamento agora. Tente novamente em instantes.', 'danger')
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


@app.route('/os/<int:id>/itens/<int:item_id>/toggle', methods=['POST'])
@login_required
@empresa_required
def toggle_item_os(id, item_id):
    os_obj = OrdemServico.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    item = ItemOs.query.filter_by(id=item_id, os_id=os_obj.id).first_or_404()
    item.concluido = not item.concluido
    item.concluido_em = datetime.now() if item.concluido else None
    db.session.commit()
    return redirect(url_for('ver_os', id=id))

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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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

def _assinar_contrato_empresa(ct, emp, ip=None):
    """Aplica a assinatura da empresa num contrato (contratante já assinou)
    e dispara o PDF assinado pro Telegram. Usado tanto pelo botão manual
    quanto pela assinatura automática logo após o cliente assinar a
    proposta -- nesse caso `ip` vem do próprio request do cliente, já que
    não existe uma ação manual separada do lado da empresa."""
    import hashlib
    ip = ip or request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr or '')
    ts = datetime.now().isoformat()
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
        logger.warning(f'[CONTRATO] falha ao notificar Telegram do contrato {ct.numero}: {e}')


@app.route('/contratos/<int:id>/assinar-empresa', methods=['POST'])
@login_required
@empresa_required
def assinar_contrato_empresa(id):
    ct = Contrato.query.filter_by(id=id, empresa_id=eid()).first_or_404()
    if ct.status == 'assinado':
        flash('Contrato ja esta totalmente assinado.', 'info')
        return redirect(url_for('ver_contrato', id=id))
    emp = Empresa.query.get(eid())
    _assinar_contrato_empresa(ct, emp)
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
@csrf.exempt
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
        db.session.flush()  # garante lic.id antes de criar o contrato vinculado

        modulos = []
        for chave_mod, nome_mod, campo_valor in [
            ('oracle',     'NeuraDBA — Monitoramento Oracle',         'valor_oracle'),
            ('wmi',        'Servidores — Monitoramento Windows',      'valor_wmi'),
            ('pfsense',    'Rede Avançada — pfSense',                 'valor_pfsense'),
            ('hostinger',  'Check Hostinger — DNS Dinâmico',          'valor_hostinger'),
        ]:
            if request.form.get(f'modulo_{chave_mod}') == 'on':
                modulos.append({
                    'chave': chave_mod,
                    'nome': nome_mod,
                    'valor': float(request.form.get(campo_valor, 0) or 0),
                })

        contrato = ContratoNeuraDesk(
            licenca_id=lic.id,
            numero=ContratoNeuraDesk.gerar_numero(),
            token_assinatura=uuid.uuid4().hex,
            empresa_razao_social=request.form['empresa_nome'],
            empresa_endereco=request.form.get('empresa_endereco'),
            representante_nome=request.form.get('representante_nome'),
            representante_cpf=request.form.get('representante_cpf'),
            representante_email=request.form.get('representante_email'),
            valor_base=lic.valor_mensal,
            usuarios_inclusos=lic.max_usuarios,
            valor_usuario_adicional=float(request.form.get('valor_usuario_adicional', 0) or 0),
            dia_vencimento=int(request.form.get('dia_vencimento', 10) or 10),
            cidade_foro=request.form.get('cidade_foro'),
            prazo_aviso_previo_dias=int(request.form.get('prazo_aviso_previo_dias', 30) or 30),
            status='pendente',
        )
        contrato.set_modulos(modulos)
        db.session.add(contrato)
        db.session.commit()
        flash(f'Licença e contrato gerados com sucesso: {chave}', 'success')
        return redirect(url_for('detalhe_licenca_neuradesk', id=lic.id))

    empresas = Empresa.query.filter_by(ativa=True).order_by(Empresa.fantasia).all()
    return render_template('form_licenca_neuradesk.html', empresas=empresas)


@app.route('/admin/licencas/<int:id>')
@login_required
@super_admin_required
def detalhe_licenca_neuradesk(id):
    lic = LicencaNeuraDesk.query.get_or_404(id)
    return render_template('detalhe_licenca_neuradesk.html', lic=lic)


# ─── CONTRATO NEURADESK ─────────────────────────────────────────────────────────

@app.route('/contrato-neuradesk/assinar/<token>', methods=['GET', 'POST'])
def contrato_neuradesk_publico(token):
    """Página pública (sem login) onde o cliente confere os dados já
    preenchidos pela CONTRATADA e assina digitalmente (nome + CPF)."""
    ct = ContratoNeuraDesk.query.filter_by(token_assinatura=token).first_or_404()

    if request.method == 'POST' and ct.status == 'pendente':
        nome = request.form.get('nome_assinatura', '').strip()
        cpf = request.form.get('cpf_assinatura', '').strip()
        if nome and cpf:
            import contrato_neuradesk_generator as gen
            ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr or '')
            ts = datetime.now().isoformat()
            ct.assinatura_nome = nome
            ct.assinatura_cpf = cpf
            ct.assinatura_ip = ip
            ct.assinatura_hash = gen.calcular_hash(nome, cpf, ip, ts, ct.numero)
            ct.assinado_em = datetime.now()
            ct.status = 'assinado_cliente'
            db.session.commit()
            _enviar_email_cobranca(ct)
            flash('Contrato assinado com sucesso! Guarde o número do hash como comprovante.', 'success')
        else:
            flash('Preencha nome e CPF para assinar.', 'warning')

    return render_template('contrato_neuradesk_publico.html', contrato=ct, licenca=ct.licenca)


@app.route('/contrato-neuradesk/download/<token>')
def contrato_neuradesk_download_publico(token):
    ct = ContratoNeuraDesk.query.filter_by(token_assinatura=token).first_or_404()
    if ct.status != 'concluido':
        abort(403)
    import contrato_neuradesk_generator as gen
    buf = gen.gerar_contrato_neuradesk_pdf(ct, ct.licenca)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                      download_name=f'contrato_{ct.numero}.pdf')


@app.route('/admin/contratos-neuradesk/<int:id>/pdf')
@login_required
@super_admin_required
def contrato_neuradesk_pdf_admin(id):
    ct = ContratoNeuraDesk.query.get_or_404(id)
    import contrato_neuradesk_generator as gen
    buf = gen.gerar_contrato_neuradesk_pdf(ct, ct.licenca)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                      download_name=f'contrato_{ct.numero}.pdf')


def _enviar_email_cobranca(contrato):
    """Manda pro cliente, assim que ele assina o contrato de licenciamento,
    o link da página de cobrança (boleto/Pix/assinatura automática).
    Silencia erros -- se o SMTP não estiver configurado ou falhar, isso
    não pode travar o fluxo de assinatura do contrato."""
    if not Config.MAIL_SERVER or not Config.MAIL_USER or not contrato.representante_email:
        print('[MAIL] envio de cobrança ignorado (SMTP não configurado ou cliente sem e-mail)')
        return
    try:
        link = url_for('cobranca_publica', token=contrato.token_assinatura, _external=True)
        assunto = f'Contrato {contrato.numero} assinado — próximos passos do pagamento'
        corpo = f"""
Olá, {contrato.representante_nome or contrato.assinatura_nome or ''}!

Recebemos a assinatura do contrato de licenciamento do NeuraDesk nº {contrato.numero},
referente à empresa {contrato.empresa_razao_social}.

Valor mensal contratado: R$ {contrato.valor_total_mensal():.2f}

Acesse o link abaixo para conferir os detalhes do contrato e gerar o pagamento
(boleto, Pix ou assinatura automática recorrente):

  {link}

Qualquer dúvida, fale com a NeuraWorks.
        """.strip()

        msg = MIMEMultipart()
        msg['From'] = Config.MAIL_FROM or Config.MAIL_USER
        msg['To'] = contrato.representante_email
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
            server.starttls()
            server.login(Config.MAIL_USER, Config.MAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        logger.error(f'[MAIL] erro ao enviar e-mail de cobrança: {e}')


# ─── COBRANÇA NEURADESK (pública) ──────────────────────────────────────────────
# Página enviada por e-mail ao cliente assim que ele assina o contrato de
# licenciamento (ver _enviar_email_cobranca, chamada em
# contrato_neuradesk_publico). Nela o cliente pode gerar boleto ou Pix
# avulsos, ou iniciar a assinatura automática recorrente do Mercado Pago.

@app.route('/cobranca/<token>')
def cobranca_publica(token):
    ct = ContratoNeuraDesk.query.filter_by(token_assinatura=token).first_or_404()
    lic = ct.licenca
    pagamentos = (PagamentoNeuraDesk.query.filter_by(licenca_id=lic.id)
                  .order_by(PagamentoNeuraDesk.criado_em.desc()).limit(10).all())
    mp = _mp_config()
    return render_template('cobranca_publica.html', contrato=ct, licenca=lic,
                           pagamentos=pagamentos, mp_configurado=bool(mp['access_token']))


@app.route('/cobranca/<token>/gerar-boleto', methods=['POST'])
def cobranca_gerar_boleto(token):
    ct = ContratoNeuraDesk.query.filter_by(token_assinatura=token).first_or_404()
    lic = ct.licenca
    mp = _mp_config()
    if not mp['access_token']:
        flash('Mercado Pago não configurado nesta instalação.', 'danger')
        return redirect(url_for('cobranca_publica', token=token))

    cpf_cnpj = ct.representante_cpf or ct.assinatura_cpf
    if not cpf_cnpj:
        flash('Não há CPF do responsável cadastrado para gerar o boleto. Entre em contato com o suporte.', 'danger')
        return redirect(url_for('cobranca_publica', token=token))

    # Boleto registrado exige endereço completo do pagador -- o formulário
    # da página de cobrança pede isso na hora, e a gente salva no contrato
    # pra não pedir de novo da próxima vez.
    ct.endereco_cep    = request.form.get('endereco_cep', ct.endereco_cep or '').strip()
    ct.endereco_rua    = request.form.get('endereco_rua', ct.endereco_rua or '').strip()
    ct.endereco_numero = request.form.get('endereco_numero', ct.endereco_numero or '').strip()
    ct.endereco_bairro = request.form.get('endereco_bairro', ct.endereco_bairro or '').strip()
    ct.endereco_cidade = request.form.get('endereco_cidade', ct.endereco_cidade or '').strip()
    ct.endereco_uf     = request.form.get('endereco_uf', ct.endereco_uf or '').strip().upper()
    db.session.commit()

    if not all([ct.endereco_cep, ct.endereco_rua, ct.endereco_numero, ct.endereco_bairro, ct.endereco_cidade, ct.endereco_uf]):
        flash('Preencha o endereço completo (CEP, rua, número, bairro, cidade e UF) para gerar o boleto — é exigido pelo Mercado Pago.', 'warning')
        return redirect(url_for('cobranca_publica', token=token))

    endereco = {
        'zip_code': ''.join(c for c in ct.endereco_cep if c.isdigit()),
        'street_name': ct.endereco_rua,
        'street_number': ct.endereco_numero,
        'neighborhood': ct.endereco_bairro,
        'city': ct.endereco_cidade,
        'federal_unit': ct.endereco_uf,
    }

    dados, erro = mp_integracao.criar_pagamento_boleto(
        mp['access_token'],
        valor=ct.valor_total_mensal(),
        descricao=f'Licença NeuraDesk — {lic.empresa_nome} — {ct.numero}',
        external_reference=lic.chave,
        email=ct.representante_email or f'{lic.chave.lower()}@neurabusiness.local',
        nome=ct.representante_nome or ct.assinatura_nome or '',
        cpf_cnpj=cpf_cnpj,
        endereco=endereco,
    )
    if erro:
        logger.error(f'[COBRANCA] erro gerando boleto pra licença {lic.chave}: {erro}')
        flash('Não consegui gerar o boleto agora. Tente novamente em instantes.', 'danger')
        return redirect(url_for('cobranca_publica', token=token))

    pag = PagamentoNeuraDesk(
        licenca_id=lic.id,
        tipo='boleto',
        mp_payment_id=str(dados.get('id')),
        status=dados.get('status') or 'pending',
        valor=dados.get('transaction_amount') or ct.valor_total_mensal(),
        linha_digitavel=(dados.get('barcode') or {}).get('content'),
        boleto_url=(dados.get('transaction_details') or {}).get('external_resource_url'),
    )
    db.session.add(pag)
    db.session.commit()
    flash('Boleto gerado com sucesso.', 'success')
    return redirect(url_for('cobranca_publica', token=token))


@app.route('/cobranca/<token>/gerar-pix', methods=['POST'])
def cobranca_gerar_pix(token):
    ct = ContratoNeuraDesk.query.filter_by(token_assinatura=token).first_or_404()
    lic = ct.licenca
    mp = _mp_config()
    if not mp['access_token']:
        flash('Mercado Pago não configurado nesta instalação.', 'danger')
        return redirect(url_for('cobranca_publica', token=token))

    dados, erro = mp_integracao.criar_pagamento_pix(
        mp['access_token'],
        valor=ct.valor_total_mensal(),
        descricao=f'Licença NeuraDesk — {lic.empresa_nome} — {ct.numero}',
        external_reference=lic.chave,
        email=ct.representante_email or f'{lic.chave.lower()}@neurabusiness.local',
        nome=ct.representante_nome or ct.assinatura_nome or '',
        cpf_cnpj=ct.representante_cpf or ct.assinatura_cpf or '',
    )
    if erro:
        logger.error(f'[COBRANCA] erro gerando pix pra licença {lic.chave}: {erro}')
        flash('Não consegui gerar o Pix agora. Tente novamente em instantes.', 'danger')
        return redirect(url_for('cobranca_publica', token=token))

    poi = dados.get('point_of_interaction') or {}
    tdata = poi.get('transaction_data') or {}
    pag = PagamentoNeuraDesk(
        licenca_id=lic.id,
        tipo='pix',
        mp_payment_id=str(dados.get('id')),
        status=dados.get('status') or 'pending',
        valor=dados.get('transaction_amount') or ct.valor_total_mensal(),
        pix_qr_base64=tdata.get('qr_code_base64'),
        pix_copia_cola=tdata.get('qr_code'),
    )
    db.session.add(pag)
    db.session.commit()
    flash('Pix gerado com sucesso.', 'success')
    return redirect(url_for('cobranca_publica', token=token))


@app.route('/cobranca/<token>/assinatura-automatica', methods=['POST'])
def cobranca_assinatura_automatica(token):
    """Cria a assinatura recorrente (preapproval) no Mercado Pago e
    redireciona o cliente pro checkout hospedado do MP, onde ele cadastra
    o cartão e autoriza a cobrança automática mensal."""
    ct = ContratoNeuraDesk.query.filter_by(token_assinatura=token).first_or_404()
    lic = ct.licenca
    mp = _mp_config()
    if not mp['access_token']:
        flash('Mercado Pago não configurado nesta instalação.', 'danger')
        return redirect(url_for('cobranca_publica', token=token))

    if not ct.representante_email:
        flash('Não há e-mail do responsável cadastrado para criar a assinatura automática. Entre em contato com o suporte.', 'danger')
        return redirect(url_for('cobranca_publica', token=token))

    dados, erro = mp_integracao.criar_preapproval(
        mp['access_token'],
        valor=ct.valor_total_mensal(),
        descricao=f'Licença NeuraDesk — {lic.empresa_nome} — {ct.numero}',
        external_reference=lic.chave,
        payer_email=ct.representante_email,
        back_url=url_for('cobranca_publica', token=token, _external=True),
    )
    if erro:
        logger.error(f'[COBRANCA] erro criando preapproval pra licença {lic.chave}: {erro}')
        flash('Não consegui iniciar a assinatura automática agora. Tente novamente em instantes.', 'danger')
        return redirect(url_for('cobranca_publica', token=token))

    lic.mp_preapproval_id = str(dados.get('id'))
    lic.mp_status = dados.get('status')
    db.session.commit()

    init_point = dados.get('init_point')
    if not init_point:
        flash('Assinatura criada, mas não recebi o link de checkout do Mercado Pago.', 'warning')
        return redirect(url_for('cobranca_publica', token=token))
    return redirect(init_point)


@app.route('/cobranca/<token>/status')
def cobranca_status(token):
    """Endpoint leve pra polling via AJAX na página de cobrança -- confere
    se algum boleto/pix pendente já foi aprovado, sem precisar recarregar
    a página nem esperar o webhook do MP (que pode demorar alguns
    segundos pra chegar)."""
    ct = ContratoNeuraDesk.query.filter_by(token_assinatura=token).first_or_404()
    mp = _mp_config()
    pendentes = PagamentoNeuraDesk.query.filter_by(licenca_id=ct.licenca_id, status='pending').all()
    if mp['access_token']:
        for p in pendentes:
            dados = mp_integracao.buscar_pagamento(p.mp_payment_id, mp['access_token'])
            if not dados:
                continue
            novo_status = dados.get('status')
            if novo_status == p.status:
                continue
            if novo_status == 'approved':
                p.pago_em = datetime.now()
                _renovar_licenca(ct.licenca, dias=mp['dias_renovacao'])
            p.status = novo_status
        db.session.commit()

    todos = (PagamentoNeuraDesk.query.filter_by(licenca_id=ct.licenca_id)
             .order_by(PagamentoNeuraDesk.criado_em.desc()).limit(10).all())
    return jsonify({
        'status_licenca': ct.licenca.status,
        'vencimento': ct.licenca.data_vencimento.isoformat() if ct.licenca.data_vencimento else None,
        'pagamentos': [{'id': p.id, 'tipo': p.tipo, 'status': p.status} for p in todos],
    })


@app.route('/admin/contratos-neuradesk/<int:id>/confirmar', methods=['POST'])
@login_required
@super_admin_required
def contrato_neuradesk_confirmar(id):
    """Contra-assinatura da CONTRATADA -- só depois disso o contrato
    conta como executado por ambas as partes (Cláusula sobre assinatura
    dupla, decisão de 25/07/2026)."""
    ct = ContratoNeuraDesk.query.get_or_404(id)
    if ct.status != 'assinado_cliente':
        flash('O cliente ainda não assinou este contrato.', 'warning')
        return redirect(url_for('detalhe_licenca_neuradesk', id=ct.licenca_id))

    import contrato_neuradesk_generator as gen
    ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr or '')
    ts = datetime.now().isoformat()
    quem = get_current_user()
    ct.confirmado_por = quem.nome if quem else 'Administrador'
    ct.confirmado_ip = ip
    ct.confirmado_hash = gen.calcular_hash(ct.confirmado_por, ip, ts, ct.numero)
    ct.confirmado_em = datetime.now()
    ct.status = 'concluido'
    db.session.commit()
    flash('Contrato confirmado! Já conta como executado por ambas as partes.', 'success')
    return redirect(url_for('detalhe_licenca_neuradesk', id=ct.licenca_id))


# ─── PACOTE INSTALADOR DO NEURADESK ─────────────────────────────────────────────

NEURADESK_REPO_DIR = '/opt/neuradesk'
PACOTES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pacotes_neuradesk')


def _pacote_atual():
    """Retorna (caminho, nome, tamanho, data) do pacote mais recente, ou None."""
    if not os.path.isdir(PACOTES_DIR):
        return None
    arquivos = [f for f in os.listdir(PACOTES_DIR) if f.endswith('.tar.gz')]
    if not arquivos:
        return None
    arquivos.sort(key=lambda f: os.path.getmtime(os.path.join(PACOTES_DIR, f)), reverse=True)
    caminho = os.path.join(PACOTES_DIR, arquivos[0])
    return {
        'caminho': caminho,
        'nome': arquivos[0],
        'tamanho_kb': round(os.path.getsize(caminho) / 1024),
        'gerado_em': datetime.fromtimestamp(os.path.getmtime(caminho)),
    }


@app.route('/admin/instalador-neuradesk')
@login_required
@super_admin_required
def instalador_neuradesk():
    return render_template('instalador_neuradesk.html', pacote=_pacote_atual())


@app.route('/admin/instalador-neuradesk/gerar', methods=['POST'])
@login_required
@super_admin_required
def instalador_neuradesk_gerar():
    os.makedirs(PACOTES_DIR, exist_ok=True)
    nome = f"neuradesk-instalador-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz"
    caminho = os.path.join(PACOTES_DIR, nome)
    try:
        subprocess.run(
            ['git', '-c', f'safe.directory={NEURADESK_REPO_DIR}',
             'archive', '--format=tar.gz', f'--output={caminho}', 'HEAD'],
            cwd=NEURADESK_REPO_DIR, check=True, capture_output=True, text=True, timeout=60,
        )
        flash(f'Pacote gerado: {nome}', 'success')
    except subprocess.CalledProcessError as e:
        flash(f'Erro ao gerar pacote: {e.stderr}', 'danger')
    except Exception as e:
        flash(f'Erro ao gerar pacote: {e}', 'danger')
    return redirect(url_for('instalador_neuradesk'))


@app.route('/admin/instalador-neuradesk/baixar')
@login_required
@super_admin_required
def instalador_neuradesk_baixar():
    pacote = _pacote_atual()
    if not pacote:
        flash('Nenhum pacote gerado ainda.', 'warning')
        return redirect(url_for('instalador_neuradesk'))
    return send_file(pacote['caminho'], as_attachment=True, download_name=pacote['nome'], mimetype='application/gzip')


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
    """Tela pra configurar tokens de integrações externas (Mercado Pago,
    InfinitePay, certificado da NFS-e Nacional) sem precisar editar .env
    no servidor. Valores ficam cifrados no banco -- o formulário nunca
    mostra o valor salvo de volta, só se já tem algo configurado ou não."""
    campos = ['MP_ACCESS_TOKEN', 'MP_WEBHOOK_SECRET', 'INFINITYPAY_HANDLE', 'NFSE_CERTIFICADO_SENHA']

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

        # Certificado (.pfx) da NFS-e -- arquivo binário, guarda em base64
        # dentro do mesmo cofre cifrado (Integracao) que os outros segredos.
        arquivo_pfx = request.files.get('NFSE_CERTIFICADO_PFX')
        if arquivo_pfx and arquivo_pfx.filename:
            import base64
            pfx_b64 = base64.b64encode(arquivo_pfx.read()).decode('ascii')
            reg = Integracao.query.filter_by(chave='NFSE_CERTIFICADO_PFX_B64').first()
            if not reg:
                reg = Integracao(chave='NFSE_CERTIFICADO_PFX_B64')
                db.session.add(reg)
            reg.set_valor(pfx_b64)

        db.session.commit()
        flash('Integrações atualizadas.', 'success')
        return redirect(url_for('admin_integracoes'))

    status = {}
    for chave in campos:
        reg = Integracao.query.filter_by(chave=chave).first()
        status[chave] = bool(reg and reg.valor_cifrado)
    reg_pfx = Integracao.query.filter_by(chave='NFSE_CERTIFICADO_PFX_B64').first()
    status['NFSE_CERTIFICADO_PFX_B64'] = bool(reg_pfx and reg_pfx.valor_cifrado)
    return render_template('admin_integracoes.html', status=status)


def _certificado_nfse_configurado():
    """Retorna (pfx_bytes, senha) se o certificado da NFS-e já foi
    configurado em /admin/integracoes, ou (None, None) se não."""
    import base64
    pfx_b64 = Integracao.obter('NFSE_CERTIFICADO_PFX_B64', '')
    senha = Integracao.obter('NFSE_CERTIFICADO_SENHA', '')
    if not pfx_b64:
        return None, None
    try:
        return base64.b64decode(pfx_b64), senha
    except Exception:
        return None, None


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
@csrf.exempt
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
        logger.warning('[MP-WEBHOOK] assinatura inválida -- notificação recusada')
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
        logger.error(f'[MP-WEBHOOK] erro processando {tipo} {data_id}: {e}')

    return jsonify({'ok': True}), 200


def _mp_processar_pagamento(payment_id, mp):
    pagamento = mp_integracao.buscar_pagamento(payment_id, mp['access_token'])
    if not pagamento:
        logger.warning(f'[MP-WEBHOOK] não consegui buscar o pagamento {payment_id} na API do MP')
        return

    chave = (pagamento.get('external_reference') or '').strip()
    status = pagamento.get('status')

    # Pagamento de uma proposta comercial do Creative (numero tipo
    # NB-202607-0009) -- checa antes da licença, que usa outro formato de
    # chave (NRDK-...).
    p = Proposta.query.filter_by(numero=chave).first()
    if p:
        if status == 'approved':
            _mp_registrar_pagamento_proposta(p, payment_id, pagamento)
        return

    chave = chave.upper()
    lic = LicencaNeuraDesk.query.filter_by(chave=chave).first()
    if not lic:
        logger.warning(f'[MP-WEBHOOK] pagamento {payment_id} aprovado mas referencia licença desconhecida: {chave!r}')
        return

    lic.mp_status = status

    # Se esse pagamento veio da página de cobrança (boleto/Pix avulso),
    # sincroniza o status na tabela de cobranças também.
    pag = PagamentoNeuraDesk.query.filter_by(mp_payment_id=str(payment_id)).first()
    if pag:
        pag.status = status
        if status == 'approved' and not pag.pago_em:
            pag.pago_em = datetime.now()

    if status == 'approved':
        if lic.mp_ultimo_pagamento_id == str(payment_id):
            # notificação duplicada do mesmo pagamento -- MP reenvia
            # quando não recebe 200 a tempo. Não renova de novo.
            db.session.commit()
            return
        _renovar_licenca(lic, dias=mp['dias_renovacao'])
        lic.mp_ultimo_pagamento_id = str(payment_id)

    db.session.commit()


def _mp_registrar_pagamento_proposta(p, payment_id, pagamento):
    """Confirma pagamento (MP) de uma proposta comercial do Creative --
    soma o valor pago (cobre tanto o sinal de 50% quanto o saldo pago
    depois) e marca pendente/parcial/pago."""
    if p.mp_payment_id == str(payment_id):
        # notificação duplicada do mesmo pagamento -- MP reenvia quando
        # não recebe 200 a tempo. Não soma de novo.
        return
    valor = float(pagamento.get('transaction_amount') or 0)
    _registrar_pagamento_proposta(p, valor, str(payment_id))


def _registrar_pagamento_proposta(p, valor, referencia_pagamento):
    """Soma `valor` ao total já confirmado da proposta, atualiza
    status_pagamento (parcial/pago) e notifica Arlindo via Telegram. Usado
    tanto pelo webhook do MP quanto pela verificação de pagamento da
    InfinitePay quanto pela confirmação manual. `referencia_pagamento` é só
    pra deduplicar notificações repetidas do mesmo pagamento (payment_id do
    MP ou transaction_nsu da InfinitePay) -- reaproveita a coluna
    mp_payment_id pra isso."""
    if valor <= 0:
        return
    p.valor_pago = round((p.valor_pago or 0) + valor, 2)
    p.mp_payment_id = referencia_pagamento
    p.pago_em = datetime.now()
    total = _valor_total_proposta(p)
    p.status_pagamento = 'pago' if p.valor_pago >= total - 0.01 else 'parcial'
    db.session.commit()
    os_obj = None
    if p.status_pagamento == 'pago':
        os_obj = _criar_os_automatica_para_proposta(p)
    _notificar_pagamento_proposta(p, valor, os_obj)


def _criar_os_automatica_para_proposta(p):
    """Gera a OS automaticamente assim que a proposta fica 100% paga, com
    um item por serviço/produto da proposta pra ir marcando conforme
    conclui. Nunca duplica -- se já existe uma OS pra essa proposta
    (gerada manualmente ou por um pagamento anterior), não cria outra."""
    if OrdemServico.query.filter_by(proposta_id=p.id).first():
        return None
    try:
        count  = OrdemServico.query.filter_by(empresa_id=p.empresa_id).count()
        numero = f"OS-{datetime.now().strftime('%Y%m')}-{count+1:04d}"
        os_obj = OrdemServico(
            empresa_id=p.empresa_id, numero=numero, titulo=p.titulo,
            cliente_id=p.cliente_id, proposta_id=p.id,
            descricao=f'OS gerada automaticamente após confirmação de pagamento da proposta {p.numero}.')
        db.session.add(os_obj)
        db.session.flush()
        for item in p.itens:
            db.session.add(ItemOs(os_id=os_obj.id, descricao=item.descricao))
        db.session.commit()
        return os_obj
    except Exception as e:
        db.session.rollback()
        logger.error(f'[OS-AUTO] erro gerando OS automática da proposta {p.numero}: {e}')
        return None


def _notificar_pagamento_proposta(p, valor, os_obj=None):
    try:
        from telegram_notify import enviar_mensagem_telegram
        from ia_assistente import fmt
        cliente_nome = p.cliente.nome if p.cliente else '?'
        total = _valor_total_proposta(p)
        status_txt = 'PAGO INTEGRALMENTE ✅' if p.status_pagamento == 'pago' else 'PARCIAL — falta receber o restante'
        msg = (
            f"💰 *Pagamento confirmado!*\n\n"
            f"📄 Proposta: {p.numero}\n"
            f"👤 Cliente: {cliente_nome}\n"
            f"💵 Valor recebido agora: {fmt(valor)}\n"
            f"📊 Total pago: {fmt(p.valor_pago)} de {fmt(total)}\n"
            f"📌 Status: {status_txt}"
        )
        if os_obj:
            msg += f"\n🛠️ OS {os_obj.numero} criada automaticamente — marque os itens conforme for concluindo."
        enviar_mensagem_telegram(msg)
    except Exception as e:
        logger.warning(f'[PAGAMENTO] falha ao notificar Telegram do pagamento da proposta {p.numero}: {e}')


def _notificar_proposta_criada_telegram(p):
    """Manda pro Telegram, quando a proposta é criada pelo site (não pelo
    bot), a mesma coisa que o bot já manda quando cria por lá: uma
    mensagem pronta pra encaminhar ao cliente + o PDF em anexo. Nunca
    levanta exceção -- a criação da proposta não pode falhar por causa
    disso."""
    try:
        from telegram_notify import enviar_mensagem_telegram, enviar_documento_telegram
        from ia_assistente import fmt
        from pdf_generator import gerar_proposta_pdf
        emp = Empresa.query.get(p.empresa_id)
        itens = [{'descricao': i.descricao, 'quantidade': i.quantidade,
                   'preco_unitario': i.preco_unitario, 'tipo': i.tipo} for i in p.itens]
        etapas = [{'titulo': e.titulo, 'descricao': e.descricao, 'duracao_dias': e.duracao_dias}
                   for e in sorted(p.etapas, key=lambda x: x.ordem)] if p.etapas else []
        total = _valor_total_proposta(p)
        cliente_nome = p.cliente.nome if p.cliente else '?'
        link_pub = f"{request.host_url.rstrip('/')}/proposta/view/{p.token_publico}"

        msg_cliente  = f"Olá, {cliente_nome}! Esperamos que esteja bem.\n\n"
        msg_cliente += f"Segue a proposta comercial para o serviço solicitado.\n"
        msg_cliente += f"Abaixo as informações:\n\n"
        msg_cliente += f"📄 Proposta: {p.numero}\n"
        msg_cliente += f"💰 Valor total: {fmt(total)}\n"
        if p.forma_pagamento:
            msg_cliente += f"💳 Pagamento: {p.forma_pagamento}\n"
        msg_cliente += f"📅 Validade: {p.validade} dias\n\n"
        msg_cliente += f"🔗 Para visualizar e aprovar a proposta, acesse:\n{link_pub}\n\n"
        msg_cliente += f"No final da página, você pode assinar autorizando o serviço e efetuar o pagamento.\n\n"
        msg_cliente += f"Qualquer dúvida, estou à disposição!"

        enviar_mensagem_telegram(f"✅ *Proposta {p.numero} criada!*\n\n_Mensagem pronta para encaminhar ao cliente:_")
        enviar_mensagem_telegram(msg_cliente)

        buf = gerar_proposta_pdf(modelo_para_dict(p), modelo_para_dict(emp),
                                  modelo_para_dict(p.cliente), itens, etapas=etapas)
        pdf_bytes = buf.getvalue() if hasattr(buf, 'getvalue') else buf.read()
        enviar_documento_telegram(pdf_bytes, f"Proposta_{p.numero.replace('-','_')}.pdf",
                                   caption=f"📎 PDF da proposta {p.numero}")
    except Exception as e:
        logger.warning(f'[PROPOSTA] falha ao notificar Telegram da criação da proposta {p.numero}: {e}')


def _infinitypay_confirmar_pagamento(p, transaction_nsu, slug):
    """Confirma de fato (via payment_check, servidor a servidor) um
    pagamento InfinitePay antes de marcar a proposta como paga -- nunca
    confia direto em parâmetros vindos do navegador ou de um webhook sem
    assinatura verificável."""
    try:
        handle = Integracao.obter('INFINITYPAY_HANDLE', '')
        if not handle:
            return
        if p.mp_payment_id == str(transaction_nsu):
            return  # já processado
        dados, erro = infinitypay_integracao.verificar_pagamento(handle, p.numero, transaction_nsu, slug)
        if erro or not dados:
            logger.warning(f'[INFINITYPAY] payment_check falhou pra proposta {p.numero}: {erro}')
            return
        aprovado = dados.get('paid') is True or str(dados.get('status', '')).lower() in ('paid', 'approved', 'success')
        if not aprovado:
            return
        valor_centavos = dados.get('amount') or dados.get('paid_amount')
        valor = round(float(valor_centavos) / 100, 2) if valor_centavos else _valor_restante_proposta(p)
        _registrar_pagamento_proposta(p, valor, str(transaction_nsu))
    except Exception as e:
        logger.error(f'[INFINITYPAY] erro confirmando pagamento da proposta {p.numero}: {e}')


@app.route('/webhook/infinitypay', methods=['POST'])
@csrf.exempt
def webhook_infinitypay():
    """Recebe a notificação de pagamento aprovado da InfinitePay. A
    InfinitePay não documenta um esquema de assinatura pra esse webhook
    (diferente do MP), então NUNCA confiamos direto no corpo -- só usamos
    ele como gatilho pra perguntar de verdade pro payment_check deles com
    os identificadores recebidos; só marca como pago se a própria API da
    InfinitePay confirmar."""
    body = request.get_json(silent=True) or {}
    order_nsu = body.get('order_nsu') or body.get('nsu')
    transaction_nsu = body.get('transaction_nsu')
    slug = body.get('slug')
    if not order_nsu or not transaction_nsu or not slug:
        return jsonify({'ok': True}), 200
    try:
        p = Proposta.query.filter_by(numero=str(order_nsu)).first()
        if p:
            _infinitypay_confirmar_pagamento(p, transaction_nsu, slug)
    except Exception as e:
        logger.error(f'[INFINITYPAY-WEBHOOK] erro processando order_nsu {order_nsu}: {e}')
    return jsonify({'ok': True}), 200


def _mp_processar_preapproval(preapproval_id, mp):
    preapproval = mp_integracao.buscar_preapproval(preapproval_id, mp['access_token'])
    if not preapproval:
        logger.warning(f'[MP-WEBHOOK] não consegui buscar o preapproval {preapproval_id} na API do MP')
        return

    chave = (preapproval.get('external_reference') or '').strip().upper()
    lic = LicencaNeuraDesk.query.filter_by(chave=chave).first()
    if not lic:
        logger.warning(f'[MP-WEBHOOK] preapproval {preapproval_id} referencia licença desconhecida: {chave!r}')
        return

    lic.mp_preapproval_id = str(preapproval_id)
    lic.mp_status = preapproval.get('status')
    db.session.commit()


@app.route('/api/licencas/ativar', methods=['POST'])
@csrf.exempt
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
@csrf.exempt
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


# ─── GESTÃO PESSOAL ────────────────────────────────────────────────────────────
# Controle de gastos pessoais do dono do sistema (cartões, recorrentes,
# parcelados e gastos fixos mensais) -- substitui a planilha GASTOS.xlsx.
# Restrito ao super_admin porque é finanças pessoais, não da empresa/cliente.
def _mes_parse(mes_str):
    try:
        return datetime.strptime(mes_str, '%Y-%m').date()
    except (TypeError, ValueError):
        return date.today().replace(day=1)

def _mes_vizinho(ref, delta):
    mes = ref.month - 1 + delta
    ano = ref.year + mes // 12
    mes = mes % 12 + 1
    return date(ano, mes, 1)

@app.route('/pessoal')
@login_required
@super_admin_required
def dashboard_pessoal():
    u = get_current_user()
    mes_explicito = request.args.get('mes')
    ref = _mes_parse(mes_explicito) if mes_explicito else date.today().replace(day=1)
    mes_str = ref.strftime('%Y-%m')

    gastos = GastoPessoal.query.filter_by(usuario_id=u.id).all()
    gastos_carro = GastoCarro.query.filter_by(usuario_id=u.id).all()
    gastos_casa = GastoCasa.query.filter_by(usuario_id=u.id).all()
    revisoes_todas = RevisaoCarro.query.filter_by(usuario_id=u.id).all()
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(CartaoPessoal.nome).all()

    fixos = sorted([g for g in gastos if g.tipo == 'fixo' and g.conta_no_mes(ref)], key=lambda g: g.descricao)
    total_fixos = sum(g.valor for g in fixos)

    por_cartao = []
    total_cartoes = 0.0
    for c in cartoes:
        # sem mês explícito na URL, usa o ciclo de fatura corrente do
        # cartão (considera o dia de fechamento) em vez do mês calendário
        # cru -- evita mostrar a parcela do mês seguinte antes da fatura
        # atual realmente fechar.
        ref_cartao = ref if mes_explicito else c.ciclo_atual()
        do_cartao = [g for g in gastos if g.cartao_id == c.id and g.conta_no_mes(ref_cartao)]
        do_cartao_carro = [g for g in gastos_carro if g.cartao_id == c.id and g.conta_no_mes(ref_cartao)]
        do_cartao_casa = [g for g in gastos_casa if g.cartao_id == c.id and g.conta_no_mes(ref_cartao)]
        do_cartao_revisoes = [r for r in revisoes_todas if r.cartao_id == c.id and r.conta_no_mes(ref_cartao)]
        subtotal = (sum(g.valor for g in do_cartao) + sum(g.valor_parcela() for g in do_cartao_carro)
                    + sum(g.valor_parcela() for g in do_cartao_casa) + sum(r.valor_parcela() for r in do_cartao_revisoes))
        total_cartoes += subtotal
        ocupado = _ocupado_cartao(c, gastos, ref_cartao)
        por_cartao.append({
            'cartao': c,
            'avista': [g for g in do_cartao if g.tipo == 'avista'],
            'recorrentes': [g for g in do_cartao if g.tipo == 'recorrente'],
            'parcelados': [g for g in do_cartao if g.tipo == 'parcelado'],
            'gastos_carro': do_cartao_carro,
            'gastos_casa': do_cartao_casa,
            'revisoes': do_cartao_revisoes,
            'subtotal': subtotal,
            'ocupado': ocupado,
            'livre': (c.limite - ocupado) if c.limite else None,
            'perc': min(ocupado / c.limite * 100, 100) if c.limite else None,
        })

    rendas = RendaPessoal.query.filter_by(usuario_id=u.id).all()
    rendas_mes = sorted([r for r in rendas if r.conta_no_mes(ref)], key=lambda r: r.descricao)
    total_receitas = sum(r.valor for r in rendas_mes)
    total_geral = total_fixos + total_cartoes
    saldo = total_receitas - total_geral
    total_a_quitar = sum(g.valor_restante(ref) for g in gastos if g.tipo == 'parcelado' and g.ativo)

    return render_template('gestao_pessoal_dashboard.html',
        total_a_quitar=total_a_quitar,
        mes_str=mes_str, mes_ref=ref,
        mes_prev=_mes_vizinho(ref, -1).strftime('%Y-%m'),
        mes_next=_mes_vizinho(ref, 1).strftime('%Y-%m'),
        fixos=fixos, total_fixos=total_fixos,
        por_cartao=por_cartao, total_cartoes=total_cartoes,
        total_geral=total_geral,
        rendas_mes=rendas_mes, total_receitas=total_receitas, saldo=saldo)

@app.route('/pessoal/lancamentos')
@login_required
@super_admin_required
def listar_gastos_pessoais():
    u = get_current_user()
    tipo_f = request.args.get('tipo') or ''
    q = GastoPessoal.query.filter_by(usuario_id=u.id)
    if tipo_f:
        q = q.filter_by(tipo=tipo_f)
    gastos = q.order_by(GastoPessoal.tipo, GastoPessoal.descricao).all()
    return render_template('gestao_pessoal_lancamentos.html', gastos=gastos, tipo_f=tipo_f, hoje=date.today())

def _preencher_gasto_form(g, u):
    tipo = request.form.get('tipo', 'fixo')
    g.tipo      = tipo
    g.descricao = request.form.get('descricao', '').strip()
    g.valor     = float((request.form.get('valor') or '0').replace(',', '.'))
    g.cartao_id = int(request.form['cartao_id']) if tipo != 'fixo' and request.form.get('cartao_id') else None
    g.mes_referencia = request.form.get('mes_referencia') if tipo == 'avista' else None
    if tipo == 'parcelado':
        dpp = request.form.get('data_primeira_parcela')
        g.data_primeira_parcela = datetime.strptime(dpp, '%Y-%m-%d').date() if dpp else None
        g.parcela_total = int(request.form.get('parcela_total') or 0)
    else:
        g.data_primeira_parcela = None
        g.parcela_total = None

@app.route('/pessoal/lancamentos/novo', methods=['GET', 'POST'])
@login_required
@super_admin_required
def novo_gasto_pessoal():
    u = get_current_user()
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(CartaoPessoal.nome).all()
    if request.method == 'POST':
        g = GastoPessoal(usuario_id=u.id, ativo=True)
        _preencher_gasto_form(g, u)
        db.session.add(g)
        db.session.commit()
        flash('Lançamento adicionado!', 'success')
        return redirect(url_for('listar_gastos_pessoais'))
    return render_template('form_gasto_pessoal.html', gasto=None, cartoes=cartoes, hoje=date.today().strftime('%Y-%m'))

@app.route('/pessoal/lancamentos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def editar_gasto_pessoal(id):
    u = get_current_user()
    g = GastoPessoal.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(CartaoPessoal.nome).all()
    if request.method == 'POST':
        _preencher_gasto_form(g, u)
        db.session.commit()
        flash('Lançamento atualizado!', 'success')
        return redirect(url_for('listar_gastos_pessoais'))
    return render_template('form_gasto_pessoal.html', gasto=g, cartoes=cartoes, hoje=date.today().strftime('%Y-%m'))

@app.route('/pessoal/lancamentos/<int:id>/toggle', methods=['POST'])
@login_required
@super_admin_required
def toggle_gasto_pessoal(id):
    u = get_current_user()
    g = GastoPessoal.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    g.ativo = not g.ativo
    db.session.commit()
    flash('Gasto reativado!' if g.ativo else 'Gasto marcado como quitado/cancelado.', 'success')
    return redirect(request.referrer or url_for('listar_gastos_pessoais'))

@app.route('/pessoal/lancamentos/<int:id>/excluir', methods=['POST'])
@login_required
@super_admin_required
def excluir_gasto_pessoal(id):
    u = get_current_user()
    g = GastoPessoal.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    db.session.delete(g)
    db.session.commit()
    flash('Lançamento excluído!', 'success')
    return redirect(url_for('listar_gastos_pessoais'))

def _ocupado_cartao(c, gastos, ref_cartao=None):
    ref_cartao = ref_cartao or c.ciclo_atual()
    gastos_carro_cartao = GastoCarro.query.filter_by(usuario_id=c.usuario_id, cartao_id=c.id).all()
    gastos_casa_cartao = GastoCasa.query.filter_by(usuario_id=c.usuario_id, cartao_id=c.id).all()
    revisoes_cartao = RevisaoCarro.query.filter_by(usuario_id=c.usuario_id, cartao_id=c.id).all()
    return (
        sum(g.valor for g in gastos if g.cartao_id == c.id and g.tipo in ('recorrente', 'avista') and g.conta_no_mes(ref_cartao))
        + sum(g.valor * g.parcelas_restantes(ref_cartao)
              for g in gastos if g.cartao_id == c.id and g.tipo == 'parcelado' and g.ativo)
        + sum(g.valor_restante(ref_cartao) for g in gastos_carro_cartao)
        + sum(g.valor_restante(ref_cartao) for g in gastos_casa_cartao)
        + sum(g.valor_restante(ref_cartao) for g in revisoes_cartao)
    )

@app.route('/pessoal/cartoes')
@login_required
@super_admin_required
def listar_cartoes_pessoais():
    u = get_current_user()
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id).order_by(CartaoPessoal.nome).all()
    gastos = GastoPessoal.query.filter_by(usuario_id=u.id).all()
    resumo = []
    for c in cartoes:
        ocupado = _ocupado_cartao(c, gastos)
        resumo.append({
            'cartao': c, 'ocupado': ocupado,
            'livre': (c.limite - ocupado) if c.limite else None,
            'perc': min(ocupado / c.limite * 100, 100) if c.limite else None,
        })
    return render_template('gestao_pessoal_cartoes.html', resumo=resumo)

def _preencher_cartao_form(c):
    c.nome           = request.form.get('nome', '').strip()
    c.limite         = float((request.form.get('limite') or '0').replace(',', '.'))
    c.dia_fechamento = int(request.form.get('dia_fechamento') or 1)
    c.cor            = request.form.get('cor') or '#64748b'

@app.route('/pessoal/cartoes/novo', methods=['GET', 'POST'])
@login_required
@super_admin_required
def novo_cartao_pessoal():
    if request.method == 'POST':
        c = CartaoPessoal(usuario_id=get_current_user().id)
        _preencher_cartao_form(c)
        db.session.add(c)
        db.session.commit()
        flash('Cartão adicionado!', 'success')
        return redirect(url_for('listar_cartoes_pessoais'))
    return render_template('form_cartao_pessoal.html', cartao=None)

@app.route('/pessoal/cartoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def editar_cartao_pessoal(id):
    u = get_current_user()
    c = CartaoPessoal.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    if request.method == 'POST':
        _preencher_cartao_form(c)
        c.ativo = bool(request.form.get('ativo'))
        db.session.commit()
        flash('Cartão atualizado!', 'success')
        return redirect(url_for('listar_cartoes_pessoais'))
    return render_template('form_cartao_pessoal.html', cartao=c)

@app.route('/pessoal/rendas')
@login_required
@super_admin_required
def listar_rendas_pessoais():
    u = get_current_user()
    rendas = RendaPessoal.query.filter_by(usuario_id=u.id).order_by(RendaPessoal.tipo, RendaPessoal.descricao).all()
    return render_template('gestao_pessoal_rendas.html', rendas=rendas, hoje=date.today())

def _preencher_renda_form(r):
    tipo = request.form.get('tipo', 'fixa')
    r.tipo            = tipo
    r.descricao       = request.form.get('descricao', '').strip()
    r.valor           = float((request.form.get('valor') or '0').replace(',', '.'))
    r.dia_recebimento = int(request.form['dia_recebimento']) if tipo == 'fixa' and request.form.get('dia_recebimento') else None
    r.mes_referencia  = request.form.get('mes_referencia') if tipo == 'extra' else None

@app.route('/pessoal/rendas/novo', methods=['GET', 'POST'])
@login_required
@super_admin_required
def nova_renda_pessoal():
    if request.method == 'POST':
        r = RendaPessoal(usuario_id=get_current_user().id, ativo=True)
        _preencher_renda_form(r)
        db.session.add(r)
        db.session.commit()
        flash('Renda adicionada!', 'success')
        return redirect(url_for('listar_rendas_pessoais'))
    return render_template('form_renda_pessoal.html', renda=None, hoje=date.today().strftime('%Y-%m'))

@app.route('/pessoal/rendas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def editar_renda_pessoal(id):
    u = get_current_user()
    r = RendaPessoal.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    if request.method == 'POST':
        _preencher_renda_form(r)
        db.session.commit()
        flash('Renda atualizada!', 'success')
        return redirect(url_for('listar_rendas_pessoais'))
    return render_template('form_renda_pessoal.html', renda=r, hoje=date.today().strftime('%Y-%m'))

@app.route('/pessoal/rendas/<int:id>/toggle', methods=['POST'])
@login_required
@super_admin_required
def toggle_renda_pessoal(id):
    u = get_current_user()
    r = RendaPessoal.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    r.ativo = not r.ativo
    db.session.commit()
    flash('Renda reativada!' if r.ativo else 'Renda desativada.', 'success')
    return redirect(request.referrer or url_for('listar_rendas_pessoais'))

@app.route('/pessoal/rendas/<int:id>/excluir', methods=['POST'])
@login_required
@super_admin_required
def excluir_renda_pessoal(id):
    u = get_current_user()
    r = RendaPessoal.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    db.session.delete(r)
    db.session.commit()
    flash('Renda excluída!', 'success')
    return redirect(url_for('listar_rendas_pessoais'))


# ─── GASTOS COM O CARRO (Gestão Pessoal) ───────────────────────────────────────
NFE_NS = '{http://www.portalfiscal.inf.br/nfe}'
_FORMAS_PAGAMENTO_NFE = {
    '01': 'Dinheiro', '02': 'Cheque', '03': 'Cartão de Crédito', '04': 'Cartão de Débito',
    '05': 'Crédito Loja', '10': 'Vale Alimentação', '11': 'Vale Refeição', '12': 'Vale Presente',
    '13': 'Vale Combustível', '15': 'Boleto', '16': 'Depósito Bancário', '17': 'PIX',
    '18': 'Transferência Bancária', '19': 'Fidelidade', '90': 'Sem Pagamento', '99': 'Outros',
}
_PALAVRAS_COMBUSTIVEL = ('GASOLINA', 'ETANOL', 'ALCOOL', 'ÁLCOOL', 'DIESEL', 'GNV', 'ARLA')
# Opções fixas de forma de pagamento (campo vira <select>, não texto livre)
# -- inclui todos os valores que o import de XML pode gerar (ver
# _FORMAS_PAGAMENTO_NFE acima) pra nunca ficar um gasto importado com um
# valor que não bate com nenhuma opção do dropdown.
FORMAS_PAGAMENTO_CARRO = ['Dinheiro', 'PIX'] + sorted(
    v for v in set(_FORMAS_PAGAMENTO_NFE.values()) if v not in ('Dinheiro', 'PIX'))


def _parse_nfe_xml(conteudo):
    """Extrai os dados relevantes de um XML de NFe/NFC-e (posto, oficina,
    etc). Aceita tanto o XML "puro" (root <NFe>) quanto o processado
    (root <nfeProc>, com <protNFe> junto). Levanta ValueError se não
    conseguir reconhecer a estrutura."""
    root = ET.fromstring(conteudo)
    inf_nfe = root.find(f'.//{NFE_NS}infNFe')
    if inf_nfe is None:
        raise ValueError('XML não parece ser uma NFe/NFC-e válida (tag infNFe não encontrada).')

    chave = (inf_nfe.get('Id') or '').replace('NFe', '').strip()
    ide   = inf_nfe.find(f'{NFE_NS}ide')
    emit  = inf_nfe.find(f'{NFE_NS}emit')
    total = inf_nfe.find(f'{NFE_NS}total/{NFE_NS}ICMSTot')
    pag   = inf_nfe.find(f'{NFE_NS}pag')

    dh_emi = (ide.findtext(f'{NFE_NS}dhEmi') or ide.findtext(f'{NFE_NS}dEmi')) if ide is not None else None
    try:
        data_nota = datetime.fromisoformat(dh_emi[:19]).date() if dh_emi else date.today()
    except ValueError:
        data_nota = date.today()

    nome_emit  = emit.findtext(f'{NFE_NS}xNome') if emit is not None else ''
    v_nf       = float((total.findtext(f'{NFE_NS}vNF') if total is not None else None) or 0)
    n_nf       = ide.findtext(f'{NFE_NS}nNF') if ide is not None else ''

    itens, litros, eh_combustivel = [], 0.0, False
    for det in inf_nfe.findall(f'{NFE_NS}det'):
        prod = det.find(f'{NFE_NS}prod')
        if prod is None:
            continue
        x_prod = prod.findtext(f'{NFE_NS}xProd') or ''
        q_com  = float(prod.findtext(f'{NFE_NS}qCom') or 0)
        v_prod = float(prod.findtext(f'{NFE_NS}vProd') or 0)
        u_com  = prod.findtext(f'{NFE_NS}uCom') or ''
        itens.append({'descricao': x_prod, 'qtd': q_com, 'unidade': u_com, 'valor': v_prod})
        if any(p in x_prod.upper() for p in _PALAVRAS_COMBUSTIVEL):
            eh_combustivel = True
            litros += q_com

    forma_pagamento = ''
    if pag is not None:
        det_pag = pag.find(f'{NFE_NS}detPag')
        if det_pag is not None:
            t_pag = det_pag.findtext(f'{NFE_NS}tPag')
            forma_pagamento = _FORMAS_PAGAMENTO_NFE.get(t_pag, t_pag or '')

    descricao = nome_emit or (itens[0]['descricao'] if itens else 'Compra')

    return {
        'chave_nfe': chave or None, 'data': data_nota, 'valor': v_nf, 'numero_nota': n_nf,
        'posto_estabelecimento': nome_emit, 'descricao': descricao, 'itens': itens,
        'tipo_sugerido': 'combustivel' if eh_combustivel else 'outro',
        'litros': round(litros, 2) if eh_combustivel else None,
        'forma_pagamento': forma_pagamento,
    }


@app.route('/pessoal/carro')
@login_required
@super_admin_required
def listar_gastos_carro():
    u = get_current_user()
    tipo_f = request.args.get('tipo') or ''
    q = GastoCarro.query.filter_by(usuario_id=u.id)
    if tipo_f:
        q = q.filter_by(tipo=tipo_f)
    gastos = q.order_by(GastoCarro.data.desc(), GastoCarro.id.desc()).all()

    total_geral = sum(g.valor for g in gastos)
    total_combustivel = sum(g.valor for g in gastos if g.tipo == 'combustivel')
    total_litros = sum(g.litros or 0 for g in gastos if g.tipo == 'combustivel')
    por_tipo = {}
    for g in gastos:
        por_tipo.setdefault(g.tipo, 0)
        por_tipo[g.tipo] += g.valor

    # Consumo (km/L) -- usa TODO o histórico de combustível (independe do
    # filtro de tipo da tela), método "cheio a cheio" ANCORADO em tanque
    # cheio: só fecha uma medição entre dois abastecimentos que realmente
    # encheram o tanque, somando os litros de qualquer abastecimento
    # parcial (top-off preventivo) no meio -- assim um "completei antes de
    # viajar" não gera um consumo falso, só engorda o litro do próximo
    # fechamento de verdade.
    combustiveis = GastoCarro.query.filter_by(usuario_id=u.id, tipo='combustivel')\
        .filter(GastoCarro.litros.isnot(None))\
        .order_by(GastoCarro.data, GastoCarro.id).all()
    pares = []
    ancora_km = None
    litros_acumulados = 0.0
    for g in combustiveis:
        litros_acumulados += (g.litros or 0)
        if g.tanque_cheio and g.km_atual is not None:
            if ancora_km is not None:
                dist = g.km_atual - ancora_km
                if dist > 0 and litros_acumulados > 0:
                    pares.append((dist, litros_acumulados))
            ancora_km = g.km_atual
            litros_acumulados = 0.0
    media_geral_kml = (sum(d for d, _ in pares) / sum(l for _, l in pares)) if pares else None
    media_ultima_kml = (pares[-1][0] / pares[-1][1]) if pares else None

    # Total de parcelas do mês -- só compras no cartão que estão parceladas
    # (independe do filtro de tipo da tela, é sempre o quadro completo).
    hoje = date.today()
    parcelados_no_cartao = GastoCarro.query.filter_by(usuario_id=u.id).filter(
        GastoCarro.cartao_id.isnot(None), GastoCarro.parcela_total.isnot(None)).all()
    total_parcelas_mes = sum(g.valor_parcela() for g in parcelados_no_cartao
                              if g.parcela_total > 1 and g.conta_no_mes(hoje))

    return render_template('gestao_pessoal_carro.html', gastos=gastos, tipo_f=tipo_f,
        total_geral=total_geral, total_combustivel=total_combustivel,
        total_litros=total_litros, por_tipo=por_tipo,
        media_geral_kml=media_geral_kml, media_ultima_kml=media_ultima_kml,
        total_parcelas_mes=total_parcelas_mes)

def _preencher_gasto_carro_form(g):
    g.tipo = request.form.get('tipo', 'outro')
    g.descricao = request.form.get('descricao', '').strip()
    g.valor = float((request.form.get('valor') or '0').replace(',', '.'))
    data_str = request.form.get('data')
    g.data = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()
    g.km_atual = int(request.form['km_atual']) if request.form.get('km_atual') else None
    g.litros = float(request.form['litros'].replace(',', '.')) if g.tipo == 'combustivel' and request.form.get('litros') else None
    g.tanque_cheio = bool(request.form.get('tanque_cheio')) if g.tipo == 'combustivel' else True
    g.posto_estabelecimento = request.form.get('posto_estabelecimento', '').strip()
    g.forma_pagamento = request.form.get('forma_pagamento', '').strip()
    g.cartao_id = int(request.form['cartao_id']) if request.form.get('cartao_id') else None
    g.parcela_total = int(request.form['parcela_total']) if request.form.get('parcela_total') else None

@app.route('/pessoal/carro/novo', methods=['GET', 'POST'])
@login_required
@super_admin_required
def novo_gasto_carro():
    u = get_current_user()
    if request.method == 'POST':
        g = GastoCarro(usuario_id=u.id, origem='manual')
        _preencher_gasto_carro_form(g)
        db.session.add(g)
        db.session.commit()
        flash('Gasto com o carro adicionado!', 'success')
        return redirect(url_for('listar_gastos_carro'))
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(CartaoPessoal.nome).all()
    return render_template('form_gasto_carro.html', gasto=None, cartoes=cartoes,
        formas_pagamento=FORMAS_PAGAMENTO_CARRO, hoje=date.today().strftime('%Y-%m-%d'))

@app.route('/pessoal/carro/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def editar_gasto_carro(id):
    u = get_current_user()
    g = GastoCarro.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    if request.method == 'POST':
        _preencher_gasto_carro_form(g)
        db.session.commit()
        flash('Gasto atualizado!', 'success')
        return redirect(url_for('listar_gastos_carro'))
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(CartaoPessoal.nome).all()
    return render_template('form_gasto_carro.html', gasto=g, cartoes=cartoes,
        formas_pagamento=FORMAS_PAGAMENTO_CARRO, hoje=g.data.strftime('%Y-%m-%d'))

@app.route('/pessoal/carro/<int:id>/excluir', methods=['POST'])
@login_required
@super_admin_required
def excluir_gasto_carro(id):
    u = get_current_user()
    g = GastoCarro.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    if g.arquivo_xml:
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'gastos_carro', g.arquivo_xml)
        try:
            os.remove(caminho)
        except OSError:
            pass
    db.session.delete(g)
    db.session.commit()
    flash('Gasto excluído!', 'success')
    return redirect(url_for('listar_gastos_carro'))

@app.route('/pessoal/carro/importar-xml', methods=['GET', 'POST'])
@login_required
@super_admin_required
def importar_xml_carro():
    if request.method == 'POST':
        arquivos = request.files.getlist('arquivos_xml')
        u = get_current_user()
        importados, duplicados, com_erro = 0, 0, []
        pasta = os.path.join(app.config['UPLOAD_FOLDER'], 'gastos_carro')
        os.makedirs(pasta, exist_ok=True)
        for f in arquivos:
            if not f or not f.filename:
                continue
            try:
                conteudo = f.read()
                dados = _parse_nfe_xml(conteudo)
                if dados['chave_nfe'] and GastoCarro.query.filter_by(
                        usuario_id=u.id, chave_nfe=dados['chave_nfe']).first():
                    duplicados += 1
                    continue
                nome_arquivo = f"{(dados['chave_nfe'] or uuid.uuid4().hex)}.xml"
                with open(os.path.join(pasta, nome_arquivo), 'wb') as out:
                    out.write(conteudo)
                g = GastoCarro(
                    usuario_id=u.id, origem='xml', tipo=dados['tipo_sugerido'],
                    data=dados['data'], descricao=dados['descricao'], valor=dados['valor'],
                    litros=dados['litros'], posto_estabelecimento=dados['posto_estabelecimento'],
                    forma_pagamento=dados['forma_pagamento'], numero_nota=dados['numero_nota'],
                    chave_nfe=dados['chave_nfe'], itens_json=json.dumps(dados['itens'], ensure_ascii=False),
                    arquivo_xml=nome_arquivo)
                db.session.add(g)
                db.session.commit()
                importados += 1
            except Exception as e:
                db.session.rollback()
                logger.exception(f'Erro importando XML de carro "{f.filename}"')
                com_erro.append(f'{f.filename}: {e}')
                continue
        msg = f'{importados} nota(s) importada(s).'
        if duplicados:
            msg += f' {duplicados} já tinham sido importada(s) antes (ignoradas).'
        if com_erro:
            msg += f' {len(com_erro)} com erro: {"; ".join(com_erro[:3])}'
        flash(msg, 'success' if importados else 'warning')
        return redirect(url_for('listar_gastos_carro'))
    return render_template('importar_xml_carro.html')


# ─── GASTOS DA CASA (Gestão Pessoal) ───────────────────────────────────────────
ROTULOS_GASTO_CASA = {'mercado': 'Mercado', 'hortifruti': 'Hortifruti', 'acougue': 'Açougue',
                      'manutencao': 'Manutenção da Casa', 'bebe': 'Bebê', 'outro': 'Outro'}

@app.route('/pessoal/casa')
@login_required
@super_admin_required
def listar_gastos_casa():
    u = get_current_user()
    tipo_f = request.args.get('tipo') or ''
    q = GastoCasa.query.filter_by(usuario_id=u.id)
    if tipo_f:
        q = q.filter_by(tipo=tipo_f)
    gastos = q.order_by(GastoCasa.data.desc(), GastoCasa.id.desc()).all()

    total_geral = sum(g.valor for g in gastos)
    por_tipo = {}
    for g in gastos:
        por_tipo.setdefault(g.tipo, 0)
        por_tipo[g.tipo] += g.valor

    hoje = date.today()
    parcelados_no_cartao = GastoCasa.query.filter_by(usuario_id=u.id).filter(
        GastoCasa.cartao_id.isnot(None), GastoCasa.parcela_total.isnot(None)).all()
    total_parcelas_mes = sum(g.valor_parcela() for g in parcelados_no_cartao
                              if g.parcela_total > 1 and g.conta_no_mes(hoje))

    return render_template('gestao_pessoal_casa.html', gastos=gastos, tipo_f=tipo_f,
        rotulos=ROTULOS_GASTO_CASA, total_geral=total_geral, por_tipo=por_tipo,
        total_parcelas_mes=total_parcelas_mes)

def _preencher_gasto_casa_form(g):
    g.tipo = request.form.get('tipo', 'outro')
    g.descricao = request.form.get('descricao', '').strip()
    data_str = request.form.get('data')
    g.data = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()
    g.estabelecimento = request.form.get('estabelecimento', '').strip()
    g.forma_pagamento = request.form.get('forma_pagamento', '').strip()
    g.cartao_id = int(request.form['cartao_id']) if request.form.get('cartao_id') else None
    g.parcela_total = int(request.form['parcela_total']) if request.form.get('parcela_total') else None

    descs = request.form.getlist('item_desc[]')
    qtds = request.form.getlist('item_qtd[]')
    valores = request.form.getlist('item_valor[]')
    itens = []
    for i, desc in enumerate(descs):
        if not desc.strip():
            continue
        qtd = float((qtds[i] if i < len(qtds) else '1').replace(',', '.') or 1)
        valor_unit = float((valores[i] if i < len(valores) else '0').replace(',', '.') or 0)
        itens.append({'descricao': desc.strip(), 'qtd': qtd, 'unidade': '', 'valor': round(qtd * valor_unit, 2)})

    if itens:
        g.itens_json = json.dumps(itens, ensure_ascii=False)
        g.valor = round(sum(it['valor'] for it in itens), 2)
    else:
        g.itens_json = None
        g.valor = float((request.form.get('valor') or '0').replace(',', '.'))

@app.route('/pessoal/casa/novo', methods=['GET', 'POST'])
@login_required
@super_admin_required
def novo_gasto_casa():
    u = get_current_user()
    if request.method == 'POST':
        g = GastoCasa(usuario_id=u.id, origem='manual')
        _preencher_gasto_casa_form(g)
        db.session.add(g)
        db.session.commit()
        flash('Gasto da casa adicionado!', 'success')
        return redirect(url_for('listar_gastos_casa'))
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(CartaoPessoal.nome).all()
    return render_template('form_gasto_casa.html', gasto=None, cartoes=cartoes,
        rotulos=ROTULOS_GASTO_CASA, formas_pagamento=FORMAS_PAGAMENTO_CARRO,
        hoje=date.today().strftime('%Y-%m-%d'))

@app.route('/pessoal/casa/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def editar_gasto_casa(id):
    u = get_current_user()
    g = GastoCasa.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    if request.method == 'POST':
        _preencher_gasto_casa_form(g)
        db.session.commit()
        flash('Gasto atualizado!', 'success')
        return redirect(url_for('listar_gastos_casa'))
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(CartaoPessoal.nome).all()
    return render_template('form_gasto_casa.html', gasto=g, cartoes=cartoes,
        rotulos=ROTULOS_GASTO_CASA, formas_pagamento=FORMAS_PAGAMENTO_CARRO,
        hoje=g.data.strftime('%Y-%m-%d'))

@app.route('/pessoal/casa/<int:id>/excluir', methods=['POST'])
@login_required
@super_admin_required
def excluir_gasto_casa(id):
    u = get_current_user()
    g = GastoCasa.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    if g.arquivo_xml:
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'gastos_casa', g.arquivo_xml)
        try:
            os.remove(caminho)
        except OSError:
            pass
    db.session.delete(g)
    db.session.commit()
    flash('Gasto excluído!', 'success')
    return redirect(url_for('listar_gastos_casa'))

@app.route('/pessoal/casa/importar-xml', methods=['GET', 'POST'])
@login_required
@super_admin_required
def importar_xml_casa():
    if request.method == 'POST':
        arquivos = request.files.getlist('arquivos_xml')
        u = get_current_user()
        importados, duplicados, com_erro = 0, 0, []
        pasta = os.path.join(app.config['UPLOAD_FOLDER'], 'gastos_casa')
        os.makedirs(pasta, exist_ok=True)
        for f in arquivos:
            if not f or not f.filename:
                continue
            try:
                conteudo = f.read()
                dados = _parse_nfe_xml(conteudo)
                if dados['chave_nfe'] and GastoCasa.query.filter_by(
                        usuario_id=u.id, chave_nfe=dados['chave_nfe']).first():
                    duplicados += 1
                    continue
                nome_arquivo = f"{(dados['chave_nfe'] or uuid.uuid4().hex)}.xml"
                with open(os.path.join(pasta, nome_arquivo), 'wb') as out:
                    out.write(conteudo)
                g = GastoCasa(
                    usuario_id=u.id, origem='xml', tipo='outro',
                    data=dados['data'], descricao=dados['descricao'], valor=dados['valor'],
                    estabelecimento=dados['posto_estabelecimento'],
                    forma_pagamento=dados['forma_pagamento'], numero_nota=dados['numero_nota'],
                    chave_nfe=dados['chave_nfe'], itens_json=json.dumps(dados['itens'], ensure_ascii=False),
                    arquivo_xml=nome_arquivo)
                db.session.add(g)
                db.session.commit()
                importados += 1
            except Exception as e:
                db.session.rollback()
                logger.exception(f'Erro importando XML de casa "{f.filename}"')
                com_erro.append(f'{f.filename}: {e}')
                continue
        msg = f'{importados} nota(s) importada(s).'
        if duplicados:
            msg += f' {duplicados} já tinham sido importada(s) antes (ignoradas).'
        if com_erro:
            msg += f' {len(com_erro)} com erro: {"; ".join(com_erro[:3])}'
        flash(msg, 'success' if importados else 'warning')
        return redirect(url_for('listar_gastos_casa'))
    return render_template('importar_xml_casa.html')


# ─── VEÍCULOS E REVISÕES (Gestão Pessoal) ──────────────────────────────────────
# Checklist de peças/serviços comuns de revisão -- conhecimento genérico de
# mecânica, NÃO é um catálogo de compatibilidade por veículo (isso é dado
# comercial fechado, tipo TecDoc, sem fonte aberta confiável pra baixar).
# Serve só de atalho pra digitar mais rápido -- a sugestão que realmente
# aprende com o carro do usuário vem do autocomplete pelo histórico dele
# (ver `_pecas_sugeridas_veiculo` abaixo).
PECAS_SERVICOS_COMUNS = [
    'Óleo do Motor', 'Filtro de Óleo', 'Filtro de Ar', 'Filtro de Cabine (Ar-Condicionado)',
    'Filtro de Combustível', 'Velas de Ignição', 'Cabos de Vela', 'Correia Dentada',
    'Correia do Alternador', 'Correia Poly-V', 'Tensor da Correia', 'Pastilha de Freio Dianteira',
    'Pastilha de Freio Traseira', 'Disco de Freio Dianteiro', 'Disco de Freio Traseiro',
    'Fluido de Freio (DOT)', 'Fluido de Arrefecimento (Aditivo)', 'Bateria', 'Amortecedor Dianteiro',
    'Amortecedor Traseiro', 'Kit de Embreagem', 'Bico Injetor', 'Bomba de Combustível', 'Radiador',
    'Mangueira do Radiador', 'Rolamento de Roda', 'Terminal de Direção', 'Bieleta',
    'Pivô de Suspensão', 'Alinhamento', 'Balanceamento', 'Troca de Pneu', 'Palheta do Limpador',
    'Junta Homocinética', 'Sonda Lambda (Sensor de Oxigênio)', 'Óleo do Câmbio', 'Mão de Obra',
]
_PALAVRAS_MAO_DE_OBRA = ('MAO DE OBRA', 'MÃO DE OBRA', 'SERVICO', 'SERVIÇO', 'INSTALACAO',
                          'INSTALAÇÃO', 'MONTAGEM', 'ALINHAMENTO', 'BALANCEAMENTO')

# Catálogo de itens de manutenção "de rotina" que valem a pena rastrear com
# intervalo (pra saber quando é a próxima). São intervalos de referência de
# mercado/manual genéricos -- não substituem o manual do proprietário do
# veículo específico, por isso ficam editáveis por registro (campo "Intervalo
# (KM)" que aparece ao marcar o checkbox no formulário de revisão). `cambios`
# = None quer dizer que se aplica a qualquer tipo_cambio; uma lista restringe
# (ex: fluido do atuador do robô só existe em câmbio automatizado Dualogic).
TIPOS_MANUTENCAO_RECORRENTE = [
    {'chave': 'oleo_motor',               'nome': 'Óleo do Motor',                          'km_padrao': 10000, 'meses_padrao': 12, 'cambios': None},
    {'chave': 'filtro_oleo',              'nome': 'Filtro de Óleo',                         'km_padrao': 10000, 'meses_padrao': 12, 'cambios': None},
    {'chave': 'filtro_ar',                'nome': 'Filtro de Ar',                           'km_padrao': 10000, 'meses_padrao': 12, 'cambios': None},
    {'chave': 'filtro_combustivel',       'nome': 'Filtro de Combustível',                  'km_padrao': 20000, 'meses_padrao': 24, 'cambios': None},
    {'chave': 'filtro_cabine',            'nome': 'Filtro de Cabine (Ar-Condicionado)',     'km_padrao': 15000, 'meses_padrao': 12, 'cambios': None},
    {'chave': 'velas',                    'nome': 'Velas de Ignição',                       'km_padrao': 30000, 'meses_padrao': 36, 'cambios': None},
    {'chave': 'correia_dentada',          'nome': 'Correia Dentada',                        'km_padrao': 60000, 'meses_padrao': 48, 'cambios': None},
    {'chave': 'fluido_freio',             'nome': 'Fluido de Freio (DOT)',                  'km_padrao': 20000, 'meses_padrao': 24, 'cambios': None},
    {'chave': 'alinhamento_balanceamento','nome': 'Alinhamento e Balanceamento',            'km_padrao': 10000, 'meses_padrao': 12, 'cambios': None},
    {'chave': 'troca_pneus',              'nome': 'Troca de Pneus',                         'km_padrao': 50000, 'meses_padrao': 60, 'cambios': None},
    {'chave': 'oleo_cambio',              'nome': 'Óleo do Câmbio',                         'km_padrao': 40000, 'meses_padrao': 48, 'cambios': None},
    {'chave': 'fluido_atuador_robo',      'nome': 'Fluido do Atuador do Robô (Dualogic)',   'km_padrao': 40000, 'meses_padrao': 48, 'cambios': ['dualogic']},
]

# Recomendação de óleo por tipo de câmbio -- pesquisado em fontes técnicas
# (Revista O Mecânico, guias de oficina) em 2026-08, não é dado oficial da
# fábrica. NÃO tem número fechado de intervalo pro fluido do robô Dualogic
# (a Fiat não divulga um padrão único) -- por isso o intervalo do sistema
# fica editável, e o texto abaixo já avisa isso.
INFO_CAMBIO = {
    'manual': {
        'nome': 'Manual',
        'oleo_caixa': 'Óleo de câmbio manual conforme especificação do fabricante (geralmente GL-4 ou GL-5 -- confira o manual do seu veículo).',
        'oleo_atuador': None, 'observacao': None, 'fontes': [],
    },
    'automatico': {
        'nome': 'Automático (conversor de torque)',
        'oleo_caixa': 'Fluido de câmbio automático (ATF) especificado pelo fabricante -- nunca use óleo de câmbio manual nele.',
        'oleo_atuador': None, 'observacao': None, 'fontes': [],
    },
    'cvt': {
        'nome': 'CVT',
        'oleo_caixa': 'Fluido CVT específico do fabricante -- fluido genérico/ATF comum pode danificar a variação contínua.',
        'oleo_atuador': None, 'observacao': None, 'fontes': [],
    },
    'dualogic': {
        'nome': 'Automatizado (Dualogic)',
        'oleo_caixa': 'Óleo de câmbio manual -- a caixa mecânica embaixo do robô é a mesma do câmbio manual do modelo. Confira no manual se o seu aceita GL-5, pois alguns Dualogic só toleram GL-4 (aditivos de GL-5 podem atacar componentes de cobre).',
        'oleo_atuador': 'Fluido hidráulico específico Petronas Tutela CS Speed, exclusivo pro atuador eletro-hidráulico -- não aceita substituto genérico.',
        'observacao': 'Não existe um intervalo oficial único e amplamente divulgado pela Fiat -- referências de oficina variam de ~40.000 km (uso severo) a ~120.000 km (uso normal). Ajuste o campo "Intervalo (KM)" ao marcar esse item na revisão conforme o manual do seu carro e a orientação de um mecânico de confiança.',
        'fontes': ['omecanico.com.br', 'pneuscarmg.com.br', 'oficinasbh.com'],
    },
    'outro': {'nome': 'Outro', 'oleo_caixa': None, 'oleo_atuador': None, 'observacao': None, 'fontes': []},
}

def _tipos_manutencao_aplicaveis(veiculo):
    return [t for t in TIPOS_MANUTENCAO_RECORRENTE if not t['cambios'] or veiculo.tipo_cambio in t['cambios']]

def _somar_meses(d, meses):
    m = d.month - 1 + meses
    ano = d.year + m // 12
    mes = m % 12 + 1
    dia = min(d.day, 28)
    return date(ano, mes, dia)

def _status_manutencoes(usuario_id, veiculo):
    """Pra cada item do catálogo que faz sentido nesse veículo, busca o
    último registro (o mais recente marcado numa revisão) e calcula
    quando é a próxima -- por KM (odômetro do veículo em relação ao
    último + intervalo) e por tempo, valendo o que vencer primeiro,
    igual uma revisão de verdade funciona."""
    resultado = []
    km_atual = veiculo.km_atual
    for t in _tipos_manutencao_aplicaveis(veiculo):
        # Ordena por ODÔMETRO (não por data) pra decidir qual é "o
        # último" -- KM só anda pra frente, então o registro com maior
        # odômetro É o mais recente de verdade. Empatando por data (ex:
        # duas revisões no mesmo dia, uma com o odômetro preenchido
        # certo e outra esquecida em 0) um desempate por id/data teria
        # 50% de chance de pegar o registro errado (com odômetro
        # zerado) e mostrar "vencido" por engano mesmo tendo acabado de
        # ser feito.
        ultimo = ManutencaoRecorrente.query.filter_by(
            usuario_id=usuario_id, veiculo_id=veiculo.id, tipo=t['chave']
        ).order_by(ManutencaoRecorrente.odometro.desc(), ManutencaoRecorrente.data.desc(),
                   ManutencaoRecorrente.id.desc()).first()
        item = {'chave': t['chave'], 'nome': t['nome'], 'km_padrao': t['km_padrao'],
                'meses_padrao': t['meses_padrao'], 'ultimo': ultimo, 'status': 'nunca'}
        if ultimo:
            km_intervalo = ultimo.intervalo_km or t['km_padrao']
            meses_intervalo = ultimo.intervalo_meses or t['meses_padrao']
            proxima_km = (ultimo.odometro + km_intervalo) if km_intervalo else None
            proxima_data = _somar_meses(ultimo.data, meses_intervalo) if meses_intervalo else None
            km_restante = (proxima_km - km_atual) if (proxima_km and km_atual) else None
            dias_restantes = (proxima_data - date.today()).days if proxima_data else None
            vencido = (km_restante is not None and km_restante <= 0) or (dias_restantes is not None and dias_restantes <= 0)
            perto = (km_restante is not None and km_intervalo and km_restante <= km_intervalo * 0.1) or \
                    (dias_restantes is not None and dias_restantes <= 30)
            item.update(
                proxima_km=proxima_km, proxima_data=proxima_data,
                km_restante=km_restante, dias_restantes=dias_restantes,
                status='vencido' if vencido else ('atencao' if perto else 'em_dia'))
        resultado.append(item)
    return resultado

def _pecas_sugeridas_veiculo(usuario_id, veiculo_id, limite=15):
    """Autocomplete que aprende com o histórico -- olha as peças já
    lançadas nas revisões desse veículo (mais usadas primeiro) e, se
    tiver pouca coisa ainda, completa com o checklist genérico."""
    contagem = {}
    revisoes = RevisaoCarro.query.filter_by(usuario_id=usuario_id, veiculo_id=veiculo_id).all()
    for r in revisoes:
        for it in r.itens():
            desc = (it.get('descricao') or '').strip()
            if desc:
                contagem[desc] = contagem.get(desc, 0) + 1
    do_historico = sorted(contagem, key=lambda d: -contagem[d])
    resto = [p for p in PECAS_SERVICOS_COMUNS if p not in contagem]
    return (do_historico + resto)[:limite]

@app.route('/pessoal/veiculos')
@login_required
@super_admin_required
def listar_veiculos():
    u = get_current_user()
    veiculos = VeiculoPessoal.query.filter_by(usuario_id=u.id).order_by(VeiculoPessoal.ativo.desc(), VeiculoPessoal.criado_em.desc()).all()
    return render_template('gestao_pessoal_veiculos.html', veiculos=veiculos)

def _preencher_veiculo_form(v):
    v.apelido = request.form.get('apelido', '').strip()
    v.marca = request.form.get('marca', '').strip()
    v.modelo = request.form.get('modelo', '').strip()
    v.ano_modelo = int(request.form['ano_modelo']) if request.form.get('ano_modelo') else None
    v.ano_fabricacao = int(request.form['ano_fabricacao']) if request.form.get('ano_fabricacao') else None
    v.placa = request.form.get('placa', '').strip().upper()
    v.cor = request.form.get('cor', '').strip()
    v.combustivel = request.form.get('combustivel', '').strip()
    v.km_atual = int(request.form['km_atual']) if request.form.get('km_atual') else None
    v.tipo_cambio = request.form.get('tipo_cambio', '').strip() or None

@app.route('/pessoal/veiculos/novo', methods=['GET', 'POST'])
@login_required
@super_admin_required
def novo_veiculo():
    if request.method == 'POST':
        v = VeiculoPessoal(usuario_id=get_current_user().id, ativo=True)
        _preencher_veiculo_form(v)
        db.session.add(v)
        db.session.commit()
        flash(f'{v.nome_exibicao()} cadastrado!', 'success')
        return redirect(url_for('listar_veiculos'))
    return render_template('form_veiculo.html', veiculo=None)

@app.route('/pessoal/veiculos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def editar_veiculo(id):
    u = get_current_user()
    v = VeiculoPessoal.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    if request.method == 'POST':
        _preencher_veiculo_form(v)
        v.ativo = bool(request.form.get('ativo'))
        db.session.commit()
        flash('Veículo atualizado!', 'success')
        return redirect(url_for('listar_veiculos'))
    return render_template('form_veiculo.html', veiculo=v)

@app.route('/pessoal/revisoes')
@login_required
@super_admin_required
def listar_revisoes():
    u = get_current_user()
    veiculos = VeiculoPessoal.query.filter_by(usuario_id=u.id).order_by(VeiculoPessoal.ativo.desc(), VeiculoPessoal.criado_em.desc()).all()
    if not veiculos:
        return render_template('gestao_pessoal_revisoes.html', veiculos=[], veiculo_atual=None, revisoes=[])

    veiculo_id = request.args.get('veiculo_id', type=int) or veiculos[0].id
    veiculo_atual = next((v for v in veiculos if v.id == veiculo_id), veiculos[0])

    todas = RevisaoCarro.query.filter_by(usuario_id=u.id, veiculo_id=veiculo_atual.id)\
        .order_by(RevisaoCarro.data.desc(), RevisaoCarro.id.desc()).all()
    # Notas importadas por XML que ainda não viraram revisão de verdade
    # (sem odômetro/motivo definidos) ficam separadas -- aparecem como
    # "pendentes" pra vincular a uma revisão, não entram nas contagens
    # de rotina/quebra nem na "última revisão" (odômetro=0 estragaria o
    # cálculo de km rodados desde então).
    pendentes = [r for r in todas if r.pendente]
    revisoes = [r for r in todas if not r.pendente]

    total_geral = sum(r.valor_total for r in todas)
    total_mao_de_obra = sum(r.mao_de_obra or 0 for r in todas)
    total_pecas = sum(r.valor_pecas() for r in todas)
    qtd_quebra = sum(1 for r in revisoes if r.motivo == 'quebra')
    qtd_rotina = sum(1 for r in revisoes if r.motivo == 'rotina')
    ultima = revisoes[0] if revisoes else None
    km_desde_ultima = None
    if ultima and veiculo_atual.km_atual:
        km_desde_ultima = veiculo_atual.km_atual - ultima.odometro

    status_manutencoes = _status_manutencoes(u.id, veiculo_atual)
    info_cambio = INFO_CAMBIO.get(veiculo_atual.tipo_cambio) if veiculo_atual.tipo_cambio else None
    manutencoes_por_revisao = {}
    if revisoes:
        nomes_tipo = {t['chave']: t['nome'] for t in TIPOS_MANUTENCAO_RECORRENTE}
        for m in ManutencaoRecorrente.query.filter(
                ManutencaoRecorrente.revisao_id.in_([r.id for r in revisoes])).all():
            manutencoes_por_revisao.setdefault(m.revisao_id, []).append(nomes_tipo.get(m.tipo, m.tipo))

    return render_template('gestao_pessoal_revisoes.html', veiculos=veiculos, veiculo_atual=veiculo_atual,
        revisoes=revisoes, pendentes=pendentes, total_geral=total_geral, total_mao_de_obra=total_mao_de_obra,
        total_pecas=total_pecas, qtd_quebra=qtd_quebra, qtd_rotina=qtd_rotina,
        ultima=ultima, km_desde_ultima=km_desde_ultima, status_manutencoes=status_manutencoes,
        info_cambio=info_cambio, manutencoes_por_revisao=manutencoes_por_revisao)

NOMES_MESES = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
    7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro',
}

def _texto_servico_revisao(r, nomes_manutencoes):
    """Monta o texto de "o que foi feito" nessa revisão pro resumo/PDF --
    prioriza as peças trocadas (mais concreto), depois os serviços de
    rotina marcados nela, cai pra descrição livre, e por último só o
    motivo (rotina/quebra) se não tiver nada mais específico registrado."""
    partes = []
    descricoes_pecas = [it.get('descricao', '').strip() for it in r.itens() if it.get('descricao', '').strip()]
    if descricoes_pecas:
        partes.append(', '.join(descricoes_pecas))
    if nomes_manutencoes:
        partes.append(', '.join(nomes_manutencoes))
    if not partes and r.descricao:
        partes.append(r.descricao.strip())
    if not partes:
        partes.append('Quebra / Problema' if r.motivo == 'quebra' else 'Revisão de rotina')
    return ' · '.join(partes)

def _montar_resumo_revisoes(u, veiculo):
    """Agrupa as revisões (não-pendentes) do veículo por ano -> mês, cada
    uma já com o texto de "o que foi feito" pronto -- usado tanto na tela
    de resumo quanto no PDF, pra não duplicar a lógica de agrupamento."""
    todas = RevisaoCarro.query.filter_by(usuario_id=u.id, veiculo_id=veiculo.id, pendente=False)\
        .order_by(RevisaoCarro.data.asc(), RevisaoCarro.id.asc()).all()
    if not todas:
        return []

    nomes_tipo = {t['chave']: t['nome'] for t in TIPOS_MANUTENCAO_RECORRENTE}
    manut_por_revisao = {}
    for m in ManutencaoRecorrente.query.filter(
            ManutencaoRecorrente.revisao_id.in_([r.id for r in todas])).all():
        manut_por_revisao.setdefault(m.revisao_id, []).append(nomes_tipo.get(m.tipo, m.tipo))

    por_ano = {}
    for r in todas:
        linha = {
            'id': r.id, 'data': r.data, 'odometro': r.odometro, 'motivo': r.motivo,
            'oficina': (r.oficina or '').strip() or '—',
            'servico': _texto_servico_revisao(r, manut_por_revisao.get(r.id, [])),
        }
        por_ano.setdefault(r.data.year, {}).setdefault(r.data.month, []).append(linha)

    resumo = []
    for ano in sorted(por_ano.keys(), reverse=True):
        meses = []
        for mes in sorted(por_ano[ano].keys(), reverse=True):
            revs_mes = sorted(por_ano[ano][mes], key=lambda x: x['data'], reverse=True)
            meses.append({'mes': mes, 'nome_mes': NOMES_MESES[mes], 'revisoes': revs_mes})
        resumo.append({'ano': ano, 'meses': meses,
                        'total_no_ano': sum(len(m['revisoes']) for m in meses)})
    return resumo

@app.route('/pessoal/revisoes/resumo')
@login_required
@super_admin_required
def resumo_revisoes():
    u = get_current_user()
    veiculos = VeiculoPessoal.query.filter_by(usuario_id=u.id)\
        .order_by(VeiculoPessoal.ativo.desc(), VeiculoPessoal.criado_em.desc()).all()
    if not veiculos:
        return render_template('gestao_pessoal_revisoes_resumo.html', veiculos=[], veiculo_atual=None, resumo=[])

    veiculo_id = request.args.get('veiculo_id', type=int) or veiculos[0].id
    veiculo_atual = next((v for v in veiculos if v.id == veiculo_id), veiculos[0])
    resumo = _montar_resumo_revisoes(u, veiculo_atual)
    total_revisoes = sum(a['total_no_ano'] for a in resumo)
    return render_template('gestao_pessoal_revisoes_resumo.html', veiculos=veiculos,
        veiculo_atual=veiculo_atual, resumo=resumo, total_revisoes=total_revisoes)

@app.route('/pessoal/revisoes/resumo/pdf')
@login_required
@super_admin_required
def resumo_revisoes_pdf():
    from pdf_generator import gerar_resumo_revisoes_pdf
    u = get_current_user()
    veiculo_id = request.args.get('veiculo_id', type=int)
    veiculo = VeiculoPessoal.query.filter_by(id=veiculo_id, usuario_id=u.id).first_or_404() if veiculo_id \
        else VeiculoPessoal.query.filter_by(usuario_id=u.id).order_by(VeiculoPessoal.criado_em.desc()).first_or_404()
    resumo = _montar_resumo_revisoes(u, veiculo)
    buf = gerar_resumo_revisoes_pdf(modelo_para_dict(veiculo), resumo)
    nome_arq = (veiculo.apelido or veiculo.modelo or 'veiculo').replace(' ', '_')
    return send_file(buf, mimetype='application/pdf', as_attachment=False,
                      download_name=f"Resumo_Revisoes_{nome_arq}.pdf")


# ============================================================
# TROCA DE CARRO — consulta FIPE + simulador de entrada/financiamento
# ============================================================

FIPE_BASE_URL = 'https://fipe.parallelum.com.br/api/v2/cars'

def _fipe_get(caminho):
    """GET simples na API pública da FIPE (Parallelum v2, sem autenticação
    -- ver https://fipe.parallelum.com.br). Timeout curto e erro tratável
    pelo chamador em vez de estourar exceção pra dentro da rota."""
    import requests
    try:
        resp = requests.get(f'{FIPE_BASE_URL}/{caminho}', timeout=12,
                             headers={'Accept': 'application/json'})
        if resp.status_code != 200:
            return None, f'FIPE respondeu {resp.status_code}'
        return resp.json(), None
    except Exception as e:
        return None, str(e)

@app.route('/pessoal/troca-carro/fipe/marcas')
@login_required
@super_admin_required
def fipe_marcas():
    dados, erro = _fipe_get('brands')
    if erro:
        return jsonify({'erro': erro}), 502
    marcas = sorted(({'codigo': m['code'], 'nome': m['name']} for m in dados), key=lambda x: x['nome'])
    return jsonify(marcas)

@app.route('/pessoal/troca-carro/fipe/modelos/<marca_codigo>')
@login_required
@super_admin_required
def fipe_modelos(marca_codigo):
    dados, erro = _fipe_get(f'brands/{marca_codigo}/models')
    if erro:
        return jsonify({'erro': erro}), 502
    modelos = sorted(({'codigo': m['code'], 'nome': m['name']} for m in dados), key=lambda x: x['nome'])
    return jsonify(modelos)

@app.route('/pessoal/troca-carro/fipe/anos/<marca_codigo>/<modelo_codigo>')
@login_required
@super_admin_required
def fipe_anos(marca_codigo, modelo_codigo):
    dados, erro = _fipe_get(f'brands/{marca_codigo}/models/{modelo_codigo}/years')
    if erro:
        return jsonify({'erro': erro}), 502
    anos = [{'codigo': a['code'], 'nome': a['name']} for a in dados]
    return jsonify(anos)

@app.route('/pessoal/troca-carro/fipe/valor/<marca_codigo>/<modelo_codigo>/<ano_codigo>')
@login_required
@super_admin_required
def fipe_valor(marca_codigo, modelo_codigo, ano_codigo):
    dados, erro = _fipe_get(f'brands/{marca_codigo}/models/{modelo_codigo}/years/{ano_codigo}')
    if erro:
        return jsonify({'erro': erro}), 502
    # "R$ 27.652,00" -> 27652.00 (número puro, mais fácil de somar no JS)
    preco_txt = (dados.get('price') or '').replace('R$', '').strip()
    preco_num = None
    try:
        preco_num = float(preco_txt.replace('.', '').replace(',', '.'))
    except (ValueError, AttributeError):
        pass
    return jsonify({
        'preco_texto': dados.get('price'), 'preco': preco_num,
        'marca': dados.get('brand'), 'modelo': dados.get('model'),
        'ano_modelo': dados.get('modelYear'), 'combustivel': dados.get('fuel'),
        'codigo_fipe': dados.get('codeFipe'), 'mes_referencia': dados.get('referenceMonth'),
    })

@app.route('/pessoal/troca-carro')
@login_required
@super_admin_required
def troca_carro():
    u = get_current_user()
    itens = ItemVendaTroca.query.filter_by(usuario_id=u.id).order_by(ItemVendaTroca.criado_em.desc()).all()
    total_itens = sum(i.valor for i in itens)
    veiculo_atual = VeiculoPessoal.query.filter_by(usuario_id=u.id, ativo=True)\
        .order_by(VeiculoPessoal.criado_em.desc()).first()
    return render_template('gestao_pessoal_troca_carro.html', itens=itens, total_itens=total_itens,
                            veiculo_atual=veiculo_atual)

def _eh_ajax():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

@app.route('/pessoal/troca-carro/itens/novo', methods=['POST'])
@login_required
@super_admin_required
def novo_item_venda_troca():
    u = get_current_user()
    descricao = request.form.get('descricao', '').strip()
    try:
        valor = float(request.form.get('valor') or 0)
    except ValueError:
        valor = 0
    if descricao and valor > 0:
        item = ItemVendaTroca(usuario_id=u.id, descricao=descricao, valor=valor)
        db.session.add(item)
        db.session.commit()
        if _eh_ajax():
            return jsonify({'ok': True, 'id': item.id, 'descricao': item.descricao, 'valor': item.valor})
        flash(f'"{descricao}" adicionado à lista!', 'success')
        return redirect(url_for('troca_carro'))
    if _eh_ajax():
        return jsonify({'ok': False, 'erro': 'Preencha a descrição e um valor maior que zero.'}), 400
    flash('Preencha a descrição e um valor maior que zero.', 'warning')
    return redirect(url_for('troca_carro'))

@app.route('/pessoal/troca-carro/itens/<int:id>/excluir', methods=['POST'])
@login_required
@super_admin_required
def excluir_item_venda_troca(id):
    u = get_current_user()
    item = ItemVendaTroca.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    if _eh_ajax():
        return jsonify({'ok': True})
    flash('Item removido da lista.', 'success')
    return redirect(url_for('troca_carro'))

@app.route('/pessoal/troca-carro/salvar', methods=['POST'])
@login_required
@super_admin_required
def salvar_simulacao_troca_carro():
    """Salva uma "foto" da simulação atual -- os números já calculados no
    JS, não só os campos de entrada, porque a FIPE e a taxa de juros
    mudam com o tempo e a simulação salva tem que continuar mostrando o
    que foi visto naquele momento."""
    u = get_current_user()
    def f(campo):
        try:
            return float(request.form.get(campo) or 0)
        except ValueError:
            return 0
    nome = request.form.get('nome_carro_novo', '').strip()
    if not nome:
        flash('Dê um nome pro carro novo antes de salvar (ex: "Corolla XEi 2023 na Fulano Motors").', 'warning')
        return redirect(url_for('troca_carro'))
    sim = SimulacaoTrocaCarro(
        usuario_id=u.id,
        nome_carro_novo=nome,
        valor_carro_novo=f('valor_carro_novo'),
        carro_atual_fipe=request.form.get('carro_atual_fipe', '').strip() or None,
        valor_fipe=f('valor_fipe') or None,
        oferta_loja=f('oferta_loja'),
        saldo_devedor=f('saldo_devedor'),
        total_itens_venda=f('total_itens_venda'),
        total_entrada=f('total_entrada'),
        taxa_juros_am=f('taxa_juros_am'),
        parcelas=int(f('parcelas')),
        valor_parcela=f('valor_parcela'),
        total_pago=f('total_pago'),
        total_juros=f('total_juros'),
        parcela_atual=f('parcela_atual') or None,
    )
    db.session.add(sim)
    db.session.commit()
    flash(f'Simulação de "{nome}" salva!', 'success')
    return redirect(url_for('simulacoes_troca_carro'))

@app.route('/pessoal/troca-carro/simulacoes')
@login_required
@super_admin_required
def simulacoes_troca_carro():
    u = get_current_user()
    simulacoes = SimulacaoTrocaCarro.query.filter_by(usuario_id=u.id)\
        .order_by(SimulacaoTrocaCarro.criado_em.desc()).all()
    return render_template('gestao_pessoal_troca_carro_simulacoes.html', simulacoes=simulacoes)

@app.route('/pessoal/troca-carro/simulacoes/<int:id>/notas', methods=['POST'])
@login_required
@super_admin_required
def atualizar_notas_simulacao(id):
    u = get_current_user()
    sim = SimulacaoTrocaCarro.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    sim.notas = request.form.get('notas', '').strip() or None
    db.session.commit()
    flash('Anotação salva!', 'success')
    return redirect(url_for('simulacoes_troca_carro'))

@app.route('/pessoal/troca-carro/simulacoes/<int:id>/excluir', methods=['POST'])
@login_required
@super_admin_required
def excluir_simulacao_troca_carro(id):
    u = get_current_user()
    sim = SimulacaoTrocaCarro.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    db.session.delete(sim)
    db.session.commit()
    flash('Simulação removida.', 'success')
    return redirect(url_for('simulacoes_troca_carro'))

def _preencher_revisao_form(r, u):
    r.veiculo_id = int(request.form['veiculo_id'])
    data_str = request.form.get('data')
    r.data = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()
    r.odometro = int(request.form.get('odometro') or 0)
    r.motivo = request.form.get('motivo', 'rotina')
    r.oficina = request.form.get('oficina', '').strip()
    r.descricao = request.form.get('descricao', '').strip()
    r.mao_de_obra = float((request.form.get('mao_de_obra') or '0').replace(',', '.'))
    r.forma_pagamento = request.form.get('forma_pagamento', '').strip()
    r.cartao_id = int(request.form['cartao_id']) if request.form.get('cartao_id') else None
    r.parcela_total = int(request.form['parcela_total']) if request.form.get('parcela_total') else None

    descs = request.form.getlist('item_desc[]')
    qtds = request.form.getlist('item_qtd[]')
    valores = request.form.getlist('item_valor[]')
    origem_tipos = request.form.getlist('item_origem_tipo[]')
    origem_notas = request.form.getlist('item_origem_nota[]')
    origem_idxs = request.form.getlist('item_origem_idx[]')
    itens = []
    consumos = []  # [(origem_tipo, nota_id, idx), ...] -- peças escolhidas individualmente de notas/gastos
    for i, desc in enumerate(descs):
        if not desc.strip():
            continue
        qtd = float((qtds[i] if i < len(qtds) else '1').replace(',', '.') or 1)
        valor_unit = float((valores[i] if i < len(valores) else '0').replace(',', '.') or 0)
        itens.append({'descricao': desc.strip(), 'qtd': qtd, 'valor': round(qtd * valor_unit, 2)})
        origem_tipo = origem_tipos[i] if i < len(origem_tipos) else ''
        nota_id = origem_notas[i] if i < len(origem_notas) else ''
        idx = origem_idxs[i] if i < len(origem_idxs) else ''
        if origem_tipo and nota_id and idx != '':
            consumos.append((origem_tipo, int(nota_id), int(idx)))
    r._consumos_notas = consumos  # atributo transiente, lido pelas rotas após salvar
    r.itens_json = json.dumps(itens, ensure_ascii=False) if itens else None
    r._manutencoes_marcadas = request.form.getlist('manutencoes[]')  # idem
    r.valor_total = round(r.mao_de_obra + sum(it['valor'] for it in itens), 2)
    # Uma vez que o odômetro (e o resto) foi preenchido, a revisão deixa
    # de ser "pendente" -- seja porque o usuário completou a nota
    # importada direto, seja porque isso é uma revisão manual normal.
    if r.odometro:
        r.pendente = False

    # Atualiza o KM do veículo se essa revisão for a mais recente (mais
    # alta) que ele conhece -- assim o "km desde a última revisão" no
    # resumo fica sempre em dia sem precisar editar o veículo à parte.
    veiculo = VeiculoPessoal.query.get(r.veiculo_id)
    if veiculo and (not veiculo.km_atual or r.odometro > veiculo.km_atual):
        veiculo.km_atual = r.odometro

def _salvar_manutencoes_marcadas(r, u):
    """Recria os "carimbos" de manutenção recorrente (óleo do motor,
    câmbio, etc.) ligados a essa revisão a partir dos checkboxes
    marcados no form -- apaga os antigos primeiro pra editar funcionar
    (desmarcar um item remove o carimbo dele)."""
    ManutencaoRecorrente.query.filter_by(revisao_id=r.id).delete()
    marcados = getattr(r, '_manutencoes_marcadas', [])
    if not marcados:
        return
    veiculo = VeiculoPessoal.query.get(r.veiculo_id)
    aplicaveis = {t['chave']: t for t in _tipos_manutencao_aplicaveis(veiculo)} if veiculo else {}
    for chave in marcados:
        cat = aplicaveis.get(chave)
        if not cat:
            continue
        km_override = request.form.get(f'intervalo_km_{chave}', type=int)
        intervalo_km = km_override if km_override and km_override != cat['km_padrao'] else None
        db.session.add(ManutencaoRecorrente(
            usuario_id=u.id, veiculo_id=r.veiculo_id, revisao_id=r.id,
            tipo=chave, data=r.data, odometro=r.odometro, intervalo_km=intervalo_km))

def _vincular_nota_pendente(r, u):
    """Se o form trouxe `nota_origem_id`, essa revisão (nova ou em
    edição) está "puxando" uma nota XML pendente pra dentro dela --
    transfere a chave/arquivo da nota pra essa revisão (fica marcada
    como vinda de XML, com o link pro arquivo original) e apaga o
    registro solto, evitando duplicar o gasto no cartão/dashboard."""
    nota_id = request.form.get('nota_origem_id', type=int)
    if not nota_id or nota_id == r.id:
        return
    nota = RevisaoCarro.query.filter_by(id=nota_id, usuario_id=u.id, pendente=True).first()
    if not nota:
        return
    chave = nota.chave_nfe
    nota.chave_nfe = None  # libera a coluna unique antes de repassar
    db.session.flush()
    r.chave_nfe = chave
    r.arquivo_xml = nota.arquivo_xml
    r.origem = 'xml'
    if not r.numero_nota:
        r.numero_nota = nota.numero_nota
    db.session.delete(nota)

def _pecas_disponiveis_notas(u, veiculo_id):
    """Lista achatada (peça a peça, não a nota inteira) de tudo que dá
    pra puxar pra dentro de uma revisão -- duas fontes, com
    comportamentos DIFERENTES ao usar (ver `_consumir_itens_de_notas`):
    1) notas XML pendentes lançadas direto em Revisões (específicas
       desse veículo) -- usar uma peça daqui REMOVE ela da nota
       pendente (e a nota some se esvaziar), porque essas notas nunca
       foram um registro "de verdade" por conta própria;
    2) notas XML já importadas no módulo "Gastos com o Carro" (esse
       módulo é mais antigo que Veículos/Revisões e não tem veiculo_id,
       então aparece pra qualquer veículo do usuário) -- usar uma peça
       daqui só COPIA a descrição/valor pra revisão; o lançamento
       original em Gastos com o Carro continua intacto (ele já é um
       gasto real, com histórico e cartão próprios).
    Cada peça carrega de onde veio (`origem_tipo`)."""
    pecas = []
    notas_revisao = RevisaoCarro.query.filter_by(usuario_id=u.id, veiculo_id=veiculo_id, pendente=True)\
        .order_by(RevisaoCarro.data.desc()).all()
    for n in notas_revisao:
        rotulo_nota = f"{n.data.strftime('%d/%m/%Y')} - {n.oficina or 'nota sem nome'}"
        for idx, it in enumerate(n.itens()):
            pecas.append({
                'origem_tipo': 'revisao', 'nota_id': n.id, 'idx': idx,
                'descricao': it.get('descricao', ''), 'qtd': it.get('qtd', 1) or 1,
                'valor': it.get('valor', 0) or 0, 'nota_label': rotulo_nota,
            })
    gastos_xml = GastoCarro.query.filter_by(usuario_id=u.id, origem='xml')\
        .filter(GastoCarro.itens_json.isnot(None)).order_by(GastoCarro.data.desc()).all()
    for g in gastos_xml:
        itens_g = g.itens()
        if not itens_g:
            continue
        rotulo_nota = f"{g.data.strftime('%d/%m/%Y')} - {g.posto_estabelecimento or 'nota sem nome'} (Gastos com o Carro)"
        for idx, it in enumerate(itens_g):
            pecas.append({
                'origem_tipo': 'gasto_carro', 'nota_id': g.id, 'idx': idx,
                'descricao': it.get('descricao', ''), 'qtd': it.get('qtd', 1) or 1,
                'valor': it.get('valor', 0) or 0, 'nota_label': rotulo_nota,
            })
    return pecas

def _consumir_item_revisao_pendente(nota_id, idxs, u):
    nota = RevisaoCarro.query.filter_by(id=nota_id, usuario_id=u.id, pendente=True).first()
    if not nota:
        return
    restantes = [it for i, it in enumerate(nota.itens()) if i not in idxs]
    nota.itens_json = json.dumps(restantes, ensure_ascii=False) if restantes else None
    nota.valor_total = round((nota.mao_de_obra or 0) + sum(it.get('valor', 0) for it in restantes), 2)
    if not restantes and not nota.mao_de_obra:
        if nota.arquivo_xml:
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'revisoes_carro', nota.arquivo_xml)
            try:
                os.remove(caminho)
            except OSError:
                pass
        db.session.delete(nota)

def _consumir_itens_de_notas(consumos, u):
    """Remove peça a peça os itens escolhidos das notas XML PENDENTES
    de Revisões (as que ainda não viraram uma revisão de verdade) --
    essas somem/encolhem porque nunca foram um registro "de verdade"
    por conta própria, só um rascunho esperando virar revisão.

    Peças que vieram de "Gastos com o Carro" (`origem_tipo ==
    'gasto_carro'`) NÃO são tocadas aqui -- ver nota histórica abaixo."""
    if not consumos:
        return
    por_origem = {}
    for origem_tipo, nota_id, idx in consumos:
        if origem_tipo != 'revisao':
            continue  # gasto_carro é só cópia/referência, nunca mexe na fonte -- ver nota abaixo
        por_origem.setdefault(nota_id, set()).add(idx)
    for nota_id, idxs in por_origem.items():
        _consumir_item_revisao_pendente(nota_id, idxs, u)

# NOTA (2026-08-09): existiu aqui uma função `_consumir_item_gasto_carro`
# que apagava/encolhia o lançamento em Gastos com o Carro sempre que uma
# peça dele era usada numa Revisão -- pra "não contar o dinheiro duas
# vezes". Na prática isso apagou de vez 11 notas fiscais reais e válidas
# de Gastos com o Carro assim que o Arlindo usou o seletor pra montar
# revisões de verdade (peças eram removidas da fonte uma a uma até a nota
# inteira sumir). Foram restauradas de backup. Peças de Gastos com o Carro
# NÃO são mais consumidas: usar uma delas numa revisão só COPIA a
# descrição/valor pra lá, sem tocar no lançamento original -- ele continua
# contando no cartão/relatórios do Carro normalmente. Isso pode fazer o
# mesmo valor aparecer nos dois lugares (Carro e na revisão), mas isso é
# só duplicação informativa nesses dois resumos -- o `_ocupado_cartao()`
# só soma revisões que têm `cartao_id` próprio, e o item copiado pra
# dentro de uma revisão não herda o cartão do gasto original, então não
# duplica o limite do cartão de verdade. Diferente do caso de notas
# pendentes de Revisões (acima), que continuam sendo consumidas -- essas
# nunca foram um registro "de verdade" independente.

def _notas_pendentes_disponiveis(u, veiculo_id, excluir_id=None):
    """Notas XML pendentes desse veículo, no formato que o form de
    revisão usa pra montar os botões de "puxar peças dessa nota"."""
    q = RevisaoCarro.query.filter_by(usuario_id=u.id, veiculo_id=veiculo_id, pendente=True)
    if excluir_id:
        q = q.filter(RevisaoCarro.id != excluir_id)
    notas = q.order_by(RevisaoCarro.data.desc()).all()
    return [{
        'id': n.id,
        'data': n.data.strftime('%d/%m/%Y'),
        'oficina': n.oficina or n.descricao or 'Nota sem descrição',
        'mao_de_obra': n.mao_de_obra or 0,
        'valor_total': n.valor_total or 0,
        'forma_pagamento': n.forma_pagamento or '',
        'cartao_id': n.cartao_id,
        'parcela_total': n.parcela_total,
        'itens': n.itens(),
    } for n in notas]

@app.route('/pessoal/revisoes/novo', methods=['GET', 'POST'])
@login_required
@super_admin_required
def novo_revisao():
    u = get_current_user()
    veiculos = VeiculoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(VeiculoPessoal.criado_em.desc()).all()
    if not veiculos:
        flash('Cadastre um veículo antes de lançar uma revisão.', 'warning')
        return redirect(url_for('listar_veiculos'))
    if request.method == 'POST':
        r = RevisaoCarro(usuario_id=u.id, origem='manual')
        _preencher_revisao_form(r, u)
        db.session.add(r)
        db.session.flush()  # precisa do r.id pros carimbos de manutenção recorrente
        _salvar_manutencoes_marcadas(r, u)
        _consumir_itens_de_notas(getattr(r, '_consumos_notas', []), u)
        _vincular_nota_pendente(r, u)
        db.session.commit()
        flash('Revisão adicionada!', 'success')
        return redirect(url_for('listar_revisoes', veiculo_id=r.veiculo_id))
    veiculo_sel = request.args.get('veiculo_id', type=int) or veiculos[0].id
    veiculo_obj_sel = next((v for v in veiculos if v.id == veiculo_sel), veiculos[0])
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(CartaoPessoal.nome).all()
    pecas_sugeridas = _pecas_sugeridas_veiculo(u.id, veiculo_sel)
    notas_disponiveis = _notas_pendentes_disponiveis(u, veiculo_sel)
    pecas_notas = _pecas_disponiveis_notas(u, veiculo_sel)
    nota_pre_id = request.args.get('usar_nota', type=int)
    tipos_manutencao = _tipos_manutencao_aplicaveis(veiculo_obj_sel)
    return render_template('form_revisao.html', revisao=None, veiculos=veiculos, veiculo_sel=veiculo_sel,
        cartoes=cartoes, formas_pagamento=FORMAS_PAGAMENTO_CARRO, pecas_sugeridas=pecas_sugeridas,
        notas_disponiveis=notas_disponiveis, pecas_notas=pecas_notas, nota_pre_id=nota_pre_id,
        tipos_manutencao=tipos_manutencao, manutencoes_marcadas={},
        hoje=date.today().strftime('%Y-%m-%d'))

@app.route('/pessoal/revisoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@super_admin_required
def editar_revisao(id):
    u = get_current_user()
    r = RevisaoCarro.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    veiculos = VeiculoPessoal.query.filter_by(usuario_id=u.id).order_by(VeiculoPessoal.ativo.desc(), VeiculoPessoal.criado_em.desc()).all()
    if request.method == 'POST':
        _preencher_revisao_form(r, u)
        _salvar_manutencoes_marcadas(r, u)
        _consumir_itens_de_notas(getattr(r, '_consumos_notas', []), u)
        _vincular_nota_pendente(r, u)
        db.session.commit()
        flash('Revisão atualizada!', 'success')
        return redirect(url_for('listar_revisoes', veiculo_id=r.veiculo_id))
    cartoes = CartaoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(CartaoPessoal.nome).all()
    pecas_sugeridas = _pecas_sugeridas_veiculo(u.id, r.veiculo_id)
    notas_disponiveis = _notas_pendentes_disponiveis(u, r.veiculo_id, excluir_id=r.id)
    pecas_notas = _pecas_disponiveis_notas(u, r.veiculo_id)
    tipos_manutencao = _tipos_manutencao_aplicaveis(r.veiculo)
    manutencoes_marcadas = {m.tipo: m.intervalo_km for m in ManutencaoRecorrente.query.filter_by(revisao_id=r.id).all()}
    return render_template('form_revisao.html', revisao=r, veiculos=veiculos, veiculo_sel=r.veiculo_id,
        cartoes=cartoes, formas_pagamento=FORMAS_PAGAMENTO_CARRO, pecas_sugeridas=pecas_sugeridas,
        notas_disponiveis=notas_disponiveis, pecas_notas=pecas_notas, nota_pre_id=None,
        tipos_manutencao=tipos_manutencao, manutencoes_marcadas=manutencoes_marcadas,
        hoje=r.data.strftime('%Y-%m-%d'))

@app.route('/pessoal/revisoes/<int:id>/pdf')
@login_required
@super_admin_required
def revisao_pdf(id):
    from pdf_generator import gerar_revisao_pdf
    u = get_current_user()
    r = RevisaoCarro.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    nomes_tipo = {t['chave']: t['nome'] for t in TIPOS_MANUTENCAO_RECORRENTE}
    marcadas = ManutencaoRecorrente.query.filter_by(revisao_id=r.id).all()
    manutencoes = [nomes_tipo.get(m.tipo, m.tipo) for m in marcadas]
    buf = gerar_revisao_pdf(modelo_para_dict(r), modelo_para_dict(r.veiculo), r.itens(), manutencoes)
    nome_arq = (r.veiculo.apelido or r.veiculo.modelo or 'veiculo').replace(' ', '_')
    return send_file(buf, mimetype='application/pdf', as_attachment=False,
                      download_name=f"Revisao_{nome_arq}_{r.data.strftime('%Y%m%d')}.pdf")

@app.route('/pessoal/revisoes/<int:id>/excluir', methods=['POST'])
@login_required
@super_admin_required
def excluir_revisao(id):
    u = get_current_user()
    r = RevisaoCarro.query.filter_by(id=id, usuario_id=u.id).first_or_404()
    veiculo_id = r.veiculo_id
    if r.arquivo_xml:
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'revisoes_carro', r.arquivo_xml)
        try:
            os.remove(caminho)
        except OSError:
            pass
    db.session.delete(r)
    db.session.commit()
    flash('Revisão excluída!', 'success')
    return redirect(url_for('listar_revisoes', veiculo_id=veiculo_id))

@app.route('/pessoal/revisoes/importar-xml', methods=['GET', 'POST'])
@login_required
@super_admin_required
def importar_xml_revisao():
    u = get_current_user()
    veiculos = VeiculoPessoal.query.filter_by(usuario_id=u.id, ativo=True).order_by(VeiculoPessoal.criado_em.desc()).all()
    if not veiculos:
        flash('Cadastre um veículo antes de importar uma nota de revisão.', 'warning')
        return redirect(url_for('listar_veiculos'))
    if request.method == 'POST':
        veiculo_id = int(request.form.get('veiculo_id') or veiculos[0].id)
        arquivos = request.files.getlist('arquivos_xml')
        importados, duplicados, com_erro = 0, 0, []
        pasta = os.path.join(app.config['UPLOAD_FOLDER'], 'revisoes_carro')
        os.makedirs(pasta, exist_ok=True)
        for f in arquivos:
            if not f or not f.filename:
                continue
            try:
                conteudo = f.read()
                dados = _parse_nfe_xml(conteudo)
                if dados['chave_nfe'] and RevisaoCarro.query.filter_by(
                        usuario_id=u.id, chave_nfe=dados['chave_nfe']).first():
                    duplicados += 1
                    continue
                # Separa mão de obra dos itens que são peça de verdade,
                # baseado em palavra-chave da descrição (mesma ideia do
                # detector de combustível do módulo Carro).
                pecas, mao_de_obra = [], 0.0
                for it in dados['itens']:
                    if any(p in it['descricao'].upper() for p in _PALAVRAS_MAO_DE_OBRA):
                        mao_de_obra += it['valor']
                    else:
                        pecas.append(it)
                nome_arquivo = f"{(dados['chave_nfe'] or uuid.uuid4().hex)}.xml"
                with open(os.path.join(pasta, nome_arquivo), 'wb') as out:
                    out.write(conteudo)
                r = RevisaoCarro(
                    usuario_id=u.id, veiculo_id=veiculo_id, origem='xml', motivo='rotina',
                    data=dados['data'], odometro=0, oficina=dados['posto_estabelecimento'],
                    descricao=dados['descricao'], mao_de_obra=round(mao_de_obra, 2),
                    valor_total=dados['valor'], forma_pagamento=dados['forma_pagamento'],
                    numero_nota=dados['numero_nota'], chave_nfe=dados['chave_nfe'],
                    itens_json=json.dumps(pecas, ensure_ascii=False), arquivo_xml=nome_arquivo,
                    pendente=True)
                db.session.add(r)
                db.session.commit()
                importados += 1
            except Exception as e:
                db.session.rollback()
                logger.exception(f'Erro importando XML de revisão "{f.filename}"')
                com_erro.append(f'{f.filename}: {e}')
                continue
        msg = (f'{importados} nota(s) importada(s) -- elas ficam em "Notas Pendentes" até você '
               f'puxar as peças pra uma revisão (nova ou existente) ou completar os dados direto nelas.')
        if duplicados:
            msg += f' {duplicados} já tinham sido importada(s) antes (ignoradas).'
        if com_erro:
            msg += f' {len(com_erro)} com erro: {"; ".join(com_erro[:3])}'
        flash(msg, 'success' if importados else 'warning')
        return redirect(url_for('listar_revisoes', veiculo_id=veiculo_id))
    return render_template('importar_xml_revisao.html', veiculos=veiculos)


# ─── ERROS ─────────────────────────────────────────────────────────────────────
@app.errorhandler(404)
def erro_404(e):
    return render_template('erro_404.html'), 404

@app.errorhandler(500)
def erro_500(e):
    logger.exception(f'Erro interno em {request.path}')
    return render_template('erro_500.html'), 500


# ─── INICIALIZAÇÃO ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("[NeuraBusiness] Tabelas criadas/verificadas")
        seed_inicial()
    print("\n[>>] NeuraBusiness v3.0 — http://localhost:5000\n")
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=5000)
