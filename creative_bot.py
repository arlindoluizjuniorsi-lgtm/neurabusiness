import sys
sys.path.insert(0, '/opt/neurabusiness')
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
TOKEN = '***REMOVED_TELEGRAM_TOKEN***'
from app import app, db
from models import Empresa, Cliente, Servico, Produto, Proposta, ItemProposta, EtapaProposta
import uuid, io, difflib, asyncio
from datetime import datetime, timedelta
from ia_audio import interpretar_audio_proposta

(MENU,CLIENTE,NC_NOME,NC_TEL,SERVICO,PRODUTO,QTD,PRECO,MAIS,
 PERGUNTA_ETAPAS,ETAPA_TITULO,ETAPA_DIAS,VALIDADE,PAGAMENTO,CONFIRMAR,
 IA_AGUARDA,IA_CORRECAO,IA_CONFIRMAR,IA_TEL,IA_CADASTRAR_CLIENTE)=range(20)

def get_emp():
    with app.app_context():
        return Empresa.query.filter_by(cnpj='45.127.220/0001-19').first()

def kb(o,c=2):
    r=[o[i:i+c] for i in range(0,len(o),c)]
    return ReplyKeyboardMarkup(r,resize_keyboard=True,one_time_keyboard=True)

def fmt(v):
    return f"R$ {v:,.2f}".replace(',','X').replace('.',',').replace('X','.')

def melhor_match(nome_falado, opcoes, cutoff=0.4):
    if not nome_falado or not opcoes:
        return None
    nome_falado_low = nome_falado.lower().strip()
    for o in opcoes:
        if o['nome'].lower().strip() == nome_falado_low:
            return o
    for o in opcoes:
        if nome_falado_low in o['nome'].lower() or o['nome'].lower() in nome_falado_low:
            return o
    nomes = [o['nome'].lower() for o in opcoes]
    matches = difflib.get_close_matches(nome_falado_low, nomes, n=1, cutoff=cutoff)
    if matches:
        for o in opcoes:
            if o['nome'].lower() == matches[0]:
                return o
    return None

def carregar_catalogo():
    with app.app_context():
        emp = get_emp()
        clientes_db = Cliente.query.filter_by(empresa_id=emp.id).order_by(Cliente.nome).all()
        servicos_db = Servico.query.filter_by(empresa_id=emp.id).order_by(Servico.nome).all()
        produtos_db = Produto.query.filter_by(empresa_id=emp.id, ativo=True).order_by(Produto.nome).all()
        return (
            [{'id':x.id,'nome':x.nome} for x in clientes_db],
            [{'id':x.id,'nome':x.nome,'preco':float(x.preco_unitario),'tipo':'servico'} for x in servicos_db],
            [{'id':x.id,'nome':x.nome,'preco':float(x.preco_venda or 0),'tipo':'produto'} for x in produtos_db],
        )

# ══════════════════════ MENU PRINCIPAL ══════════════════════
async def start(u:Update,c:ContextTypes.DEFAULT_TYPE):
    c.user_data.clear()
    await u.message.reply_text(
        f"👋 Olá *{u.effective_user.first_name}*!\n\nComo deseja criar a proposta?",
        parse_mode='Markdown',
        reply_markup=kb(["📋 Nova Proposta Manual","🎤 Nova Proposta IA","❌ Cancelar"],1))
    return MENU

