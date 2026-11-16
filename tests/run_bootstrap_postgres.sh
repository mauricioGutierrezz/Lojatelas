#!/usr/bin/env bash
# Cluster NUEVO del test, sin conexiones a instalaciones o QA existentes.
set -euo pipefail
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$(pg_config --bindir):$PATH"
cluster_dir=$(mktemp -d "${TMPDIR:-/tmp}/loja-bootstrap-pg.XXXXXX")
mkdir -p "$cluster_dir/socket"
cleanup() {
    if [[ -f "$cluster_dir/data/postmaster.pid" ]]; then
        pg_ctl -D "$cluster_dir/data" -m fast -w stop >/dev/null
    fi
    rm -rf -- "$cluster_dir"
}
trap cleanup EXIT
port=$((57000 + ($$ % 1000)))
initdb -A trust --no-locale --encoding=UTF8 -D "$cluster_dir/data" >/dev/null
# Socket técnico trust del fixture; TCP de la aplicación realmente exige SCRAM.
printf 'host all all 127.0.0.1/32 scram-sha-256\n' > "$cluster_dir/hba"
cat "$cluster_dir/data/pg_hba.conf" >> "$cluster_dir/hba"
cp "$cluster_dir/hba" "$cluster_dir/data/pg_hba.conf"
# Verificar sigilo mesmo se o cluster registrar statements/erros por padrão.
printf "log_statement='all'\nlog_min_duration_statement=0\n" >> "$cluster_dir/data/postgresql.conf"
pg_ctl -D "$cluster_dir/data" -l "$cluster_dir/server.log" -o "-F -k $cluster_dir/socket -p $port -c listen_addresses='127.0.0.1'" -w start >/dev/null
export PGHOST="$cluster_dir/socket" PGPORT="$port" PGDATABASE=postgres PGUSER="$(id -un)" LOJA_TEST_DB=1 LOJA_BOOTSTRAP_TCP=1 LOJA_BOOTSTRAP_LOG="$cluster_dir/server.log"
if sudo -n -u postgres -- /usr/bin/true 2>/dev/null; then
    # Únicamente el directorio temporal de ESTE test; nunca la home/proyecto.
    chmod 711 "$cluster_dir"
    chmod 755 "$cluster_dir/socket"
    psql -X -v ON_ERROR_STOP=1 -c 'CREATE ROLE postgres LOGIN SUPERUSER' >/dev/null
    export LOJA_BOOTSTRAP_SUDO=1
fi
cd "$repo_dir"
"$repo_dir/.venv/bin/python" -m unittest discover -s tests -p test_bootstrap_local.py -v
