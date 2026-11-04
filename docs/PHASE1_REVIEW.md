# Phase 1 development review

This review uses fictional records only and preserves the existing professional interface, employee avatars, six work-order workflows, document filenames, and requirements. Advanced Excel editing has not started.

## Verified

- Python 3.12 virtual environment; all requirements installed; `python -m pip check` passes.
- Six pytest integration tests pass, including the four original tests.
- A real Chromium browser signs in, renders the dashboard, creates and assigns each of the six work-order types, saves status/assignment changes, looks up equivalent part numbers, opens drawing management and employee administration, and sends/renders an internal message. No page errors or HTTP 5xx responses occurred in these checks.
- Integration tests cover Excel Part Master preview/commit/idempotence/conflicts and blank values; original folder paths and filenames; drawing mappings and historical revision snapshots; overwrite prevention and path traversal rejection; account creation and internal messages.
- Uvicorn startup, health, HTML, JavaScript, CSS, and authenticated API requests succeed with local SQLite and local document storage.

## Fix

Dashboard totals previously counted only the latest 30 assignments. The API now counts all assignments and all open assignments for the current employee while retaining the bounded recent list. The dashboard uses the new total. Regression coverage includes more than 30 orders, completed/closed orders, and another employee's assignment. An additional import regression confirms case-variant aliases within one row remain idempotent.

## Database

SQLAlchemy models include users, product families, physical parts and aliases, stored file metadata, per-type/year work-order counters, work orders and part revision snapshots, direct messages, and import audits. SQLite and local files remain development storage. No schema changes were required for this fix.

## Review access

Run the README development instructions and use a supported host port-8000 preview if available. This cloud session exposes no preview/port-forwarding tool, so a shareable browser URL cannot be supplied. Headless browser validation is local and does not establish externally accessible preview support. Never expose the development server publicly with real company data.

## Still required

The README and PRODUCT_REQUIREMENTS remain authoritative: approved persistent cloud storage, PostgreSQL migrations, stronger access controls/auditing and security review, drawing revision approval workflows, richer part/family-specific work instructions and validation, projects/tasks/labor/pallets/reporting, controlled form rules, and later exact-fidelity Excel editing and completed-form filing under user-entered filenames. Part Master search/import works; direct editing of missing metadata is still a backlog item. Deprecation warnings for FastAPI startup events and the test client remain non-failing. Large-import scale and Excel round-trip fidelity were not validated by this review.
