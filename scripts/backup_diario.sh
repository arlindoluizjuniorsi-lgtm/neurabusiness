#!/usr/bin/env bash
#
# backup_diario.sh -- roda 1x por dia via systemd timer (neurabusiness-backup.timer).
# Faz backup do banco (pg_dump, formato custom) e dos arquivos enviados
# (logos de empresas, anexos de propostas), com rotação -- mantém só os
# últimos N dias, pra não encher o disco sozinho.

set -euo pipefail

APP_DIR="/opt/neurabusiness"
BACKUP_DIR="/var/backups/neurabusiness"
DIAS_RETENCAO=14

# Le so as chaves de banco do .env (nao usa `source` no arquivo inteiro --
# outros valores tem espaco, ex: CONTRATADA_RAZAO_SOCIAL, e quebrariam o
# parser do shell).
_env() {
    grep -E "^$1=" "${APP_DIR}/.env" | head -1 | cut -d'=' -f2-
}
NB_PG_HOST="$(_env NB_PG_HOST)"
NB_PG_PORT="$(_env NB_PG_PORT)"
NB_PG_DATABASE="$(_env NB_PG_DATABASE)"
NB_PG_USER="$(_env NB_PG_USER)"
NB_PG_PASS="$(_env NB_PG_PASS)"

mkdir -p "$BACKUP_DIR"
DATA="$(date +%Y%m%d_%H%M%S)"

PGPASSWORD="$NB_PG_PASS" pg_dump -h "${NB_PG_HOST:-localhost}" -p "${NB_PG_PORT:-5432}" \
    -U "$NB_PG_USER" -Fc "$NB_PG_DATABASE" > "${BACKUP_DIR}/db_${DATA}.dump"

tar -czf "${BACKUP_DIR}/arquivos_${DATA}.tar.gz" -C "$APP_DIR" \
    static/uploads 2>/dev/null || true

find "$BACKUP_DIR" -name 'db_*.dump' -mtime "+${DIAS_RETENCAO}" -delete
find "$BACKUP_DIR" -name 'arquivos_*.tar.gz' -mtime "+${DIAS_RETENCAO}" -delete

echo "Backup concluido: ${BACKUP_DIR}/db_${DATA}.dump"
