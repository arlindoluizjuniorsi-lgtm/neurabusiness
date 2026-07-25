"""NeuraBusiness — Modelos de Dados (SQLAlchemy)"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets
import json

db = SQLAlchemy()

class Empresa(db.Model):
    __tablename__ = 'empresas'
    id           = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(200), nullable=False)
    fantasia     = db.Column(db.String(100), nullable=False)
    cnpj         = db.Column(db.String(30))
    telefone     = db.Column(db.String(30))
    email        = db.Column(db.String(120))
    endereco     = db.Column(db.String(300))
    cidade       = db.Column(db.String(100))
    estado       = db.Column(db.String(2))
    cep          = db.Column(db.String(10))
    logo         = db.Column(db.String(300))
    briefing     = db.Column(db.Text)
    ativa        = db.Column(db.Boolean, default=True)
    criado_em    = db.Column(db.DateTime, default=datetime.now)

    usuarios  = db.relationship('Usuario', backref='empresa', lazy=True,
                    foreign_keys='Usuario.empresa_id')
    clientes  = db.relationship('Cliente', backref='empresa', lazy=True)
    propostas = db.relationship('Proposta', backref='empresa', lazy=True)
    os        = db.relationship('OrdemServico', backref='empresa', lazy=True)


class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id             = db.Column(db.Integer, primary_key=True)
    nome           = db.Column(db.String(100), nullable=False)
    usuario        = db.Column(db.String(50), nullable=False, unique=True)
    email          = db.Column(db.String(120), nullable=False, unique=True)
    senha_hash     = db.Column(db.String(300), nullable=False)
    empresa_id     = db.Column(db.Integer, db.ForeignKey('empresas.id'))
    is_admin       = db.Column(db.Boolean, default=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    ativo          = db.Column(db.Boolean, default=True)
    criado_em      = db.Column(db.DateTime, default=datetime.now)

    empresas_acesso = db.relationship('UsuarioEmpresa', backref='usuario', lazy=True)


class UsuarioEmpresa(db.Model):
    __tablename__ = 'usuario_empresas'
    id         = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('usuario_id', 'empresa_id'),)


class Produto(db.Model):
    __tablename__ = 'produtos'
    id              = db.Column(db.Integer, primary_key=True)
    empresa_id      = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    nome            = db.Column(db.String(200), nullable=False)
    descricao       = db.Column(db.Text)
    especificacoes  = db.Column(db.Text)
    preco_custo     = db.Column(db.Float, default=0)
    preco_venda     = db.Column(db.Float, default=0)
    markup_padrao   = db.Column(db.Float, default=0)
    markup_sugerido = db.Column(db.Float, default=0)
    margem_minima   = db.Column(db.Float, default=0)
    estoque         = db.Column(db.Integer, default=0)
    categoria       = db.Column(db.String(100))
    tipo            = db.Column(db.String(20), default='produto')
    foto            = db.Column(db.String(300))
    ativo           = db.Column(db.Boolean, default=True)
    token_link      = db.Column(db.String(64))
    link_expira_em  = db.Column(db.DateTime)
    slug            = db.Column(db.String(200))
    criado_em       = db.Column(db.DateTime, default=datetime.now)
    empresa_rel     = db.relationship('Empresa', foreign_keys=[empresa_id], lazy=True)


class Servico(db.Model):
    __tablename__ = 'servicos'
    id             = db.Column(db.Integer, primary_key=True)
    empresa_id     = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    nome           = db.Column(db.String(200), nullable=False)
    descricao      = db.Column(db.Text)
    preco_unitario = db.Column(db.Float, default=0)
    unidade        = db.Column(db.String(20), default='un')
    ativo          = db.Column(db.Boolean, default=True)
    criado_em      = db.Column(db.DateTime, default=datetime.now)


class CatalogoServico(db.Model):
    __tablename__ = 'catalogo_servicos'
    id               = db.Column(db.Integer, primary_key=True)
    empresa_id       = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    categoria        = db.Column(db.String(100), nullable=False)
    subcategoria     = db.Column(db.String(100))
    nome             = db.Column(db.String(200), nullable=False)
    descricao        = db.Column(db.Text)        # descrição técnica interna
    descricao_cliente= db.Column(db.Text)        # descrição para o cliente
    tipo_preco       = db.Column(db.String(20), default='fixo')  # fixo, hora, metro, ponto, orcamento
    unidade          = db.Column(db.String(20), default='serviço')
    preco_base       = db.Column(db.Float, default=0)
    tempo_horas      = db.Column(db.Float, default=0)
    ativo            = db.Column(db.Boolean, default=True)


class MaterialInfra(db.Model):
    __tablename__ = 'materiais_infra'
    id             = db.Column(db.Integer, primary_key=True)
    empresa_id     = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    nome           = db.Column(db.String(200), nullable=False)
    unidade        = db.Column(db.String(20), default='un')
    preco_unitario = db.Column(db.Float, default=0)
    categoria      = db.Column(db.String(100))
    ativo          = db.Column(db.Boolean, default=True)


class Cliente(db.Model):
    __tablename__ = 'clientes'
    id          = db.Column(db.Integer, primary_key=True)
    empresa_id  = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    nome        = db.Column(db.String(200), nullable=False)
    tipo        = db.Column(db.String(2), default='PF')   # PF ou PJ
    email       = db.Column(db.String(120))
    telefone    = db.Column(db.String(30))
    cpf_cnpj    = db.Column(db.String(30))
    endereco    = db.Column(db.String(300))
    cidade      = db.Column(db.String(100))
    estado      = db.Column(db.String(2))
    cep         = db.Column(db.String(10))
    observacoes = db.Column(db.Text)
    criado_em   = db.Column(db.DateTime, default=datetime.now)

    propostas = db.relationship('Proposta', backref='cliente', lazy=True)
    os        = db.relationship('OrdemServico', backref='cliente', lazy=True)


class Proposta(db.Model):
    __tablename__ = 'propostas'
    id                = db.Column(db.Integer, primary_key=True)
    empresa_id        = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    numero            = db.Column(db.String(30), nullable=False)
    titulo            = db.Column(db.String(200), nullable=False)
    cliente_id        = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    status            = db.Column(db.String(20), default='rascunho')
    tipo_proposta     = db.Column(db.String(20), default='padrao')
    validade          = db.Column(db.Integer, default=15)
    observacoes       = db.Column(db.Text)
    condicoes         = db.Column(db.Text)
    forma_pagamento   = db.Column(db.String(100))
    custo_locomocao   = db.Column(db.Float, default=0)
    custo_alimentacao = db.Column(db.Float, default=0)
    custo_outros      = db.Column(db.Float, default=0)
    descricao_custos  = db.Column(db.Text)
    cronograma        = db.Column(db.Text)
    analise_ambiente  = db.Column(db.Text)
    token_publico     = db.Column(db.String(64), unique=True)
    token_expira_em   = db.Column(db.DateTime)
    template_estilo   = db.Column(db.String(20), default='tech')
    criado_em         = db.Column(db.DateTime, default=datetime.now)
    enviado_em        = db.Column(db.DateTime)
    aprovado_em       = db.Column(db.DateTime)
    usuario_id        = db.Column(db.Integer)
    assinatura_nome   = db.Column(db.String(200))
    assinatura_cpf    = db.Column(db.String(20))
    assinatura_ip     = db.Column(db.String(45))
    assinatura_hash   = db.Column(db.String(128))

    # Link de pagamento gerado automaticamente quando o cliente assina --
    # mostrado na propria pagina de aprovacao (proposta_publica.html).
    mp_preference_id      = db.Column(db.String(100))
    mp_init_point         = db.Column(db.String(500))
    infinitypay_link      = db.Column(db.String(500))
    link_pagamento_gerado_em = db.Column(db.DateTime)

    itens   = db.relationship('ItemProposta', backref='proposta', lazy=True,
                  cascade='all, delete-orphan')
    anexos  = db.relationship('ProjetoAnexo', backref='proposta', lazy=True,
                  cascade='all, delete-orphan')

    anexos_projeto = db.relationship('AnexoProposta', backref='proposta', lazy=True, cascade='all, delete-orphan')
    etapas = db.relationship('EtapaProposta', backref='proposta', lazy=True, cascade='all, delete-orphan')


class ItemProposta(db.Model):
    __tablename__ = 'itens_proposta'
    id                  = db.Column(db.Integer, primary_key=True)
    proposta_id         = db.Column(db.Integer, db.ForeignKey('propostas.id'), nullable=False)
    produto_id          = db.Column(db.Integer)
    servico_id          = db.Column(db.Integer)
    descricao           = db.Column(db.String(300), nullable=False)
    quantidade          = db.Column(db.Float, default=1)
    preco_unitario      = db.Column(db.Float, default=0)
    markup              = db.Column(db.Float, default=0)
    tipo                = db.Column(db.String(20), default='produto')
    foto                = db.Column(db.String(300))
    descricao_detalhada = db.Column(db.Text)


class OrdemServico(db.Model):
    __tablename__ = 'ordens_servico'
    id             = db.Column(db.Integer, primary_key=True)
    empresa_id     = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    numero         = db.Column(db.String(30), nullable=False)
    titulo         = db.Column(db.String(200), nullable=False)
    cliente_id     = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    proposta_id    = db.Column(db.Integer)
    status         = db.Column(db.String(20), default='aberta')
    prioridade     = db.Column(db.String(20), default='normal')
    descricao      = db.Column(db.Text, nullable=False)
    solucao        = db.Column(db.Text)
    tecnico        = db.Column(db.String(100))
    data_prevista  = db.Column(db.Date)
    data_conclusao = db.Column(db.Date)
    criado_em      = db.Column(db.DateTime, default=datetime.now)
    usuario_id     = db.Column(db.Integer)

    assinatura = db.relationship('OsAssinatura', backref='os', lazy=True,
                     uselist=False, cascade='all, delete-orphan')


class ProjetoAnexo(db.Model):
    __tablename__ = 'projeto_anexos'
    id            = db.Column(db.Integer, primary_key=True)
    proposta_id   = db.Column(db.Integer, db.ForeignKey('propostas.id'), nullable=False)
    nome_original = db.Column(db.String(300), nullable=False)
    nome_arquivo  = db.Column(db.String(300), nullable=False)
    tipo          = db.Column(db.String(50))
    descricao     = db.Column(db.String(200))
    criado_em     = db.Column(db.DateTime, default=datetime.now)

class AnexoProposta(db.Model):
    """Anexos de projeto: plantas, fotos, elétrica, hidráulica"""
    __tablename__ = 'anexos_proposta'
    id            = db.Column(db.Integer, primary_key=True)
    proposta_id   = db.Column(db.Integer, db.ForeignKey('propostas.id'), nullable=False)
    nome_original = db.Column(db.String(300), nullable=False)
    nome_arquivo  = db.Column(db.String(300), nullable=False)
    tipo          = db.Column(db.String(50))  # planta_baixa, eletrica, hidraulica, foto, outro
    descricao     = db.Column(db.String(200))
    tamanho       = db.Column(db.Integer, default=0)
    criado_em     = db.Column(db.DateTime, default=datetime.now)


class EtapaProposta(db.Model):
    """Fases/etapas de execução de um serviço na proposta"""
    __tablename__ = 'etapas_proposta'
    id          = db.Column(db.Integer, primary_key=True)
    proposta_id = db.Column(db.Integer, db.ForeignKey('propostas.id'), nullable=False)
    ordem       = db.Column(db.Integer, default=0)
    titulo      = db.Column(db.String(200), nullable=False)
    descricao   = db.Column(db.Text)
    duracao_dias= db.Column(db.Integer, default=1)


class Contrato(db.Model):
    __tablename__ = 'contratos'
    id               = db.Column(db.Integer, primary_key=True)
    empresa_id       = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    proposta_id      = db.Column(db.Integer, db.ForeignKey('propostas.id'), nullable=False)
    numero           = db.Column(db.String(30), nullable=False)
    cliente_id       = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    status           = db.Column(db.String(20), default='pendente')
    token_assinatura = db.Column(db.String(64), unique=True)
    # Assinatura digital com validade jurídica (Marco Civil da Internet)
    assinado_em      = db.Column(db.DateTime)
    assinatura_nome  = db.Column(db.String(200))
    assinatura_cpf   = db.Column(db.String(20))
    assinatura_ip    = db.Column(db.String(45))
    assinatura_hash  = db.Column(db.String(128))  # SHA-256 cliente
    # Assinatura da empresa (segundo passo)
    empresa_assinado_em    = db.Column(db.DateTime)
    empresa_assinatura_nome= db.Column(db.String(200))
    empresa_assinatura_ip  = db.Column(db.String(45))
    empresa_assinatura_hash= db.Column(db.String(128))  # SHA-256 empresa
    texto_contrato   = db.Column(db.Text)
    clausulas_extra  = db.Column(db.Text)  # JSON com cláusulas customizadas
    prazo_dias       = db.Column(db.Integer, default=30)
    criado_em        = db.Column(db.DateTime, default=datetime.now)

    cliente  = db.relationship('Cliente', backref='contratos', lazy=True)
    proposta = db.relationship('Proposta', backref=db.backref('contrato', uselist=False), lazy=True)


class OsAssinatura(db.Model):
    __tablename__ = 'os_assinaturas'
    id              = db.Column(db.Integer, primary_key=True)
    os_id           = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=False)
    token           = db.Column(db.String(64), unique=True)
    assinado_em     = db.Column(db.DateTime)
    assinatura_nome = db.Column(db.String(200))
    assinatura_cpf  = db.Column(db.String(20))
    assinatura_ip   = db.Column(db.String(45))


class LicencaNeuraDesk(db.Model):
    """Licenças do produto NeuraDesk vendido para outras empresas.
    Cada linha representa UMA instalação do NeuraDesk em algum cliente."""
    __tablename__ = 'licencas_neuradesk'
    id                     = db.Column(db.Integer, primary_key=True)
    chave                  = db.Column(db.String(40), unique=True, nullable=False)
    empresa_nome           = db.Column(db.String(200), nullable=False)
    empresa_cnpj           = db.Column(db.String(30))
    empresa_id_nb          = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=True)
    max_usuarios           = db.Column(db.Integer, default=5)
    fingerprint_servidor   = db.Column(db.String(128))
    ativada_em             = db.Column(db.DateTime)
    status                 = db.Column(db.String(20), default='pendente')  # pendente, ativa, carencia, bloqueada, cancelada
    data_ultimo_pagamento  = db.Column(db.DateTime)
    data_vencimento        = db.Column(db.DateTime)
    valor_mensal           = db.Column(db.Float, default=0)
    mp_preapproval_id      = db.Column(db.String(100))
    mp_status              = db.Column(db.String(30))
    # Ultimo pagamento do Mercado Pago ja processado -- evita renovar duas
    # vezes se o MP reenviar a mesma notificacao de webhook (ele reenvia
    # quando nao recebe 200 a tempo, entao duplicata e esperada).
    mp_ultimo_pagamento_id = db.Column(db.String(50))
    ultima_verificacao     = db.Column(db.DateTime)
    ultimo_ip_verificacao  = db.Column(db.String(45))
    observacoes            = db.Column(db.Text)
    criado_em              = db.Column(db.DateTime, default=datetime.now)

    empresa_nb = db.relationship('Empresa', foreign_keys=[empresa_id_nb], lazy=True)

    @staticmethod
    def gerar_chave():
        grupos = [secrets.token_hex(2).upper() for _ in range(4)]
        return 'NRDK-' + '-'.join(grupos)


class ContratoNeuraDesk(db.Model):
    """Contrato de licenciamento de uso do NeuraDesk vendido a um cliente.
    Independente do Contrato/Proposta usado no negocio de propostas
    comerciais (Creative) -- esse aqui e especifico do licenciamento de
    software, com seu proprio texto e ciclo de assinatura. Uma linha por
    licenca (1:1 com LicencaNeuraDesk)."""
    __tablename__ = 'contratos_neuradesk'

    id         = db.Column(db.Integer, primary_key=True)
    licenca_id = db.Column(db.Integer, db.ForeignKey('licencas_neuradesk.id'), nullable=False, unique=True)

    numero           = db.Column(db.String(30), unique=True, nullable=False)
    token_assinatura = db.Column(db.String(64), unique=True, nullable=False)

    # Dados do contratante -- preenchidos pelo admin ao cadastrar, o
    # cliente so confere e assina (nao redigita nada).
    empresa_razao_social = db.Column(db.String(200))
    empresa_endereco     = db.Column(db.Text)
    representante_nome   = db.Column(db.String(150))
    representante_cpf    = db.Column(db.String(20))
    representante_email  = db.Column(db.String(150))

    # Endereço estruturado do responsável -- exigido pela API do Mercado
    # Pago pra emitir boleto registrado (payer.address). O empresa_endereco
    # acima é só texto livre pro contrato em si, não serve pra API.
    endereco_cep       = db.Column(db.String(10))
    endereco_rua       = db.Column(db.String(150))
    endereco_numero    = db.Column(db.String(20))
    endereco_bairro    = db.Column(db.String(100))
    endereco_cidade    = db.Column(db.String(100))
    endereco_uf        = db.Column(db.String(2))

    # Condicoes comerciais "congeladas" no momento da geracao -- mesmo
    # que o plano padrao mude depois, o que foi assinado fica registrado
    # aqui do jeito que foi combinado com esse cliente.
    valor_base              = db.Column(db.Float, default=0)
    usuarios_inclusos       = db.Column(db.Integer, default=5)
    valor_usuario_adicional = db.Column(db.Float, default=0)
    modulos_json            = db.Column(db.Text)  # [{"chave":"oracle","nome":"NeuraDBA","valor":150.0}, ...]
    dia_vencimento          = db.Column(db.Integer, default=10)
    cidade_foro             = db.Column(db.String(100))
    prazo_aviso_previo_dias = db.Column(db.Integer, default=30)

    # pendente -> assinado_cliente -> concluido (so 'concluido' e valido
    # como contrato executado -- ver Cláusula sobre assinatura dupla)
    status = db.Column(db.String(20), default='pendente')

    assinatura_nome  = db.Column(db.String(150))
    assinatura_cpf   = db.Column(db.String(20))
    assinatura_ip    = db.Column(db.String(45))
    assinatura_hash  = db.Column(db.String(64))
    assinado_em      = db.Column(db.DateTime)

    confirmado_por  = db.Column(db.String(150))
    confirmado_ip   = db.Column(db.String(45))
    confirmado_hash = db.Column(db.String(64))
    confirmado_em   = db.Column(db.DateTime)

    criado_em = db.Column(db.DateTime, default=datetime.now)

    licenca = db.relationship('LicencaNeuraDesk', backref=db.backref('contrato', uselist=False))

    def get_modulos(self):
        if not self.modulos_json:
            return []
        try:
            return json.loads(self.modulos_json)
        except Exception:
            return []

    def set_modulos(self, lista):
        self.modulos_json = json.dumps(lista, ensure_ascii=False)

    def valor_total_mensal(self):
        return (self.valor_base or 0) + sum(m.get('valor', 0) for m in self.get_modulos())

    @staticmethod
    def gerar_numero():
        return f"NDK-CT-{datetime.now().strftime('%Y%m')}-{secrets.token_hex(2).upper()}"


class PagamentoNeuraDesk(db.Model):
    """Cobranças avulsas (boleto/Pix) geradas pela página pública de
    cobrança, uma por tentativa. Não confundir com a assinatura recorrente
    (mp_preapproval_id em LicencaNeuraDesk) -- isso aqui é o mecanismo
    manual, o cliente clica e gera quando quiser pagar daquele jeito."""
    __tablename__ = 'pagamentos_neuradesk'

    id         = db.Column(db.Integer, primary_key=True)
    licenca_id = db.Column(db.Integer, db.ForeignKey('licencas_neuradesk.id'), nullable=False)

    tipo          = db.Column(db.String(10), nullable=False)  # boleto, pix
    mp_payment_id = db.Column(db.String(50))
    status        = db.Column(db.String(20), default='pending')  # pending, approved, cancelled, expired, rejected
    valor         = db.Column(db.Float, default=0)

    linha_digitavel = db.Column(db.String(80))
    boleto_url      = db.Column(db.String(500))
    pix_qr_base64   = db.Column(db.Text)
    pix_copia_cola  = db.Column(db.Text)

    criado_em = db.Column(db.DateTime, default=datetime.now)
    expira_em = db.Column(db.DateTime)
    pago_em   = db.Column(db.DateTime)

    licenca = db.relationship('LicencaNeuraDesk', backref='pagamentos')


def _fernet_integracoes():
    """Instância Fernet usada para cifrar/decifrar valores de integrações
    (tokens de API etc) em repouso. A chave vem só do .env -- nunca do
    código. O NeuraBusiness não usa python-dotenv (config.py lê o .env
    direto do arquivo), então usamos a mesma função aqui."""
    from cryptography.fernet import Fernet
    from config import Config
    chave = Config.INTEGRACOES_FERNET_KEY
    if not chave:
        raise RuntimeError(
            "INTEGRACOES_FERNET_KEY não definida. Gere uma com: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
            "e defina no .env antes de salvar integrações pela tela de admin."
        )
    return Fernet(chave.encode())


class Integracao(db.Model):
    """Configurações de integração com serviços externos (Mercado Pago,
    etc), editáveis pelo admin sem precisar mexer no servidor. Valor
    fica cifrado em repouso (Fernet) -- nunca em texto puro no banco."""
    __tablename__ = 'integracoes'

    id            = db.Column(db.Integer, primary_key=True)
    chave         = db.Column(db.String(50), unique=True, nullable=False)
    valor_cifrado = db.Column(db.Text)
    atualizado_em = db.Column(db.DateTime, default=datetime.now)

    def set_valor(self, valor_plano):
        self.valor_cifrado = _fernet_integracoes().encrypt(valor_plano.encode()).decode() if valor_plano else None
        self.atualizado_em = datetime.now()

    def get_valor(self):
        if not self.valor_cifrado:
            return ''
        return _fernet_integracoes().decrypt(self.valor_cifrado.encode()).decode()

    @staticmethod
    def obter(chave, default=''):
        reg = Integracao.query.filter_by(chave=chave).first()
        if not reg:
            return default
        return reg.get_valor() or default