async def menu(u:Update,c:ContextTypes.DEFAULT_TYPE):
    txt = u.message.text
    if "Manual" in txt:
        c.user_data['itens']=[];c.user_data['etapas']=[]
        return await listar_clientes(u,c)
    if "IA" in txt:
        c.user_data['itens']=[];c.user_data['etapas']=[]
        c.user_data['cliente']=None
        c.user_data['tentativas_cliente']=0
        await u.message.reply_text(
            "🎤 *Manda um áudio explicando a proposta.*\n\n"
            "Exemplo: _\"Proposta pra Câmara de Mataraca, câmera VIP 1220 quantidade 6, "
            "serviço de instalação de CFTV, pagamento pix, validade 15 dias\"_",
            parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
        return IA_AGUARDA
    await u.message.reply_text("Cancelado.",reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ══════════════════════ FLUXO MANUAL (clientes/servicos/produtos) ══════════════════════
async def listar_clientes(u:Update,c:ContextTypes.DEFAULT_TYPE):
    clientes_opts, _, _ = carregar_catalogo()
    c.user_data['clientes']=clientes_opts
    msg="👤 *Selecione o cliente:*\n\n"+"".join(f"`{i:02d}` — {x['nome']}\n" for i,x in enumerate(clientes_opts,1))+"\n`00` — ➕ Novo cliente"
    await u.message.reply_text(msg,parse_mode='Markdown',reply_markup=ReplyKeyboardRemove());return CLIENTE

async def escolher_cliente(u:Update,c:ContextTypes.DEFAULT_TYPE):
    try:num=int(u.message.text.strip())
    except:await u.message.reply_text("Digite o número.");return CLIENTE
    if num==0:await u.message.reply_text("Nome do novo cliente:");return NC_NOME
    cl=c.user_data.get('clientes',[])
    if num<1 or num>len(cl):await u.message.reply_text("Inválido.");return CLIENTE
    c.user_data['cliente']=cl[num-1];return await listar_servicos(u,c)

async def nc_nome(u:Update,c:ContextTypes.DEFAULT_TYPE):
    c.user_data['nc_nome']=u.message.text.strip();await u.message.reply_text("WhatsApp do cliente:");return NC_TEL

async def nc_tel(u:Update,c:ContextTypes.DEFAULT_TYPE):
    with app.app_context():
        emp=get_emp();x=Cliente(empresa_id=emp.id,nome=c.user_data['nc_nome'],telefone=u.message.text.strip(),tipo='PF')
        db.session.add(x);db.session.commit();c.user_data['cliente']={'id':x.id,'nome':x.nome}
    await u.message.reply_text(f"✅ *{c.user_data['nc_nome']}* cadastrado!",parse_mode='Markdown');return await listar_servicos(u,c)

async def listar_servicos(u:Update,c:ContextTypes.DEFAULT_TYPE):
    _, servicos_opts, _ = carregar_catalogo()
    c.user_data['servicos']=servicos_opts
    msg=f"✅ *{c.user_data['cliente']['nome']}*\n\n🔧 *Serviços:*\n\n"+"".join(f"`{i:02d}` — {x['nome']} ({fmt(x['preco'])})\n" for i,x in enumerate(servicos_opts,1))+"\n`99` — Ir para produtos\n`00` — Pular"
    await u.message.reply_text(msg,parse_mode='Markdown',reply_markup=ReplyKeyboardRemove());return SERVICO

async def escolher_servico(u:Update,c:ContextTypes.DEFAULT_TYPE):
    try:num=int(u.message.text.strip())
    except:await u.message.reply_text("Digite o número.");return SERVICO
    if num in(0,99):return await listar_produtos(u,c)
    sv=c.user_data.get('servicos',[])
    if num<1 or num>len(sv):await u.message.reply_text("Inválido.");return SERVICO
    s=sv[num-1];c.user_data['item_atual']={'tipo':'servico',**s};c.user_data['voltando']='servico'
    await u.message.reply_text(f"🔧 *{s['nome']}*\nQtd:",parse_mode='Markdown');return QTD

async def listar_produtos(u:Update,c:ContextTypes.DEFAULT_TYPE):
    _, _, produtos_opts = carregar_catalogo()
    c.user_data['produtos']=produtos_opts
    itens=c.user_data.get('itens',[])
    msg=("📦 *Adicionados:*\n"+"".join(f"• {i['nome']} x{i['qtd']}\n" for i in itens)+"\n") if itens else ""
    msg+="📦 *Produtos:*\n\n"
    parte=""
    for i,p in enumerate(produtos_opts,1):
        linha=f"`{i:02d}` — {p['nome']} ({fmt(p['preco'])})\n"
        if len(msg+parte+linha)>3800:
            await u.message.reply_text(msg+parte,parse_mode='Markdown');msg="";parte=""
        parte+=linha
    msg+=parte+"\n`99` — ✅ Finalizar\n`00` — Voltar serviços"
    await u.message.reply_text(msg,parse_mode='Markdown',reply_markup=ReplyKeyboardRemove());return PRODUTO

async def escolher_produto(u:Update,c:ContextTypes.DEFAULT_TYPE):
    try:num=int(u.message.text.strip())
    except:await u.message.reply_text("Digite o número.");return PRODUTO
    if num==99:return await perguntar_etapas(u,c)
    if num==0:return await listar_servicos(u,c)
    pd=c.user_data.get('produtos',[])
    if num<1 or num>len(pd):await u.message.reply_text("Inválido.");return PRODUTO
    p=pd[num-1];c.user_data['item_atual']={'tipo':'produto',**p};c.user_data['voltando']='produto'
    await u.message.reply_text(f"📦 *{p['nome']}*\nQtd:",parse_mode='Markdown');return QTD

async def receber_qtd(u:Update,c:ContextTypes.DEFAULT_TYPE):
    try:
        qtd=float(u.message.text.strip().replace(',','.'))
        if qtd<=0:raise ValueError
    except:await u.message.reply_text("Qtd inválida.");return QTD
    c.user_data['item_qtd']=qtd;item=c.user_data['item_atual']
    await u.message.reply_text(f"💰 Valor: *{fmt(item['preco'])}*\nDigite novo valor ou *ok*:",parse_mode='Markdown');return PRECO

async def receber_preco(u:Update,c:ContextTypes.DEFAULT_TYPE):
    txt=u.message.text.strip().lower();item=c.user_data['item_atual'];qtd=c.user_data['item_qtd']
    if txt!='ok':
        try:item['preco']=float(txt.replace('r$','').replace('.','').replace(',','.').strip());c.user_data['item_atual']=item
        except:await u.message.reply_text("Valor inválido. Digite ou *ok*.",parse_mode='Markdown');return PRECO
    c.user_data['itens'].append({'id':item['id'],'nome':item['nome'],'tipo':item['tipo'],'preco':item['preco'],'qtd':qtd})
    total=sum(i['preco']*i['qtd'] for i in c.user_data['itens'])
    await u.message.reply_text(f"✅ *{item['nome']}* x{qtd}\n💰 Total: *{fmt(total)}*\n\nO que mais?",parse_mode='Markdown',
        reply_markup=kb(["➕ Mais produtos","🔧 Mais serviços","✅ Finalizar"],2));return MAIS

async def mais_itens(u:Update,c:ContextTypes.DEFAULT_TYPE):
    txt=u.message.text
    if "serviç" in txt.lower():return await listar_servicos(u,c)
    if "produto" in txt.lower():return await listar_produtos(u,c)
    if "Finalizar" in txt:return await perguntar_etapas(u,c)
    await u.message.reply_text("Escolha:",reply_markup=kb(["➕ Mais produtos","🔧 Mais serviços","✅ Finalizar"],2));return MAIS

# ══════════════════════ ETAPAS (comum para manual e IA) ══════════════════════
async def perguntar_etapas(u:Update,c:ContextTypes.DEFAULT_TYPE):
    itens=c.user_data.get('itens',[])
    if not itens:await u.message.reply_text("⚠️ Adicione pelo menos um item!");return await listar_servicos(u,c)
    await u.message.reply_text(
        "📅 *Deseja adicionar as fases de execução (cronograma de entrega)?*",
        parse_mode='Markdown', reply_markup=kb(["✅ Sim, adicionar etapas","⏭️ Pular etapas"],2))
    return PERGUNTA_ETAPAS

async def resposta_pergunta_etapas(u:Update,c:ContextTypes.DEFAULT_TYPE):
    txt=u.message.text
    if "Pular" in txt or "Concluir" in txt:
        return await perguntar_validade(u,c)
    await u.message.reply_text("📝 Digite o *título da etapa*:",parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
    return ETAPA_TITULO

async def receber_etapa_titulo(u:Update,c:ContextTypes.DEFAULT_TYPE):
    c.user_data['etapa_titulo_atual']=u.message.text.strip()
    await u.message.reply_text("⏱️ Quantos *dias* de duração?",parse_mode='Markdown');return ETAPA_DIAS

async def receber_etapa_dias(u:Update,c:ContextTypes.DEFAULT_TYPE):
    try:
        dias=int(u.message.text.strip())
        if dias<1:raise ValueError
    except:await u.message.reply_text("Digite um número válido.");return ETAPA_DIAS
    c.user_data['etapas'].append({'titulo':c.user_data['etapa_titulo_atual'],'duracao_dias':dias,'descricao':''})
    msg = f"✅ Etapa adicionada!\n\n📋 *Etapas até agora:*\n"
    for i, et in enumerate(c.user_data['etapas'], 1):
        msg += f"{i}. {et['titulo']} — {et['duracao_dias']} dia(s)\n"
    await u.message.reply_text(msg, parse_mode='Markdown',
        reply_markup=kb(["➕ Mais uma etapa","✅ Concluir cronograma"],2))
    return PERGUNTA_ETAPAS

async def perguntar_validade(u:Update,c:ContextTypes.DEFAULT_TYPE):
    itens=c.user_data.get('itens',[])
    total=sum(i['preco']*i['qtd'] for i in itens)
    msg="📋 *Resumo:*\n\n"+"".join(f"• {i['nome']} x{i['qtd']} — {fmt(i['preco']*i['qtd'])}\n" for i in itens)
    if c.user_data.get('etapas'):
        msg += "\n📅 *Cronograma:*\n"+"".join(f"{i}. {et['titulo']} — {et['duracao_dias']} dia(s)\n" for i,et in enumerate(c.user_data['etapas'],1))
    msg += f"\n💰 *TOTAL: {fmt(total)}*\n\n📅 *Validade da proposta (dias):*"
    await u.message.reply_text(msg,parse_mode='Markdown',reply_markup=kb(["5","10","15","30","45","60"],3));return VALIDADE

async def receber_validade(u:Update,c:ContextTypes.DEFAULT_TYPE):
    try:
        dias=int(u.message.text.strip())
        if dias<1:raise ValueError
    except:await u.message.reply_text("Número inválido.");return VALIDADE
    c.user_data['validade']=dias
    await u.message.reply_text("💳 *Forma de pagamento:*",parse_mode='Markdown',
        reply_markup=kb(["Pix à Vista","Pix ou Cartão (c/ acréscimo)","Boleto 30 dias","Cartão de Crédito","A combinar"],1));return PAGAMENTO

async def receber_pagamento(u:Update,c:ContextTypes.DEFAULT_TYPE):
    c.user_data['pagamento']=u.message.text.strip()
    itens=c.user_data['itens'];total=sum(i['preco']*i['qtd'] for i in itens)
    msg=f"📄 *Confirmar:*\n\n👤 *{c.user_data['cliente']['nome']}*\n💳 {c.user_data['pagamento']}\n📅 {c.user_data['validade']} dias\n\n"
    msg+="".join(f"• {i['nome']} x{i['qtd']} — {fmt(i['preco']*i['qtd'])}\n" for i in itens)
    if c.user_data.get('etapas'):
        msg += "\n📅 *Cronograma:*\n"+"".join(f"{i}. {et['titulo']} — {et['duracao_dias']} dia(s)\n" for i,et in enumerate(c.user_data['etapas'],1))
    msg+=f"\n💰 *TOTAL: {fmt(total)}*"
    await u.message.reply_text(msg,parse_mode='Markdown',reply_markup=kb(["✅ Confirmar e Gerar","❌ Cancelar"],2));return CONFIRMAR

# ══════════════════════ GERAÇÃO FINAL (comum) ══════════════════════
async def confirmar(u:Update,c:ContextTypes.DEFAULT_TYPE):
    if "Cancelar" in u.message.text:
        await u.message.reply_text("❌ Cancelado.",reply_markup=ReplyKeyboardRemove());return ConversationHandler.END
    await u.message.reply_text("⏳ Gerando proposta e PDF...",reply_markup=ReplyKeyboardRemove())
    try:
        with app.app_context():
            emp=get_emp();itens=c.user_data['itens'];cliente_nome=c.user_data['cliente']['nome']
            etapas_data=c.user_data.get('etapas',[])

            count=Proposta.query.filter_by(empresa_id=emp.id).count()
            numero=f"NB-{datetime.now().strftime('%Y%m')}-{count+1:04d}"
            token=uuid.uuid4().hex;expira=datetime.now()+timedelta(days=c.user_data['validade'])
            p=Proposta(empresa_id=emp.id,numero=numero,titulo=f"Proposta para {cliente_nome}",
                cliente_id=c.user_data['cliente']['id'],status='enviada',validade=c.user_data['validade'],
                forma_pagamento=c.user_data['pagamento'],token_publico=token,token_expira_em=expira,usuario_id=1)
            db.session.add(p);db.session.flush()
            for i in itens:
                db.session.add(ItemProposta(proposta_id=p.id,descricao=i['nome'],quantidade=i['qtd'],preco_unitario=i['preco'],tipo=i['tipo']))
            for idx, et in enumerate(etapas_data, 1):
                db.session.add(EtapaProposta(proposta_id=p.id, ordem=idx, titulo=et['titulo'],
                    duracao_dias=et['duracao_dias'], descricao=et.get('descricao','')))
            db.session.commit()
            total=sum(i['preco']*i['qtd'] for i in itens)
            pid=p.id

            from pdf_generator import gerar_proposta_pdf
            p_reload = Proposta.query.get(pid)
            itens_pdf = [{'descricao':i.descricao,'quantidade':i.quantidade,'preco_unitario':i.preco_unitario,'tipo':i.tipo} for i in p_reload.itens]
            etapas_pdf = [{'titulo':e.titulo,'descricao':e.descricao,'duracao_dias':e.duracao_dias}
                          for e in sorted(p_reload.etapas, key=lambda x: x.ordem)] if p_reload.etapas else []
            emp_dict = {c2.name: getattr(emp, c2.name) for c2 in emp.__table__.columns}
            p_dict = {c2.name: getattr(p_reload, c2.name) for c2 in p_reload.__table__.columns}
            cli_dict = {c2.name: getattr(p_reload.cliente, c2.name) for c2 in p_reload.cliente.__table__.columns} if p_reload.cliente else {}
            pdf_buf = gerar_proposta_pdf(p_dict, emp_dict, cli_dict, itens_pdf, etapas=etapas_pdf)
            pdf_bytes = pdf_buf.getvalue() if hasattr(pdf_buf, 'getvalue') else pdf_buf.read()

        link_pub = f"https://app.creativeinfra.com.br/proposta/view/{token}"

        msg_cliente  = f"Olá, {cliente_nome}! Esperamos que esteja bem.\n\n"
        msg_cliente += f"Segue a proposta comercial para o serviço solicitado.\n"
        msg_cliente += f"Abaixo as informações:\n\n"
        msg_cliente += f"📄 Proposta: {numero}\n"
        msg_cliente += f"💰 Valor total: {fmt(total)}\n"
        msg_cliente += f"💳 Pagamento: {c.user_data['pagamento']}\n"
        msg_cliente += f"📅 Validade: {c.user_data['validade']} dias\n\n"
        msg_cliente += f"🔗 Para visualizar e aprovar a proposta, acesse:\n{link_pub}\n\n"
        msg_cliente += f"Qualquer dúvida, estou à disposição!"

        await u.message.reply_text(f"✅ *Proposta {numero} gerada!*\n\n_Mensagem pronta para encaminhar ao cliente:_",parse_mode='Markdown')
        await u.message.reply_text(msg_cliente)

        pdf_io = io.BytesIO(pdf_bytes)
        pdf_io.name = f"Proposta_{numero.replace('-','_')}.pdf"
        await u.message.reply_document(document=pdf_io,filename=pdf_io.name,caption=f"📎 PDF da proposta {numero}")

        await u.message.reply_text("👆 Copie a mensagem acima e o PDF para encaminhar ao cliente!",
            reply_markup=kb(["📋 Nova Proposta Manual","🎤 Nova Proposta IA"],2))
    except Exception as e:
        await u.message.reply_text(f"❌ Erro: {e}")
    return ConversationHandler.END

async def cancelar(u:Update,c:ContextTypes.DEFAULT_TYPE):
    c.user_data.clear();await u.message.reply_text("❌ Cancelado.",reply_markup=ReplyKeyboardRemove());return ConversationHandler.END

# ══════════════════════ FLUXO POR ÁUDIO (IA) ══════════════════════
async def processar_audio(u:Update, c:ContextTypes.DEFAULT_TYPE, primeiro=True):
    """Baixa e interpreta o audio, faz o match, e decide o proximo passo."""
    voice = u.message.voice or u.message.audio
    tg_file = await c.bot.get_file(voice.file_id)
    audio_bytes = await tg_file.download_as_bytearray()

    clientes_opts, servicos_opts, produtos_opts = carregar_catalogo()
    todos_itens_opts = servicos_opts + produtos_opts

    resultado = await asyncio.to_thread(
        interpretar_audio_proposta,
        bytes(audio_bytes), 'audio/ogg',
        [x['nome'] for x in clientes_opts],
        [x['nome'] for x in servicos_opts],
        [x['nome'] for x in produtos_opts]
    )

    if not resultado:
        await u.message.reply_text(
            "❌ Não consegui interpretar o áudio. Grave novamente, com calma e um pouco mais alto.",
            parse_mode='Markdown')
        return IA_AGUARDA if primeiro else IA_CORRECAO

    # ── CLIENTE ──
    if not c.user_data.get('cliente'):
        cliente_falado = resultado.get('cliente', '') or ''
        match = melhor_match(cliente_falado, clientes_opts)
        if match:
            c.user_data['cliente'] = match
        elif cliente_falado:
            c.user_data['cliente_falado_novo'] = cliente_falado
            c.user_data['tentativas_cliente'] = c.user_data.get('tentativas_cliente', 0) + 1

    # ── ITENS ──
    itens_ja = c.user_data.get('itens', [])
    itens_nao_encontrados = []
    for item_falado in resultado.get('itens', []):
        nome_falado = item_falado.get('nome', '')
        qtd = item_falado.get('quantidade', 1) or 1
        match = melhor_match(nome_falado, todos_itens_opts)
        if match:
            ja_existe = any(x['id']==match['id'] and x['tipo']==match['tipo'] for x in itens_ja)
            if not ja_existe:
                itens_ja.append({'id':match['id'],'nome':match['nome'],'tipo':match['tipo'],'preco':match['preco'],'qtd':qtd})
        else:
            itens_nao_encontrados.append(nome_falado)
    c.user_data['itens'] = itens_ja

    # Guarda dados extras (so na primeira vez, se ja nao tiver)
    if primeiro:
        c.user_data['audio_pagamento'] = resultado.get('pagamento')
        c.user_data['audio_validade'] = resultado.get('validade_dias')
        c.user_data['audio_etapas'] = resultado.get('etapas', [])

    # ── AVALIA O QUE FALTA ──
    cliente_ok = bool(c.user_data.get('cliente'))
    tem_itens = bool(c.user_data['itens'])

    if cliente_ok and tem_itens and not itens_nao_encontrados:
        return await mostrar_resumo_ia(u, c)

    # Falta alguma coisa - pede correcao por audio
    msg = "🎤 *Progresso da interpretação:*\n\n"
    if cliente_ok:
        msg += f"👤 Cliente: *{c.user_data['cliente']['nome']}* ✅\n"
    elif c.user_data.get('cliente_falado_novo'):
        msg += f"👤 Cliente: *{c.user_data['cliente_falado_novo']}* — não encontrado no cadastro ⚠️\n"
    else:
        msg += f"👤 Cliente: não identificado ⚠️\n"

    if c.user_data['itens']:
        msg += "\n📦 *Itens já identificados:*\n"
        for it in c.user_data['itens']:
            msg += f"  • {it['nome']} x{it['qtd']}\n"

    if itens_nao_encontrados:
        msg += "\n⚠️ *Não encontrei no catálogo:*\n"
        for nome in itens_nao_encontrados:
            msg += f"  • {nome}\n"

    msg += "\n🎙️ *Grave um novo áudio* corrigindo ou completando as informações que faltam."
    if not cliente_ok and c.user_data.get('tentativas_cliente', 0) >= 2:
        msg += "\n\nOu digite *cadastrar* para criar o cliente com o nome que você falou."
    msg += "\nOu digite *manual* para continuar preenchendo na mão."

    await u.message.reply_text(msg, parse_mode='Markdown')
    return IA_CORRECAO

async def ia_aguarda(u:Update, c:ContextTypes.DEFAULT_TYPE):
    if not (u.message.voice or u.message.audio):
        await u.message.reply_text("🎤 Preciso que você *grave um áudio*. Digite *manual* para preencher na mão.", parse_mode='Markdown')
        return IA_AGUARDA
    await u.message.reply_text("🎧 Processando áudio...")
    try:
        return await processar_audio(u, c, primeiro=True)
    except Exception as e:
        await u.message.reply_text(f"❌ Erro ao processar áudio: {e}\n\nTente gravar novamente ou digite *manual*.", parse_mode='Markdown')
        return IA_AGUARDA

async def ia_correcao(u:Update, c:ContextTypes.DEFAULT_TYPE):
    if u.message.voice or u.message.audio:
        await u.message.reply_text("🎧 Processando novo áudio...")
        try:
            return await processar_audio(u, c, primeiro=False)
        except Exception as e:
            await u.message.reply_text(f"❌ Erro ao processar áudio: {e}\n\nTente novamente ou digite *manual*.", parse_mode='Markdown')
            return IA_CORRECAO

    txt = (u.message.text or '').strip().lower().rstrip('.!?')
    if 'manual' in txt:
        # Se ja tem cliente, pula pra servicos; senao lista clientes
        if c.user_data.get('cliente'):
            return await listar_servicos(u, c)
        return await listar_clientes(u, c)

    if 'cadastr' in txt and c.user_data.get('cliente_falado_novo'):
        await u.message.reply_text(f"📱 WhatsApp do cliente *{c.user_data['cliente_falado_novo']}*:", parse_mode='Markdown')
        return IA_TEL

    await u.message.reply_text("🎤 Grave um novo áudio, ou digite *manual* / *cadastrar*.", parse_mode='Markdown')
    return IA_CORRECAO

async def ia_tel(u:Update, c:ContextTypes.DEFAULT_TYPE):
    with app.app_context():
        emp=get_emp()
        nome = c.user_data['cliente_falado_novo']
        x=Cliente(empresa_id=emp.id,nome=nome,telefone=u.message.text.strip(),tipo='PF')
        db.session.add(x);db.session.commit();c.user_data['cliente']={'id':x.id,'nome':x.nome}
    await u.message.reply_text(f"✅ *{nome}* cadastrado!",parse_mode='Markdown')
    if c.user_data['itens']:
        return await mostrar_resumo_ia(u, c)
    await u.message.reply_text("🎤 Agora grave um áudio com os itens da proposta.")
    return IA_CORRECAO

async def mostrar_resumo_ia(u:Update, c:ContextTypes.DEFAULT_TYPE):
    itens = c.user_data['itens']
    total = sum(i['preco']*i['qtd'] for i in itens)
    msg = "✅ *Tudo identificado!*\n\n"
    msg += f"👤 Cliente: *{c.user_data['cliente']['nome']}*\n\n"
    msg += "📦 *Itens:*\n"
    for it in itens:
        msg += f"  • {it['nome']} x{it['qtd']} — {fmt(it['preco']*it['qtd'])}\n"
    msg += f"\n💰 *Total: {fmt(total)}*"
    await u.message.reply_text(msg, parse_mode='Markdown',
        reply_markup=kb(["✅ Continuar","🔧 Ajustar manualmente"],2))
    return IA_CONFIRMAR

async def ia_confirmar(u:Update, c:ContextTypes.DEFAULT_TYPE):
    txt = u.message.text
    if "Ajustar" in txt:
        return await listar_servicos(u, c)

    # Usa etapas/pagamento/validade ja capturados no audio, se tiver
    if c.user_data.get('audio_etapas'):
        c.user_data['etapas'] = [{'titulo':e.get('titulo',''),'duracao_dias':e.get('dias',1),'descricao':''} for e in c.user_data['audio_etapas']]
    else:
        c.user_data['etapas'] = c.user_data.get('etapas', [])

    if c.user_data.get('audio_validade'):
        c.user_data['validade'] = int(c.user_data['audio_validade'])
        if c.user_data.get('audio_pagamento'):
            c.user_data['pagamento'] = c.user_data['audio_pagamento']
            itens=c.user_data['itens'];total=sum(i['preco']*i['qtd'] for i in itens)
            msg=f"📄 *Confirmar:*\n\n👤 *{c.user_data['cliente']['nome']}*\n💳 {c.user_data['pagamento']}\n📅 {c.user_data['validade']} dias\n\n"
            msg+="".join(f"• {i['nome']} x{i['qtd']} — {fmt(i['preco']*i['qtd'])}\n" for i in itens)
            if c.user_data.get('etapas'):
                msg += "\n📅 *Cronograma:*\n"+"".join(f"{i}. {et['titulo']} — {et['duracao_dias']} dia(s)\n" for i,et in enumerate(c.user_data['etapas'],1))
            msg+=f"\n💰 *TOTAL: {fmt(total)}*"
            await u.message.reply_text(msg,parse_mode='Markdown',reply_markup=kb(["✅ Confirmar e Gerar","❌ Cancelar"],2))
            return CONFIRMAR
        await u.message.reply_text("💳 *Forma de pagamento:*",parse_mode='Markdown',
            reply_markup=kb(["Pix à Vista","Pix ou Cartão (c/ acréscimo)","Boleto 30 dias","Cartão de Crédito","A combinar"],1))
        return PAGAMENTO

    if c.user_data.get('etapas'):
        return await perguntar_validade(u, c)

    await u.message.reply_text(
        "📅 *Deseja adicionar as fases de execução (cronograma de entrega)?*",
        parse_mode='Markdown', reply_markup=kb(["✅ Sim, adicionar etapas","⏭️ Pular etapas"],2))
    return PERGUNTA_ETAPAS

# ══════════════════════ MAIN ══════════════════════
def main():
    print("[OK] CreativeNeura Bot v5 (com IA por audio) iniciando...")
    from telegram.request import HTTPXRequest
    req = HTTPXRequest(connect_timeout=30, read_timeout=60, write_timeout=60, pool_timeout=60, connection_pool_size=50)
    req_polling = HTTPXRequest(connect_timeout=30, read_timeout=40, write_timeout=30, pool_timeout=30, connection_pool_size=10)
    app_bot=Application.builder().token(TOKEN).request(req).get_updates_request(req_polling).build()
    conv=ConversationHandler(
        entry_points=[CommandHandler('start',start),MessageHandler(filters.Regex(r'(?i)^(oi|ola|menu)'),start)],
        states={
            MENU:[MessageHandler(filters.TEXT&~filters.COMMAND,menu)],
            CLIENTE:[MessageHandler(filters.TEXT&~filters.COMMAND,escolher_cliente)],
            NC_NOME:[MessageHandler(filters.TEXT&~filters.COMMAND,nc_nome)],
            NC_TEL:[MessageHandler(filters.TEXT&~filters.COMMAND,nc_tel)],
            SERVICO:[MessageHandler(filters.TEXT&~filters.COMMAND,escolher_servico)],
            PRODUTO:[MessageHandler(filters.TEXT&~filters.COMMAND,escolher_produto)],
            QTD:[MessageHandler(filters.TEXT&~filters.COMMAND,receber_qtd)],
            PRECO:[MessageHandler(filters.TEXT&~filters.COMMAND,receber_preco)],
            MAIS:[MessageHandler(filters.TEXT&~filters.COMMAND,mais_itens)],
            PERGUNTA_ETAPAS:[MessageHandler(filters.TEXT&~filters.COMMAND,resposta_pergunta_etapas)],
            ETAPA_TITULO:[MessageHandler(filters.TEXT&~filters.COMMAND,receber_etapa_titulo)],
            ETAPA_DIAS:[MessageHandler(filters.TEXT&~filters.COMMAND,receber_etapa_dias)],
            VALIDADE:[MessageHandler(filters.TEXT&~filters.COMMAND,receber_validade)],
            PAGAMENTO:[MessageHandler(filters.TEXT&~filters.COMMAND,receber_pagamento)],
            CONFIRMAR:[MessageHandler(filters.TEXT&~filters.COMMAND,confirmar)],
            IA_AGUARDA:[MessageHandler(filters.VOICE|filters.AUDIO|filters.TEXT,ia_aguarda)],
            IA_CORRECAO:[MessageHandler(filters.VOICE|filters.AUDIO|filters.TEXT,ia_correcao)],
            IA_CONFIRMAR:[MessageHandler(filters.TEXT&~filters.COMMAND,ia_confirmar)],
            IA_TEL:[MessageHandler(filters.TEXT&~filters.COMMAND,ia_tel)],
        },
        fallbacks=[CommandHandler('cancelar',cancelar)],allow_reentry=True)
    app_bot.add_handler(conv)
    print("[OK] Bot rodando! t.me/CreativeNeura_bot")
    app_bot.run_polling(allowed_updates=Update.ALL_TYPES,drop_pending_updates=True)

if __name__=='__main__':main()
