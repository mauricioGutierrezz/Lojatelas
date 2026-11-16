#!/usr/bin/env python3
"""Testes de concorrencia com sessoes psql reais.

Pressupoe schema.sql e phase0_functional.sql aplicados no banco indicado
pelas variaveis PGHOST, PGPORT, PGDATABASE e PGUSER.
"""

from __future__ import annotations

import os
import subprocess
import time


PSQL = os.environ.get("PSQL", "psql")


def run_sql(sql: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PSQL, "-X", "-v", "ON_ERROR_STOP=1", "-At"],
        input=sql,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
        timeout=15,
    )


def start_sql() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [PSQL, "-X", "-v", "ON_ERROR_STOP=1", "-At"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def collect(proc: subprocess.Popen[str]) -> tuple[int, str, str]:
    return_code = proc.wait(timeout=15)
    assert proc.stdout is not None
    assert proc.stderr is not None
    return return_code, proc.stdout.read(), proc.stderr.read()


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def scalar(sql: str) -> str:
    return run_sql(sql).stdout.strip()


def main() -> None:
    # Dois cortes concorrentes no mesmo lote: o segundo revalida o saldo.
    run_sql(
        "SET ROLE loja_operador; "
        "SELECT public.fn_iniciar_ticket(pg_catalog.gen_random_uuid(),2) FROM generate_series(1,2);"
    )
    session_a = start_sql()
    sql_a = """
        SET ROLE loja_operador;
        BEGIN;
        SELECT public.fn_adicionar_item_corte(
            6, 1, 20, 20,
            '[{"lote_id":4,"quantidade":20}]'::jsonb,
            2, pg_catalog.gen_random_uuid()
        );
        SELECT pg_catalog.pg_sleep(2);
        COMMIT;
    """
    session_a.stdin.write(sql_a)
    session_a.stdin.close()
    time.sleep(0.25)
    result_b = run_sql(
        "SET ROLE loja_operador; "
        "SELECT public.fn_adicionar_item_corte("
        "7, 1, 20, 20, '[{\"lote_id\":4,\"quantidade\":20}]'::jsonb, 2, pg_catalog.gen_random_uuid());",
        check=False,
    )
    code_a, out_a, err_a = collect(session_a)
    expect(code_a == 0, f"primeiro corte concorrente falhou: {err_a}")
    expect(result_b.returncode != 0, "segundo corte consumiu saldo inexistente")
    expect(scalar("SELECT quantidade_atual FROM public.estoque_lotes WHERE id=4;") == "10.000",
           "saldo concorrente do lote incorreto")
    expect(scalar("SELECT count(*) FROM public.itens_ticket WHERE ticket_id=7;") == "0",
           "corte concorrente falho deixou item parcial")

    # Inclusao de item e pagamento serializam pelo ticket. O pagamento espera
    # o corte confirmar e rejeita uma conferência anterior à inclusão do item.
    run_sql("SET ROLE loja_operador; SELECT public.fn_iniciar_ticket(pg_catalog.gen_random_uuid(),2);")
    session_a = start_sql()
    session_a.stdin.write("""
        SET ROLE loja_operador;
        BEGIN;
        SELECT public.fn_adicionar_item_corte(
            8, 1, 1, 1,
            '[{"lote_id":3,"quantidade":1}]'::jsonb,
            2, pg_catalog.gen_random_uuid()
        );
        SELECT pg_catalog.pg_sleep(2);
        COMMIT;
    """)
    session_a.stdin.close()
    time.sleep(0.25)
    result_b = run_sql(
        "SET ROLE loja_operador; "
        "SELECT * FROM public.fn_finalizar_venda(8, 2, public.fn_conferencia_ticket(8), 0);",
        check=False,
    )
    code_a, out_a, err_a = collect(session_a)
    expect(code_a == 0, f"corte na corrida com pagamento falhou: {err_a}")
    expect(result_b.returncode != 0, "pagamento aceitou conferencia desatualizada")
    expect(scalar("SELECT status FROM public.tickets WHERE id=8;") == "pendente",
           "ticket alterado foi pago silenciosamente")
    run_sql("SET ROLE loja_operador; SELECT * FROM public.fn_finalizar_venda(8, 2, public.fn_conferencia_ticket(8), 0);")
    expect(scalar("SELECT status FROM public.tickets WHERE id=8;") == "pago",
           "ticket nao terminou pago apos serializacao")

    # Dois pagamentos do mesmo ticket: exatamente um persiste.
    run_sql("""
        SET ROLE loja_operador;
        SELECT public.fn_iniciar_ticket(pg_catalog.gen_random_uuid(),2);
        SELECT public.fn_adicionar_item_corte(
            9, 1, 1, 1,
            '[{"lote_id":3,"quantidade":1}]'::jsonb,
            2, pg_catalog.gen_random_uuid()
        );
    """)
    session_a = start_sql()
    session_a.stdin.write("""
        SET ROLE loja_operador;
        BEGIN;
        SELECT * FROM public.fn_finalizar_venda(9, 2, public.fn_conferencia_ticket(9), 0);
        SELECT pg_catalog.pg_sleep(2);
        COMMIT;
    """)
    session_a.stdin.close()
    time.sleep(0.25)
    result_b = run_sql(
        "SET ROLE loja_operador; "
        "SELECT * FROM public.fn_finalizar_venda(9, 2, public.fn_conferencia_ticket(9), 0);",
        check=False,
    )
    code_a, out_a, err_a = collect(session_a)
    expect(code_a == 0, f"primeiro pagamento falhou: {err_a}")
    expect(result_b.returncode == 0, "reenvio concorrente identico nao retornou a venda existente")
    expect(scalar("SELECT count(*) FROM public.vendas WHERE ticket_id=9;") == "1",
           "cardinalidade de venda concorrente incorreta")

    # Confirmacao operacional concorrente: mesma chave retorna o mesmo ingresso.
    session_a = start_sql()
    session_a.stdin.write("""
        SET ROLE loja_operador;
        BEGIN;
        SELECT public.fn_confirmar_ingresso('00000000-0000-0000-0000-000000000002',
            '[{"produto_id":1,"rolos":1,"quantidade":1}]',2);
        SELECT pg_catalog.pg_sleep(2);
        COMMIT;
    """)
    session_a.stdin.close()
    time.sleep(0.25)
    result_b = run_sql(
        "SET ROLE loja_operador; SELECT public.fn_confirmar_ingresso("
        "'00000000-0000-0000-0000-000000000002',"
        "'[{\"produto_id\":1,\"rolos\":1,\"quantidade\":1}]',2);",
        check=False,
    )
    code_a, out_a, err_a = collect(session_a)
    expect(code_a == 0, f"primeira confirmacao falhou: {err_a}")
    expect(result_b.returncode == 0, "confirmacao concorrente identica nao foi idempotente")
    expect(scalar("SELECT count(*) FROM public.estoque_lotes WHERE item_ingresso_id=5;") == "1",
           "confirmacao concorrente nao criou exatamente um lote")

    approval_a = start_sql()
    approval_b = start_sql()
    approval_a.stdin.write("SET ROLE loja_operador; SELECT public.fn_confirmar_ingresso("
        "'00000000-0000-0000-0000-000000000003',"
        "'[{\"produto_id\":1,\"rolos\":1,\"quantidade\":1}]',2);")
    approval_b.stdin.write("SET ROLE loja_operador; SELECT public.fn_confirmar_ingresso("
        "'00000000-0000-0000-0000-000000000004',"
        "'[{\"produto_id\":1,\"rolos\":1,\"quantidade\":1}]',2);")
    approval_a.stdin.close()
    approval_b.stdin.close()
    code_a, out_a, err_a = collect(approval_a)
    code_b, out_b, err_b = collect(approval_b)
    expect(code_a == 0, f"confirmacao paralela A falhou: {err_a}")
    expect(code_b == 0, f"confirmacao paralela B falhou: {err_b}")
    expect(scalar("SELECT count(*) = count(DISTINCT codigo_interno) FROM public.estoque_lotes;") == "t",
           "codigos de lote colidiram sob concorrencia")
    expect(scalar("SELECT count(*) FROM public.vw_reconciliacao_estoque WHERE diferenca<>0;") == "0",
           "concorrencia deixou livro-razao divergente")

    print("phase0_concurrency: ok")


if __name__ == "__main__":
    main()
