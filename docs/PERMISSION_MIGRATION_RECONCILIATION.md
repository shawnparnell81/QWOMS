# Permission regression results and safe schema reconciliation

This change is development-only. No Render deployment, environment change, live migration, company data, paid license, PR or main merge is authorized or performed.

## The five previously failed checks

The original synchronized hosted report for commit `55c7b3e` recorded 141 passes and these five failures. They concerned missing granularity, rather than an observed authorization bypass:

| Original failed requirement | Old result | New development result |
|---|---:|---|
| `import.work_instructions` independently assignable |422|PASS|
| `import.supporting_documents` independently assignable |422|PASS|
| `import.other` independently assignable |422|PASS|
| Folder category `work-instruction` supported |400|PASS|
| Folder category `other` supported |400|PASS|

Each exact case now passes on isolated SQLite and PostgreSQL, plus actual Chromium Administrator permission controls. Before a grant:403. Explicit individual grant:200; authorized upload:200; unrelated import:403. Revocation completes before testing: prior session401 and reauthenticated import403. The synthetic browser employee is cleared of permissions and deactivated at completion; imported synthetic originals/audits remain. Other employees are untouched. These checks target the newest local development code, **not an undeployed version at the live Render URL**.

The existing five Administrator/permission tests also pass in the full suite: department defaults, grant/revoke/audit/last Administrator, one-time owner claim, concurrent last-Administrator protection and explicit Engineering approval separation.

## Why migration `0013` is necessary

Both histories used the same revision labels with different meanings:

| Layout |0008|0009|
|---|---|---|
| Historical hosted branch |`users.permissions`, independent `is_admin`, `system_authority` marker|one-time password flag|
| Canonical development branch |`users.capabilities`, independent `is_admin`|labor/pallet/forklift/chargeback tables|

Revision labels alone could therefore appear current while required columns or operations tables were missing. The new forward migration `0013`, after0012, reconciles the known historical layout. There is no operator stamping workaround and no rewrite of an already applied migration file.

Explicit legacy grant mapping:

| Existing grant | Preserved canonical authority |
|---|---|
|`import.parts`|`import.part_master`|
|`import.drawings`|`import.drawings`|
|`import.documents`|`import.work_instructions` **and** `import.supporting_documents`|
|`import.templates`|`import.form_masters`|
|`revision.approve`|`engineering.approve`|

A legacy documents grant already covered both document kinds. Splitting that existing right preserves its authority; it is not assigned to ungranted employees. It does not add Other imports. Empty lists stay empty. Existing canonical grant names are preserved. No department, title or Administrator promotion is inferred. Administrator IDs/flags, active state, username, password hash, initial-password flag and existing sessions remain intact. New requests read current grants from the database; no token embeds an old grant list.

For legacy 0008, the normal canonical0009 step creates operations. For legacy 0009, migration `0013` detects their complete absence and executes the fixed historical operations migration. Partially present operations tables, simultaneous old/new permission columns, unknown grant strings or an inconsistent authority layout stop the transaction without committed changes. The same one-time-password flag is preserved where already present.

The original permission arrays, exact mapping, Administrator flags before/after and all authority-marker rows are retained in the new system `schema_reconciliations` ledger before the obsolete marker table is removed. No human actor is impersonated and no service account is created. Existing application audit events remain unchanged. Administrators can read the ledger at `/api/admin/migration-history` and in **User Administration → Database migration history**. Other employees receive403. Fresh canonical databases have no invented legacy event.

The readiness/startup check now checks layout and required tables as well as revision IDs. Stamping a legacy database to0013 cannot make it pass readiness. SQLite migrations explicitly retain transactional DDL; PostgreSQL takes an exclusive lock on legacy account/authority tables during conversion.

## What was actually tested

