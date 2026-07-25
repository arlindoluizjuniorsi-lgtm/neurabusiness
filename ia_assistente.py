"""
Assistente de gestao do NeuraBusiness via Gemini (function calling).

Diferente de ia_unificada.py (que so classifica e devolve dados pro bot
montar a proposta), este modulo deixa a IA de fato AGIR sobre o banco:
consultar propostas/clientes/produtos/servicos, cadastrar e editar
registros, adicionar/remover item de proposta etc.

Design: o Gemini recebe uma lista de "ferramentas" (funcoes Python reais)
e decide qual chamar e com quais parametros a partir do comando em
portugues. A propria funcao Python formata o resultado em texto pronto
pra Telegram -- a IA NAO formata o resultado nem "narra" numeros, so
escolhe a ferramenta e os argumentos. Isso evita qualquer risco da IA
inventar/alucinar valor, cliente ou numero de proposta que na verdade
vem do banco.

Escopo: sistema mono-empresa (so existe uma Empresa cadastrada, ver
creative_bot.get_emp()) -- toda ferramenta recebe empresa_id e filtra
por ele, mas nao ha necessidade de isolamento entre "tenants" porque so
existe um.
"""
import urllib.request
import urllib.error
import json
import base64
import difflib
from datetime import timedelta

from config import Config

GEMINI_API_KEY = Config.GEMINI_API_KEY
GEMINI_MODEL   = 'gemini-3.5-flash'
GEMINI_URL     = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'


def fmt(v):
    return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def _match(nome_busca, opcoes):
    """opcoes: lista de objetos com atributo .nome. Retorna o objeto mais
    parecido ou None (mesma logica de melhor_match do creative_bot)."""
    if not nome_busca or not opcoes:
        return None
    alvo = nome_busca.lower().strip()
    for o in opcoes:
        if o.nome.lower().strip() == alvo:
            return o
    for o in opcoes:
        if alvo in o.nome.lower() or o.nome.lower() in alvo:
            return o
    nomes = [o.nome.lower() for o in opcoes]
    m = difflib.get_close_matches(alvo, nomes, n=1, cutoff=0.4)
    if m:
        for o in opcoes:
            if o.nome.lower() == m[0]:
                return o
    return None


# ═══════════════════════ FERRAMENTAS (mexem no banco de verdade) ═══════════════════════

def listar_propostas(empresa_id, status=None, limite=10):
    from app import app
    from models import Proposta
    with app.app_context():
        qry = Proposta.query.filter_by(empresa_id=empresa_id)
        if status:
            qry = qry.filter(Proposta.status.ilike(f'%{status}%'))
        props = qry.order_by(Proposta.criado_em.desc()).limit(min(int(limite or 10), 30)).all()
        if not props:
            return "Nenhuma proposta encontrada."
        linhas = ["📋 *Propostas:*\n"]
        for p in props:
            total = sum(i.preco_unitario * i.quantidade for i in p.itens)
            linhas.append(f"• `{p.numero}` — {p.cliente.nome if p.cliente else '?'} — {fmt(total)} — _{p.status}_")
        return "\n".join(linhas)


def buscar_proposta(empresa_id, numero_ou_cliente):
    from app import app
    from models import Proposta
    with app.app_context():
        termo = (numero_ou_cliente or '').strip()
        p = Proposta.query.filter_by(empresa_id=empresa_id, numero=termo).first()
        if not p:
            propostas = Proposta.query.filter_by(empresa_id=empresa_id) \
                .order_by(Proposta.criado_em.desc()).all()
            candidatas = [pp for pp in propostas if pp.cliente and termo.lower() in pp.cliente.nome.lower()]
            if candidatas:
                p = candidatas[0]
        if not p:
            return f"Não encontrei nenhuma proposta com '{numero_ou_cliente}'."
        total = sum(i.preco_unitario * i.quantidade for i in p.itens)
        linhas = [
            f"📄 *Proposta {p.numero}* — _{p.status}_",
            f"👤 Cliente: {p.cliente.nome if p.cliente else '?'}",
            f"💳 Pagamento: {p.forma_pagamento or '-'}",
            f"📅 Validade: {p.validade} dias",
            "", "📦 Itens:",
        ]
        for i in p.itens:
            linhas.append(f"  • {i.descricao} x{i.quantidade} — {fmt(i.preco_unitario * i.quantidade)}")
        linhas.append(f"\n💰 Total: {fmt(total)}")
        return "\n".join(linhas)


