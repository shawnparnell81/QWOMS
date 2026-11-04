# QWOMS — full build and acceptance plan

**Branch:** `development/qwoms-complete-build`
**PR policy:** Code + tests are developed through small commits on this single branch; open **one** final pull request to `main` only after the user authorizes it and the acceptance gates are satisfied.

This plan complements the approved domain requirements in `PRODUCT_REQUIREMENTS.md`. A module is **not complete** simply because an API endpoint or mock UI exists. It must function from the browser, persist data correctly, respect permissions, and pass relevant tests.

## Mandatory launch gate: owner is sole initial system Administrator

Production starts with exactly **one** named, owner-controlled Administrator account (secure initial bootstrap, no shared or default credentials). The owner independently imports all initial Part Master spreadsheets, folder trees, drawings, instructions, document masters/forms and sets up every employee's role/site/permissions. Production must not seed synthetic demo accounts or allow public signup.

Implement a system admin privilege distinct from department roles; by default Quality, Engineering, Production and Management accounts cannot manage users or import/commit master records and files. Admin may explicitly delegate/revoke narrowly scoped import/user-management privileges and add another administrator later. Engineering revision approval stays a separately assignable duty. Provide admin portal, audit, session revocation, secure password/account lifecycle, last-active-admin protection and per-endpoint enforcement.

Acceptance: production first-start has only owner/admin; user creation and role/permission assignment flow works; non-admin attempts to access account creation and all imports are denied; approved delegated privilege works then immediately stops when revoked; last admin cannot be deactivated/demoted; demo-only accounts never appear in production; security and browser tests pass. The current prototype's Management-as-admin logic and department-scoped import endpoints **must be changed before company go-live**.

## Completion gates by workstream

| Area | Accepted behavior to implement and test |
|---|---|
| 1. Accounts & dashboard | Username/password accounts, Quality/Engineering/Production/Management roles, permission boundaries, active/inactive users, site, employee avatars, assigned tasks/work orders, reassignments, due-date and priority display, logged actions |
| 2. Work orders | Exactly six top-level types, correct inspection subtypes, distinct part/type-specific workflows/fields, one/multiple parts, auto work-order numbering only, user-selected part alias, statuses, ownership, assignment history, attachments, no customer fields |
| 3. Part Master | Families, physical parts, alias groups (O'Reilly/NAPA etc.), lookup by any alias, draw/UPC blanks remain nullable/editable, bulk Excel 3,000+ rows with configurable column mapping, preview/dedup/conflict controls, idempotence and audit |
| 4. Drawings & documents | Folder import preserves byte-for-byte contents plus exact paths/filenames, no silent overwrite, authoritative revision from Excel, manual match/reconciliation, controlled revision record, current/obsolete state and approvals, immutable work-order revision snapshot, work instruction revision control |
| 5. Forms | Versioned blank master templates, family/part/type/subtype automatic form selection, no unused blank work orders, separate working copy at execution, manually supplied completed filenames (validation, development, inspection etc. folders), duplicate name rejection, linked work order and project |
| 6. Exact Excel editor | User fills native-style Excel workbook *inside browser*; preserve sheets, formulas, conditional formatting (PASS green/FAIL red), styles, merged cells, images, data validation, print setup, and downloadable round-trip files; test with representative original workbooks. Don't claim success when fidelity not proven |
| 7. Projects & labor | Parent project links multiple work orders, user-specific time entry/timers, assignment/task history, elapsed time distinct from person-hours, rebox/paperwork/repair time, approvals and adjustments, replaced parts and cost |
| 8. Pallets & material handling | Pallet IDs, quantities, locations, inspection/repair/disposition/reboxing and return confirmation; management-only forklift actual/estimated time; no forklift-driver accounts |
| 9. Chargebacks & exports | Project-wide supplier chargeback includes only approved recoverable items and evidence; **all forklift records entirely excluded**; Word/Excel/PDF report/packet generation and file export with manual filenames where documents are saved |
| 10. Messaging & photos | Direct and group cross-site messaging for authorized users, avatars, work-order-linked conversations and attachments; Ortery 360/catalog photo workflow and image hand-off |
| 11. Cloud and security | PostgreSQL migrations, approved cloud object storage with durable original files, per-role authorization, CSRF/session protections, secure cookies, uploads validation, import rollback, audit logs, backups/restores, access isolation, staging deployment and IT approval |

## Required test evidence

- Automated: schema/migration tests, API unit+integration tests, browser UI/end-to-end tests, permission/security negative tests, import/reimport/duplicate tests, concurrency/idempotence tests, report math and forklift exclusion tests.
- Excel: round-trip open/edit/export tests compare formulas, formatting, conditional rules, named ranges, widths/heights, validation, drawing links, images, print settings and Excel rendering/calculation behavior on **representative genuine forms** after company approval. Record any Excel feature incompatible with the chosen spreadsheet editor.
- Scale: sample synthetic 3,000+ row import, large nested folder import, data rollback after failures, concurrent work-order numbering and assignments.
- Manual browser acceptance: sign in as each role; complete an order of each type; search aliases; view drawing revision; complete Excel form and reopen; send cross-site message; generate project report.
- Security and launch: secrets never in Git, approved storage, backup restore demonstrated, data retention agreed, performance acceptable, risk review and explicit company IT sign-off.

## Build sequence

1. Validate existing starter (4 baseline tests), migrations, access control and durable store.
2. Finish work-order workflows, assignment history, Part Master import and drawing revisions.
3. Add document/form registries, auto-form rules, copy-on-use and manual completed filenames.
4. Evaluate and integrate **specialized** in-browser Excel editor (licensing/feature compatibility), then prove workbook preservation. Resolve blockers before claiming form editing complete.
5. Implement tasks, per-user timers, projects, pallets and chargebacks (forklift exclusion); record/verify all labor calculations.
6. Complete Ortery photo workflows, cross-site group chat, reporting/export and security hardening.
7. End-to-end, regression, role matrix, synthetic scale, approved sample-form checks and cloud staging verification.
8. Produce final release report with exact test commands/results, unresolved risks, sample UI screenshots and deployment plan. Ask user before opening **the only PR**.

## Explicitly unresolved / not to fabricate

- Real Excel workbook samples, external workbook editor licensing and restrictions.
- Exact final work-order numbering policy; no change without user approval.
- Final cloud service/provider, deployment credentials, company network-drive accessibility and IT approval.
- Company-specific sample files and supplier rules should not be invented; use synthetic fixtures until provided.
- Policy/procedure control beyond work-related supporting documents is optional, not a new QMS.

Codex must never report full delivery unless every gate is proved. Record missing evidence and continue implementation accordingly.
