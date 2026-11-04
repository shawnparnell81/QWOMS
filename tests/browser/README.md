# Synthetic browser smoke check

Run against an isolated synthetic review database. This test **creates six work orders and a message**, so never use it against real company data. Fixture prerequisites: a Management account; employee `Sam Sample` at `Fictional Site`; physical part aliases `DEMO-001` and `DEMO-ALT-001` under O'Reilly/NAPA. Provision these via the UI or an approved test fixture. Credentials remain outside Git.

```sh
npm ci --prefix tests/browser
npx --prefix tests/browser playwright install chromium
QWOMS_TEST_CREDENTIAL_FILE=/path/to/ignored/manager-credentials.txt node tests/browser/smoke.cjs
```

Credential file format: username on first line, password on second. Restrict local file access. Optional environment variables: `QWOMS_TEST_BASE_URL` (default local port 8000), `QWOMS_CHROMIUM_PATH` (use existing Chromium), `QWOMS_SCREENSHOT_PATH`. The test checks all six type-specific creation screens, assignment/status, revision display, assignment history, alias search, drawing management navigation, internal messaging, employee administration, management audit display, and project create/link/aggregate display. API tests separately validate drawing bytes/revisions, role denials, and CSRF/session security. It does not prove workbook fidelity or production browser acceptance.

For the private Render demo gate, set `QWOMS_TEST_GATE_CREDENTIAL_FILE` to another ignored private file containing the gate username (`demo`) and generated gate password on separate lines. This is independent of the employee credential file. Use the actual HTTPS URL in `QWOMS_TEST_BASE_URL`. Never enable `ignoreHTTPSErrors` or put passwords in command arguments, screenshots, or Git. The seeded demonstration part intentionally has blank drawing metadata; controlled drawing upload/approval is an additional workflow to verify, not inferred from a filename.

Additional browser checks:

- `controlled.cjs`: set `QWOMS_TEST_ENGINEERING_CREDENTIAL_FILE` for the independently authenticated Engineering reviewer; verifies actual original import/registration/submission/review/approval screens.
- `forms.cjs`: also set `QWOMS_TEST_MASTER_WORKBOOK_FILE` and `QWOMS_TEST_COMPLETED_WORKBOOK_FILE` to representative synthetic `.xlsx` files. Tests the blank master/rule/field/attachment/completed filename/duplicate/immutability/completion flow. It retires only prior synthetic rules named `Fictional part-specific shock validation ...` before creating its own, preserving existing order snapshots. Never point this fixture at company records.
- Error output filters authentication-cookie/header lines. API download validation uses browser fetch so localhost name resolution and TLS trust stay in the browser. Test sessions are still disposable; revoke them after a diagnostic exposure. No TLS verification bypass is enabled.

## Managed hosted acceptance (synthetic demo only)

The secure runtime bindings `QWOMS_DEMO_GATE_PASSWORD`, `QWOMS_BOOTSTRAP_PASSWORD`, `QWOMS_DEMO_QUALITY_PASSWORD`, `QWOMS_DEMO_ENGINEERING_PASSWORD` and `QWOMS_DEMO_PRODUCTION_PASSWORD` can replace private credential files. Usernames are fixed to the documented `demo.*` accounts and HTTP Basic `demo`. Do not print values or export them in shell commands. The launcher preserves the configured HTTP proxy for hosted URLs and keeps TLS verification enabled. Do not enable Playwright trace/video/network-body logging on credential workflows.

Generate fictional fixtures with `.venv/bin/python -m tests.browser.synthetic_fixtures /tmp/qwoms-hosted-fixtures`. Set `QWOMS_TEST_BASE_URL` to the actual authorized synthetic deployment and `QWOMS_CHROMIUM_PATH` if needed. Run suites sequentially where they share rule fixtures:

- `smoke.cjs`: six types, assignments, aliases, project linking and messages. Waits for the save-detail refresh before navigating, including on older deployed builds.
- `permissions.cjs`: four independent employee logins, current audit permissions, unauthenticated access and CSRF denial. Optional `QWOMS_TEST_EVIDENCE_FILE` writes only named checks/status codes. Passing this suite does not establish every new owner/import authorization gate.
- `controlled.cjs`: independent work-instruction approval.
- `forms.cjs`: set `QWOMS_TEST_MASTER_WORKBOOK_FILE` and `QWOMS_TEST_COMPLETED_WORKBOOK_FILE` to the two generated XLSX paths. Registry, approval, correct attachment, filing/duplicates and master hash. This does not exercise an in-app Excel editor.
- `drawings.cjs`: set `QWOMS_TEST_DRAWING_FIXTURE_FILE` to the generated JSON path. Drawing approvals, missing/superseded blocking, historical pins and mapping immutability. Generates unique fictional parts/documents; leaves auditable synthetic evidence.
- `accounts.cjs`: **requires the newer account/owner-permission UI**; creates a synthetic disabled employee, verifies zero initial grants, explicit grant/revoke, role/access changes and password reset. Use an isolated local service until its source commit is confirmed deployed.

These tests create persistent synthetic records and are not a production-data test plan. The forms suite retires matching prior synthetic test rules only; it never changes historical order snapshots. Screenshots must be taken after login, never while password fields are filled. `credentials.cjs` and `safe-error.cjs` redact loaded or generated credential values and authentication headers on errors.
