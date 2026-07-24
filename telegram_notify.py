"""
Helper para enviar mensagens e documentos via Telegram Bot API
Usado pelo app.py para notificar Arlindo quando o contrato for totalmente assinado
"""
import urllib.request
import json
import mimetypes
import uuid

TELEGRAM_TOKEN   = '***REMOVED_TELEGRAM_TOKEN***'
TELEGRAM_CHAT_ID = '6295632432'  # Chat ID do Arlindo


def enviar_mensagem_telegram(texto):
    """Envia uma mensagem de texto simples."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({
        'chat_id': TELEGRAM_CHAT_ID,
        'text': texto,
        'parse_mode': 'Markdown'
    }).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[ERRO Telegram] {e}")
        return None


def enviar_documento_telegram(pdf_bytes, filename, caption=''):
    """Envia um arquivo PDF (em bytes) como documento."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    boundary = uuid.uuid4().hex

    body = b''
    # chat_id
    body += f'--{boundary}\r\n'.encode()
    body += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
    body += f'{TELEGRAM_CHAT_ID}\r\n'.encode()
    # caption
    if caption:
        body += f'--{boundary}\r\n'.encode()
        body += b'Content-Disposition: form-data; name="caption"\r\n\r\n'
        body += f'{caption}\r\n'.encode()
    # document
    body += f'--{boundary}\r\n'.encode()
    body += f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode()
    body += b'Content-Type: application/pdf\r\n\r\n'
    body += pdf_bytes
    body += f'\r\n--{boundary}--\r\n'.encode()

    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[ERRO Telegram Documento] {e}")
        return None
