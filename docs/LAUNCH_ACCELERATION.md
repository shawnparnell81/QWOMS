# QWOMS — accelerated launch decision and release gates
Updated: 2026-11-04
Branch: `development/qwoms-complete-build`. No PR until user explicitly authorizes a single final PR.

## Objective and realistic scope

User requests the fastest safe go-live, potentially today. Do not assert production availability on this basis. Create a minimal **private, password-protected demo environment with entirely synthetic data** as soon as permitted; then build toward a restricted operational pilot and full rollout. An internet-accessible site alone is not proof of readiness.

### Lane A — hosted demo (synthetic data ONLY)

**Conditions for claiming demo live:**
1. Confirm written authorization for a hosting provider, account/workspace, possible charges, and required test-only data usage. Do not provision external services, upload user/company files, or share credentials before permission.
2. Cloud environment uses HTTPS and secure cookies, non-default secret, migrations, isolated test PostgreSQL and storage (demo persistence limits explicitly stated), restricted access, private administrative credentials and no public sign-up.
3. Validate service health and authenticated end-to-end browser flow for all six work order types, assignments, Part Master aliases, drawings, project linking and internal messages.
4. Complete basic unauthenticated access/role restriction tests, origin/CSRF tests and login brute-force protections at minimum; record remaining risks. No real company parts, drawings, supplier files or users.
5. Record actual URL, deploy commit, test evidence, data reset instructions and rollback path in a private handoff (no secrets in Git).
6. Explicit banner: "DEMO — SYNTHETIC DATA ONLY. NOT APPROVED FOR COMPANY OPERATIONS."

If these conditions cannot be met today, report blocker with next concrete step rather than claim launch.

### Lane B — limited employee pilot (company data)

Company/IT approves provider, data classification, acceptable retention/backup, access boundaries and credential policy. Implement minimum operational workflow required for pilot with proven transaction integrity, backups/restore, revision enforcement, correct document storage, real employee sign-in policies, logging/monitoring, and security testing. No pilot using real documents/records until these gates pass.

**Critical functional dependency:** If pilot users need to execute and complete Excel workbooks inside the app, do not launch them on a generic editable grid; demonstrate exact import/edit/export behavior on approved representative forms including formulas, formatting, conditional green/red fills, charts/images/print setup and validation. Until verified, label form editing unavailable and do not count it as delivered. Avoid a hidden fallback that loses fidelity.

### Lane C — full operational launch

Fulfill all accepted requirements in PRODUCT_REQUIREMENTS.md and BUILD_PLAN.md, including user-owned completed filenames, controlled form rules, audit/revision enforcement, time tracking, management-only forklift internal time entirely excluded from chargebacks, pallets, reporting and exports; comprehensive regression, stress/security and disaster recovery testing; company approval and onboarding.

## Build priorities in accelerated mode

P0: deployment path for synthetic-data demo; harden account/session, login throttling, secure configuration; integrate environment health and browser smoke tests.
P1: controlled drawing/work instruction revision approvals; manual part metadata editing; configurable family/part/type/subtype fields; blank form template registry and auto-attachment rules; distinct work order UIs.
P1-parallel: evaluate commercial/licensed Excel browser editing options with compatible actual workbooks; verify formula/format conditional behavior and licensing before integration. Avoid speculative fidelity claims.
P2: complete projects/tasks/labor/pallets/chargebacks/report exports, photo workflow, group chat, role/security coverage, storage durability and rollback. Reorder only to meet approved pilot scope.
P3: audited production release with a single final PR and approvals. Keep code on the same development branch. Test and commit each milestone; no per-feature PRs.

## Evidence required at every checkpoint

- `docs/BUILD_STATUS.md`: commit, tests executed and counts, browser steps, blocker, next action.
- Separate code functioning locally from cloud deployed URL and from company-approved production readiness.
- No emails, no training module, no customer data fields on orders, no generated completed document names, no automatic import renaming.
- Host provisioning may incur external charges and must not be silently performed. Render account access alone does not establish approval.
