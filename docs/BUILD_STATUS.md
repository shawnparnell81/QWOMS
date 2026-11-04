# QWOMS implementation status

Updated: 2026-11-04. This is the development record, not a certification.

## Baseline

- Phase 1 starter exists on `main`: FastAPI, initial SQLite dev database, separate username/password login, dashboards/assignments, six differentiated order types, alias-based Part Master lookup, preview/commit Excel part import, drawing folder import and mapping, direct messaging.
- The **user reports** a Codex run installed dependencies, started the app on port 8000 and passed **4 automated tests**. No test log was committed as evidence; rerun tests on the current build branch.
- Codex's prior environment did not expose a working browser preview. Browser acceptance **not yet performed**.
- The prototype does not implement production-grade cloud persistence, migrations, in-browser Excel fidelity, form rules, projects, pallets, labor, chargebacks, exports or complete photo/messaging workflows.
- No real company data or credentials have been used for development.

## Workflow

- Current long-lived branch: `development/qwoms-complete-build`.
- **Single PR at completion**, with explicit user approval. Normal commits on this branch are permitted; do not open milestone PRs.
- After each milestone, append a dated record describing files changed, tests run and exact results, known failures, constraints and next step. Do not mark as complete without runnable proof.

## Acceptance gate status

| Gate | Status |
|---|---|
| Starter smoke/API tests | 20 passed on SQLite and PostgreSQL; see milestone records below |
| Dashboard/browser manual acceptance | Automated Chromium checks passed through stage 3; manual user acceptance still pending |
| Work-order/part/drawing workflows beyond starter | Partial |
| Controlled forms and exact Excel editing | Not built |
| Projects, labor, pallets, chargebacks | Project linking verified; labor/pallets/chargebacks not built |
| Production cloud storage, deployment and security review | Not built |
| Final PR | **Not opened** |

See `BUILD_PLAN.md` for detailed feature and test criteria.

## 2026-11-04 — Phase 1 verified review imported into build branch

- Codex completed external review on `fix/phase1-review` at commit `b015425` and reported `6 passed` plus successful Chromium browser workflow checks. This assistant did **not** independently rerun the tests.
- Reviewed and integrated the four changed files into `development/qwoms-complete-build`: `app/main.py`, `app/static/app.js`, `tests/test_foundation.py`, and `docs/PHASE1_REVIEW.md`.
- Fix: dashboard recent-list cap remains at 30; total assigned/open assignment counters query all assigned records. Additional regression tests verify >30 assignments and case-varied alias imports.
- No pull request opened. Future Codex tasks must select `development/qwoms-complete-build`, not `fix/phase1-review`.
- Phase 2 next: PostgreSQL migrations; durable, access-controlled storage; audit trail and security groundwork; role tests; then controlled form registry and automatic attachment rules. Excel WYSIWYG fidelity remains a separate verification milestone.

## 2026-11-04 — Phase 2 stage 1: migrations and storage foundations

- Working branch remains `development/qwoms-complete-build`; no PR created and no main commits.
- Added frozen Alembic Phase 1 baseline, explicit upgrades, checked legacy adoption, startup schema-version validation, and migration-aware account bootstrap. Verified adoption preserves synthetic records and rejects unknown schemas. Automatic startup `create_all` removed.
- Added a storage interface with exclusive-create local writes, conditional encrypted S3 writes, exact path/name preservation, authenticated checksum-verified downloads, and traversal checks. S3 contract tested with SDK stubs; no live cloud bucket or credentials configured. PostgreSQL and S3-compatible storage confirmed as target providers by user.
- Added non-root Docker image, Compose PostgreSQL/migration/app services, persistent database/document volumes, ignored generated local credentials, and `PHASE2_OPERATIONS.md` with Docker Desktop/optional pgAdmin instructions. Local Compose uses a persistent volume, not cloud S3.
- Tests: `.venv/bin/python -m pytest -q` **10 passed**; same suite with `QWOMS_TEST_DATABASE_URL` targeting isolated PostgreSQL 17 schemas **10 passed**. Covers upgrade/downgrade/re-upgrade on SQLite/PostgreSQL, repeated upgrades, legacy adoption, all original integrations, concurrent no-overwrite writes, and stubbed S3 contracts. Three non-failing FastAPI/TestClient deprecation warnings remain.
- Docker image built with TLS verification and session CA mounted as a temporary build secret. Compose migration service completed and app/database reported healthy. Chromium against Compose/PostgreSQL created/assigned all six work types, updated status, displayed aliases, drawing management and employees, and sent/rendered a message: passed without page/HTTP 5xx errors.
- Errors investigated: S3 test inherited a deliberately unavailable cloud profile (isolated only the stubbed test credentials); non-root migration container could not read source configuration permissions (fixed COPY ownership). Both affected checks rerun successfully.
- Remaining: live S3/provider validation, IAM/backup/retention/recovery, database/object reconciliation after interrupted writes, production TLS/deployment and security approval. No production readiness claim. Next stage: revocable sessions, CSRF, role-bound audit access and work-order assignment history. Projects, controlled drawing/work-instruction revisions, configurable fields and form registry remain pending; later accepted phases and exact Excel fidelity are unchanged.

