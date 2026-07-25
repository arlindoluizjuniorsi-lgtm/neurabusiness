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
