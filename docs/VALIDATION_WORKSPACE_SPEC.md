# QWOMS — integrated Validation/FAI work-order workspace
Updated 2026-11-04. Requirements from inspection of a user-uploaded **completed** validation workbook. The original file and its company-specific data are NOT stored in this repository or in the synthetic Render demo.

## Key product outcome

One Validation/FAI work order must be the **single starting location** for all work related to that part. Employees must not need to hunt through independent network folders/windows for the drawing, the matching blank form, work instructions, or test software reports. The view should remain accessible while editing/reviewing linked items. Use the professionally polished, modern, subtly playful QWOMS design direction in `UI_REDESIGN_BRIEF.md`.

### Context from actual completed workbook (read-only inspection)

A representative completed CSA Validation Report was supplied. It contains one worksheet, `Test Report`, with at least these six numbered sections:
1. Part and inspection information, including part, engineering drawing number, supplier/factory, batch, inspector and date.
2. Strut physicals.
3. Damper performance.
4. Coil spring.
5. Mounts and bump stops.
6. Final disposition, notes and engineering approval for conditional decisions.

The workbook contains 21 formula-bearing cell records (including shared formulas), approximately 25 merged regions, two conditional-formatting regions applying red/green PASS/FAIL fills, two dropdown validation rules, sample 1/sample 2 columns, and page settings. Its visible report is roughly A1:G52, with auxiliary entries further to the right and extensive formatted cells below. It contains **no embedded image files**, so image fidelity must also be proven on a separate real representative workbook with images. Do not assume this completed file is the reusable blank master: obtain the original approved blank template, or create an explicitly user-approved copy after measured verification.

The top-level calculated result shows failure while a separate manual final disposition/conditional approval area exists. Model calculated measurements, actual evidence, final human disposition, conditional exception rationale and Engineering approval as **separate auditable facts**. A blank second sample currently yields a spreadsheet `#DIV/0!` in a calculated cell. A paint-thickness tolerance symbol and some formula comparisons may differ in interpretation; flag for Quality/Engineering confirmation rather than silently changing source formulas or criteria. Do not publish names, customer/part numbers, batch IDs or source workbooks to GitHub/test infrastructure.

## Work-order screen requirements

**Header** — WO number (auto-generated only), type `Validation / FAI`, subtype, selected physical part and customer alias, number of samples, project, status, priority, assigned technicians, progress, timestamps.

**Pinned resource area** — recognizable cards/sections:
- **Part & engineering drawing**: selected part alias, physical part identity, drawing number and authoritative approved revision from Part Master, secured original-file preview/download, immutable order snapshot, approval/revision history and missing-mapping warning.
- **Blank validation workbook**: find appropriate *approved* master revision by type/subtype/family/part; no empty work orders generated on template import. Start a separate job-specific working copy, open Excel editor in the browser with a familiar sheet/tab interface, save/reopen/export under user's filename without mutating master. Preserve worksheet names, formulas, red/green CF fills, dimensions, merged cells, data validation, page setup and any images. No claim of exact fidelity until real edit/reopen/export comparisons pass with a permitted licensed editor.
- **Work instruction**: automatically attach the approved instruction revision for this work type/family/part; preview PDF/Word/other supported file, with owner/effective-date/revision, acknowledgement where appropriate, and immutable reference used for this job.
- **Test software evidence**: upload one or more outputs as-is from dynamometer, spring-rate equipment, and other applicable software/equipment. Support PDFs, XLSX, CSV, graphs/images and additional approved formats; video where applicable. Preserve original filenames/bytes/format, hashes and version/upload metadata. Preview safely when supported and always permit authorized download. Attach to the specific work order, measurement/test or sample, with equipment, test date, uploaded-by, description and source. Do not require a software API as a prerequisite; use direct file attachment first, then optional format-specific result extraction after reviewing representative exports.

**Work execution** — differentiated Validation/FAI sampling, measurements, test plan, task checklist, employee timers and manual audited time adjustments, photo/video evidence, rework/exception/engineering review, sample 1 and sample 2 evidence, history and notifications inside the app only (no email).

**Disposition and closeout** — distinguish calculated PASS/FAIL per criterion and sample from final approved Pass/Fail/Conditional Pass. Preserve any failed measurements when conditional release is approved. Require authorized approver and rationale where rule demands; retain all completed forms/files and drawing/instruction revisions. Ensure work order can be searched and reported as an immutable historical record.

## Interaction design

At desktop widths, consider a responsive **resource rail + central active editor/preview + evidence/context panel** within the same application; provide tabs or drawer switching, without opening network folders. Maintain full-size editing/preview mode for spreadsheets/drawings; link context back to order. A resource may open a focused in-app workspace while still having breadcrumbs/back navigation to the same order.

Use actual data to show availability and statuses (e.g., Approved / Missing / Pending / Failed), not decorative or invented values. Each canonical top-level work-order type remains distinct.

## Acceptance tests

1. Create an actual synthetic Validation/FAI order from a part alias and verify auto-links: correct drawing + authoritative revision, correct blank form revision, correct work instruction.
2. Demonstrate all three originals remain unchanged and work-order snapshots remain the original revisions after a later master supersession.
3. Attach synthetic exported test-result files (PDF/CSV/XLSX/image/video fixture), preserving filename, file contents/hash, association, authorization and download.
4. Open the blank validation master in an **actual in-browser editor**, enter numeric sample measurements, calculate results, preserve red/green conditional formatting, save with chosen filename, reopen, export and compare source/master/completed workbook properties. Test two sample columns and empty sample behavior, mixed manual/formula cells, conditional exception and revision approval.
5. Exercise failure conditions: incorrect/missing drawing, unapproved instructions/forms, duplicate completed filename, upload interruption, unsafe file formats, no permission, overwritten original, unauthorized download, and stale revision.
6. Run screenshot/browser acceptance of the complete integrated screen as well as API tests on SQLite and PostgreSQL; validate on hosted synthetic demo only after authorized, reviewed deployment.

No real user-uploaded form or company identifiers are to be copied into repository, Codex prompts or hosted demo. First obtain an approved sanitized blank template for full-fidelity acceptance, plus one or more sanitized test-software exports to establish import/preview formats.
