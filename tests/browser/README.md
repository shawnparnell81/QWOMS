# Synthetic browser smoke check

Run against an isolated synthetic review database. This test **creates six work orders and a message**, so never use it against real company data. Fixture prerequisites: a Management account; employee `Sam Sample` at `Fictional Site`; physical part aliases `DEMO-001` and `DEMO-ALT-001` under O'Reilly/NAPA. Provision these via the UI or an approved test fixture. Credentials remain outside Git.

```sh
npm ci --prefix tests/browser
npx --prefix tests/browser playwright install chromium
QWOMS_TEST_CREDENTIAL_FILE=/path/to/ignored/manager-credentials.txt node tests/browser/smoke.cjs
```

Credential file format: username on first line, password on second. Restrict local file access. Optional environment variables: `QWOMS_TEST_BASE_URL` (default local port 8000), `QWOMS_CHROMIUM_PATH` (use existing Chromium), `QWOMS_SCREENSHOT_PATH`. The test checks all six type-specific creation screens, assignment/status, revision display, assignment history, alias search, drawing management navigation, internal messaging, employee administration and management audit display. API tests separately validate drawing bytes/revisions, role denials, and CSRF/session security. It does not prove workbook fidelity or production browser acceptance.