## 2026-11-04 — Phase 2 stage 2: sessions, department permissions and histories

- Added Alembic revision 0002 for revocable sessions (hashed identifiers/CSRF tokens), audit events and assignment history. Old cookies require reauthentication. Logout revokes copied tokens server-side; authenticated mutations enforce session-bound CSRF tokens and cross-origin write checks. Trimmed identities/titles are validated before persistence.
- Initial department boundaries enforced and tested: Management-only account creation/audit access; Quality/Engineering/Management order and import management; Production can change only its own assigned order status and cannot reassign. Existing drawing mapping remains Engineering/Management; all active authorized roles retain internal messaging and shared read access. Full site/record isolation and admin account-management UI remain pending.
- New assignment events record creation, real reassignment and unassignment; repeated saves do not invent events. PostgreSQL row locking serializes order updates. UI displays history with employee avatars and a Management audit view while retaining existing professional layouts and all six work types. Earlier history is explicitly not fabricated.
- Part Master data and audit records now share a transaction; SQLite transaction control fixed so releasing a savepoint cannot commit data early. Injected audit failure verifies import rollback.
- Tests: full SQLite suite **18 passed**, full PostgreSQL suite **18 passed**; additional PostgreSQL migration/schema-parity check **2 passed** after adding ORM-drift comparison. JavaScript syntax checks passed. Three non-failing pre-existing FastAPI/TestClient deprecation warnings remain.
- Compose rebuilt/upgraded the existing synthetic PostgreSQL database and passed health checks. Committed repeatable Chromium smoke test (`tests/browser`) created/assigned all six types, saved status, rendered assignment/audit history, searched aliases, and sent/rendered messaging: passed with no page/HTTP 5xx errors. Exact drawing filename/bytes, authoritative mapped revision A despite filename Z, and work-order counts survived app/database container restart. This proves local volume persistence, not disaster recovery or live S3 durability.
- Test harness error: initial persistence script reused an already-open httpx client context; corrected the helper and reran successfully. No application workaround required.
- Remaining security work includes throttling, password lifecycle, active-account admin UI, comprehensive event coverage, session cleanup, tamper-evident audit retention and independent review. Remaining Phase 2 includes controlled drawing/work-instruction approvals, projects, configurable fields, and controlled template rules. Exact Excel editing still awaits editor licensing and representative-workbook compatibility evidence; later accepted workstreams remain pending. No PR opened.

## 2026-11-04 — Phase 2 stage 3: projects linking independent work orders

- Added Alembic revision 0003: employee-named projects and nullable indexed project links on work orders. No automatic project/document naming. Existing orders survive upgrades with unchanged fields and null project links.
- Added project creation/list/detail APIs and browser screens, linked-order totals/open totals, project selection during order creation, and audited link/unlink in order detail. Every linked work order retains its own number, type, status, assignee and part/drawing revision snapshots. Department permissions cover project creation/linking; Production remains read-only for projects.
- Tests: full `.venv/bin/python -m pytest -q` **20 passed** on SQLite and the same suite **20 passed** on PostgreSQL 17 via isolated schemas. Includes migration/schema parity, downgrade/re-upgrade, preservation of pre-Phase-2 orders, project counts, creation/link/unlink, invalid links, blank-name rejection, audit and department boundaries. JavaScript syntax and `git diff --check` passed. Three previously recorded non-failing deprecation warnings remain.
- Compose rebuilt and migrated the populated synthetic PostgreSQL environment successfully; app/database healthy. Committed Chromium smoke check passed all six type-specific creation/assignment flows, status, Part Master, drawing screen, internal message send/render, employee/audit/assignment history, and project create/link/aggregate display. No page errors or server 5xx responses in the final run.
- Browser failures investigated: fetching project choices on every type selection could rerender and clear newly entered fields. Moved asynchronous project loading before the editable form, retaining cached options during type switches; reran all six browser flows successfully. Repeat-run message assertion also needed a unique synthetic body to distinguish existing messages; test corrected and passed.
- Reviewed local Docker Desktop operations are in `docs/PHASE2_OPERATIONS.md`. Work is saved in the cloud workspace, not automatically downloaded to the user's work laptop. Personal-laptop execution remains synthetic-data development only; pgAdmin is optional.
- Phase 2 **not complete**: controlled drawing/work-instruction revision state/approval and immutable references; configurable family/part/type fields; versioned blank form registry and automatic attachments remain next. Security and durable cloud operations limitations from stages 1–2 also remain open. Project editing/status lifecycle, task/labor aggregates and chargebacks are not implemented by this project-link milestone.
- Later plan remains pending: exact-fidelity specialized workbook editor, copy-on-use/completed files with employee filenames, labor/pallets/forklift exclusion, photography, group messaging and reports. No Excel editor/license selected or representative original workbook round-trip evidence available; no fidelity or licensing completion claimed. No PR opened; explicit user approval remains required.

