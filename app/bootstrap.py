"""First-run personal Administrator account creation. No default credentials are provided."""
import argparse
import getpass
from .db import Base, engine, SessionLocal
from .models import User
from .security import hash_password
from .audit import record
from sqlalchemy import select
from .schema import require_current


def main():
    parser = argparse.ArgumentParser(description="Create the initial personal Administrator account")
    parser.add_argument("username")
    parser.add_argument("--display-name", default="System Manager")
    args = parser.parse_args()
    password = getpass.getpass("New password (12+ characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    require_current(engine)
    with SessionLocal() as db:
        # Serialize first-claim attempts, including legacy installations.
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy import text
            db.execute(text("LOCK TABLE users IN EXCLUSIVE MODE"))
        else:
            from sqlalchemy import text
            db.execute(text("UPDATE users SET id=id WHERE 1=0"))
        if db.scalar(select(User.id).where(User.is_admin.is_(True))):
            raise SystemExit("Administrator already claimed; use Administration")
        if db.query(User).filter_by(username=args.username).first():
            raise SystemExit("Username already exists")
        owner=User(username=args.username, display_name=args.display_name, role="Management", is_admin=True, password_hash=hash_password(password))
        db.add(owner); db.flush()
        record(db,owner,"administrator.claimed","user",owner.id)
        db.commit()
        print("Administrator account claimed")

if __name__ == "__main__":
    main()
