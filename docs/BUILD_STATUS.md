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
| Starter smoke/API tests | 4 passed as reported by user's prior Codex response; rerun needed |
| Dashboard/browser manual acceptance | Not run |
| Work-order/part/drawing workflows beyond starter | Partial |
| Controlled forms and exact Excel editing | Not built |
| Projects, labor, pallets, chargebacks | Not built |
| Production cloud storage, deployment and security review | Not built |
| Final PR | **Not opened** |

See `BUILD_PLAN.md` for detailed feature and test criteria.

## 2026-11-04 — Phase 1 verified review imported into build branch

- Codex completed external review on `fix/phase1-review` at commit `b015425` and reported `6 passed` plus successful Chromium browser workflow checks. This assistant did **not** independently rerun the tests.
- Reviewed and integrated the four changed files into `development/qwoms-complete-build`: `app/main.py`, `app/static/app.js`, `tests/test_foundation.py`, and `docs/PHASE1_REVIEW.md`.
- Fix: dashboard recent-list cap remains at 30; total assigned/open assignment counters query all assigned records. Additional regression tests verify >30 assignments and case-varied alias imports.
- No pull request opened. Future Codex tasks must select `development/qwoms-complete-build`, not `fix/phase1-review`.
- Phase 2 next: PostgreSQL migrations; durable, access-controlled storage; audit trail and security groundwork; role tests; then controlled form registry and automatic attachment rules. Excel WYSIWYG fidelity remains a separate verification milestone.
