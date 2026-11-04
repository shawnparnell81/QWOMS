# QWOMS — review of owner-built Sequfloh Excel implementation
Reviewed: 2026-11-04
Source: `shawnparnell81/Sequfloh`, branch `main`, GitHub repository (user explicitly authorized review). This is an engineering inspection of source code and its test suite, **not an assertion that QWOMS now has this functionality**. No company workbook, source passwords, or proprietary files were imported.

## High-level finding

Sequfloh implements a custom workbook-oriented editor with **ClosedXML 0.105.1 (.NET/C#)** on the backend and **React 19 + MUI** on the frontend. No SpreadJS, paid Collabora editor or licensed browser Excel SDK is listed in its `Sequfloh.Api.csproj` / `web/package.json`. ClosedXML is MIT-licensed open-source software; retain its attribution/license notices if using or distributing it.

**Do not confuse preserving an original upload with proving full Excel round-trip fidelity after edits.** Sequfloh retains the original file under `OriginalStorageKey`, but working-file saves use `XLWorkbook.SaveAs(...)` and may alter unsupported/partially supported XLSX structures. We have reviewed tests for representative dynamic PASS/FAIL behavior, not a complete round-trip of all workbook features.

## Exact source architecture

1. **Upload and source preservation:** `src/Sequfloh.Api/Imports/ImportedFileService.cs::UploadAsync` stores original bytes in private storage at `imports/<id>/original<ext>` and creates an editable first version separately; names/versions are stored in DB. Also supports PDF evidence unchanged via `PreparePdfAsync`.
2. **Parse/visualize any uploaded workbook without part-specific layout code:** `Imports/WorkbookReader.cs::Read` uses ClosedXML plus raw XLSX ZIP/XML checks to construct per-sheet cells, styles, values/formulas/cached results, dimensions, merges, validations, conditional rules, metadata and warnings. `WorkbookIntake.cs::Grid` translates this into a compact JSON sheet. The first visible sheet's grid is cached as `.grid1.json` for faster loading. `SheetAsync` serves requested worksheet names dynamically.
3. **Custom in-browser grid:** `web/src/sequfloh/Imports.tsx::SheetEditor` renders a styled HTML table from returned row heights, column widths, merged cells and per-cell style; tabs correspond to uploaded workbook sheets. It edits selected cell values/formulas and shows a formula bar. It is **not** an embedded commercial spreadsheet editor.
4. **Live calculations and red/green results:** UI POSTs pending cell edits to `/api/imported-files/{id}/preview` after a short debounce. Backend `ImportedFileService.Preview` applies edits in a temporary ClosedXML workbook and `RecalculateAllFormulas`; `ConditionalStyles.Evaluate` evaluates supported conditional rules and returns fill/color overrides. The UI does not persist these until Save.
5. **Saving a new version:** `ImportedFileService.ApplyCells` writes changed cells/formulas with ClosedXML, recalculates (or flags the need for Excel recalculation), and calls `XLWorkbook.SaveAs` to produce the edited XLSX; `SaveVersionAsync` stores a numbered new version with audit/history.
6. **Unmodified masters and user-named copies:** `FillOutAsync`, `SaveAsCopyAsync`, and `CreateCopyAsync` distinguish a protected blank master from filled copies; the copy keeps its master/version and associated work order. `BlankFormId`, `BlankFormVersion`, and `WorkOrderId` make copies trackable. Archive/retire removes a master from active views.
7. **PDF tests and file evidence:** `ImportedFileService.PreparePdfAsync` checks PDF signature, stores its bytes unchanged and returns original PDF. The new QWOMS requirement is simpler: attach original PDF to an existing work order, with preview and download, without template conversion.

## Evidence in Sequfloh's tests

- `web/e2e/blank-forms.spec.ts`: imports arbitrary synthetic workbook, confirms master protected, creates a user-named filled copy, edits a measurement, confirms green PASS / red FAIL, saves/reopens, creates a second copy and verifies original/master unchanged.
- `tests/Sequfloh.Tests/ConditionalStyleTests.cs`: checks conditional fills after edits, including certain `00`-alpha colors/formula caching quirks.
- `tests/Sequfloh.Tests/FormulaFormSpeedTests.cs` and `WholeColumnFormattingTests.cs`: speed/formatting tests for formula-heavy workbooks, whole-column formatting and wide/long ranges.
- `tests/Sequfloh.Tests/WorkOrderValidationFormTests.cs`: verifies form copies associated with work orders and product families, and person-entered numbers.

## Important differences and open questions

- **Different technology stacks:** Sequfloh is ASP.NET/C# and React; QWOMS is Python/FastAPI and custom JS. Do not copy C# into Python or assume components can be dropped in unchanged.
- **In-browser grid scope:** Sequfloh's current grid request caps the visible view (typically 500 rows × 60 columns) and workbook reader has additional limits. It also reports image/chart presence, but this grid does not display all native Excel objects. Therefore it is not literally an unlimited, pixel-perfect Microsoft Excel renderer.
- **SaveAs rewrite:** ClosedXML `SaveAs` can modify workbook serialization and unsupported features. Sequfloh's tests establish useful functionality and preserved master files, **not guaranteed identical conditional XML, fonts, images, anchors, margins or print layout for arbitrary customer XLSX files after edits**.
- **Formula coverage:** common formula expressions recalculate through ClosedXML. FormulaTranslator classifies some functions as preserved-only, unsupported, external/macro or review-needed; not every Excel function will calculate identically.
- **Licensing:** ClosedXML MIT allows use without a paid SDK license, subject to attribution and dependency license review. Hosting cost, infrastructure memory, privacy and support are separate questions. Do not purchase a spreadsheet SDK.
- **No unauthorized real data:** keep the customer's uploaded completed validation workbook private; use sanitized approved samples and synthetic fixtures for QWOMS tests.

## Recommended QWOMS implementation approach — no commercial editor

1. **Reuse the tested architectural method**, not Sequfloh's branding, pages, unrelated business logic, or customer data. The user wants a distinct QWOMS interface.
2. Build a small, isolated workbook processing interface that accepts source XLSX bytes and a set of `{sheet,row,col,value}` edits, returns structured visible grid and recalculated/conditional values, and produces a versioned edited XLSX. **Strong candidate:** extract/adapt the owner-authored ClosedXML workbook reader, preview and writer into a narrow .NET service that QWOMS FastAPI calls over a private process/API boundary; measure memory/CPU and concurrency within actual chosen hosting. Consider a Python implementation only if it meets the same evidence standard and is faster to deliver.
3. Design QWOMS's own modern, integrated validation screen: uploaded dynamic workbook preview/editor, document/drawing/instruction rail, attached PDF results and tasks. Master XLSX remains untouched. Do not hardcode a form per part.
4. **Test two fidelity approaches instead of assuming full SaveAs rewrite is enough:** (A) ordinary ClosedXML save, measured on the real approved blank form; (B) targeted Open XML package edits preserving untouched ZIP/XML parts if full rewrites modify required content. Targeted edits must also update caches or mark formulas for reliable calculation, handle strings/types, and preserve valid XLSX references; do not claim ZIP patches alone support Excel rendering/calculation.
5. Compare before/after: sheet names/order/visibility, formulas, cached results, conditional rule definitions and displayed red/green fills, cell styles, merge geometry, row/column dimensions, validations, images and anchors, headers/footers, page setup and Excel print/PDF rendering. Classify each difference as visible/functional, harmless metadata or blocking; inspect the output in Excel. Never silently rewrite user templates or claim exact fidelity when a genuine mismatch exists.
6. Provide a reproducible QWOMS demo with at least three very different synthetic workbooks (fuel pump, injector, shock), an owner-uploaded fourth novel template (no code change), a completed form with chosen filename, and a PDF test result attached directly to that work order.
7. Keep changes in `development/qwoms-complete-build`, preserve unpushed Codex changes, avoid staging the user's original file in GitHub/Render, and do not deploy over the live demo before migration/test approval.

## Relevant links

- https://github.com/shawnparnell81/Sequfloh/blob/main/src/Sequfloh.Api/Imports/ImportedFileService.cs
- https://github.com/shawnparnell81/Sequfloh/blob/main/src/Sequfloh.Api/Imports/WorkbookReader.cs
- https://github.com/shawnparnell81/Sequfloh/blob/main/src/Sequfloh.Api/Imports/WorkbookIntake.cs
- https://github.com/shawnparnell81/Sequfloh/blob/main/src/Sequfloh.Api/Imports/ConditionalStyles.cs
- https://github.com/shawnparnell81/Sequfloh/blob/main/web/src/sequfloh/Imports.tsx
- https://github.com/shawnparnell81/Sequfloh/blob/main/web/e2e/blank-forms.spec.ts
- https://github.com/ClosedXML/ClosedXML