- Full suite: **106 passed SQLite; 106 passed PostgreSQL 17**, three existing deprecation warnings each. PostgreSQL uses disposable random schemas in the existing local synthetic test database.
- Exact five historical permission cases: **5/5 API tests per backend and 5/5 Chromium workflows**. Full suites include the other five Administrator regression tests.
- Four legacy upgrade profiles:0008/0009 × local-original/database-BLOB storage. Preserved all original rows/fields, IDs, hashes/passwords, sessions, aliases, orders, controlled pins, workflow/filing rules, completed workbook records and bytes. Reopened completed workbook still calculates/displays cached PASS. Model/schema parity passes after conversion.
- Backup/restore rehearsal: synthetic logical schema/data restore, including PostgreSQL sequences, reproduces the entire pre-upgrade snapshot; re-upgrade works. This is not certification of Render/provider backup facilities.
- Negative migration cases: unknown grant, partial operations schema, both permission columns, and a simulated ledger outage after conversion/DDL. Schema, revision and rows roll back to their exact originals on both backends.
- Canonical upgrade: existing labor, raw equipment PDF, work-order data and workbook draft survive unchanged. No legacy grants are fabricated.
- Actual Alembic CLI on separate synthetic SQLite clones:0008 and0009 upgrade successfully; unknown-grant refusal leaves the complete old state unchanged.
- Free Excel browser regression: **46 assertions pass** across shock, pump, injector and a novel uploaded form. Independent checks on edited/reopened exports again show **zero measured feature differences**, unchanged masters/PDF bytes and only value/cache worksheet XML changed. No free-editor source file was modified by this task.

Safe results are under `docs/evidence/permission-reconciliation/`. Raw database backups, workbooks, PDFs, credentials and detailed private logs remain ignored under `work/` or disposable test directories.

## Operator sequence — restored isolated clone only

Do not apply this sequence to the live Render service during this task.

1. Record the exact source application artifact and migration revision. Back up database contents, schema, sequences and migration-version table, plus the corresponding original-file storage. Verify restoration to a separate isolated environment. Database-backed originals are part of the DB backup; local/S3 originals need the matching storage backup/version set.
2. Stop writers and prevent mixed old/new application versions during the migration/rollback acceptance window. Keep the original application artifact and verified backup available. Never paste connection strings or credentials into chat, commands or logs; select the clone through approved secure environment bindings.
3. With `DATABASE_URL` bound to that isolated clone, inspect metadata without exposing row values:

   ```sh
   python -m app.schema inspect
   python -m alembic current
   ```

   Confirm the source layout/revision and backup. Ambiguous/custom layouts require manual review. Never stamp over a discrepancy.
4. Execute the forward migration on the clone:

   ```sh
   python -m alembic upgrade head
   python -m app.schema inspect
   ```

   Expected: revision `0013`, canonical permission layout, complete operations and initial-password field, reconciliation ledger present. A failure must leave the old version/schema/data intact; investigate before retrying.
5. Verify original account IDs and active Administrator count, grant mapping, ledger, audit history, user/password-setup flows, direct grant/deny/revoke cases, historical documents/completed XLSX/PDF downloads and original hashes. Run the free workbook workflow and all applicable regression/security tests against the clone. Confirm persistence and recoverability with the actual proposed hosting/storage configuration.
6. Rehearse rollback while writers remain stopped: restore the verified pre-upgrade database **and matching originals**, then run the exact original application artifact. Confirm original rows/grants/sessions/files and schema version. **After legacy conversion, `alembic downgrade` is deliberately refused**: new granular grants and newly recorded operations cannot safely be collapsed into the old schema. A restore discards post-backup writes; do not allow operational writes during a rollback acceptance window.
7. Only a separately authorized deployment may change the live service. No deploy was performed here. Render auto-deploy must remain off; source commits use `[skip render]` as an additional guard.

## Testing the updated development app now

The private synthetic preview is running at port 8020 on the updated schema. Open that port through the attached environment, or pull the development branch in the configured devcontainer/Codespace and run:

```sh
PYTHONPATH=. python scripts/run_free_preview.py
```

Open the **private** forwarded port 8020, then work order2. If an older preview already owns the port, stop it cleanly before starting the updated version. Private review credentials are in ignored `work/excel-editor/reviewer.credentials`; never share their values. The launcher selects only isolated synthetic storage, not an inherited live database. No office server or paid editor is needed. The actual Codespaces forwarded-host route remains unverified here; the local browser workflow is verified.

No permission or migration regression is still failing in this tested scope. Remaining gates are representative/native Excel visual and print compatibility, unsupported formula families/rendering limits already documented in `FREE_WORKBOOK_EDITOR.md`, real hosting backup/restore/security acceptance, and an authorized live deployment. The current Render application remains unchanged and therefore does not yet show these updates.
