"""Private original-file storage. Keys retain user-supplied paths; writes never replace."""
import os
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
import boto3
from botocore.exceptions import ClientError


class StorageConflict(Exception):
    pass


class OriginalStore(Protocol):
    def put_new(self, key: str, content: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...


def validate_key(key):
    if not key or key.startswith('/') or any(p in ('', '.', '..') for p in key.split('/')):
        raise ValueError('Unsafe storage key')
    if '\\' in key or ':' in key or any(ord(c) < 32 for c in key):
        raise ValueError('Unsafe storage key')
    return key


class LocalStore:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, key):
        path = self.root / validate_key(key)
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('Storage path escapes its root')
        return path

    def put_new(self, key, content):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation closes the exists()/write race between concurrent imports.
        try:
            with path.open('xb') as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
        except FileExistsError as exc:
            raise StorageConflict('Original file already exists; nothing overwritten') from exc

    def read(self, key):
        return self.path(key).read_bytes()

    def discard_new(self,key):
        self.path(key).unlink(missing_ok=True)


class S3Store:
    def __init__(self, bucket, prefix='', client=None):
        if not bucket:
            raise ValueError('QWOMS_S3_BUCKET is required for S3 storage')
        self.bucket = bucket
        self.prefix = (validate_key(prefix.strip('/')) + '/') if prefix.strip('/') else ''
        self.client = client if client is not None else boto3.client(
            's3', endpoint_url=os.getenv('QWOMS_S3_ENDPOINT_URL') or None)

    def put_new(self, key, content):
        try:
            self.client.put_object(Bucket=self.bucket, Key=self.prefix + validate_key(key),
                                   Body=content, IfNoneMatch='*', ServerSideEncryption='AES256')
        except ClientError as exc:
            if exc.response['Error']['Code'] in ('PreconditionFailed', 'ConditionalRequestConflict', '412', '409'):
                raise StorageConflict('Original object already exists or conflicts; nothing overwritten') from exc
            raise

    def discard_new(self,key):
        self.client.delete_object(Bucket=self.bucket,Key=self.prefix+validate_key(key))

    def read(self, key):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.prefix + validate_key(key))
        except ClientError as exc:
            if exc.response['Error']['Code'] in ('NoSuchKey', '404'):
                raise FileNotFoundError(key) from exc
            raise
        body = response['Body']
        try:
            return body.read()
        finally:
            body.close()


class DatabaseStore:
    """Temporary synthetic demos only: bytes commit atomically with their file metadata."""
    def __init__(self, db):
        self.db = db

    def put_new(self, key, content):
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        from .models import DemoOriginalBlob
        insert = pg_insert if self.db.bind.dialect.name == 'postgresql' else sqlite_insert
        result = self.db.execute(insert(DemoOriginalBlob).values(key=validate_key(key),content=content)
                                  .on_conflict_do_nothing(index_elements=['key']))
        if result.rowcount == 0:
            raise StorageConflict('Original file already exists; nothing overwritten')

    def read(self, key):
        from .models import DemoOriginalBlob
        blob = self.db.get(DemoOriginalBlob,validate_key(key))
        if not blob:
            raise FileNotFoundError(key)
        return blob.content


def original_store(root, db=None) -> OriginalStore:
    backend = os.getenv('QWOMS_STORAGE_BACKEND', 'local')
    if backend == 'local':
        return LocalStore(root)
    if backend == 'database':
        from .deployment import demo_mode
        if not demo_mode():
            raise ValueError('Database file backend is restricted to synthetic demo mode')
        return DatabaseStore(db)
    if backend == 's3':
        endpoint = os.getenv('QWOMS_S3_ENDPOINT_URL')
        if endpoint and urlsplit(endpoint).scheme != 'https':
            raise ValueError('S3 endpoints must use HTTPS')
        return S3Store(os.getenv('QWOMS_S3_BUCKET'), os.getenv('QWOMS_S3_PREFIX', ''))
    raise ValueError('Unknown QWOMS_STORAGE_BACKEND')
