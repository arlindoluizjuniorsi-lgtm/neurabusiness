"""
NeuraBusiness — Windows Service Wrapper
Registra o Flask como serviço do Windows usando pywin32.

Comandos manuais:
  python neurabusiness_service.py install   -> instala
  python neurabusiness_service.py start     -> inicia
  python neurabusiness_service.py stop      -> para
  python neurabusiness_service.py remove    -> remove
  python neurabusiness_service.py restart   -> reinicia
"""
import sys
import os
import time
import logging

# Garante que o diretório do script está no path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Configura log
LOG_FILE = os.path.join(BASE_DIR, 'neurabusiness_service.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    import socket
except ImportError:
    print("pywin32 não instalado. Execute: pip install pywin32")
    sys.exit(1)


class NeuraBusiness(win32serviceutil.ServiceFramework):
    _svc_name_         = 'NeuraBusiness'
    _svc_display_name_ = 'NeuraBusiness Sistema Comercial'
    _svc_description_  = 'NeuraBusiness — Sistema Comercial Creative (Flask + SQL Server)'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.server     = None
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        logging.info("Parando NeuraBusiness...")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.server:
            try:
                self.server.close()
            except: pass

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ''))
        logging.info("Iniciando NeuraBusiness...")
        self.main()

    def main(self):
        try:
            os.chdir(BASE_DIR)
            logging.info(f"Diretório: {BASE_DIR}")

            # Importa e configura o app Flask
            from app import app, db
            from seed_servicos import seed_catalogo_sqla

            with app.app_context():
                db.create_all()
                logging.info("Schema verificado/criado")

                # Seed inicial se necessário
                try:
                    from app import seed_inicial
                    seed_inicial()
                except Exception as e:
                    logging.warning(f"seed_inicial: {e}")

            # Usa waitress como servidor WSGI de produção
            try:
                from waitress import serve
                logging.info("Servidor: waitress (produção)")

                # Roda em thread para não bloquear o loop de controle
                import threading
                def run_server():
                    try:
                        serve(app, host='0.0.0.0', port=5000,
                              threads=4, channel_timeout=300,
                              cleanup_interval=30)
                    except Exception as e:
                        logging.error(f"Servidor parou: {e}")

                t = threading.Thread(target=run_server, daemon=True)
                t.start()
                logging.info("NeuraBusiness rodando em http://0.0.0.0:5000")

            except ImportError:
                # Fallback para Flask dev server
                logging.warning("waitress não encontrado, usando Flask dev server")
                import threading
                def run_flask():
                    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
                t = threading.Thread(target=run_flask, daemon=True)
                t.start()
                logging.info("NeuraBusiness rodando (Flask dev) em http://0.0.0.0:5000")

            # Aguarda sinal de parada
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            logging.info("NeuraBusiness parado.")

        except Exception as e:
            logging.error(f"Erro fatal: {e}", exc_info=True)
            servicemanager.LogErrorMsg(f"NeuraBusiness erro: {str(e)}")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Chamado pelo SCM (Service Control Manager)
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(NeuraBusiness)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Chamado via linha de comando
        win32serviceutil.HandleCommandLine(NeuraBusiness)
