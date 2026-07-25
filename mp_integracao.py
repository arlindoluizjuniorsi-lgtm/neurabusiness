"""Integração com o Mercado Pago -- validação de webhook e busca de
pagamentos/assinaturas, usadas pra renovar automaticamente as licenças
do NeuraDesk quando um cliente paga.

Como configurar (quando estiver pronto):
  1. No .env do NeuraBusiness, defina:
       MP_ACCESS_TOKEN=<access token da aplicação MP>
       MP_WEBHOOK_SECRET=<chave secreta do webhook, painel MP>
  2. No painel do Mercado Pago, cadastre a URL de notificação:
       https://SEU_DOMINIO/webhook/mercadopago
  3. Ao criar a assinatura (preapproval) de um cliente, defina
     external_reference = chave da licença (ex: NRDK-XXXX-XXXX-XXXX-XXXX)
     -- é assim que o webhook sabe qual licença renovar.

Enquanto MP_ACCESS_TOKEN / MP_WEBHOOK_SECRET não estiverem definidos, o
endpoint do webhook fica inerte (responde 503), sem risco de aceitar
notificações não autenticadas.
"""
import hmac
import hashlib
import uuid
import requests

MP_API_BASE = 'https://api.mercadopago.com'


def validar_assinatura(headers, query_args, secret):
    """Confere a assinatura HMAC que o Mercado Pago manda em toda
    notificação de webhook (header x-signature), pelo esquema
    documentado oficialmente. Sem isso, qualquer um poderia forjar um
    POST dizendo 'pagamento aprovado' e renovar uma licença de graça."""
    if not secret:
        return False

    x_signature = headers.get('x-signature', '') or ''
    x_request_id = headers.get('x-request-id', '') or ''
    data_id = (query_args.get('data.id') or query_args.get('id') or '').lower()

    partes = {}
    for pedaco in x_signature.split(','):
        if '=' in pedaco:
            k, v = pedaco.split('=', 1)
            partes[k.strip()] = v.strip()
    ts = partes.get('ts')
    v1 = partes.get('v1')
    if not ts or not v1:
        return False

    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    esperado = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


def buscar_pagamento(payment_id, access_token, timeout=15):
    r = requests.get(
        f'{MP_API_BASE}/v1/payments/{payment_id}',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=timeout,
    )
    if r.status_code != 200:
        return None
    return r.json()


def buscar_preapproval(preapproval_id, access_token, timeout=15):
    r = requests.get(
        f'{MP_API_BASE}/preapproval/{preapproval_id}',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=timeout,
    )
    if r.status_code != 200:
        return None
    return r.json()


def _payer_nome(nome_completo):
    """MP exige first_name/last_name separados -- o cadastro do
    NeuraBusiness só tem o nome completo do representante, então
    quebramos na primeira palavra."""
    partes = (nome_completo or '').strip().split(' ', 1)
    first = partes[0] if partes else ''
    last = partes[1] if len(partes) > 1 else first
    return first, last


def _payer_identification(cpf_ou_cnpj):
    doc = ''.join(c for c in (cpf_ou_cnpj or '') if c.isdigit())
    tipo = 'CNPJ' if len(doc) > 11 else 'CPF'
    return {'type': tipo, 'number': doc}


def criar_pagamento_boleto(access_token, valor, descricao, external_reference,
                            email, nome, cpf_cnpj, endereco=None, timeout=20):
    """Gera um boleto (bolbradesco) via API de Pagamentos do MP. Retorna o
    JSON completo da resposta (contém transaction_details.external_resource_url
    com o link do PDF do boleto e barcode.content com a linha digitável).

    `endereco` é obrigatório pra boleto registrado -- dict com
    zip_code/street_name/street_number/neighborhood/city/federal_unit."""
    first, last = _payer_nome(nome)
    payer = {
        'email': email,
        'first_name': first,
        'last_name': last,
        'identification': _payer_identification(cpf_cnpj),
    }
    if endereco:
        payer['address'] = endereco
    body = {
        'transaction_amount': round(float(valor), 2),
        'description': descricao,
        'payment_method_id': 'bolbradesco',
        'external_reference': external_reference,
        'payer': payer,
    }
    r = requests.post(
        f'{MP_API_BASE}/v1/payments',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'X-Idempotency-Key': str(uuid.uuid4()),
        },
        json=body,
        timeout=timeout,
    )
    dados = r.json() if r.content else {}
    if r.status_code not in (200, 201):
        return None, dados
    return dados, None


def criar_pagamento_pix(access_token, valor, descricao, external_reference,
                         email, nome, cpf_cnpj, timeout=20):
    """Gera uma cobrança Pix via API de Pagamentos do MP. Retorna o JSON
    completo (contém point_of_interaction.transaction_data.qr_code_base64
    e .qr_code, o "copia e cola")."""
    first, last = _payer_nome(nome)
    body = {
        'transaction_amount': round(float(valor), 2),
        'description': descricao,
        'payment_method_id': 'pix',
        'external_reference': external_reference,
        'payer': {
            'email': email,
            'first_name': first,
            'last_name': last,
            'identification': _payer_identification(cpf_cnpj),
        },
    }
    r = requests.post(
        f'{MP_API_BASE}/v1/payments',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'X-Idempotency-Key': str(uuid.uuid4()),
        },
        json=body,
        timeout=timeout,
    )
    dados = r.json() if r.content else {}
    if r.status_code not in (200, 201):
        return None, dados
    return dados, None


def criar_preapproval(access_token, valor, descricao, external_reference,
                       payer_email, back_url, frequencia=1, timeout=20):
    """Cria uma assinatura recorrente (preapproval) ad-hoc -- sem plano
    pré-cadastrado -- e retorna o JSON com 'init_point', a URL do checkout
    hospedado pelo MP onde o cliente informa o cartão e autoriza a
    cobrança automática mensal."""
    body = {
        'reason': descricao,
        'external_reference': external_reference,
        'payer_email': payer_email,
        'back_url': back_url,
        'status': 'pending',
        'auto_recurring': {
            'frequency': frequencia,
            'frequency_type': 'months',
            'transaction_amount': round(float(valor), 2),
            'currency_id': 'BRL',
        },
    }
    r = requests.post(
        f'{MP_API_BASE}/preapproval',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        json=body,
        timeout=timeout,
    )
    dados = r.json() if r.content else {}
    if r.status_code not in (200, 201):
        return None, dados
    return dados, None