def listar_clientes(empresa_id, busca=None, limite=20):
    from app import app
    from models import Cliente
    with app.app_context():
        qry = Cliente.query.filter_by(empresa_id=empresa_id)
        if busca:
            qry = qry.filter(Cliente.nome.ilike(f'%{busca}%'))
        clientes = qry.order_by(Cliente.nome).limit(min(int(limite or 20), 50)).all()
        if not clientes:
            return "Nenhum cliente encontrado."
        linhas = ["👥 *Clientes:*\n"]
        for c in clientes:
            linhas.append(f"• {c.nome}" + (f" — {c.telefone}" if c.telefone else ""))
        return "\n".join(linhas)


def listar_produtos(empresa_id, busca=None, limite=20):
    from app import app
    from models import Produto
    with app.app_context():
        qry = Produto.query.filter_by(empresa_id=empresa_id, ativo=True)
        if busca:
            qry = qry.filter(Produto.nome.ilike(f'%{busca}%'))
        produtos = qry.order_by(Produto.nome).limit(min(int(limite or 20), 50)).all()
        if not produtos:
            return "Nenhum produto encontrado."
        linhas = ["📦 *Produtos:*\n"]
        for p in produtos:
            linhas.append(f"• {p.nome} — {fmt(p.preco_venda or 0)}" + (f" (estoque: {p.estoque})" if p.estoque else ""))
        return "\n".join(linhas)


def listar_servicos(empresa_id, busca=None, limite=20):
    from app import app
    from models import Servico
    with app.app_context():
        qry = Servico.query.filter_by(empresa_id=empresa_id, ativo=True)
        if busca:
            qry = qry.filter(Servico.nome.ilike(f'%{busca}%'))
        servicos = qry.order_by(Servico.nome).limit(min(int(limite or 20), 50)).all()
        if not servicos:
            return "Nenhum serviço encontrado."
        linhas = ["🔧 *Serviços:*\n"]
        for s in servicos:
            linhas.append(f"• {s.nome} — {fmt(s.preco_unitario or 0)}")
        return "\n".join(linhas)


def resumo_geral(empresa_id):
    from app import app
    from models import Proposta, Cliente, Produto, Servico
    with app.app_context():
        total_propostas = Proposta.query.filter_by(empresa_id=empresa_id).count()
        aprovadas = Proposta.query.filter_by(empresa_id=empresa_id, status='aprovada').all()
        clientes = Cliente.query.filter_by(empresa_id=empresa_id).count()
        produtos = Produto.query.filter_by(empresa_id=empresa_id, ativo=True).count()
        servicos = Servico.query.filter_by(empresa_id=empresa_id, ativo=True).count()
        valor_aprovado = sum(i.preco_unitario * i.quantidade for p in aprovadas for i in p.itens)
        return (
            "📊 *Resumo geral:*\n\n"
            f"📋 Propostas: {total_propostas} ({len(aprovadas)} aprovadas)\n"
            f"💰 Valor aprovado: {fmt(valor_aprovado)}\n"
            f"👥 Clientes: {clientes}\n"
            f"📦 Produtos ativos: {produtos}\n"
            f"🔧 Serviços ativos: {servicos}"
        )


def cadastrar_cliente(empresa_id, nome, telefone=None, email=None, cpf_cnpj=None,
                       endereco=None, cidade=None, estado=None, cep=None, tipo=None):
    from app import app, db
    from models import Cliente
    with app.app_context():
        c = Cliente(empresa_id=empresa_id, nome=nome, telefone=telefone, email=email,
                    cpf_cnpj=cpf_cnpj, endereco=endereco, cidade=cidade,
                    estado=(estado or '')[:2] or None, cep=cep,
                    tipo=(tipo or 'PF').upper()[:2])
        db.session.add(c)
        db.session.commit()
        return f"✅ Cliente *{nome}* cadastrado" + (f" ({telefone})" if telefone else "") + "."


