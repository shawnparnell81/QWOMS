"""Private one-time owner bootstrap. No default credentials or department promotion."""
import argparse
import getpass
from sqlalchemy import select
from .db import engine,SessionLocal
from .models import User
from .security import hash_password,verify_password,authority_lock
from .schema import require_current
from .audit import record
from .deployment import demo_mode


def claim(db,username,password,display_name,existing=False):
    if demo_mode():raise ValueError('Use the isolated demo bootstrap in demo mode')
    state=authority_lock(db)
    if state.initialized or db.scalar(select(User.id).where(User.is_admin.is_(True))):
        raise ValueError('Owner bootstrap already claimed; use an authorized Administrator')
    user=db.scalar(select(User).where(User.username==username))
    if existing:
        if not user or not user.active or not verify_password(password,user.password_hash):
            raise ValueError('Existing personal account verification failed')
    else:
        if db.scalar(select(User.id).limit(1)):
            raise ValueError('Existing users require explicit --claim-existing and personal password verification')
        if len(password)<12 or len(password)>128:raise ValueError('Use a unique 12–128 character password')
        user=User(username=username,display_name=display_name,role='Management',password_hash=hash_password(password))
        db.add(user);db.flush()
    user.is_admin=True;state.initialized=True
    record(db,user,'administrator.initial_claim','user',user.id,{'existing_personal_account':existing})
    db.flush();return user


def main():
    parser=argparse.ArgumentParser(description='Claim the sole initial personal Administrator account')
    parser.add_argument('username');parser.add_argument('--display-name',required=True);parser.add_argument('--claim-existing',action='store_true')
    args=parser.parse_args()
    if not 3<=len(args.username.strip())<=80 or not 2<=len(args.display_name.strip())<=120:raise SystemExit('Invalid personal identity')
    password=getpass.getpass('Personal password (never printed): ')
    if not args.claim_existing and password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match')
    require_current(engine)
    with SessionLocal() as db:
        try:claim(db,args.username.strip(),password,args.display_name.strip(),args.claim_existing)
        except ValueError as exc:raise SystemExit(str(exc))
        db.commit()
    print('Personal Administrator claimed. No employee accounts were created.')

if __name__=='__main__':main()
