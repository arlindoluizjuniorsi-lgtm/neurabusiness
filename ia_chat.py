"""
Chat livre com o Google Gemini, pelo mesmo bot do Telegram usado pra
gerar propostas por audio. Aceita pergunta em texto ou audio e responde
em texto -- usado pra calculos rapidos ou duvidas sobre os proprios
servicos/produtos cadastrados.
"""
import urllib.request
import urllib.error
import json
import base64
import time

GEMINI_API_KEY = '***REMOVED_GEMINI_API_KEY***'
GEMINI_MODEL   = 'gemini-3.5-flash'
GEMINI_URL     = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'


def responder_pergunta(pergunta_texto=None, audio_bytes=None, mime_type=None, contexto_servicos=''):
    """Manda a pergunta (texto e/ou audio) pro Gemini, com a lista de
    servicos/produtos cadastrados como contexto, e devolve a resposta em
    texto pronta pra mandar de volta no Telegram. Retorna None em caso de
    erro (quem chama decide a mensagem de falha)."""
    prompt = f"""Voce e um assistente que ajuda um profissional de instalacao e manutencao de CFTV e
infraestrutura a responder perguntas rapidas do dia a dia: calculos, duvidas sobre os
proprios servicos/produtos, ou perguntas gerais relacionadas ao trabalho dele.

Responda de forma direta e objetiva, em portugues, sem formalidade excessiva. Se for um
calculo, mostre o resultado com clareza. Se a pergunta for sobre os servicos/produtos da
empresa, use a lista abaixo como referencia e nao invente precos que nao estao nela.

SERVICOS E PRODUTOS CADASTRADOS:
{contexto_servicos}"""

    parts = [{"text": prompt}]
    if pergunta_texto:
        parts.append({"text": f"Pergunta: {pergunta_texto}"})
    if audio_bytes:
        parts.append({"inline_data": {
            "mime_type": mime_type,
            "data": base64.b64encode(audio_bytes).decode('utf-8'),
        }})

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.3},
    }
    req = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'X-goog-api-key': GEMINI_API_KEY,
        },
    )

    ultimo_erro = None
    for _tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        except urllib.error.HTTPError as e:
            corpo = e.read().decode('utf-8', errors='ignore')
            ultimo_erro = f"HTTP {e.code}: {corpo[:300]}"
            if e.code == 503:
                time.sleep(2)
                continue
            print(f"[ERRO Gemini chat] {ultimo_erro}")
            return None
        except Exception as e:
            ultimo_erro = str(e)
            print(f"[ERRO Gemini chat] {ultimo_erro}")
            return None

    print(f"[ERRO Gemini chat] Falhou apos 3 tentativas: {ultimo_erro}")
    return None