def editar_cliente(empresa_id, nome_atual, novo_nome=None, telefone=None, email=None,
                   endereco=None, cidade=None, estado=None, cep=None):
    from app import app, db
    from models import Cliente
    with app.app_context():
        clientes = Cliente.query.filter_by(empresa_id=empresa_id).all()
        c = _match(nome_atual, clientes)
        if not c:
            return f"Não encontrei nenhum cliente parecido com '{nome_atual}'."
        alterado = []
        if novo_nome: c.nome = novo_nome; alterado.append('nome')
        if telefone: c.telefone = telefone; alterado.append('telefone')
        if email: c.email = email; alterado.append('email')
        if endereco: c.endereco = endereco; alterado.append('endereço')
        if cidade: c.cidade = cidade; alterado.append('cidade')
        if estado: c.estado = estado[:2]; alterado.append('estado')
        if cep: c.cep = cep; alterado.append('CEP')
        if not alterado:
            return "Nada pra alterar -- diga o que quer mudar nesse cliente."
        db.session.commit()
        return f"✅ Cliente *{c.nome}* atualizado: {', '.join(alterado)}."


def cadastrar_produto(empresa_id, nome, preco_venda, preco_custo=None, categoria=None,
                      descricao=None, estoque=None):
    from app import app, db
    from models import Produto
    with app.app_context():
        pr = Produto(empresa_id=empresa_id, nome=nome, preco_venda=float(preco_venda),
                     preco_custo=float(preco_custo) if preco_custo is not None else 0,
                     categoria=categoria, descricao=descricao,
                     estoque=int(estoque) if estoque is not None else 0)
        db.session.add(pr)
        db.session.commit()
        return f"✅ Produto *{nome}* cadastrado — {fmt(float(preco_venda))}."


def editar_produto(empresa_id, nome, novo_nome=None, preco_venda=None, preco_custo=None,
                   estoque=None, categoria=None, ativo=None):
    from app import app, db
    from models import Produto
    with app.app_context():
        produtos = Produto.query.filter_by(empresa_id=empresa_id).all()
        p = _match(nome, produtos)
        if not p:
            return f"Não encontrei nenhum produto parecido com '{nome}'."
        alterado = []
        if novo_nome: p.nome = novo_nome; alterado.append('nome')
        if preco_venda is not None: p.preco_venda = float(preco_venda); alterado.append('preço de venda')
        if preco_custo is not None: p.preco_custo = float(preco_custo); alterado.append('preço de custo')
        if estoque is not None: p.estoque = int(estoque); alterado.append('estoque')
        if categoria: p.categoria = categoria; alterado.append('categoria')
        if ativo is not None: p.ativo = bool(ativo); alterado.append('ativo' if ativo else 'inativo')
        if not alterado:
            return "Nada pra alterar -- diga o que quer mudar nesse produto."
        db.session.commit()
        return f"✅ Produto *{p.nome}* atualizado: {', '.join(alterado)}."


def cadastrar_servico(empresa_id, nome, preco_unitario, unidade=None, descricao=None):
    from app import app, db
    from models import Servico
    with app.app_context():
        s = Servico(empresa_id=empresa_id, nome=nome, preco_unitario=float(preco_unitario),
                    unidade=unidade or 'un', descricao=descricao)
        db.session.add(s)
        db.session.commit()
        return f"✅ Serviço *{nome}* cadastrado — {fmt(float(preco_unitario))}."


def editar_servico(empresa_id, nome, novo_nome=None, preco_unitario=None, descricao=None, ativo=None):
    from app import app, db
    from models import Servico
    with app.app_context():
        servicos = Servico.query.filter_by(empresa_id=empresa_id).all()
        s = _match(nome, servicos)
        if not s:
            return f"Não encontrei nenhum serviço parecido com '{nome}'."
        alterado = []
        if novo_nome: s.nome = novo_nome; alterado.append('nome')
        if preco_unitario is not None: s.preco_unitario = float(preco_unitario); alterado.append('preço')
        if descricao: s.descricao = descricao; alterado.append('descrição')
        if ativo is not None: s.ativo = bool(ativo); alterado.append('ativo' if ativo else 'inativo')
        if not alterado:
            return "Nada pra alterar -- diga o que quer mudar nesse serviço."
        db.session.commit()
        return f"✅ Serviço *{s.nome}* atualizado: {', '.join(alterado)}."


