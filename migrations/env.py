"""Migrations use DATABASE_URL; credentials are never saved in alembic.ini."""
from alembic import context
from sqlalchemy import create_engine
from app.db import Base, DATABASE_URL, make_engine
from app import models  # register all models

config = context.config
target_metadata = Base.metadata


def migrate(connection):
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True, transactional_ddl=True, render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        # sqlite3 legacy transaction mode does not BEGIN for DDL. Explicitly
        # start it so a refused reconciliation rolls back schema AND data.
        if connection.dialect.name=='sqlite' and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        config.attributes['qwoms_source_revisions']=list(context.get_context().get_current_heads())
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = config.attributes.get("connection")
    if connection is not None:
        migrate(connection)
    else:
        engine = make_engine(DATABASE_URL)
        with engine.connect() as connection:
            migrate(connection)
        engine.dispose()
