"""Generate ignored, local-only credentials without overwriting an existing setup."""
from pathlib import Path
import secrets

path = Path(__file__).resolve().parent.parent / '.env.docker'
with path.open('x') as output:
    path.chmod(0o600)
    output.write('QWOMS_DB_PASSWORD=' + secrets.token_hex(32) + '\n')
    output.write('QWOMS_SECRET_KEY=' + secrets.token_hex(48) + '\n')
print('Created .env.docker for synthetic local development; do not commit or share it.')
