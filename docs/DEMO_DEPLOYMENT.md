# Private synthetic demo deployment — Render free tier

Authorization recorded in chat on 2026-11-04: existing Render workspace, **free services only**. The user identified the workspace as `my workspace`; API authentication/owner-ID discovery is still required before agent provisioning. These files do not establish a live hosted URL. No company operations or real data are approved. Follow `LAUNCH_ACCELERATION.md`.

## Prepared deployment

`render.yaml` defines one free Docker web service and one free PostgreSQL 17 database. It does not request a paid disk, worker, pre-deploy job, or paid plan. All generated secrets stay in Render's environment settings. The private database has no external IP allowlist entries. Application connections require TLS. Startup validates demo settings, applies Alembic migrations, idempotently creates fictional accounts and a part/alias fixture, then starts Uvicorn on Render's `PORT`. No blank work orders are pre-created. Do not change a plan to get past a free-tier quota error.

Free web filesystems are ephemeral. `QWOMS_STORAGE_BACKEND=database` therefore stores synthetic original file bytes in PostgreSQL in the **same transaction** as their metadata; restart cannot leave metadata pointing at an evaporated local upload. This backend is restricted to demo mode. It is not the final S3 architecture. Keep fixtures small (prefer under 1 MB), monitor the database quota, and expect total loss when the free database expires or is removed. Confirm current expiry, storage, idle spin-down, build and free-service quotas in the Render dashboard before provisioning. No availability or backup guarantee is claimed.

## Exact deployment steps after workspace access is available

1. Select the authorized existing Render workspace. Connect its GitHub integration to the **private** `shawnparnell81/QWOMS` repository if access is not already granted. Do not send GitHub/Render keys in chat.
2. Create a Blueprint from that repository, selecting branch `development/qwoms-complete-build` and `render.yaml`. Confirm both resources explicitly show **Free** and no billable add-ons/disks. If Render rejects a free plan, existing free-database quota, PostgreSQL version, or a schema field, stop and report it; do not choose a paid alternative. Remote Blueprint acceptance remains unverified until access is supplied.
3. Keep auto-deploy off. Deploy the tested commit recorded in `BUILD_STATUS.md`; record the actual Render deployment commit and assigned HTTPS URL privately. Render supplies `RENDER_EXTERNAL_URL`; the application uses it as its exact allowed browser origin. `QWOMS_SECRET_KEY` and the demo gate/account passwords are generated independently in service environment settings. Do not reuse development secrets.
4. Wait for database availability, migration/bootstrap success, and `/readyz` HTTP 200. Inspect application logs for errors without copying environment dumps. `/healthz` is liveness; `/readyz` checks the schema/database and storage. API docs are disabled in demo mode.
5. Retrieve the generated `QWOMS_DEMO_GATE_PASSWORD` privately from environment settings. The first HTTPS browser prompt uses username `demo` and that gate password. Then sign into the application using `demo.manager` and `QWOMS_BOOTSTRAP_PASSWORD`. Other fictional accounts are `demo.quality`, `demo.engineer`, `demo.production`, each with its own generated password variable. No password appears in Git or logs. Bootstrap never silently rotates existing passwords; changing an environment password after account creation does not reset an existing account.
6. Verify the exact banner: **DEMO — SYNTHETIC DATA ONLY. NOT APPROVED FOR COMPANY OPERATIONS.** Check Secure/HttpOnly/SameSite cookies, unauthenticated API/file denial, department restrictions, CSRF/origin rejection, and login throttling. Requests through the gate still require each employee's account/session. Do not bypass TLS errors or disable certificate verification.
7. Run the committed Chromium test against the actual HTTPS URL with private local credential files (see `tests/browser/README.md`), then review each role manually. It creates actual synthetic orders of all six types, assignments/status changes, Part Master alias checks, drawing navigation, project links and messages. Run `controlled.cjs` and `forms.cjs` for the new approval/template workflows, then perform a drawing import/approval check with authoritative synthetic Part Master metadata. A screenshot or a green health check alone is insufficient.
8. Record URL, workspace, resource IDs, deploy commit, exact test results, reset/rollback choices and persistence limits in a **private** handoff. Keep credentials out of the handoff stored in Git. Only after these checks can this be called a live temporary synthetic demo.

## Access and provisioning blockers