def editar_proposta(empresa_id, numero, validade_dias=None, forma_pagamento=None,
                    observacoes=None, status=None):
    from app import app, db
    from models import Proposta
    with app.app_context():
        p = Proposta.query.filter_by(empresa_id=empresa_id, numero=numero).first()
        if not p:
            return f"Não encontrei a proposta {numero}."
        alterado = []
        if validade_dias is not None:
            p.validade = int(validade_dias)
            p.token_expira_em = p.criado_em + timedelta(days=int(validade_dias))
            alterado.append('validade')
        if forma_pagamento:
            p.forma_pagamento = forma_pagamento
            alterado.append('forma de pagamento')
        if observacoes is not None:
            p.observacoes = observacoes
            alterado.append('observações')
        if status:
            p.status = status
            alterado.append('status')
        if not alterado:
            return "Nada pra alterar -- diga o que quer mudar na proposta."
        db.session.commit()
        return f"✅ Proposta *{p.numero}* atualizada: {', '.join(alterado)}."


def adicionar_item_proposta(empresa_id, numero, nome_item, quantidade=None):
    from app import app, db
    from models import Proposta, ItemProposta, Servico, Produto
    with app.app_context():
        p = Proposta.query.filter_by(empresa_id=empresa_id, numero=numero).first()
        if not p:
            return f"Não encontrei a proposta {numero}."
        if p.status not in ('rascunho', 'enviada'):
            return f"A proposta {numero} já está '{p.status}' -- não dá pra alterar itens depois de assinada."
        servicos = Servico.query.filter_by(empresa_id=empresa_id, ativo=True).all()
        produtos = Produto.query.filter_by(empresa_id=empresa_id, ativo=True).all()
        alvo_s = _match(nome_item, servicos)
        alvo_p = _match(nome_item, produtos) if not alvo_s else None
        if alvo_s:
            alvo, tipo, preco = alvo_s, 'servico', alvo_s.preco_unitario
        elif alvo_p:
            alvo, tipo, preco = alvo_p, 'produto', (alvo_p.preco_venda or 0)
        else:
            return f"Não encontrei nenhum produto/serviço parecido com '{nome_item}'."
        qtd = float(quantidade or 1)
        db.session.add(ItemProposta(proposta_id=p.id, descricao=alvo.nome, quantidade=qtd,
                                    preco_unitario=preco, tipo=tipo))
        db.session.commit()
        return f"✅ Adicionado *{alvo.nome}* x{qtd} na proposta {numero}."


def remover_item_proposta(empresa_id, numero, nome_item):
    from app import app, db
    from models import Proposta
    with app.app_context():
        p = Proposta.query.filter_by(empresa_id=empresa_id, numero=numero).first()
        if not p:
            return f"Não encontrei a proposta {numero}."
        if p.status not in ('rascunho', 'enviada'):
            return f"A proposta {numero} já está '{p.status}' -- não dá pra alterar itens depois de assinada."
        alvo = None
        alvo_low = (nome_item or '').lower().strip()
        for i in p.itens:
            if alvo_low in i.descricao.lower() or i.descricao.lower() in alvo_low:
                alvo = i
                break
        if not alvo:
            return f"Não encontrei nenhum item parecido com '{nome_item}' na proposta {numero}."
        nome_removido = alvo.descricao
        db.session.delete(alvo)
        db.session.commit()
        return f"✅ Removido *{nome_removido}* da proposta {numero}."


# ═══════════════════════ CADASTRO DE PRODUTO POR FOTO (visão do Gemini) ═══════════════════════

