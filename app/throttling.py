"""Database-backed limits shared by workers. Only digests of throttle subjects are stored."""
import hashlib
import math
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .models import LoginThrottle
from .security import SECRET


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def bucket(db, kind, subject, moment):
    key = hashlib.sha256((SECRET + ':' + kind + ':' + subject).encode()).hexdigest()
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    db.execute(insert(LoginThrottle).values(key=key, attempts=0, window_started=moment)
               .on_conflict_do_nothing(index_elements=['key']))
    return db.scalar(select(LoginThrottle).where(LoginThrottle.key == key).with_for_update())


def deny(until, moment):
    seconds = max(1, math.ceil((utc(until) - moment).total_seconds()))
    raise HTTPException(429, 'Too many sign-in attempts; try again later', headers={'Retry-After':str(seconds)})


def check_login(db, address, username):
    moment = now()
    ip = bucket(db, 'ip', address, moment)
    if moment - utc(ip.window_started) >= timedelta(minutes=5):
        ip.attempts = 0
        ip.window_started = moment
    if ip.attempts >= 30:
        db.commit()
        deny(utc(ip.window_started) + timedelta(minutes=5), moment)
    ip.attempts += 1
    account = bucket(db, 'account', username, moment)
    if account.blocked_until and utc(account.blocked_until) > moment:
        until = account.blocked_until
        db.commit()
        deny(until, moment)
    if moment - utc(account.window_started) >= timedelta(minutes=15):
        account.attempts = 0
        account.blocked_until = None
        account.window_started = moment
    return account


def finish_login(db, account, succeeded):
    if succeeded:
        account.attempts = 0
        account.blocked_until = None
        account.window_started = now()
    else:
        account.attempts += 1
        if account.attempts >= 5:
            account.blocked_until = now() + timedelta(minutes=15)
