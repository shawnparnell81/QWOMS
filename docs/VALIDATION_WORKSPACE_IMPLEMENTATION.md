# Integrated Validation/FAI workspace — working synthetic review

> **Historical milestone.** The owner has ruled out paid spreadsheet licenses. The active default is the working free editor described in `FREE_WORKBOOK_EDITOR.md`; commercial pricing/experiments below are retained historical evidence, not a purchase recommendation or current dependency.

The implementation is on `development/qwoms-complete-build`, following the uploaded workspace, dynamic-template and redesign requirements. The actual local application is running with a real Collabora office engine; it is not a spreadsheet mockup or a remotely deployed release.

## Open the working application

In the attached development environment, open `http://127.0.0.1:8020/#work-order-2` (forward ports 8020 **and 9980** securely if using your own browser). These loopback addresses are inside this environment, not your computer and not a public site. The private review credentials are in ignored `work/excel-editor/reviewer.credentials`; do not paste their values into chat. The separately assigned synthetic Engineering reviewer uses `synthetic.engineer` and the same local synthetic password. No real employees or company forms are present.

The selected synthetic strut order contains approved drawing C, work instruction 2, its own automatically matched original workbook, two distinct equipment PDFs plus subsequent browser-test PDFs, a generated photo, video, project, assignment and actual per-person labor entries. Pump and injector orders 3 and 4 have unrelated uploaded workbook layouts. Counts reflect real records; repeated browser runs add synthetic records and never overwrite them.

1. Open **Engineering drawing** or **Work instruction** in the left resource rail. The original opens in the central viewer.
2. Open **Validation workbook**, then **Expand workspace**. Enter measurements directly in native workbook cells. The shock fixture uses B5; try 12 then 8 to see calculated green PASS/red FAIL. This address belongs to the synthetic test, not application logic.
3. Use **Upload Test Results** while editing. The original PDF retains its filename, uploader/date, sample/equipment metadata and SHA-256. Preview or download it. **Return to workbook** restores the same editor session.
4. Enter a completed filename ending `.xlsx`, save, review the measured fidelity differences and explicitly acknowledge them for synthetic testing. Retry Save. The completed copy is filed in its configured Validation folder with order/project links. Duplicate names fail; the master stays unchanged.
5. Reopen a saved workbook in the rail or dedicated editor. Export an `.xlsx`, or use the actual office **Print** action.
6. **Form library** accepts a previously unknown supported `.xlsx` with its original basename and bytes. Choose part/family/type/subtype matching scope; the upload creates no empty work order. Submit, then independently review/approve through the separately authorized Engineering account. New matching orders attach the approved revision. Use matching rules/controlled revisions for further mappings or revisions. Retire removes active selections/matching while historical orders retain originals; restore is audited.

## Implemented behavior

- Unified light workspace: aliases, pinned drawing/revision, instructions/forms, in-app document previews, evidence, assignment/status/project, real timers/person-hours and activity history. Expandable native workbook editing retains an active editing session while another resource is viewed. Other five work-order screens remain distinct.
- Upload-defined masters: no production worksheet/cell map. Most-specific matching wins; conflicting equally specific templates fail explicitly. Revision approval, immutable attachment snapshots, retirement/restoration and preserved historical records are enforced server-side.
- Raw evidence: multiple original equipment PDFs, PNG/JPEG, MP4/WebM, supported XLSX/CSV attachments. Dedicated transactional SQL storage preserves metadata and exact bytes together. Files have per-order access checks, integrity verification, no-overwrite uniqueness and video byte ranges. Maximum 25 MB per original. Employee evidence is separate from permission to import blank masters.
- Separate append-only human Pass/Fail/Conditional Pass disposition. Conditional Pass requires rationale and independent, explicitly authorized Engineering approval before closeout. Human decisions never rewrite workbook calculations.
- Administrator/explicit import capabilities remain the only import authority; department membership supplies no import grants. Controlled Engineering approval remains separate.

## Actual verification

SQLite and PostgreSQL 17: **75 passed each**, including migration upgrade/downgrade/model parity, all department/import/security/account regressions, nine new workspace tests, matching/retirement/new revisions, immutable originals, evidence ACL/duplicates/rollback and independent conditional approval. PostgreSQL tests used random disposable schemas in the existing local synthetic database. Initial direct Docker-IP connectivity failed; inherited demo gate/storage settings also invalidated container test attempts. With isolated test-process settings the full suite passed; no hosted database was tested or changed. Three existing deprecation warnings remain.

Chromium integrated workflow: **22 assertions passed**, including 1440/1280 layouts, original drawing/instruction/PDF preview, start/stop ledger, native editing, duplicate PDF rejection, continuing the same draft after PDF upload/preview, completed filing/parent refresh, image/video preview, persistence on reload, unknown-layout upload and retirement/history/restore. Browser-discovered iframe hiding and expanded-view return navigation problems were fixed before the passing run.