def interpretar_produto_imagem(imagem_bytes, mime_type, legenda=None, produtos_existentes=None):
    """Manda uma foto (propaganda/etiqueta/embalagem de produto) pro Gemini
    e pede pra extrair os dados de cadastro. Retorna um dict:
      {"encontrado": true, "nome":..., "preco_venda": numero, "preco_custo": numero ou null,
       "categoria": ... ou null, "descricao": ... ou null, "estoque": numero ou null}
      ou
      {"encontrado": false, "motivo": "..."}
    Retorna None em caso de erro de rede/API."""
    lista_produtos = '\n'.join(f'- {p}' for p in (produtos_existentes or [])[:200])
    prompt = f"""Você é o assistente de um profissional de instalação e manutenção de CFTV e
infraestrutura. A pessoa te mandou uma FOTO (propaganda, etiqueta, embalagem ou nota de um
produto) pedindo pra cadastrar esse produto no estoque do sistema.

Extraia da imagem:
1. Nome do produto (claro e objetivo, sem o texto todo da propaganda)
2. Preço de venda (se a imagem mostrar mais de um preço -- ex: "de X por Y" -- use o preço
   final/promocional Y; se não tiver certeza de qual é o preço de venda, marque encontrado=false)
3. Categoria (ex: câmera, cabo, conector, fonte, sensor etc), se der pra inferir
4. Descrição curta com as especificações visíveis (resolução, modelo, voltagem etc)

Se a legenda da mensagem mencionar quantidade/estoque ou algum ajuste de preço, considere isso
também.

{"Legenda enviada junto com a foto: " + legenda if legenda else "Nenhuma legenda foi enviada."}

PRODUTOS JÁ CADASTRADOS (contexto, evite sugerir nome idêntico a um já existente sem avisar):
{lista_produtos}

Se a imagem não mostrar claramente um produto com preço identificável, retorne
encontrado=false e explique o motivo em "motivo".

Responda APENAS com um JSON no formato exato abaixo, sem texto adicional:
{{
  "encontrado": true ou false,
  "motivo": "só se encontrado==false, senão null",
  "nome": "nome do produto ou null",
  "preco_venda": numero ou null,
  "preco_custo": numero ou null,
  "categoria": "categoria ou null",
  "descricao": "descrição curta ou null",
  "estoque": numero ou null
}}"""

    parts = [{"text": prompt}, {"inline_data": {
        "mime_type": mime_type,
        "data": base64.b64encode(imagem_bytes).decode('utf-8'),
    }}]
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    req = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'X-goog-api-key': GEMINI_API_KEY},
    )

    ultimo_erro = None
    for _tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            texto_resp = data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(texto_resp)
        except urllib.error.HTTPError as e:
            corpo = e.read().decode('utf-8', errors='ignore')
            ultimo_erro = f"HTTP {e.code}: {corpo[:300]}"
            if e.code == 503:
                import time
                time.sleep(2)
                continue
            print(f"[ERRO Gemini imagem produto] {ultimo_erro}")
            return None
        except Exception as e:
            print(f"[ERRO Gemini imagem produto] {e}")
            return None

    print(f"[ERRO Gemini imagem produto] Falhou após 3 tentativas: {ultimo_erro}")
    return None


FUNMAP = {
    'listar_propostas': listar_propostas,
    'buscar_proposta': buscar_proposta,
    'listar_clientes': listar_clientes,
    'listar_produtos': listar_produtos,
    'listar_servicos': listar_servicos,
    'resumo_geral': resumo_geral,
    'cadastrar_cliente': cadastrar_cliente,
    'editar_cliente': editar_cliente,
    'cadastrar_produto': cadastrar_produto,
    'editar_produto': editar_produto,
    'cadastrar_servico': cadastrar_servico,
    'editar_servico': editar_servico,
    'editar_proposta': editar_proposta,
    'adicionar_item_proposta': adicionar_item_proposta,
    'remover_item_proposta': remover_item_proposta,
}

