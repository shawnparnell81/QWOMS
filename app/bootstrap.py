"""First-run management account creation. No default credentials are provided."""
import argparse
import getpass
from .db import Base, engine, SessionLocal
from .models import User
from .security import hash_password


def main():
    parser = argparse.ArgumentParser(description="Create the initial management account")
    parser.add_argument("username")
    parser.add_argument("--display-name", default="System Manager")
    args = parser.parse_args()
    password = getpass.getpass("New password (12+ characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(User).filter_by(username=args.username).first():
            raise SystemExit("Username already exists")
        db.add(User(username=args.username, display_name=args.display_name, role="Management", password_hash=hash_password(password)))
        db.commit()
        print("Management account created")

if __name__ == "__main__":
    main()
