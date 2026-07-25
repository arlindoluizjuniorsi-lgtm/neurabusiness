"""
Interpretacao unificada de mensagens (texto ou audio) via Google Gemini.
Uma unica chamada decide se a mensagem e um pedido de PROPOSTA comercial
ou uma PERGUNTA solta (calculo, duvida sobre servicos/produtos etc) e ja
devolve os dados prontos pro bot do Telegram usar em qualquer um dos
dois casos -- assim o usuario nao precisa escolher um modo antes de
falar com a IA.
"""
import urllib.request
import urllib.error
import json
import base64
import time

from config import Config

GEMINI_API_KEY = Config.GEMINI_API_KEY
GEMINI_MODEL   = 'gemini-3.5-flash'
GEMINI_URL     = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'


def interpretar_mensagem(texto, audio_bytes, mime_type, clientes, servicos, produtos):
    """
    texto: string ou None. audio_bytes/mime_type: bytes/string ou None
    (pelo menos um dos dois precisa vir preenchido).
    clientes/servicos/produtos: listas de nomes ja cadastrados (contexto pro modelo).

    Retorna um dict:
      {"tipo": "pergunta", "resposta": "..."}
      ou
      {"tipo": "proposta", "cliente": "...", "itens": [{"nome":..,"quantidade":..}],
       "pagamento": "..." ou None, "validade_dias": numero ou None,
       "etapas": [{"titulo":..,"dias":..}]}
    Retorna None em caso de erro na chamada.
    """
    lista_clientes = '\n'.join(f'- {c}' for c in clientes[:100])
    lista_servicos = '\n'.join(f'- {s}' for s in servicos[:100])
    lista_produtos = '\n'.join(f'- {p}' for p in produtos[:200])

    prompt = f"""Você é o assistente de um profissional de instalação e manutenção de CFTV e
infraestrutura, que usa esse chat do Telegram tanto para GERAR PROPOSTAS COMERCIAIS quanto
para tirar DÚVIDAS RÁPIDAS (cálculos, perguntas sobre os próprios serviços/produtos etc).

Primeiro decida o TIPO da mensagem:
- "proposta": a pessoa está pedindo para montar uma proposta comercial para um cliente
  (geralmente menciona nome de cliente + serviços/produtos + quantidades).
- "pergunta": qualquer outra coisa -- cálculo, dúvida, pergunta geral relacionada ao trabalho.

Se for "proposta", identifique e preencha os campos de proposta (deixe "resposta" como null):
1. O CLIENTE mencionado (compare com a lista abaixo e retorne o nome mais parecido se houver
   correspondência, senão retorne exatamente o nome que foi dito)
2. Os SERVIÇOS e PRODUTOS mencionados, com quantidades (compare com as listas abaixo)
3. Forma de pagamento, se mencionada
4. Validade da proposta em dias, se mencionada
5. Etapas/fases de execução (cronograma), se mencionadas

Se for "pergunta", responda de forma direta e objetiva em português, sem formalidade excessiva,
e deixe os demais campos como null/vazio. Se for um cálculo, mostre o resultado com clareza. Se
for sobre os serviços/produtos da empresa, use as listas abaixo como referência e não invente
preço que não está nelas.

CLIENTES CADASTRADOS:
{lista_clientes}

SERVIÇOS CADASTRADOS:
{lista_servicos}

PRODUTOS CADASTRADOS:
{lista_produtos}

Responda APENAS com um JSON no formato exato abaixo, sem texto adicional:
{{
  "tipo": "proposta ou pergunta",
  "resposta": "resposta da pergunta (só se tipo==pergunta, senão null)",
  "cliente": "nome do cliente identificado (só se tipo==proposta, senão null)",
  "itens": [
    {{"nome": "nome do servico ou produto", "quantidade": numero}}
  ],
  "pagamento": "forma de pagamento mencionada ou null",
  "validade_dias": numero ou null,
  "etapas": [
    {{"titulo": "nome da etapa", "dias": numero}}
  ]
}}"""

    parts = [{"text": prompt}]
    if texto:
        parts.append({"text": f"Mensagem do usuário: {texto}"})
    if audio_bytes:
        parts.append({"inline_data": {
            "mime_type": mime_type,
            "data": base64.b64encode(audio_bytes).decode('utf-8'),
        }})

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
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
            texto_resp = data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(texto_resp)
        except urllib.error.HTTPError as e:
            corpo = e.read().decode('utf-8', errors='ignore')
            ultimo_erro = f"HTTP {e.code}: {corpo[:300]}"
            if e.code == 503:
                time.sleep(2)
                continue
            print(f"[ERRO Gemini unificado] {ultimo_erro}")
            return None
        except Exception as e:
            ultimo_erro = str(e)
            print(f"[ERRO Gemini unificado] {ultimo_erro}")
            return None

    print(f"[ERRO Gemini unificado] Falhou após 3 tentativas: {ultimo_erro}")
    return None
