# QWOMS — user-managed, upload-defined Excel form library
Status: mandatory user-confirmed product behavior (2026-11-04). Source workbooks are never embedded in source control.

**Separate from spreadsheet templates:** completed equipment test reports are user-uploaded PDF evidence on the individual work order. Upload them as original files without conversion, reformatting, cell mappings or application code changes. These PDFs must not be treated as Excel masters. See `VALIDATION_WORKSPACE_SPEC.md`.

## Core principle: the uploaded workbook IS the form

The owner has an existing application that accepts arbitrary Excel spreadsheets and retains their formatting/layout without hardcoded form designs. QWOMS must use the same **upload-driven, configuration-driven architecture**, but add part lookup, order linking, revision control, in-browser completion, evidence, and project/labor context.

- A fuel pump, fuel injector, shock absorber, alternator and other physical parts can have entirely different validation forms, worksheets, formulas, conditional PASS-green/FAIL-red fills, images, merged cells, print properties, data validation and other Excel features.
- **Never implement a permanent shock/fuel-pump/injector-specific spreadsheet layout or cell map in source code, static HTML, database migration, or fixed part-type renderer.** No deployment or developer changes should be needed to add, replace or retire a template. Any feature-specific mapping (e.g. optional cell-to-summary metrics) is editable metadata and never required merely to use the original workbook.
- The administrator or a specifically permitted individual uploads the original blank workbook (.xlsx), and the application retains the original bytes, filename, worksheet content, layout, formulas, rules and revision. The owner chooses applicable physical part(s)/family and work-order type/subtype. Equivalent customer aliases resolve through the same physical part.
- The application displays the uploaded workbook in an in-app spreadsheet editor that actually reflects its source file. Users fill a **working copy** without changing the master, enter a completed filename, save it to the appropriate configured folder and link to the work order/project. Reopening/exporting preserves the workbook's original features and user edits.
- The form registry is persisted data, not hardcoded application content. The owner can upload, replace through an approved controlled revision, change matching rules, unpublish/archive/retire, and remove obsolete templates from all active selection, search and automatic attachment views. **Retired templates must not remain available as phantom built-in forms.**
- Removed/retired masters are not linked to new orders. Previously created work orders remain associated with immutable historical template revision snapshots and any completed evidence needed for traceability; no silent mutation or deletion of a historical validation. If truly permanent deletion is requested, implement an explicit authorized retention/deletion workflow and verify no protected record still needs the file.
- The upload must not require a specific workbook schema or hardcoded sheet/cell names. It can flag a workbook's unsupported features clearly, without silently stripping them or rewriting the user's original layout. Limit dangerous content, macros/external links, unsupported features and large files with auditable error messages, not blanket implicit reformatting.
- Preserve visual representation and XLSX file semantics separately: a grid approximation that looks similar but drops formulas/conditional formatting on save is not acceptable. Exact fidelity must be demonstrated with representative workbook round-trip tests and a properly licensed editor. If the chosen editor cannot preserve a feature, stop and report the incompatibility; do not covertly modify the user's template to make the test pass.
- The owner controls initial imports and may explicitly grant named employees narrow template-import rights; department roles confer no automatic import permission.
- Keep work-order-type-specific **operational** fields and instructions configurable, but never make their built-in form inputs a substitute for or prerequisite of an uploaded workbook's own layout.

## Concrete acceptance exercises

1. Upload three deliberately dissimilar synthetic .xlsx templates for fuel pump, fuel injector, shock. Distinct sheet counts, layouts, formulas, conditional rules, merges, images, formatting, print settings. No source-code changes or deployment between uploads.
2. Associate each with its correct physical part/family/type/subtype using administrative UI, and assert that work orders link only correct approved versions, independent of customer part-number aliases.
3. Open any selected workbook in the actual browser editor, fill cells, recalculate, preserve visible PASS/FAIL colors and all workbook features, save under a person-entered name, reopen and export to native Excel with compared fidelity.
4. Upload a fourth previously unknown workbook after the application is already deployed. It must immediately become available for rule mapping and order creation without a code or schema change.
5. Retire the fuel pump template or delete its **active registry entry**: it must disappear from all active form pickers/rules and cease attaching to new orders; preserve pre-existing order evidence/revision history.
6. Replace an old template with a newly approved revision: new orders use the new revision; old completed orders retain the precise original revision and evidence. Confirm undo/recovery, duplicate filename handling and audit.
7. Exercise no-import-permission, unsupported workbook features and insecure workbook content; denial or errors do not mutate source files or leave phantom templates.

The completed validation form supplied privately is **reference evidence only**, not a hardcoded canonical design, not the approved blank master and not permitted in GitHub or the synthetic demo. Production company-data use remains blocked on verified fidelity/licensing, access control and durable storage.

## Zero-fee implementation route confirmed by owner

The owner has ruled out any paid spreadsheet-editor license, subscription or per-seat costs. This is a product constraint, not an open procurement decision. Codex should compare against the successful implementation approach in the user's **other owned application** (source to be provided or identified with permission). Do not copy that app's design or non-relevant modules. The goal is an original QWOMS workflow using upload-defined, format-preserving workbook editing.

Engineering must separate (a) original template file-byte preservation, (b) accurate on-screen rendering and formula/conditional-rule evaluation, and (c) export/save fidelity after user edits. Assess proven open-source approaches and carefully scoped XLSX package editing without rewriting unrelated parts where appropriate. Do not promise a ZIP/XML patch alone evaluates arbitrary Excel formulas or renders every Excel feature. Report remaining incompatibilities clearly rather than suggesting a $1,500 license.
