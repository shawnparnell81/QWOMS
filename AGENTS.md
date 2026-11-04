# QWOMS instructions for Codex

Read `docs/PRODUCT_REQUIREMENTS.md` and `README.md` before coding. Implement features incrementally with automated tests and only fictional development data.

## Essential rules
- This is **Quality Work Order Management**, not a full QMS. No training-document module, general CAPA or auditing suite, or email functionality.
- Six work-order types: Validation / FAI, Inspection, Test, Repair, Parts Weighing, Photos. Distinct fields and interfaces based on type, subtype, product family and physical part; never one generic work order form.
- Automatically generate **work order numbers only**. Users manually name completed Excel forms and other saved files; never auto-name or rename them.
- Product families within Part Master. One physical part can have many customer-specific equivalent part numbers. Searching any alias displays related aliases; user picks the correct one. Work orders have no customer info fields.
- Import thousands of Excel Part Master rows with drawing number, **authoritative revision from Excel**, UPC and related part numbers. Preserve missing values as blank and editable later. Review collisions, duplicates, and conflicting mappings; never automatically merge purely on drawing number.
- Bulk-import complete drawing/document folder trees preserving exact filename, extension, and relative folder structure. Never overwrite existing different files. Drawing number/revision cross-links are metadata, not filename-derived. Snapshot drawing/document revisions per work order.
- Retain one blank, revision-controlled template for each required form. Rules auto-attach correct forms based on part/product family and type/subtype. Only create actual work orders when needed; no unused blank work orders. On completion, save the workbook in its designated type folder under a **user-entered filename** and link it to work order/project. Master blank form stays unchanged.
- **Critical Excel requirement**: in-browser workbook editing must retain the EXACT original layout, cells, formulas, conditional PASS-green/FAIL-red formatting, merges, validation, pictures and print settings. Test actual representative workbooks and round-trips; don't claim accuracy based on generic HTML sheets or openpyxl alone.
- Role-based username/password accounts for Quality, Engineering, Production, and Management, with assignments, dashboards, employee avatars and internal messaging for all authorized users. No emails.
- Forklift drivers have no accounts. Management records forklift time for internal use only; omit all forklift time/tasks/costs completely from supplier chargeback reports.
- Future requirements: projects with multiple work orders, task and per-person labor tracking, elapsed vs labor-hours, repairs/replacements, pallets and inventory return, supplier chargeback summaries excluding forklift, Ortery 360 photography/catalog workflows, controlled work-instruction revisions, Word/PDF/Excel imports and exports.
- Cloud browser application across sites. Private repository and synthetic data only. Never commit company drawings, spreadsheet masters, passwords, secrets or sensitive records.
- The starter is a developer prototype, NOT production-ready: require migrations, approved persistent storage, robust auditing/access control and security review before real data.

## Repository workflow — single final pull request (2026-11-04)

- **Work only on `development/qwoms-complete-build`**. Do not commit feature work directly to `main`.
- Implement and verify the entire accepted QWOMS scope in reviewable milestones. Multiple commits on the same development branch are encouraged; **do not create a pull request after individual milestones**.
- Continue from the current branch and preserve accepted requirements. When starting a new Codex cloud task, select `development/qwoms-complete-build`, inspect existing commits, and avoid overwriting uncommitted task work.
- After each milestone: run the applicable tests, inspect `git status` and diff, record results and known limitations in `docs/BUILD_STATUS.md`, and commit/push verified progress to the same branch. If Codex cannot push, provide exact commands or a patch without opening a PR.
- Open **one PR from `development/qwoms-complete-build` to `main` only after user authorization**, all agreed features are implemented and the complete acceptance/security/test matrix passes. Do not merge without explicit user approval.
- Never claim exact in-browser Excel fidelity, production readiness, cloud deployment, or security completion without tested evidence and representative workbooks. Show failed or blocked checks explicitly.
- The GitHub private-repository setting does not change this branching policy. Keep production/company data out of GitHub.

## Accelerated launch priority

Read `docs/LAUNCH_ACCELERATION.md` at the beginning of each task. Prioritize an explicitly authorized, private synthetic-data **hosted demo** and test evidence, then approved real-data pilot and full production gates. Do not equate a running local app with a live website or approved company use. User wants fastest safe launch; do not delay a secure demo just for non-critical enhancements. Obtain authorization before provisioning chargeable services. Preserve the one-final-PR policy.

### Explicit, owner-granted import permissions — zero inherited grants
- **All import permissions default to DENIED for every non-administrator employee**, regardless of Quality, Engineering, Production, Management, site, job title or work-order assignment. Never grant them via a role template, account creation default, group membership, promotion, or department inheritance.
- Only the sole initial system Administrator may grant or revoke **specific import capabilities to named employee accounts**, based on who needs them. Examples: Part Master spreadsheet preview/commit; drawings/folder upload; work-instruction/supporting-document import; blank Excel form/master template import; other data/file imports. Keep read/view, edit, controlled Engineering approval, and import permissions separate.
- Permission grants and revocations must be explicit actions in an administrative interface, immediately enforced server-side on every import API and relevant bulk import path, and recorded in an audit trail (actor, recipient, capability, timestamp).
- Default employee-role templates carry **zero** import grants. Only the administrator has all import permissions at production first-start. No implicit grants even to Management or Engineering. Test grant, deny, revoke, direct API bypass attempts, and employee account creation defaults.

