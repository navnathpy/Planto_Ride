"""Run the same booking, payment and Captain suite against either database."""
import os
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql
import app as service


@pytest.fixture(autouse=True)
def isolated_storage(monkeypatch):
    url = os.getenv('TEST_POSTGRES_URL','')
    monkeypatch.setattr(service,'DATABASE_URL',url)
    monkeypatch.delenv('RENDER',raising=False)
    if not url:
        yield
        return
    schema='planto_test_'+uuid4().hex
    monkeypatch.setattr(service,'DATABASE_SCHEMA',schema)
    try:
        yield
    finally:
        with psycopg.connect(url,autocommit=True) as c:
            c.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
