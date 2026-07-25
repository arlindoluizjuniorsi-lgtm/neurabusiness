"""Integração com a InfinitePay -- geração de links de pagamento (Checkout
Integrado) que aceitam Pix e cartão (parcelado) na mesma tela, sem exigir
tokenização de cartão no nosso servidor.

Como configurar:
  1. Crie uma conta InfinitePay e pegue seu "handle" (tag) e a API key
     do checkout integrado -- painel InfinitePay > Integrações > Checkout.
  2. Configure na tela /admin/integracoes (INFINITYPAY_HANDLE e
     INFINITYPAY_API_KEY) -- fica cifrado no banco, igual ao Mercado Pago.

Referência: https://ajuda.infinitepay.io (Checkout Integrado). Como não
temos uma conta real pra testar em produção, esta integração não foi
validada contra a API de verdade -- se o formato da resposta mudar,
ajustar `_extrair_link` abaixo.
"""
import requests

INFINITYPAY_API_BASE = 'https://api.checkout.infinitepay.io'


def _extrair_link(dados):
    """A doc pública não deixa 100% claro o nome do campo de resposta --
    tenta as chaves mais prováveis antes de desistir."""
    if not isinstance(dados, dict):
        return None
    for chave in ('url', 'link', 'payment_url', 'checkout_url', 'payment_link'):
        if dados.get(chave):
            return dados[chave]
    return None


def criar_link_pagamento(handle, api_key, itens, order_nsu, redirect_url,
                          webhook_url=None, timeout=20):
    """Cria um link de pagamento (Pix + cartão) via Checkout Integrado da
    InfinitePay. `itens` é uma lista de dicts {titulo, quantidade,
    valor_unitario} (valor em reais -- convertido pra centavos aqui).
    Retorna (url_pagamento, None) em caso de sucesso, ou (None, erro)."""
    body = {
        'handle': handle,
        'redirect_url': redirect_url,
        'order_nsu': order_nsu,
        'items': [
            {
                'quantity': int(i.get('quantidade', 1) or 1),
                'price': round(float(i['valor_unitario']) * 100),  # centavos
                'description': i['titulo'][:250],
            }
            for i in itens
        ],
    }
    if webhook_url:
        body['webhook_url'] = webhook_url

    try:
        r = requests.post(
            f'{INFINITYPAY_API_BASE}/links',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json=body,
            timeout=timeout,
        )
    except requests.RequestException as e:
        return None, {'message': str(e)}

    dados = r.json() if r.content else {}
    if r.status_code not in (200, 201):
        return None, dados

    link = _extrair_link(dados)
    if not link:
        return None, {'message': 'resposta da InfinitePay sem link reconhecível', 'raw': dados}
    return link, None