TOOLS = [
    {
        "name": "listar_propostas",
        "description": "Lista as propostas comerciais cadastradas, mais recentes primeiro. "
                        "Use quando pedirem pra ver/mostrar as propostas.",
        "parameters": {"type": "OBJECT", "properties": {
            "status": {"type": "STRING", "description": "Filtrar por status: rascunho, enviada, aprovada, recusada. Vazio = todas."},
            "limite": {"type": "INTEGER", "description": "Máximo de propostas a trazer (padrão 10)."},
        }},
    },
    {
        "name": "buscar_proposta",
        "description": "Busca e mostra o detalhe completo de UMA proposta específica, pelo número "
                        "(ex: NB-202607-0001) ou pelo nome do cliente.",
        "parameters": {"type": "OBJECT", "properties": {
            "numero_ou_cliente": {"type": "STRING", "description": "Número da proposta ou nome do cliente."},
        }, "required": ["numero_ou_cliente"]},
    },
    {
        "name": "listar_clientes",
        "description": "Lista os clientes cadastrados.",
        "parameters": {"type": "OBJECT", "properties": {
            "busca": {"type": "STRING", "description": "Filtrar por parte do nome. Vazio = todos."},
            "limite": {"type": "INTEGER", "description": "Máximo a trazer (padrão 20)."},
        }},
    },
    {
        "name": "listar_produtos",
        "description": "Lista os produtos ativos do catálogo, com preço.",
        "parameters": {"type": "OBJECT", "properties": {
            "busca": {"type": "STRING", "description": "Filtrar por parte do nome. Vazio = todos."},
            "limite": {"type": "INTEGER", "description": "Máximo a trazer (padrão 20)."},
        }},
    },
    {
        "name": "listar_servicos",
        "description": "Lista os serviços ativos do catálogo, com preço.",
        "parameters": {"type": "OBJECT", "properties": {
            "busca": {"type": "STRING", "description": "Filtrar por parte do nome. Vazio = todos."},
            "limite": {"type": "INTEGER", "description": "Máximo a trazer (padrão 20)."},
        }},
    },
    {
        "name": "resumo_geral",
        "description": "Mostra um resumo geral do negócio: total de propostas, quantas aprovadas, "
                       "valor total aprovado, quantidade de clientes/produtos/serviços cadastrados. "
                       "Use pra perguntas gerais tipo 'como estão as coisas' ou 'me dá um resumo'.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "cadastrar_cliente",
        "description": "Cadastra um cliente novo.",
        "parameters": {"type": "OBJECT", "properties": {
            "nome": {"type": "STRING", "description": "Nome do cliente."},
            "telefone": {"type": "STRING"},
            "email": {"type": "STRING"},
            "cpf_cnpj": {"type": "STRING"},
            "endereco": {"type": "STRING"},
            "cidade": {"type": "STRING"},
            "estado": {"type": "STRING", "description": "Sigla do estado (ex: PB)."},
            "cep": {"type": "STRING"},
            "tipo": {"type": "STRING", "description": "PF (pessoa física) ou PJ (pessoa jurídica)."},
        }, "required": ["nome"]},
    },
    {
        "name": "editar_cliente",
        "description": "Edita um cliente já cadastrado (busca por nome aproximado).",
        "parameters": {"type": "OBJECT", "properties": {
            "nome_atual": {"type": "STRING", "description": "Nome (ou parte dele) do cliente a editar."},
            "novo_nome": {"type": "STRING"},
            "telefone": {"type": "STRING"},
            "email": {"type": "STRING"},
            "endereco": {"type": "STRING"},
            "cidade": {"type": "STRING"},
            "estado": {"type": "STRING"},
            "cep": {"type": "STRING"},
        }, "required": ["nome_atual"]},
    },
    {
        "name": "cadastrar_produto",
        "description": "Cadastra um produto novo no catálogo.",
        "parameters": {"type": "OBJECT", "properties": {
            "nome": {"type": "STRING"},
            "preco_venda": {"type": "NUMBER", "description": "Preço de venda em reais."},
            "preco_custo": {"type": "NUMBER"},
            "categoria": {"type": "STRING"},
            "descricao": {"type": "STRING"},
            "estoque": {"type": "INTEGER"},
        }, "required": ["nome", "preco_venda"]},
    },
    {
        "name": "editar_produto",
        "description": "Edita um produto já cadastrado (busca por nome aproximado).",
        "parameters": {"type": "OBJECT", "properties": {
            "nome": {"type": "STRING", "description": "Nome (ou parte dele) do produto a editar."},
            "novo_nome": {"type": "STRING"},
            "preco_venda": {"type": "NUMBER"},
            "preco_custo": {"type": "NUMBER"},
            "estoque": {"type": "INTEGER"},
            "categoria": {"type": "STRING"},
            "ativo": {"type": "BOOLEAN", "description": "false pra desativar o produto."},
        }, "required": ["nome"]},
    },
    {
        "name": "cadastrar_servico",
        "description": "Cadastra um serviço novo no catálogo.",
        "parameters": {"type": "OBJECT", "properties": {
            "nome": {"type": "STRING"},
            "preco_unitario": {"type": "NUMBER", "description": "Preço em reais."},
            "unidade": {"type": "STRING", "description": "Ex: un, m, hora, ponto."},
            "descricao": {"type": "STRING"},
        }, "required": ["nome", "preco_unitario"]},
    },
    {
        "name": "editar_servico",
        "description": "Edita um serviço já cadastrado (busca por nome aproximado).",
        "parameters": {"type": "OBJECT", "properties": {
            "nome": {"type": "STRING", "description": "Nome (ou parte dele) do serviço a editar."},
            "novo_nome": {"type": "STRING"},
            "preco_unitario": {"type": "NUMBER"},
            "descricao": {"type": "STRING"},
            "ativo": {"type": "BOOLEAN", "description": "false pra desativar o serviço."},
        }, "required": ["nome"]},
    },
    {
        "name": "editar_proposta",
        "description": "Edita campos gerais de uma proposta já existente (validade, forma de "
                       "pagamento, observações, status). Não mexe nos itens.",
        "parameters": {"type": "OBJECT", "properties": {
            "numero": {"type": "STRING", "description": "Número da proposta (ex: NB-202607-0001)."},
            "validade_dias": {"type": "INTEGER"},
            "forma_pagamento": {"type": "STRING"},
            "observacoes": {"type": "STRING"},
            "status": {"type": "STRING", "description": "rascunho, enviada, aprovada ou recusada."},
        }, "required": ["numero"]},
    },
    {
        "name": "adicionar_item_proposta",
        "description": "Adiciona um produto ou serviço já cadastrado como item de uma proposta "
                       "existente que ainda não foi assinada (rascunho ou enviada).",
        "parameters": {"type": "OBJECT", "properties": {
            "numero": {"type": "STRING", "description": "Número da proposta."},
            "nome_item": {"type": "STRING", "description": "Nome do produto/serviço a adicionar."},
            "quantidade": {"type": "NUMBER"},
        }, "required": ["numero", "nome_item"]},
    },
    {
        "name": "remover_item_proposta",
        "description": "Remove um item de uma proposta existente que ainda não foi assinada "
                       "(rascunho ou enviada).",
        "parameters": {"type": "OBJECT", "properties": {
            "numero": {"type": "STRING", "description": "Número da proposta."},
            "nome_item": {"type": "STRING", "description": "Nome (ou parte dele) do item a remover."},
        }, "required": ["numero", "nome_item"]},
    },
]

