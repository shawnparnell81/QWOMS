from sqlalchemy import create_engine, inspect, text
from alembic import command
from app.schema import upgrade, require_current, configuration, adopt_phase1
import pytest
from tests.db_helpers import test_engine as isolated_test_engine
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.db import Base


def test_upgrade_downgrade_and_repeat(tmp_path):
    with isolated_test_engine(tmp_path) as engine:
        with pytest.raises(RuntimeError, match='migration required'):
            require_current(engine)
        upgrade(engine)
        upgrade(engine)
        require_current(engine)
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        assert 'work_order_parts' in inspect(engine).get_table_names()
        config = configuration()
        with engine.begin() as connection:
            config.attributes['connection'] = connection
            command.downgrade(config, 'base')
        assert inspect(engine).get_table_names() == ['alembic_version']
        upgrade(engine)
        require_current(engine)


def test_adopt_baseline_preserves_data_and_rejects_unknown_schema(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "legacy.db"}')
    upgrade(engine, '0001')
    with engine.begin() as connection:
        connection.execute(text('DROP TABLE alembic_version'))
        connection.execute(text("INSERT INTO product_families (name) VALUES ('Fictional family')"))
    adopt_phase1(engine)
    upgrade(engine)
    require_current(engine)
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT name FROM product_families')) == 'Fictional family'
    broken = create_engine('sqlite://')
    with pytest.raises(RuntimeError, match='does not match'):
        adopt_phase1(broken)
    broken.dispose()
    engine.dispose()


def test_upgrade_preserves_existing_orders(tmp_path):
    from datetime import datetime, timezone
    from sqlalchemy import MetaData, select
    from app.models import WorkOrder
    from sqlalchemy.orm import Session
    with isolated_test_engine(tmp_path) as engine:
        upgrade(engine, '0001')
        old = MetaData()
        old.reflect(bind=engine)
        with engine.begin() as connection:
            user_id = connection.execute(old.tables['users'].insert().values(
                username='fictional', display_name='Fictional User', role='Quality',
                site='Test Site', password_hash='fictional-not-a-login', active=True)).inserted_primary_key[0]
            connection.execute(old.tables['work_orders'].insert().values(
                number='INS-FICTIONAL-LEGACY', order_type='Inspection', subtype='AQL',
                title='Fictional legacy order', status='Open', priority='Normal', notes='',
                details={'sampling_plan':'Fictional sample'}, assigned_to=user_id, created_by=user_id,
                created_at=datetime.now(timezone.utc)))
        upgrade(engine)
        with Session(engine) as db:
            order = db.scalar(select(WorkOrder))
            assert order.number == 'INS-FICTIONAL-LEGACY'
            assert order.assigned_to == user_id
            assert order.project_id is None
            assert order.details == {'sampling_plan':'Fictional sample'}
