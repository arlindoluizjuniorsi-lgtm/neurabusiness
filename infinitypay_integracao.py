"""Integração com a InfinitePay -- geração de links de pagamento (Checkout
Integrado) que aceitam Pix e cartão (parcelado) na mesma tela, sem exigir
tokenização de cartão no nosso servidor.

Como configurar:
  1. Pegue seu "handle" (InfiniteTag, sem o $ na frente) no app/site da
     InfinitePay.
  2. Configure na tela /admin/integracoes (INFINITYPAY_HANDLE) -- fica
     cifrado no banco, igual ao Mercado Pago.

Referência oficial: https://www.infinitepay.io/checkout-documentacao
O Checkout Integrado NÃO exige API key/token -- a requisição em POST /links
leva só handle + items (e campos opcionais como order_nsu, redirect_url,
webhook_url).
"""
import requests

INFINITYPAY_API_BASE = 'https://api.checkout.infinitepay.io'


def criar_link_pagamento(handle, itens, order_nsu, redirect_url,
                          webhook_url=None, timeout=20):
    """Cria um link de pagamento (Pix + cartão) via Checkout Integrado da
    InfinitePay. `itens` é uma lista de dicts {titulo, quantidade,
    valor_unitario} (valor em reais -- convertido pra centavos aqui).
    Retorna (url_pagamento, None) em caso de sucesso, ou (None, erro)."""
    body = {
        'handle': handle,
        'order_nsu': str(order_nsu),
        'items': [
            {
                'quantity': int(i.get('quantidade', 1) or 1),
                'price': round(float(i['valor_unitario']) * 100),  # centavos
                'description': i['titulo'][:250],
            }
            for i in itens
        ],
    }
    if redirect_url:
        body['redirect_url'] = redirect_url
    if webhook_url:
        body['webhook_url'] = webhook_url

    try:
        r = requests.post(
            f'{INFINITYPAY_API_BASE}/links',
            headers={'Content-Type': 'application/json'},
            json=body,
            timeout=timeout,
        )
    except requests.RequestException as e:
        return None, {'message': str(e)}

    dados = r.json() if r.content else {}
    if r.status_code not in (200, 201):
        return None, dados

    link = dados.get('url')
    if not link:
        return None, {'message': 'resposta da InfinitePay sem link reconhecível', 'raw': dados}
    return link, None


def verificar_pagamento(handle, order_nsu, transaction_nsu, slug, timeout=15):
    """Consulta POST /payment_check -- alternativa ao webhook pra confirmar
    se um pagamento foi mesmo aprovado. Usado tanto quando o cliente volta
    do checkout pro redirect_url (que traz transaction_nsu/slug na URL)
    quanto quando o webhook chega, pra nao confiar cegamente no corpo do
    webhook (a InfinitePay nao documenta um esquema de assinatura pra ele,
    entao qualquer um poderia forjar um POST -- so confirmamos de fato
    perguntando pra API deles com os identificadores recebidos)."""
    try:
        r = requests.post(
            f'{INFINITYPAY_API_BASE}/payment_check',
            headers={'Content-Type': 'application/json'},
            json={
                'handle': handle,
                'order_nsu': str(order_nsu),
                'transaction_nsu': transaction_nsu,
                'slug': slug,
            },
            timeout=timeout,
        )
    except requests.RequestException as e:
        return None, {'message': str(e)}

    dados = r.json() if r.content else {}
    if r.status_code != 200:
        return None, dados
    return dados, None