No Render tool/CLI identity is connected in this session. A personal `RENDER_API_KEY` requirement for destination `api.render.com` has been saved to the cloud environment draft; entering a value in environment settings and publishing that configuration is separate from deploying QWOMS. The supplied workspace name is `my workspace`; its exact owner ID will be resolved after authentication to avoid provisioning into a different account. Do not paste the key into chat. Manual Blueprint deployment in the authorized workspace can avoid agent API access, but must follow the same free-only checks. There is no built-in cloud preview/port-forwarding tool in this session. No anonymous tunnel is created.

## Reset and rollback

This is disposable synthetic data. Before resetting, confirm the exact **demo** web/database resource IDs; never touch another database. With the owner’s deletion approval, remove only this demo database and recreate the same free Blueprint database, then redeploy to rerun migrations and fictional bootstrap. Generated passwords may change when environment resources are recreated. Existing free-tier quotas/expiry can block recreation; do not purchase replacements without authorization.

For code-only changes with unchanged schema, redeploy the previously tested commit through Render. For schema changes, do not blindly downgrade or deploy code whose expected schema differs: it will correctly fail readiness. Restore a verified test database backup together with the matching application commit, or reset the disposable demo and deploy that commit. Automated backup/restore and a validated schema rollback on hosted Render are not complete; this blocks an operational pilot. Never use destructive migrations to force a green health check.

## Local verification without external provisioning

`deploy/compose.demo.yaml` is a separate private VM/container deployment option with Caddy HTTPS, explicit viewer CIDRs, and persistent demo volumes. It is **not** a Render Blueprint and should not be run on an external host without separate authorization. The committed `deploy/compose.https-test.yaml` override replaces public ports with loopback `8443` and uses an explicitly generated local certificate, without ACME/public provisioning. Locally trusted TLS tests are preparation evidence, not a live public preview. The local Compose route uses volume-backed files; the Render route uses database bytes.

## Pilot blockers

Temporary demo preparation does not complete controlled revision/form workflows, exact workbook editing, secure cloud S3/backup recovery, account/password lifecycle, monitoring, comprehensive permissions/isolation/audit retention, scale/concurrency testing or IT approval. Free database/file storage is not an operational design. Workbook editing remains unavailable until licensing and representative import/edit/export fidelity tests pass; no generic grid fallback is supplied.

## Environment contract and release check

| Setting | Required demo value/source |
|---|---|
| `DATABASE_URL` | Private Blueprint database connection string; never place it in Git |
| `QWOMS_DATABASE_REQUIRE_TLS` | `true` on Render; connection fails rather than fall back to plaintext |
| `QWOMS_DEMO_MODE`, `QWOMS_SYNTHETIC_DATA_ONLY` | `true` |
| `QWOMS_COOKIE_SECURE` | `true` |
| `QWOMS_SECRET_KEY` | Independent random secret, at least 48 characters; startup rejects defaults/test placeholders. Confirm generated length privately before launch |
| `QWOMS_PUBLIC_URL` | Optional exact HTTPS origin; otherwise Render-injected `RENDER_EXTERNAL_URL` |
| `QWOMS_STORAGE_BACKEND` | `database` for the free-tier synthetic demo; never ephemeral `local` |
| `QWOMS_DEMO_ACCESS_MODE` | `basic` on Render |
| `QWOMS_DEMO_GATE_PASSWORD` | Independent generated random secret, at least 32 characters |
| `QWOMS_BOOTSTRAP_PASSWORD`, `QWOMS_DEMO_QUALITY_PASSWORD`, `QWOMS_DEMO_ENGINEERING_PASSWORD`, `QWOMS_DEMO_PRODUCTION_PASSWORD` | Independent generated secrets for fictional accounts, 16–128 characters |
| `QWOMS_RUN_MIGRATIONS`, `QWOMS_SEED_SYNTHETIC` | `true`; one instance/worker and serial deployments for this demo |
| `QWOMS_TRUSTED_PROXIES` | Loopback by default; only change to verified provider ingress addresses after checking spoof rejection, never blindly use `*` |
| `PORT` | Supplied by Render; startup uses it |

`/healthz` reports an image build commit when supplied or Render's injected `RENDER_GIT_COMMIT`. Record that exact commit with the live URL. This metadata does not replace authenticated acceptance tests. Run all SQLite/PostgreSQL regressions and the smoke/control/forms browser checks before claiming a deployment ready. Free-tier quota/expiry, remote Blueprint schema acceptance, provider DB TLS, role/browser tests at the actual assigned URL, and backup/reset behavior remain provider-side checks, not established by local tests.