## 2026-11-04 — Accelerated P0: private synthetic demo deployment preparation

- Read and fast-forwarded the existing development branch to the launch decision (`c586c93`). User authorized the existing Render workspace with **free services only**; workspace name/API access still missing. No external resources, charges, company uploads or PRs were created.
- Added fail-closed demo configuration, Secure cookies/HTTPS origin validation, private optional HTTP Basic demo gate (separate from individual employee sessions), HSTS/frame protections, disabled demo API docs, explicit synthetic-only banner, configurable service port, schema/database/storage readiness and build identification. Generated secrets are not in Git.
- Added database-backed per-IP and per-account login throttling shared across workers: 30 requests/5 minutes per observed IP and account lock after 5 failures/15 minutes. Tests cover recovery and attempts across unknown usernames. Trusted proxy configuration still requires provider-specific validation; absent it, a shared ingress IP is limited conservatively.
- Added migrations 0004–0005 and a demo-only database byte store. PostgreSQL file bytes and metadata commit together; injected audit failure rolls both back. Original names/bytes and duplicate refusal are preserved. This avoids ephemeral local uploads on free Render web services; S3 remains the operational architecture, not silently replaced for a pilot.
- Added `render.yaml` (free web + free PostgreSQL only, no paid disk/job, public database access disabled), pinned Python constraints, migration/fictional bootstrap startup, independent generated passwords for four fictional employees, and private deployment/reset/rollback instructions in `DEMO_DEPLOYMENT.md`. Blueprint provider-schema acceptance and deployment remain unverified without Render access. No fallback to a paid tier is permitted.
- Added separate Caddy/private-network Compose deployment preparation plus loopback-only HTTPS/Render-runtime test overrides. A real TLS certificate was trusted locally for testing, with certificate/hostname verification enabled; no insecure browser/TLS bypass. HTTPS browser checks passed both the volume-backed and fresh Render-equivalent database-backed/private-gate stacks: six work-order types, assignment/status, Part Master aliases, drawings navigation, employee/audit/history, project link/count and messaging. Readiness, Secure cookies, origin denial and disabled docs also passed over TLS.
- Tests: full SQLite suite **28 passed** and full PostgreSQL 17 suite **28 passed**; existing migration/schema-parity/regression tests included. `pip check`, JavaScript syntax, Compose parsing and free-only Blueprint guard tests pass. Three prior non-failing deprecation warnings remain. This is local preparation evidence, not a hosted URL.
- Errors resolved: internal Caddy backend requests inherited the outbound proxy and were denied; added internal-only NO_PROXY names while preserving external proxy use. Initial Python HTTPS probe sent IP SNI while Caddy expected the hostname; corrected the test's SNI, with certificate verification retained. No weakened security workaround.
- Credentials/blockers: inspected actual binding metadata and variable names—no Render identity/key exists. Saved a user-provided `RENDER_API_KEY` requirement for `api.render.com` in the environment draft; successful save does not supply the key, apply policy or deploy. Requires secure value entry plus configuration review/save/publish. Workspace name remains requested. Session tools provide no hosted preview/port forwarding. No anonymous tunnel was created.
- Readiness: **not live; not an operational pilot**. A temporary synthetic demo can be evaluated after actual free Blueprint acceptance, authenticated hosted browser/security checks, URL/commit handoff, persistence/expiry confirmation, and reset/rollback review. Pilot blockers include backup/recovery, full security/account lifecycle, durable S3, permissions isolation, controlled revisions/forms, exact Excel fidelity and IT approval. P1 work remains authorized and continues separately.