Three additional unrelated layouts passed native measurements, formula calculation, named completed filing/export, then actual saved-file reopening and employee export controls. Independent inspection verifies pump E5=12/F5=11 → PASS; injector F9=6/G9=1 → PASS; previously unknown Z8=42 → PASS, original formulas/sheets/merges and unchanged masters. Integrated shock B5=14 → PASS and byte-identical equipment PDF also passed artifact checks. Addresses appear only in synthetic fixture/tests.

Seven regression suites passed: all six type creation/status screens plus aliases/messages/admin/projects (`smoke`), independent controlled approvals, rules/fields/completed forms, accounts, explicit grants/revocation, operations and standalone real-office editing. The standalone office test independently rechecked 12/PASS/green RGB(0,176,80), 8/FAIL/red RGB(255,0,0), original validation prompt, unchanged embedded image bytes, two worksheets, saved-file reopen/export and actual two-page office-generated PDF with A4 landscape first page.

Safe screenshots and machine-readable evidence are in `docs/evidence/validation-workspace/`. Uploaded/exported XLSX/PDFs and credentials remain in ignored local storage. Screenshots show the application itself, not design mockups.

## Unresolved requirements and deployment gates

**Exact Excel fidelity still fails.** The generic comparator now inspects all styled cells rather than the former fixed synthetic probes. The latest standalone shock run reports **31** raw differences; integrated shock **30**, pump **21**, injector **15**, unknown layout **25**. Earlier 26-difference evidence remains valid under the earlier narrower comparator and was preserved. Differences include conditional-fill representation, font/alignment defaults, dimensions and print margins. Passing formulas, visible colors, original image bytes and print generation do not certify exact rendering or arbitrary workbook support. No source original or vendor code was modified to make comparisons pass. Native Microsoft Excel visual/print acceptance, complex functions/charts/protection and representative approved blank masters remain unverified. Only validated `.xlsx` is supported; macros, unsafe external links/programs and external-fetch formulas are refused.

The original-vs-working-copy comparison is structural/style sampling, not a complete visual or every-OOXML-feature proof. No generic automatic workbook-result extraction is claimed: arbitrary forms keep their own formula locations, and the independent human disposition is explicit. The broader dashboard/all-type visual redesign, full production data isolation/security review, recovery/storage/scale acceptance and remaining previously approved release scope are still gates. This milestone does not claim full QWOMS completion.

**Licensing:** local Collabora CODE is free MPL 2.0 development/testing software, with no vendor code bundled or modified. It is not the approved production office deployment. Official supported Collabora Business pricing observed is **$3.40/user/month** (up to 99 users); custom WOPI integration, minimums, billing and final terms require a vendor quote and approval. SpreadJS remains an evaluated alternative with unresolved image/conditional-format/anchor/print differences; official pricing observed is **$1,999 developer + one annual hostname bundle**, **$1,499 additional annual hostname**, optional Designer add-on **$1,299/hostname/year**. See `EXCEL_EDITOR_IMPLEMENTATION.md` for official source links and evaluation restrictions. No purchase, vendor contact or commercial evaluation deployment occurred.

**Exact next action:** Quality can test this running local synthetic workspace now via secure environment port forwarding. A shared hosted review requires reconciling the divergent local/deployed permission migrations (different 0008 schemas and additional remote migrations), testing an isolated restored clone through migration and rollback, verifying durable original/document storage and HTTPS office callbacks, and approving the selected office hosting/license terms. Do not auto-push this divergent branch to Render's auto-deployed branch. No PR, main merge, live deployment or production-resource change was made.

## Reproduce

With Python/browser dependencies installed, start the isolated office/app using `EXCEL_EDITOR_IMPLEMENTATION.md`, then:

```sh
PYTHONPATH=. .venv/bin/python tests/browser/seed_workspace.py
node tests/browser/workspace.cjs
node tests/browser/dynamic-workbooks.cjs
node tests/browser/reopen-workbooks.cjs
PYTHONPATH=. .venv/bin/python tests/excel/verify_workspace_artifacts.py
```

The seed uses normal authenticated APIs and synthetic fixtures only; rerunning intentionally creates another unique fixture set. The scripts are explicitly restricted to the isolated review app at local port 8020. Run the normal suite with `.venv/bin/pytest -q`; for PostgreSQL set `QWOMS_TEST_DATABASE_URL` securely to an isolated local test database, avoid inherited demo/gate/storage settings, and retain the per-test schema isolation. Do not print connection strings or run these mutation suites against Render/company records.
