# Phase 2 environment operations

Use synthetic data only. This is development infrastructure; no production deployment or IT approval is implied.

## Schema migrations

Install `requirements.txt`, activate `.venv`, then run `python -m alembic upgrade head` **before** bootstrap or startup. Startup checks the current migration version and refuses unversioned/stale databases. It never silently creates or alters application tables. `DATABASE_URL` supports SQLite for development and `postgresql+psycopg://…` for PostgreSQL. Never commit connection secrets.

For an existing unversioned Phase 1 database: stop the app, make and verify a backup, then run `python -m app.schema adopt-phase1`. This checks its schema against the frozen baseline and refuses unknown schemas. It stamps only the matching schema, preserving records. Then run `python -m alembic upgrade head`. Do not stamp an unfamiliar database manually. Downgrade commands are destructive; use only disposable test databases or a reviewed recovery plan.

Tests default to temporary SQLite databases. Set `QWOMS_TEST_DATABASE_URL` to a disposable PostgreSQL database to exercise the integration suite there. Tests create/drop random `qwoms_test_*` schemas, never reset the whole database. Use a test-only account permitted to create schemas.

## Personal laptop with Docker Desktop

Clone and check out `development/qwoms-complete-build`. With Docker Desktop running, from the repository directory:

```sh
python scripts/init_docker_env.py
docker compose --env-file .env.docker up --build -d
docker compose --env-file .env.docker exec app python -m app.bootstrap manager --display-name "Fictional Manager"
```

The bootstrap command securely prompts for a new password; there are no default account passwords. Open `http://localhost:8000` **on that laptop** and sign in. Create fictional employees and import only synthetic fixtures. Commands work in a normal terminal; Python may be invoked as `py` on Windows. Alternatively generate `.env.docker` with Python inside a temporary container before starting Compose. The Compose file binds application and database ports to loopback. PostgreSQL and documents persist in separate named volumes. `docker compose ... down` stops services without deleting volumes; do not use `down -v` unless intentionally deleting synthetic data.

pgAdmin 4 is optional. A desktop pgAdmin installation can connect to host `localhost`, port `5433`, database/user `qwoms`, using the generated database password from your local `.env.docker`. It is a database tool, not a required application dependency. Avoid editing application records directly.

## S3-compatible original storage

Set `QWOMS_STORAGE_BACKEND=s3`, `QWOMS_S3_BUCKET`, optional `QWOMS_S3_PREFIX` (unique per environment), optional HTTPS `QWOMS_S3_ENDPOINT_URL`, and the approved SDK credential/region configuration. TLS verification remains enabled. Never enter credentials in Git or chat. Local is the default backend; Compose currently uses a persistent local volume, not a cloud object service.

The S3 adapter sends conditional `If-None-Match: *` writes and AES256 server-side encryption requests. Your selected provider must support both; failures are not bypassed. All downloads pass through the authenticated application and verify the database SHA-256 digest. No public bucket links or object ACLs are created. Exact user-supplied relative paths and names are retained under `files/` (plus the configured namespace), not inferred drawing identities. Switching backends does not migrate existing objects: copy and verify original bytes, paths and hashes with a reviewed migration before changing a populated environment.

Required deployment policy remains external: private bucket, least-privilege prefix access, encryption/key policy, versioning/retention, backups, TLS PostgreSQL connections, availability and a demonstrated restore. The adapter is contract-tested with SDK stubs; live S3 interoperability, IAM, retention and recovery are unverified without an approved endpoint. Database and object writes are not a distributed transaction: an interrupted import can leave an unindexed object. Conditional writes refuse to overwrite it; reconciliation/recovery remains required. Local exclusive-create prevents competing overwrites but is not an object-store durability guarantee.

## Session and permission changes (migration 0002)

Migration 0002 adds hashed server-side session IDs, CSRF hashes, audit events and assignment events. Existing pre-0002 cookies require signing in again. Logout revokes the session server-side, including copied tokens. Authenticated API writes must include `X-QWOMS-CSRF` from the `qwoms_csrf` cookie; the browser client supplies it automatically. Cross-origin writes are rejected. If an approved reverse proxy presents a different browser origin, explicitly configure exact `QWOMS_ALLOWED_ORIGINS` values; do not use wildcards. Use secure cookies over production HTTPS.

Management may create accounts and read audit history; Quality/Engineering/Management may manage work orders and import parts/files. Production may view shared work records, use messaging, and change status only on its assigned orders; it may not reassign work. Drawing mapping remains Engineering/Management. These are initial department boundaries, not a completed site/record isolation policy.

Assignment history begins with migration 0002 and records actual new assignments/reassignments/unassignment; earlier history is not fabricated. Work-order detail shows it; Management administration shows the latest 100 audit events. Older audit events can be queried with `before_id` in `/api/admin/audit`. There are no audit edit/delete APIs, but database administrators can still modify records; external tamper-evident retention is not implemented. Audit events exclude passwords, tokens and message bodies. Account creation, login/logout, work-order creation/status/assignment, Part Master imports, file imports and drawing mapping are covered; comprehensive failed-access, download and message auditing remain outstanding.

Still required before real use: login throttling, password reset/change and credential rotation policy, account-management UI, session cleanup, independent permissions/security review, approved origin/TLS policy, and operational audit retention. This milestone is not a security certification.
