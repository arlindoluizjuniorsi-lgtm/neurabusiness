"""NeuraBusiness — Modelos de Dados (SQLAlchemy)"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
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

    # Config fiscal pra emissao de NFS-e via Sistema Nacional NFS-e (Sefin
    # Nacional/ADN) -- ver nfse_nacional.py. O certificado (.pfx) e a senha
    # ficam cifrados em Integracao, nao aqui.
    nfse_codigo_municipio          = db.Column(db.String(7))    # codigo IBGE do municipio do prestador
    nfse_inscricao_municipal       = db.Column(db.String(30))
    nfse_codigo_tributacao_nacional = db.Column(db.String(10))  # ex: 010701 (item 1.07.01 da lista LC116)
    nfse_cnbs                      = db.Column(db.String(15))   # Nomenclatura Brasileira de Servicos
    nfse_regime_tributario         = db.Column(db.String(20), default='mei')  # mei | simples_nacional | normal
    nfse_aliquota_iss              = db.Column(db.Float, default=0)
    nfse_ambiente                  = db.Column(db.String(20), default='homologacao')  # homologacao | producao
    nfse_serie_dps                 = db.Column(db.String(5), default='1')
    nfse_ultimo_numero_dps         = db.Column(db.Integer, default=0)

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

    # Codigo do municipio (IBGE, 7 digitos) do endereco do cliente -- usado
    # na emissao de NFS-e (tomador do servico). Preenchido automaticamente
    # (e cacheado aqui) via consulta a API publica do IBGE por cidade/estado
    # na primeira emissao, ver nfse_nacional.buscar_codigo_municipio_ibge.
    codigo_municipio_ibge = db.Column(db.String(7))

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

    # Confirmacao de pagamento (webhook MP / verificacao InfinitePay).
    # status_pagamento: pendente (nada confirmado) | parcial (sinal pago) | pago (total confirmado)
    status_pagamento      = db.Column(db.String(20), default='pendente')
    valor_pago            = db.Column(db.Float, default=0)
    # 50 (cliente optou por pagar so o sinal) ou 100 (integral) -- escolhido
    # na propria assinatura publica; some para 100 quando o cliente decide
    # pagar o restante depois.
    pagamento_percentual  = db.Column(db.Integer)
    mp_payment_id         = db.Column(db.String(50))
    pago_em               = db.Column(db.DateTime)

    # Nota Fiscal de Servico Eletronica (NFS-e Nacional) emitida a partir
    # desta proposta -- ver nfse_nacional.py.
    nfse_chave_acesso = db.Column(db.String(60))
    nfse_numero_dps   = db.Column(db.Integer)
    nfse_serie_dps    = db.Column(db.String(5))
    nfse_status       = db.Column(db.String(20), default='nao_emitida')  # nao_emitida | emitida | erro
    nfse_emitido_em   = db.Column(db.DateTime)
    nfse_erro         = db.Column(db.Text)

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
    itens = db.relationship('ItemOs', backref='ordem_servico', lazy=True,
                     cascade='all, delete-orphan', order_by='ItemOs.id')


class ItemOs(db.Model):
    """Tarefa/item da OS -- pré-preenchido a partir dos itens da proposta
    quando a OS é gerada automaticamente após o pagamento, pra marcar
    conforme vai concluindo."""
    __tablename__ = 'itens_os'
    id           = db.Column(db.Integer, primary_key=True)
    os_id        = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=False)
    descricao    = db.Column(db.String(300), nullable=False)
    concluido    = db.Column(db.Boolean, default=False)
    concluido_em = db.Column(db.DateTime)


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


class CartaoPessoal(db.Model):
    """Cartão de crédito usado nos gastos pessoais (Gestão Pessoal) --
    agrupa lançamentos (ex: BB, Meli) e guarda limite/fechamento/cor."""
    __tablename__ = 'gp_cartoes'
    id             = db.Column(db.Integer, primary_key=True)
    usuario_id     = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nome           = db.Column(db.String(50), nullable=False)
    limite         = db.Column(db.Float, default=0)
    dia_fechamento = db.Column(db.Integer, default=1)  # dia do mês em que a fatura fecha (1 = sem ajuste, usa mês calendário puro)
    cor            = db.Column(db.String(7), default='#64748b')  # cor do badge (hex), texto claro/escuro calculado automaticamente
    ativo          = db.Column(db.Boolean, default=True)
    criado_em      = db.Column(db.DateTime, default=datetime.now)

    def ciclo_atual(self):
        """Mês (date, dia 1) da fatura corrente, considerando o dia de
        fechamento -- antes do fechamento do mês, a fatura "corrente"
        ainda é a do mês anterior (evita avançar a numeração das
        parcelas cedo demais, antes da fatura realmente fechar)."""
        hoje = date.today()
        if hoje.day >= (self.dia_fechamento or 1):
            return hoje.replace(day=1)
        mes = hoje.month - 2
        ano = hoje.year + mes // 12
        mes = mes % 12 + 1
        return date(ano, mes, 1)


class RendaPessoal(db.Model):
    """Entrada de renda pessoal (Gestão Pessoal) -- alimentada manualmente
    (ex: Salário dia 20, Salário dia 05, Extra) pra comparar com os gastos
    do mês e saber quanto precisa entrar/sobra.
      fixa  -> se repete todo mês (salário), conta enquanto ativo=True
      extra -> pontual, só conta no mês de mes_referencia (ex: '2026-08')
    """
    __tablename__ = 'gp_rendas'
    id              = db.Column(db.Integer, primary_key=True)
    usuario_id      = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tipo            = db.Column(db.String(20), nullable=False, default='fixa')  # fixa|extra
    descricao       = db.Column(db.String(200), nullable=False)
    valor           = db.Column(db.Float, nullable=False, default=0)
    dia_recebimento = db.Column(db.Integer)  # informativo, usado em 'fixa' (ex: 20, 5)
    mes_referencia  = db.Column(db.String(7))  # 'YYYY-MM', usado em 'extra'
    ativo           = db.Column(db.Boolean, default=True)
    criado_em       = db.Column(db.DateTime, default=datetime.now)
    atualizado_em   = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def conta_no_mes(self, ref=None):
        ref = ref or date.today()
        if self.tipo == 'fixa':
            return self.ativo
        return self.ativo and self.mes_referencia == ref.strftime('%Y-%m')


class GastoPessoal(db.Model):
    """Lançamento de gasto pessoal (Gestão Pessoal). Substitui a planilha
    GASTOS.xlsx -- cobre os 4 tipos que existiam nela:
      fixo       -> gasto fixo mensal (categoria, sem cartão), sempre conta
                    enquanto ativo=True (ex: Carro, Energia, MEI...)
      recorrente -> assinatura/gasto recorrente de um cartão (Spotify,
                    Netflix...), sempre conta enquanto ativo=True
      avista     -> compra pontual de um cartão, só conta no mês de
                    mes_referencia (ex: "2026-08")
      parcelado  -> compra parcelada de um cartão; a parcela atual é
                    calculada a partir de data_primeira_parcela + o mês
                    corrente (não precisa mais atualizar "X/Y" à mão toda
                    fatura -- isso é o que a planilha exigia manualmente)
    """
    __tablename__ = 'gp_gastos'
    id                    = db.Column(db.Integer, primary_key=True)
    usuario_id            = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tipo                  = db.Column(db.String(20), nullable=False)  # fixo|recorrente|avista|parcelado
    cartao_id             = db.Column(db.Integer, db.ForeignKey('gp_cartoes.id'))  # null pra 'fixo'
    categoria             = db.Column(db.String(100))  # usado em 'fixo' (Carro, Seguro, Energia...)
    descricao             = db.Column(db.String(200), nullable=False)
    valor                 = db.Column(db.Float, nullable=False, default=0)
    mes_referencia         = db.Column(db.String(7))   # 'YYYY-MM', usado em 'avista'
    data_primeira_parcela = db.Column(db.Date)          # usado em 'parcelado'
    parcela_total         = db.Column(db.Integer)       # usado em 'parcelado'
    ativo                 = db.Column(db.Boolean, default=True)
    criado_em             = db.Column(db.DateTime, default=datetime.now)
    atualizado_em         = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    cartao = db.relationship('CartaoPessoal')

    def parcela_atual(self, ref=None):
        """Nº da parcela corrente (1-based) na competência `ref` (date,
        default hoje), calculado a partir de data_primeira_parcela --
        automatiza o que antes era editado à mão na planilha."""
        if not self.data_primeira_parcela:
            return None
        ref = ref or date.today()
        meses = (ref.year - self.data_primeira_parcela.year) * 12 + (ref.month - self.data_primeira_parcela.month) + 1
        return meses

    def quitado(self, ref=None):
        if self.tipo != 'parcelado' or not self.parcela_total:
            return False
        atual = self.parcela_atual(ref)
        return atual is not None and atual > self.parcela_total

    def parcelas_restantes(self, ref=None):
        """Quantas parcelas (contando a corrente) ainda faltam pagar --
        usado pra calcular quanto do limite do cartão está comprometido."""
        if self.tipo != 'parcelado' or not self.parcela_total:
            return 0
        atual = self.parcela_atual(ref)
        if atual is None:
            return 0
        return max(self.parcela_total - atual + 1, 0)

    def valor_restante(self, ref=None):
        """Quanto ainda falta pagar no total (parcelas restantes x valor da parcela)."""
        return self.valor * self.parcelas_restantes(ref)

    def conta_no_mes(self, ref=None):
        """Se este lançamento entra na conta do mês de referência."""
        ref = ref or date.today()
        if self.tipo in ('fixo', 'recorrente'):
            return self.ativo
        if self.tipo == 'avista':
            return self.mes_referencia == ref.strftime('%Y-%m')
        if self.tipo == 'parcelado':
            atual = self.parcela_atual(ref)
            return self.ativo and atual is not None and 1 <= atual <= (self.parcela_total or 0)
        return False


class GastoCarro(db.Model):
    """Gasto com o carro (Gestão Pessoal) -- lançado manualmente ou
    importado de XML de NFe/NFC-e (posto de gasolina, oficina, etc).
    `chave_nfe` é única pra não importar a mesma nota duas vezes."""
    __tablename__ = 'gp_gastos_carro'
    id                     = db.Column(db.Integer, primary_key=True)
    usuario_id             = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tipo                   = db.Column(db.String(20), nullable=False, default='outro')
    # combustivel|manutencao|pedagio|multa|seguro|ipva|lavagem|acessorio|outro
    data                   = db.Column(db.Date, nullable=False, default=date.today)
    descricao              = db.Column(db.String(300))
    valor                  = db.Column(db.Float, nullable=False, default=0)  # valor TOTAL da compra (se parcelado, a parcela é calculada dividindo por parcela_total)
    km_atual               = db.Column(db.Integer)
    litros                 = db.Column(db.Float)  # usado em 'combustivel'
    tanque_cheio           = db.Column(db.Boolean, default=True)  # abasteceu até completar o tanque? se não (top-off preventivo), entra na conta de consumo sem virar ponto de referência
    posto_estabelecimento  = db.Column(db.String(200))
    forma_pagamento        = db.Column(db.String(50))
    numero_nota            = db.Column(db.String(20))
    chave_nfe              = db.Column(db.String(44), unique=True)
    itens_json             = db.Column(db.Text)  # itens detalhados da nota (se importado de XML)
    arquivo_xml            = db.Column(db.String(300))  # nome do arquivo salvo em static/uploads
    origem                 = db.Column(db.String(10), default='manual')  # manual|xml
    cartao_id              = db.Column(db.Integer, db.ForeignKey('gp_cartoes.id'))  # se pago no cartão -- entra na fatura/limite dele
    parcela_total          = db.Column(db.Integer)  # se > 1, `valor` (total) é dividido por parcela_total pra saber quanto entra em cada fatura
    criado_em              = db.Column(db.DateTime, default=datetime.now)
    atualizado_em          = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    cartao = db.relationship('CartaoPessoal')

    def itens(self):
        if not self.itens_json:
            return []
        try:
            return json.loads(self.itens_json)
        except (ValueError, TypeError):
            return []

    def parcela_atual(self, ref=None):
        """Nº da parcela corrente (1-based) -- sempre 1 se não for parcelado."""
        if not self.parcela_total or self.parcela_total <= 1:
            return 1
        ref = ref or date.today()
        return (ref.year - self.data.year) * 12 + (ref.month - self.data.month) + 1

    def quitado(self, ref=None):
        if not self.parcela_total or self.parcela_total <= 1:
            return False
        return self.parcela_atual(ref) > self.parcela_total

    def parcelas_restantes(self, ref=None):
        """Quantas parcelas (contando a corrente) ainda vão aparecer em
        faturas a partir de `ref` -- usado pra saber quanto do limite do
        cartão esse gasto ainda compromete."""
        ref = ref or date.today()
        if not self.parcela_total or self.parcela_total <= 1:
            return 1 if (self.data.year == ref.year and self.data.month == ref.month) else 0
        atual = self.parcela_atual(ref)
        return max(self.parcela_total - atual + 1, 0)

    def valor_parcela(self):
        """Quanto entra em CADA fatura -- `valor` é o total da compra;
        se parcelado, divide pelo nº de parcelas."""
        if self.parcela_total and self.parcela_total > 1:
            return self.valor / self.parcela_total
        return self.valor

    def valor_restante(self, ref=None):
        return self.valor_parcela() * self.parcelas_restantes(ref)

    def conta_no_mes(self, ref=None):
        ref = ref or date.today()
        if not self.parcela_total or self.parcela_total <= 1:
            return self.data.year == ref.year and self.data.month == ref.month
        atual = self.parcela_atual(ref)
        return 1 <= atual <= self.parcela_total


class GastoCasa(db.Model):
    """Gasto da casa (Gestão Pessoal) -- mercado, hortifruti, açougue,
    manutenção da casa, coisas do bebê etc. Mesmo esquema do GastoCarro
    (XML de NFe/NFC-e, cartão/parcelas, dedup por chave_nfe), mas também
    dá pra montar a compra item a item na mão (sem precisar de XML)."""
    __tablename__ = 'gp_gastos_casa'
    id                 = db.Column(db.Integer, primary_key=True)
    usuario_id         = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tipo               = db.Column(db.String(20), nullable=False, default='outro')
    # mercado|hortifruti|acougue|manutencao|bebe|outro
    data               = db.Column(db.Date, nullable=False, default=date.today)
    descricao          = db.Column(db.String(300))
    valor              = db.Column(db.Float, nullable=False, default=0)  # valor TOTAL da compra (se parcelado, a parcela é calculada dividindo por parcela_total)
    estabelecimento    = db.Column(db.String(200))
    forma_pagamento    = db.Column(db.String(50))
    numero_nota        = db.Column(db.String(20))
    chave_nfe          = db.Column(db.String(44), unique=True)
    itens_json         = db.Column(db.Text)  # itens da compra -- vindos do XML OU montados item a item na mão
    arquivo_xml        = db.Column(db.String(300))
    origem             = db.Column(db.String(10), default='manual')  # manual|xml
    cartao_id          = db.Column(db.Integer, db.ForeignKey('gp_cartoes.id'))
    parcela_total      = db.Column(db.Integer)
    criado_em          = db.Column(db.DateTime, default=datetime.now)
    atualizado_em      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    cartao = db.relationship('CartaoPessoal')

    def itens(self):
        if not self.itens_json:
            return []
        try:
            return json.loads(self.itens_json)
        except (ValueError, TypeError):
            return []

    def parcela_atual(self, ref=None):
        if not self.parcela_total or self.parcela_total <= 1:
            return 1
        ref = ref or date.today()
        return (ref.year - self.data.year) * 12 + (ref.month - self.data.month) + 1

    def quitado(self, ref=None):
        if not self.parcela_total or self.parcela_total <= 1:
            return False
        return self.parcela_atual(ref) > self.parcela_total

    def parcelas_restantes(self, ref=None):
        ref = ref or date.today()
        if not self.parcela_total or self.parcela_total <= 1:
            return 1 if (self.data.year == ref.year and self.data.month == ref.month) else 0
        atual = self.parcela_atual(ref)
        return max(self.parcela_total - atual + 1, 0)

    def valor_parcela(self):
        if self.parcela_total and self.parcela_total > 1:
            return self.valor / self.parcela_total
        return self.valor

    def valor_restante(self, ref=None):
        return self.valor_parcela() * self.parcelas_restantes(ref)

    def conta_no_mes(self, ref=None):
        ref = ref or date.today()
        if not self.parcela_total or self.parcela_total <= 1:
            return self.data.year == ref.year and self.data.month == ref.month
        atual = self.parcela_atual(ref)
        return 1 <= atual <= self.parcela_total


class VeiculoPessoal(db.Model):
    """Veículo do usuário (Gestão Pessoal) -- separado da revisão em si
    justamente pra poder trocar de carro sem perder o histórico: as
    revisões antigas continuam ligadas ao carro antigo, as novas vão pro
    carro novo, sem precisar migrar nada na mão."""
    __tablename__ = 'gp_veiculos'
    id              = db.Column(db.Integer, primary_key=True)
    usuario_id      = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    apelido         = db.Column(db.String(100))
    marca           = db.Column(db.String(60))
    modelo          = db.Column(db.String(80))
    ano_modelo      = db.Column(db.Integer)
    ano_fabricacao  = db.Column(db.Integer)
    placa           = db.Column(db.String(10))
    cor             = db.Column(db.String(40))
    combustivel     = db.Column(db.String(20))  # flex|gasolina|diesel|etanol|eletrico|hibrido
    km_atual        = db.Column(db.Integer)
    # manual|automatico|cvt|dualogic|outro -- define quais itens de
    # manutenção recorrente fazem sentido (ex: fluido do atuador do
    # robô só existe em câmbio automatizado tipo Dualogic) e qual óleo
    # recomendar em cada caixa (ver INFO_CAMBIO em app.py).
    tipo_cambio     = db.Column(db.String(20))
    ativo           = db.Column(db.Boolean, default=True)
    criado_em       = db.Column(db.DateTime, default=datetime.now)

    def nome_exibicao(self):
        partes = [self.apelido, self.marca, self.modelo, str(self.ano_modelo) if self.ano_modelo else None]
        nome = ' '.join(p for p in partes if p)
        return nome or f'Veículo #{self.id}'


class RevisaoCarro(db.Model):
    """Revisão/manutenção de um veículo (Gestão Pessoal) -- odômetro,
    motivo (rotina/quebra), peças usadas (item a item ou via XML da nota
    da oficina) e mão de obra separada. Mesmo esquema de cartão/parcelas
    dos outros módulos de gastos."""
    __tablename__ = 'gp_revisoes_carro'
    id              = db.Column(db.Integer, primary_key=True)
    usuario_id      = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    veiculo_id      = db.Column(db.Integer, db.ForeignKey('gp_veiculos.id'), nullable=False)
    data            = db.Column(db.Date, nullable=False, default=date.today)
    odometro        = db.Column(db.Integer, nullable=False)
    motivo          = db.Column(db.String(20), nullable=False, default='rotina')  # rotina|quebra
    oficina         = db.Column(db.String(200))
    descricao       = db.Column(db.String(400))
    mao_de_obra     = db.Column(db.Float, default=0)
    itens_json      = db.Column(db.Text)  # peças: [{descricao, qtd, valor}]
    valor_total     = db.Column(db.Float, nullable=False, default=0)  # mao_de_obra + peças (ou vNF da nota, se XML)
    forma_pagamento = db.Column(db.String(50))
    numero_nota     = db.Column(db.String(20))
    chave_nfe       = db.Column(db.String(44), unique=True)
    arquivo_xml     = db.Column(db.String(300))
    origem          = db.Column(db.String(10), default='manual')  # manual|xml
    cartao_id       = db.Column(db.Integer, db.ForeignKey('gp_cartoes.id'))
    parcela_total   = db.Column(db.Integer)
    # True só pra notas importadas por XML que ainda não viraram uma
    # revisão de verdade (falta odômetro/motivo) -- ficam "soltas" até o
    # usuário puxar as peças delas pra dentro de uma revisão (nova ou já
    # existente) ou completar os dados direto nela mesma.
    pendente        = db.Column(db.Boolean, default=False)
    criado_em       = db.Column(db.DateTime, default=datetime.now)
    atualizado_em   = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    veiculo = db.relationship('VeiculoPessoal')
    cartao  = db.relationship('CartaoPessoal')

    def itens(self):
        if not self.itens_json:
            return []
        try:
            return json.loads(self.itens_json)
        except (ValueError, TypeError):
            return []

    def valor_pecas(self):
        return sum(it.get('valor', 0) for it in self.itens())

    def parcela_atual(self, ref=None):
        if not self.parcela_total or self.parcela_total <= 1:
            return 1
        ref = ref or date.today()
        return (ref.year - self.data.year) * 12 + (ref.month - self.data.month) + 1

    def quitado(self, ref=None):
        if not self.parcela_total or self.parcela_total <= 1:
            return False
        return self.parcela_atual(ref) > self.parcela_total

    def parcelas_restantes(self, ref=None):
        ref = ref or date.today()
        if not self.parcela_total or self.parcela_total <= 1:
            return 1 if (self.data.year == ref.year and self.data.month == ref.month) else 0
        atual = self.parcela_atual(ref)
        return max(self.parcela_total - atual + 1, 0)

    def valor_parcela(self):
        if self.parcela_total and self.parcela_total > 1:
            return self.valor_total / self.parcela_total
        return self.valor_total

    def valor_restante(self, ref=None):
        return self.valor_parcela() * self.parcelas_restantes(ref)

    def conta_no_mes(self, ref=None):
        ref = ref or date.today()
        if not self.parcela_total or self.parcela_total <= 1:
            return self.data.year == ref.year and self.data.month == ref.month
        atual = self.parcela_atual(ref)
        return 1 <= atual <= self.parcela_total


class ManutencaoRecorrente(db.Model):
    """Um "carimbo" de quando um item de manutenção de rotina (óleo do
    motor, filtro de ar, óleo do câmbio, fluido do atuador do robô
    Dualogic etc.) foi feito -- gerado a partir dos checkboxes marcados
    numa RevisaoCarro. Serve pra calcular "próxima troca prevista"
    (odômetro/data do último registro + intervalo do catálogo em
    app.py, ou o intervalo customizado abaixo se o usuário informou
    um diferente do padrão)."""
    __tablename__ = 'gp_manutencoes_recorrentes'
    id              = db.Column(db.Integer, primary_key=True)
    usuario_id      = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    veiculo_id      = db.Column(db.Integer, db.ForeignKey('gp_veiculos.id'), nullable=False)
    revisao_id      = db.Column(db.Integer, db.ForeignKey('gp_revisoes_carro.id'))
    tipo            = db.Column(db.String(40), nullable=False)  # chave do catálogo TIPOS_MANUTENCAO_RECORRENTE
    data            = db.Column(db.Date, nullable=False)
    odometro        = db.Column(db.Integer, nullable=False)
    intervalo_km    = db.Column(db.Integer)     # None = usa o padrão do catálogo
    intervalo_meses = db.Column(db.Integer)     # None = usa o padrão do catálogo
    criado_em       = db.Column(db.DateTime, default=datetime.now)

    veiculo = db.relationship('VeiculoPessoal')
    revisao = db.relationship('RevisaoCarro')


class ItemVendaTroca(db.Model):
    """Item avulso que o usuário pretende vender pra ajudar na entrada de
    um carro novo (Gestão Pessoal > Troca de Carro) -- ex: "Moto, R$
    5.000". Não é ligado a um veículo específico (é sobre o carro que
    ainda não existe), só uma lista solta que soma no simulador."""
    __tablename__ = 'gp_itens_venda_troca'
    id          = db.Column(db.Integer, primary_key=True)
    usuario_id  = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    descricao   = db.Column(db.String(200), nullable=False)
    valor       = db.Column(db.Float, nullable=False, default=0)
    criado_em   = db.Column(db.DateTime, default=datetime.now)


class SimulacaoTrocaCarro(db.Model):
    """Uma "foto" salva do simulador de Troca de Carro -- pra comparar
    carros diferentes que o usuário considerou, ou revisitar depois pra
    ver se a compra valeu a pena frente ao que foi simulado. Guarda os
    números já calculados (não só os campos de entrada) porque a FIPE e
    a taxa de juros mudam com o tempo -- a simulação salva tem que
    continuar mostrando o que foi visto NAQUELE momento, não recalcular
    com dado novo."""
    __tablename__ = 'gp_simulacoes_troca_carro'
    id                  = db.Column(db.Integer, primary_key=True)
    usuario_id          = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nome_carro_novo     = db.Column(db.String(150), nullable=False)
    valor_carro_novo    = db.Column(db.Float, nullable=False, default=0)

    # Carro atual (referência FIPE usada nessa simulação)
    carro_atual_fipe    = db.Column(db.String(200))   # "Fiat Linea LX 1.8 Dualogic 2011 Flex"
    valor_fipe          = db.Column(db.Float)
    oferta_loja         = db.Column(db.Float, default=0)
    saldo_devedor       = db.Column(db.Float, default=0)

    total_itens_venda   = db.Column(db.Float, default=0)
    total_entrada       = db.Column(db.Float, default=0)

    taxa_juros_am       = db.Column(db.Float, default=0)   # % a.m.
    parcelas             = db.Column(db.Integer, default=0)
    valor_parcela        = db.Column(db.Float, default=0)
    total_pago           = db.Column(db.Float, default=0)
    total_juros          = db.Column(db.Float, default=0)

    # Quanto o usuário já paga hoje (financiamento do carro atual, se
    # ainda tiver) -- pra comparar direto com valor_parcela e saber se a
    # troca aumenta ou diminui o comprometimento mensal.
    parcela_atual        = db.Column(db.Float)

    notas               = db.Column(db.Text)  # espaço livre pra anotar depois como foi ("comprei em X", "desisti porque Y")
    criado_em           = db.Column(db.DateTime, default=datetime.now)
