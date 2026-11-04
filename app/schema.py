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

    # Revision numbers alone cannot distinguish the two historical 0008/0009
    # implementations. Fail closed even if an operator stamped the latest ID.
    from sqlalchemy import inspect
    from .db import Base
    from . import models
    inspector=inspect(engine)
    tables=set(inspector.get_table_names())
    columns={c['name'] for c in inspector.get_columns('users')} if 'users' in tables else set()
    if not set(Base.metadata.tables).issubset(tables) or 'permissions' in columns or 'system_authority' in tables or not {'capabilities','is_admin','must_change_password'}.issubset(columns):
        raise RuntimeError('Database schema history is incompatible; migration required. Do not stamp past reconciliation; restore/rehearse the backed-up clone first.')


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


def inspect_history(engine):
    """Read-only layout diagnosis; never output credentials, URLs or row values."""
    from sqlalchemy import inspect
    inspector=inspect(engine);tables=set(inspector.get_table_names())
    columns={c['name'] for c in inspector.get_columns('users')} if 'users' in tables else set()
    with engine.connect() as c:heads=list(MigrationContext.configure(c).get_current_heads())
    legacy='permissions' in columns and 'capabilities' not in columns and 'system_authority' in tables
    canonical='capabilities' in columns and 'permissions' not in columns and 'system_authority' not in tables
    return {'current_revisions':heads,'expected_revisions':ScriptDirectory.from_config(configuration()).get_heads(),
        'permission_layout':'legacy' if legacy else 'canonical' if canonical else 'ambiguous_or_uninitialized',
        'operations_complete':{'labor_entries','pallets','pallet_movements','forklift_entries','charge_items'}.issubset(tables),
        'initial_password_field_present':'must_change_password' in columns,'reconciliation_ledger_present':'schema_reconciliations' in tables}


if __name__ == '__main__':
    import argparse
    from .db import engine
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['adopt-phase1','inspect'])
    args=parser.parse_args()
    if args.action=='inspect':
        import json
        print(json.dumps(inspect_history(engine),indent=2))
    else:
        adopt_phase1(engine)
        print('Verified Phase 1 baseline adopted; run python -m alembic upgrade head next.')
