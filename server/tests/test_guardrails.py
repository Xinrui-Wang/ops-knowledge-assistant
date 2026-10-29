import pytest

from app.sql.guardrails import UnsafeSQL, clean_llm_sql, validate_sql


def test_allows_select_and_appends_limit():
    sql = validate_sql("SELECT * FROM fact_sales")
    assert sql.startswith("SELECT")
    assert sql.endswith("LIMIT 200")


def test_keeps_existing_limit():
    sql = validate_sql("SELECT * FROM fact_sales LIMIT 5")
    assert sql.count("LIMIT") == 1


def test_rejects_mutation_keywords():
    for sql in (
        "DELETE FROM fact_sales",
        "UPDATE fact_sales SET amount = 0",
        "DROP TABLE fact_sales",
        "PRAGMA writable_schema = ON",
    ):
        with pytest.raises(UnsafeSQL):
            validate_sql(sql)


def test_rejects_multiple_statements():
    with pytest.raises(UnsafeSQL):
        validate_sql("SELECT 1; SELECT 2")


def test_strips_markdown_fence():
    raw = "```sql\nSELECT 1\n```"
    assert clean_llm_sql(raw) == "SELECT 1"


def test_with_clause_is_allowed():
    sql = validate_sql("WITH t AS (SELECT 1 AS a) SELECT a FROM t")
    assert sql.startswith("WITH")
