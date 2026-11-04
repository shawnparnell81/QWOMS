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