## Sole initial administrator and owner-controlled onboarding — REQUIRED (2026-11-04)

- **Production launch starts with exactly one authorized administrator: the user's own individually credentialed account.** Never create other administrator accounts by default; the user creates and enables all employee accounts after first login. No public self-registration, no shared admin account, no seeded fictional employee accounts in a real-data environment. Demo-only fictional bootstrap must be isolated and disabled in production.
- Explicitly separate **system Administrator** authority from department/job roles (Quality, Engineering, Production, Management). Merely choosing the Management role must NOT grant administrator privileges.
- The sole Administrator controls initial account creation/invitation and activation/deactivation, password resets/recovery workflow, role/site assignments, fine-grained permissions, and all initial data/file imports. Administrator may later explicitly grant/revoke import permissions or create another administrator, but the defaults are **admin-only**.
- Require administrator authorization for Part Master spreadsheet imports/commits, complete drawing/document folder imports, form-master/template imports, work-instruction/supporting-document imports, and their initial mappings. Department-level users must not gain import authority just by being in Quality, Engineering, or Management.
- Preserve Engineering-specific controlled-document review/approval privileges for **explicitly authorized** Engineering approvers; that approval is distinct from system administration and importing. Preserve employee work-order functions according to scoped permissions.
- Create a secure one-time initial-admin bootstrap/claim flow with a unique personal account, no default password, auditable admin operations, session revocation on deactivation, and guard against disabling or demoting the last active administrator. Test unauthorized account creation/import attempts, delegated permission revocation, last-admin protection, and production startup without demo seeding.
- This is a company-wide launch gate, not a future nice-to-have. Do not represent the current Management-based `require_admin` and Quality/Engineering/Management import endpoints as satisfying it until code + browser/API tests prove the change.

## User-confirmed release scope — full functionality (2026-11-04)
- The user expects **all previously accepted QWOMS workflows working before a company-wide production go-live**. A synthetic-data demo or limited pilot may help testing but is never described as satisfying this release.
- Updates and improvements can follow launch, but **do not defer any accepted mandatory requirement** as a post-launch enhancement without explicit user agreement. The exact-fidelity in-app Excel forms, rules-driven template attachment, controlled revisions, labor/projects/pallets, chargebacks, six differentiated work-order types, alias Part Master and folder imports are release-critical.
- Favor fast, integrated development and automated regression tests across workstreams. An impressive demo, local test pass, or cloud URL alone is insufficient evidence of operational readiness.
- Do not claim the app will work perfectly without testing. Real representative workbook compatibility, security, backups/restore, and user acceptance are release gates.
- Stay on `development/qwoms-complete-build`; multiple commits, one final PR only upon user approval. Code and tests cannot be run asynchronously outside an active Codex task.

## One login only — user requirement (2026-11-04)

- The QWOMS website must show **one username/password login only**. No separate browser HTTP Basic prompt, demo-gate password, secondary employee portal login or extra authentication layer before the app's login screen.
- For the synthetic Render demo, remove the HTTP Basic gate while preserving individual QWOMS sessions, HTTPS, CSRF protection, permission checks and login throttling. A public login screen is acceptable for **synthetic test data only**; no real company content until independent production security approval.
- For production, each user signs in once using their individual QWOMS account. Sole initial Administrator sets up all employees and grants permissions explicitly. Do not reintroduce double login through future Blueprint sync/deploy.

## Visual quality is a launch requirement — QWOMS look and feel
Read `docs/UI_REDESIGN_BRIEF.md` before UI development. The user is dissatisfied with the present appearance relative to the polished original concept visuals. A functional prototype does **not** satisfy design acceptance. Restore the analytics-first dashboard, high-quality visual hierarchy and differentiated type/part workflows; obtain user review from actual screenshots rather than assuming the current design is acceptable. Never invent illustrated metrics. Do not substitute styling work for the Excel/editor and security acceptance gates.

## Uploaded Excel masters + direct PDF test evidence (2026-11-04)
Read `docs/DYNAMIC_EXCEL_TEMPLATES.md`: every part-specific validation workbook is **uploaded data**, never a hardcoded layout, sheet or formula. The owner assigns, replaces and retires approved blank templates without code changes. Retired masters disappear from active picks/automatic attachments, while previously completed order evidence and controlled revision snapshots are preserved.
For Validation/FAI testing-software results, the user's normal export is a **PDF**. Provide a simple **Upload Test Results PDF** action directly in each work order. Save the unmodified original PDF bytes and filename attached to that order immediately on successful upload. Show it in the same order's Test Results section with an inline PDF preview/open and authorized download. No conversion, extraction, format mapping, or spreadsheet rewriting is needed. Verify no overwrite, secure access and persistence. Keep the separate blank validation Excel workbook behavior unchanged.

## One integrated validation work-order workspace (actual workbook reviewed)
Read `docs/VALIDATION_WORKSPACE_SPEC.md` before implementing Validation/FAI UI, Excel, drawing/instruction auto-links, or test-software evidence attachments. A user-supplied completed validation workbook has been examined privately; it is not a blank master and must never be copied into repository or synthetic Render. The specification records worksheet structures, formulas, conditional statuses, and the single-workspace interaction. Obtain a company-approved blank master and sanitized software export fixtures before asserting exact Excel round-trip fidelity. Keep calculated PASS/FAIL distinct from Engineering-authorized final disposition.
