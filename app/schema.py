"""Explicit schema management. Starting the application never changes its schema."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory


def configuration():
    return Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))


def upgrade(engine, revision="head"):
    config = configuration()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def require_current(engine):
    expected = set(ScriptDirectory.from_config(configuration()).get_heads())
    with engine.connect() as connection:
        current = set(MigrationContext.configure(connection).get_current_heads())
    if current != expected:
        raise RuntimeError("Database migration required. Back up data and run: python -m alembic upgrade head. "
                           "For an unversioned Phase 1 database, follow docs/PHASE2_OPERATIONS.md first.")


def adopt_phase1(engine):
    """Stamp only a structurally matching, unversioned starter DB; never create/drop its data."""
    from sqlalchemy import create_engine, MetaData
    from alembic.autogenerate import compare_metadata
    baseline = create_engine('sqlite://')
    try:
        upgrade(baseline, '0001')
        metadata = MetaData()
        metadata.reflect(bind=baseline, only=lambda name, _: name != 'alembic_version')
        config = configuration()
        with engine.begin() as connection:
            if MigrationContext.configure(connection).get_current_heads():
                raise RuntimeError('Database already versioned; use alembic upgrade head')
            differences = compare_metadata(MigrationContext.configure(connection), metadata)
            if differences:
                raise RuntimeError('Database does not match the Phase 1 baseline; manual review required')
            config.attributes['connection'] = connection
            command.stamp(config, '0001')
    finally:
        baseline.dispose()


if __name__ == '__main__':
    import argparse
    from .db import engine
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['adopt-phase1'])
    parser.parse_args()
    adopt_phase1(engine)
    print('Verified Phase 1 baseline adopted; run python -m alembic upgrade head next.')
