import os
from waitress import serve
from app import app, db, seed_inicial

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("[NeuraBusiness] Tabelas criadas/verificadas")
        seed_inicial()

    host = os.environ.get('SERVER_IP', '0.0.0.0')
    port = int(os.environ.get('SERVER_PORT', 5000))
    print(f"\n[>>] NeuraBusiness v3.0 — http://{host}:{port}\n")
    # waitress ignora X-Forwarded-* por padrão (proteção contra spoofing) --
    # precisa confiar explicitamente no nginx local pra repassar o esquema
    # (http/https) e IP originais pro app. Sem isso, request.is_secure e
    # url_for(_external=True) sempre acham que a conexão é HTTP.
    serve(app, host=host, port=port, threads=8,
          trusted_proxy='127.0.0.1',
          trusted_proxy_headers={'x-forwarded-for', 'x-forwarded-proto', 'x-forwarded-host'},
          trusted_proxy_count=1)
