"""Each PostgreSQL test owns a random schema; never reset a supplied database."""
import os
from contextlib import contextmanager
from uuid import uuid4
from sqlalchemy import create_engine, text


@contextmanager
def test_engine(tmp_path):
    url = os.getenv('QWOMS_TEST_DATABASE_URL')
    admin = None
    if url:
        if not url.startswith('postgresql+psycopg://'):
            raise ValueError('QWOMS_TEST_DATABASE_URL must use postgresql+psycopg')
        admin = create_engine(url)
        schema = 'qwoms_test_' + uuid4().hex
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={'options': '-csearch_path=' + schema})
    else:
        engine = create_engine(f'sqlite:///{tmp_path / "test.db"}',
                               connect_args={'check_same_thread': False})
    try:
        yield engine
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
