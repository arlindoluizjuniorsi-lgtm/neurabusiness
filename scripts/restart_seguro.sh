#!/usr/bin/env bash
#
# restart_seguro.sh -- wrapper do restart semanal do NeuraBusiness
# (neurabusiness-restart.timer). So reinicia se NAO tiver:
#   1) nenhuma rotina de backup do NeuraDesk marcada "executando" no banco
#   2) o backup diario do proprio NeuraBusiness rodando agora
# Backup e coisa seria -- se qualquer um dos dois estiver ativo, pula
# essa semana (o timer tenta de novo na proxima segunda).

set -euo pipefail

NEURADESK_ENV="/opt/neuradesk/.env"
_env_neuradesk() {
    grep -E "^$1=" "$NEURADESK_ENV" | head -1 | cut -d'=' -f2-
}

if [ -f "$NEURADESK_ENV" ]; then
    DB_SERVER="$(_env_neuradesk DB_SERVER)"
    DB_PORT="$(_env_neuradesk DB_PORT)"
    DB_NAME="$(_env_neuradesk DB_NAME)"
    DB_USER="$(_env_neuradesk DB_USER)"
    DB_PASSWORD="$(_env_neuradesk DB_PASSWORD)"

    RODANDO=$(PGPASSWORD="$DB_PASSWORD" psql -h "${DB_SERVER:-localhost}" -p "${DB_PORT:-5432}" \
        -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT count(*) FROM backup_rotinas WHERE ultima_execucao_status='executando';" 2>/dev/null || echo "?")

    if [ "$RODANDO" = "?" ]; then
        echo "$(date '+%F %T') Nao consegui checar backup_rotinas do NeuraDesk -- pulando restart por seguranca." >&2
        exit 0
    fi
    if [ "$RODANDO" != "0" ]; then
        echo "$(date '+%F %T') Ha $RODANDO rotina(s) de backup do NeuraDesk em execucao -- pulando restart desta semana." >&2
        exit 0
    fi
fi

if systemctl is-active --quiet neurabusiness-backup.service; then
    echo "$(date '+%F %T') Backup do proprio NeuraBusiness esta rodando agora -- pulando restart desta semana." >&2
    exit 0
fi

echo "$(date '+%F %T') Nenhum backup em andamento -- reiniciando NeuraBusiness e o bot."
systemctl restart neurabusiness.service creative-bot.service
