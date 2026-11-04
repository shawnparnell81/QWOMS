import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'qwoms.db'}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
def make_engine(url, **kwargs):
    if str(url).startswith("sqlite"):
        kwargs.setdefault("connect_args", {"check_same_thread": False})
    result = create_engine(url, pool_pre_ping=True, **kwargs)
    if result.dialect.name == "sqlite":
        # sqlite3 legacy mode otherwise commits a released SAVEPOINT outside an
        # actual outer transaction, separating imported data from its audit.
        @event.listens_for(result, "connect")
        def transaction_control(connection, _):
            connection.isolation_level = None
        @event.listens_for(result, "begin")
        def begin(connection):
            connection.exec_driver_sql("BEGIN")
    return result


engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass

def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
