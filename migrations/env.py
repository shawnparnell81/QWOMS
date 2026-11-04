"""Migrations use DATABASE_URL; credentials are never saved in alembic.ini."""
from alembic import context
from sqlalchemy import create_engine
from app.db import Base, DATABASE_URL, make_engine
from app import models  # register all models

config = context.config
target_metadata = Base.metadata


def migrate(connection):
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True, render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
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
