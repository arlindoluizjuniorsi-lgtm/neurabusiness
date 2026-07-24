"""
Interpretacao de audio via Google Gemini API (gratuito)
Recebe audio (bytes) e devolve dados estruturados da proposta
"""
import urllib.request
import urllib.error
import json
import base64

GEMINI_API_KEY = '***REMOVED_GEMINI_API_KEY***'
GEMINI_MODEL   = 'gemini-3.5-flash'
GEMINI_URL     = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'


def interpretar_audio_proposta(audio_bytes, mime_type, clientes, servicos, produtos):
    """
    Envia audio para o Gemini e pede para extrair dados estruturados da proposta.
    clientes/servicos/produtos: listas de nomes já cadastrados (para dar contexto ao modelo).
    Retorna dict com: cliente, itens (lista de {nome, quantidade}), pagamento, validade_dias, etapas
    """
    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

    lista_clientes = '\n'.join(f'- {c}' for c in clientes[:100])
    lista_servicos = '\n'.join(f'- {s}' for s in servicos[:100])
    lista_produtos = '\n'.join(f'- {p}' for p in produtos[:200])

    prompt = f"""Voce e um assistente que transcreve audios em portugues e extrai dados estruturados para gerar uma proposta comercial.

Ouça o audio e identifique:
1. O nome do CLIENTE mencionado (compare com a lista de clientes já cadastrados abaixo e retorne o nome mais parecido se houver correspondencia, senao retorne exatamente o nome que foi dito)
2. Os SERVIÇOS e PRODUTOS mencionados, com suas quantidades (compare com as listas abaixo)
3. Se mencionar forma de pagamento
4. Se mencionar validade da proposta em dias
5. Se mencionar etapas/fases de execucao (cronograma)

CLIENTES CADASTRADOS:
{lista_clientes}

SERVIÇOS CADASTRADOS:
{lista_servicos}

PRODUTOS CADASTRADOS:
{lista_produtos}

Responda APENAS com um JSON no formato exato abaixo, sem texto adicional:
{{
  "cliente": "nome do cliente identificado",
  "itens": [
    {{"nome": "nome do servico ou produto", "quantidade": numero}}
  ],
  "pagamento": "forma de pagamento mencionada ou null",
  "validade_dias": numero ou null,
  "etapas": [
    {{"titulo": "nome da etapa", "dias": numero}}
  ]
}}"""

    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": audio_b64}}
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    req = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'X-goog-api-key': GEMINI_API_KEY
        }
    )

    import time
    ultimo_erro = None
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            texto = data['candidates'][0]['content']['parts'][0]['text']
            resultado = json.loads(texto)
            return resultado
        except urllib.error.HTTPError as e:
            corpo = e.read().decode('utf-8', errors='ignore')
            ultimo_erro = f"HTTP {e.code}: {corpo[:300]}"
            if e.code == 503:
                time.sleep(2)
                continue
            print(f"[ERRO Gemini] {ultimo_erro}")
            return None
        except Exception as e:
            ultimo_erro = str(e)
            print(f"[ERRO Gemini] {ultimo_erro}")
            return None

    print(f"[ERRO Gemini] Falhou apos 3 tentativas: {ultimo_erro}")
    return None
