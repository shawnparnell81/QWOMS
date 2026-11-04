"""Fail-closed synthetic demo settings; this module does not provision services."""
import os
import base64
import hmac
from urllib.parse import urlsplit


def demo_mode():
    return os.getenv('QWOMS_DEMO_MODE', 'false').casefold() == 'true'


def public_origin():
    return (os.getenv('QWOMS_PUBLIC_URL') or os.getenv('RENDER_EXTERNAL_URL', '')).rstrip('/')


def demo_gate_ok(request):
    if not demo_mode() or os.getenv('QWOMS_DEMO_ACCESS_MODE','network') != 'basic':
        return True
    if request.url.path in ('/healthz','/readyz'):
        return True
    try:
        scheme, encoded = request.headers.get('authorization','').split(' ',1)
        username, password = base64.b64decode(encoded,validate=True).decode().split(':',1)
        return scheme.casefold()=='basic' and hmac.compare_digest(username.encode(),b'demo') and hmac.compare_digest(password.encode(),os.getenv('QWOMS_DEMO_GATE_PASSWORD','').encode())
    except (ValueError,UnicodeError):
        return False


def validate_settings(database_url):
    if not demo_mode():
        return
    from .security import SECRET
    if len(SECRET) < 48 or SECRET.startswith(('REPLACE_', 'development-test-')):
        raise RuntimeError('Demo requires a non-default random QWOMS_SECRET_KEY of at least 48 characters')
    if os.getenv('QWOMS_COOKIE_SECURE', '').casefold() != 'true':
        raise RuntimeError('Demo requires QWOMS_COOKIE_SECURE=true')
    origin = urlsplit(public_origin())
    if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.path or origin.query or origin.fragment:
        raise RuntimeError('Demo requires QWOMS_PUBLIC_URL as an exact HTTPS origin without a path')
    if not database_url.startswith('postgresql+psycopg://'):
        raise RuntimeError('Demo requires isolated PostgreSQL')
    if os.getenv('RENDER_EXTERNAL_URL') and os.getenv('QWOMS_DATABASE_REQUIRE_TLS','').casefold()!='true':
        raise RuntimeError('Hosted Render demo requires QWOMS_DATABASE_REQUIRE_TLS=true')
    if os.getenv('QWOMS_SYNTHETIC_DATA_ONLY', '').casefold() != 'true':
        raise RuntimeError('Demo requires explicit QWOMS_SYNTHETIC_DATA_ONLY=true acknowledgement')
    if '*' in os.getenv('QWOMS_ALLOWED_ORIGINS', ''):
        raise RuntimeError('Wildcard origins are not permitted')
    access = os.getenv('QWOMS_DEMO_ACCESS_MODE','network')
    if access not in ('network','basic'):
        raise RuntimeError('Choose network or basic private demo access')
    if access == 'basic' and len(os.getenv('QWOMS_DEMO_GATE_PASSWORD','')) < 32:
        raise RuntimeError('Private demo gate password must be random and at least 32 characters')
    if os.getenv('QWOMS_STORAGE_BACKEND', 'local') == 'local':
        root = os.getenv('QWOMS_STORAGE_ROOT', '')
        if not root.startswith('/'):
            raise RuntimeError('Demo requires an absolute persistent QWOMS_STORAGE_ROOT mount')


if __name__=='__main__':
    from .db import DATABASE_URL
    validate_settings(DATABASE_URL)
