# QWOMS — Quality Work Order Management System

> **Working free Validation/FAI editor:** run `PYTHONPATH=. python scripts/run_free_preview.py` and open private port **8020**. No commercial editor or office server required. See `docs/FREE_WORKBOOK_EDITOR.md` for the tested workflow, exact compatibility limits and evidence. Original masters stay unchanged.

**Development in progress. A private synthetic Render demo is live; company production use is not approved.**

A browser-based Quality Work Order Management System for Quality, Engineering, Production, and Management across multiple sites. This is **not** a full QMS.

## What works in this starter

- Modern browser UI with employee initials as avatars, a dashboard, and role-aware navigation.
- Separate usernames/passwords (a separate Administrator creates accounts; no default passwords).
- Six distinct work order types with different subtype choices and job-specific fields: Validation/FAI, Inspection, Test, Repair, Parts Weighing, Photos.
- Automatic **work order** numbers; users, not the app, name completed uploads and saved documents. A real in-app workbook editor is implemented for configured local synthetic review; exact fidelity is not certified.
- Assign work orders to employees and show assigned work on their dashboards.
- Multiple parts per work order and customer-specific part-number aliases for the same physical part.
- Excel `.xlsx` Part Master import with a preview, deduplication, conflict reporting, and blank fields retained; includes product families, UPC, drawing number, and revision.
- Import complete folders using the browser folder picker, retaining **exact** relative folder paths, filenames, and extensions. Existing conflicting files are never overwritten.
- Drawings can be mapped to the drawing number and revision recorded in Part Master Excel; revisions are **not** inferred from filenames. Work orders snapshot drawing numbers/revisions.
- Internal one-to-one messages for all authorized users. No email features.
- Automated API/integration tests using fictional parts.

## Important limitations

**Phase 2 foundations:** Alembic migrations, local Docker/PostgreSQL setup, private S3 storage adapter, revocable sessions with CSRF protection, separate Administrator and explicit per-employee import capabilities, audit/assignment history, project links, controlled Engineering revision approvals, scoped work requirements and approved form attachments/completed-file storage are available. See [controlled workflows](docs/CONTROLLED_WORKFLOWS.md). See `docs/BUILD_STATUS.md` for exact evidence and limits.

**Not complete yet:** exact Excel fidelity/production editor acceptance, full task/labor and supplier report/export acceptance, production-approved storage/restore, comprehensive audit/security coverage, group chat and production deployment. Initial labor/timer, pallet movement and approved chargeback ledgers are available in Labor & pallets. These remain requirements; see `docs/PRODUCT_REQUIREMENTS.md`.

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
python -m app.bootstrap PERSONAL_USERNAME --display-name "Your name"
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

Follow `docs/BUILD_STATUS.md` and `docs/LAUNCH_ACCELERATION.md`. Resolve exact Excel editor licensing/fidelity, finish all remaining accepted workflows and security/storage/restore gates, and validate a hosted synthetic demo only in the authorized free Render workspace. A demo is not company-wide go-live. No PR until explicit user approval.

Personal Administrator bootstrap, import grants and safe migration prerequisites: [Administration](docs/ADMINISTRATION.md). The live Render demo runs an older commit; new development here has not been deployed.

Interactive workbook review: [Excel editor implementation and hands-on guide](docs/EXCEL_EDITOR_IMPLEMENTATION.md). Uses an independent approved-master working copy, real browser spreadsheet measurements/formulas, explicit filenames, saved-file reopening, XLSX export and printing. Measured fidelity differences require review; the live Render demo has not been changed.
