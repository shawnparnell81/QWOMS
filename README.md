# QWOMS — Quality Work Order Management System

**Phase 1 development foundation — not a deployed or production-approved company application.**

A browser-based Quality Work Order Management System for Quality, Engineering, Production, and Management across multiple sites. This is **not** a full QMS.

## What works in this starter

- Modern browser UI with employee initials as avatars, a dashboard, and role-aware navigation.
- Separate usernames/passwords (management creates accounts; no default passwords).
- Six distinct work order types with different subtype choices and job-specific fields: Validation/FAI, Inspection, Test, Repair, Parts Weighing, Photos.
- Automatic **work order** numbers; users, not the app, name saved documents/forms (completed form saving comes in a later phase).
- Assign work orders to employees and show assigned work on their dashboards.
- Multiple parts per work order and customer-specific part-number aliases for the same physical part.
- Excel `.xlsx` Part Master import with a preview, deduplication, conflict reporting, and blank fields retained; includes product families, UPC, drawing number, and revision.
- Import complete folders using the browser folder picker, retaining **exact** relative folder paths, filenames, and extensions. Existing conflicting files are never overwritten.
- Drawings can be mapped to the drawing number and revision recorded in Part Master Excel; revisions are **not** inferred from filenames. Work orders snapshot drawing numbers/revisions.
- Internal one-to-one messages for all authorized users. No email features.
- Automated API/integration tests using fictional parts.

## Important limitations

**Not built yet:** advanced Excel forms editing inside the app with exact Excel fidelity, automatic form rules, completed-form filing by type with user-entered filenames, projects, time/labor, pallet tracking, supplier chargebacks, production-ready object storage and migrations, approval flows, advanced audit trail, group chat, and cloud deployment. These remain requirements; see `docs/PRODUCT_REQUIREMENTS.md`.

The current file store uses local disk and SQLite is the default developer database; neither arrangement should be treated as the final cloud-hosting design. Security review, CSRF protection, origin policy, rate limiting, backups, SSO policy if needed, object storage, database migrations, permissions testing, and Excel compatibility testing are mandatory before using company data.

**Keep the GitHub repository PRIVATE before putting any real company part master, drawings, document templates, supplier information, or credentials into it.** This repository should contain source code, synthetic examples, and test fixtures only.

## Run in a development environment (including Codex Cloud)

```bash
python -m venv .venv
source .venv/bin/activate  # Use the cloud/Linux terminal; no work-PC install required
pip install -r requirements.txt
python -m alembic upgrade head  # New database; see Phase 2 operations for existing Phase 1 data
export QWOMS_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export QWOMS_COOKIE_SECURE=false # local HTTP development ONLY
python -m app.bootstrap manager --display-name "Quality Manager"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the port-8000 preview exposed by the cloud development environment. Sign in with the username/password created by the bootstrap command. You can create other employee accounts in User Administration. No real data is seeded.

On Windows PowerShell, environment variable syntax differs; use Codex Cloud instead of installing software on the work computer.

To run tests:

```bash
python -m pytest -q
```

For a PostgreSQL environment, set `DATABASE_URL=postgresql+psycopg://...`, use a persistent `QWOMS_SECRET_KEY`, and configure secure cookies and approved persistent document storage **before** evaluating deployment. Alembic now owns schema changes; startup refuses a stale database. See [Phase 2 operations](docs/PHASE2_OPERATIONS.md) for legacy database adoption, S3 configuration, and Docker Desktop instructions.

## Repository structure

- `app/main.py`: API endpoints, assignment, drawing folder import, work orders, messaging.
- `app/models.py`: initial relational data model.
- `app/imports.py`: spreadsheet import with duplicate/conflict review.
- `app/security.py`: password hashes, authenticated sessions, role checking.
- `app/static/`: modern UI (HTML/CSS/JavaScript) with no required browser installation.
- `app/bootstrap.py`: interactive first admin account creation (no default password).
- `tests/`: integration tests using fabricated records.
- `AGENTS.md`: persistent instructions to Codex for future development.
- `docs/PRODUCT_REQUIREMENTS.md`: accepted requirements and development phases.

## Next milestone for Codex

Add database migrations, robust authentication/security review, durable PostgreSQL-backed cloud storage, and a controlled **form template registry** before implementing browser-based Excel workbook editing. Do not replace workbook formulas or formatting with a basic HTML form; exact workbook preservation must be proven on representative real examples.
