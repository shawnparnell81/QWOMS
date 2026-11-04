#!/bin/sh
set -eu
python -m app.deployment
if [ "${QWOMS_RUN_MIGRATIONS:-false}" = "true" ]; then
    python -m alembic upgrade head
fi
if [ "${QWOMS_SEED_SYNTHETIC:-false}" = "true" ]; then
    python -m app.demo_bootstrap
fi
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips "${QWOMS_TRUSTED_PROXIES:-127.0.0.1}"
