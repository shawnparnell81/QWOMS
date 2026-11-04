from sqlalchemy import create_engine, inspect, text
from alembic import command
from app.schema import upgrade, require_current, configuration, adopt_phase1
import pytest
from tests.db_helpers import test_engine as isolated_test_engine


def test_upgrade_downgrade_and_repeat(tmp_path):
    with isolated_test_engine(tmp_path) as engine:
        with pytest.raises(RuntimeError, match='migration required'):
            require_current(engine)
        upgrade(engine)
        upgrade(engine)
        require_current(engine)
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