SYSTEM_PROMPT = """Você é o assistente de gestão do NeuraBusiness, sistema de propostas
comerciais de uma empresa de CFTV e infraestrutura. Você recebe um comando em português
(às vezes vindo de áudio transcrito) pedindo pra consultar ou alterar dados do sistema:
propostas, clientes, produtos ou serviços.

Escolha SEMPRE a ferramenta mais adequada e preencha os parâmetros a partir do que a pessoa
disse. Se faltar uma informação obrigatória (por exemplo, preço de um produto novo), NÃO
invente um valor -- em vez disso responda em texto pedindo essa informação. Se o comando não
corresponder a nenhuma ferramenta disponível, responda em texto explicando que não entendeu."""


def executar_comando(comando, empresa_id):
    """Manda o comando pro Gemini com as ferramentas disponíveis, executa a(s)
    função(ões) que ele escolher contra o banco de verdade, e devolve o texto
    pronto pra responder no Telegram. Retorna None em caso de erro de rede."""
    body = {
        "contents": [{"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\nComando: {comando}"}]}],
        "tools": [{"functionDeclarations": TOOLS}],
        "generationConfig": {"temperature": 0.1},
    }
    req = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'X-goog-api-key': GEMINI_API_KEY},
    )

    ultimo_erro = None
    for _tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            corpo = e.read().decode('utf-8', errors='ignore')
            ultimo_erro = f"HTTP {e.code}: {corpo[:300]}"
            if e.code == 503:
                import time
                time.sleep(2)
                continue
            print(f"[ERRO Gemini assistente] {ultimo_erro}")
            return None
        except Exception as e:
            print(f"[ERRO Gemini assistente] {e}")
            return None
    else:
        print(f"[ERRO Gemini assistente] Falhou após 3 tentativas: {ultimo_erro}")
        return None

    try:
        parts = data['candidates'][0]['content']['parts']
    except (KeyError, IndexError):
        return None

    respostas = []
    for part in parts:
        if 'functionCall' in part:
            nome_fn = part['functionCall'].get('name')
            args = part['functionCall'].get('args', {}) or {}
            fn = FUNMAP.get(nome_fn)
            if not fn:
                respostas.append(f"(a IA tentou usar uma ferramenta desconhecida: {nome_fn})")
                continue
            try:
                respostas.append(fn(empresa_id=empresa_id, **args))
            except Exception as e:
                respostas.append(f"❌ Erro executando '{nome_fn}': {e}")
        elif 'text' in part and part['text'].strip():
            respostas.append(part['text'].strip())

    if not respostas:
        return "Não entendi esse comando. Tente algo como 'mostra minhas propostas' ou 'cadastra um cliente novo'."
    return "\n\n".join(respostas)
