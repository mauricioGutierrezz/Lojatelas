#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if command -v pg_config >/dev/null 2>&1; then
    export PATH="$(pg_config --bindir):$PATH"
fi

for command_name in initdb pg_ctl createdb psql python3; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "Dependencia ausente: $command_name" >&2
        exit 2
    fi
done

cluster_dir=$(mktemp -d "${TMPDIR:-/tmp}/loja-phase0-pg.XXXXXX")
socket_dir="$cluster_dir/socket"
data_dir="$cluster_dir/data"
mkdir -p "$socket_dir"
port=$((55432 + ($$ % 1000)))

cleanup() {
    if [[ -f "$data_dir/postmaster.pid" ]]; then
        pg_ctl -D "$data_dir" -m fast -w stop >/dev/null
    fi
    rm -rf -- "$cluster_dir"
}
trap cleanup EXIT

initdb -A trust --no-locale --encoding=UTF8 -D "$data_dir" >/dev/null
pg_ctl -D "$data_dir" -l "$cluster_dir/server.log" -o "-F -k $socket_dir -p $port -c listen_addresses=''" -w start >/dev/null || {
    cat "$cluster_dir/server.log" >&2
    exit 1
}

export PGHOST="$socket_dir"
export PGPORT="$port"
export PGDATABASE="loja_unidades_descartavel_test"
export PGUSER="$(id -un)"

createdb "$PGDATABASE"
psql -X -v ON_ERROR_STOP=1 -c "SELECT current_database(),version();"
echo "Destino descartável: $PGDATABASE · porta $PGPORT · socket $PGHOST"
psql -X -v ON_ERROR_STOP=1 -f "$repo_dir/schema.sql"
psql -X -v ON_ERROR_STOP=1 -f "$repo_dir/tests/sql/phase0_functional.sql"
python3 "$repo_dir/tests/phase0_concurrency.py"
export LOJA_TEST_DB=1
cd "$repo_dir"
if [[ -x "$repo_dir/.venv/bin/python" ]]; then
    "$repo_dir/.venv/bin/python" -m unittest discover -s tests -p 'test_*.py' -v
else
    python3 -m unittest discover -s tests -p 'test_*.py' -v
fi
psql -X -v ON_ERROR_STOP=1 -f "$repo_dir/tests/sql/phase0_closing.sql"

echo "phase0_postgres: ok"
