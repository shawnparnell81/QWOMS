# QWOMS — Approved Requirements / Build Backlog

## Product boundary
A cloud-hosted, multi-site Quality Work Order Management System for an aftermarket automotive parts manufacturer/supplier. The customer has explicitly rejected a full QMS and training-document management. No email functionality under any circumstances.

### All import permissions are individually assigned by the owner

On initial production setup **no employee has import permissions**, including Management, Engineering and Quality employees. The sole administrator is permitted to import. No department role, group, site, or employee account creation grants imports implicitly. The administrator chooses each named employee who needs a particular import right, grants it explicitly, and may revoke it at any time. Separate rights for Part Master imports, drawing/folder imports, controlled work-document and Excel form-master imports, and other supported bulk imports. The UI must show each employee's effective import permissions, and the backend must deny imports unless the exact capability is granted. Record every grant/revocation in the audit history.

## Launch onboarding and exclusive administrator control (confirmed 2026-11-04)

At company go-live, the Quality Manager who owns initial setup is the **only active system Administrator**. On first secure login they personally import Part Master spreadsheets, drawing folders, work instructions, approved blank Excel form masters and supporting files; create employee accounts; and choose employee roles, permissions, and sites. No employee is automatically provisioned in production, no default shared administrative account is allowed, and there is no public signup. Synthetic demo employees are test-only and must never be promoted/copied into production.

Administrator is a **separate privilege** from department/job roles. Quality, Engineering, Production and Management role membership alone grants no ability to create/manage accounts or perform administrator-restricted imports. Initial file imports and user/role/permission administration are **admin-only**; the owner can explicitly delegate and revoke specific privileges later, including appointing another admin if desired. Engineering-controlled revision review/approval is a separate explicitly assigned duty; it must not implicitly grant account administration or file import privileges.

Provide a secure owner-account bootstrap, admin portal for employee creation/activation/deactivation and granular permission assignment, audit trail of all admin actions and imports, proper credential reset/lifecycle, and protection against removal of the last active administrator. Users should see only actions authorized to them. Test unauthorized access even when UI controls are hidden.

## Foundation
- Secure individual user accounts for Quality, Engineering, Production and Management. No forklift-driver accounts.
- Employee avatars/initials and internal in-app direct messaging for all authorized employees, including across sites, with possible link to work order. Future group messaging and attachment options.
- Dashboard with assigned orders/tasks, overdue and unassigned work; creators assign and reassign work orders, track assignments and each employee's work.
- Numbering automatically assigned by the application based on order type, year/sequence and part number or multi-part designation; final pattern configurable later. **Only work orders get automatic numbers**.
- Work orders can contain one or multiple parts, quantity, configurable supporting attachments, priority, status, user assignments and project association. No customer information fields on work orders. Supplier references may be relevant but are not customer fields.

## Six work order types, differentiated experience
1. **Validation / FAI:** first article, product validation, development validation. Sample sizes, validation plans, test/inspection criteria, controlled product-family form.
2. **Inspection:** AQL, Non-conformance, Product Alert, Customer Complaint, Supplier Issue, Re-inspection and expandable subtypes. Sampling, defect types, counts, disposition, photos.
3. **Test:** functional, performance, durability, customized tests. Method, setup, results, acceptance criteria.
4. **Repair:** rework, component replacement, repair and reinspection, replacement parts, labor and disposition.
5. **Parts Weighing:** single/batch/verification, equipment, target range, recorded weights and acceptance.
6. **Photos:** Ortery 360 booth, marketing/catalog product images, photo requirements, image delivery and product return.

Different type/subtype/product-family/part combinations must have tailored UI sections, required fields, and work instructions. **Never force identical standard cards/instructions for all jobs.**

## Part Master, aliasing, drawings
- Group physical master parts by product family under `Part Master`.
- One physical part may have O'Reilly PN 123, NAPA PN 321, etc., with the same engineering drawing. Searching 123 shows 321 and all other equivalent aliases; user selects correct number for work order.
- Bulk import `.xlsx` with 3,000+ rows: physical grouping, customer/channel PN columns, drawing number, authoritative drawing revision, UPC, related numbers, family. Excel columns may vary; implement column matching, preview/confirmation, idempotence, import audit, collision reconciliation.
- Missing drawing/UPC/aliases remain truly blank and can be added later. Preserve identifier leading zeros. Never merge distinct physical parts simply because of shared drawing numbers.
- Import entire folders of engineering drawings and supporting files with their exact original filenames, extensions and nested relative paths. No rename. Prevent silent overwrite; flag duplicates/path collisions.
- Part Master Excel is authoritative for drawing number/revision, **not** imported drawing filename. Metadata cross-references files to drawings; conflict/missing mapping flagged.
- Controlled engineering drawing revisions with authorized review/approval and immutable work-order snapshots. Work orders retain the revision used at their creation even after revisions update.

## Forms, documents and exact Excel behavior — critical future milestone
- Allow importing/exporting Microsoft Excel, Word and PDF. Preserve blank master forms separate from filled-out evidence. Work instructions have controlled revisions. Broader policy/procedure control remains undecided and should not turn into a QMS.
- Auto-attach correct mandatory forms for product family + physical part + work order type/subtype. Example: shock + Validation/FAI gets Shock Validation Form.xlsx. The template is reused; no blank work order is stored for each type.
- Excel must be edited **inside the app** with fidelity to the uploaded `.xlsx`: exact cells, formulas, green pass/red fail conditional formatting, merged cells, dimensions, styles, validation/dropdowns, images, worksheets, print layout. Recalculate correctly. Test Microsoft Excel round-trip and actual forms before claiming success.
- Employee manually enters each **completed file name**. App never generates document filenames. Save completed Excel forms to a category-specific location in app (Validation, Development, Inspection, Test, Repair, Weighing, Photos; folder taxonomy adjustable) and link to work order/project; local download optional; never overwrite a duplicate silently. Master remains blank.
- Controlled document revisions for work instructions and related work-order documents, optional policies/procedures. No training materials.

## Projects, labor, pallets and reporting — future milestones
- Project is parent of multiple independent work orders; each order retains its own labor, evidence and statuses; project aggregate reports and supplier chargebacks span all linked orders.
- Accurate timing for order creation, tasks, per person, inspection/validation/test, repair, replacements, rebox/label, return to bins, documentation, management review. Distinguish elapsed duration from summed person-hours; manual corrections audited.
- Track pallet IDs, quantities, original bin, pull/return, condition/disposition, movement and final locations.
- Forklift drivers do not sign in. Management separately records actual/estimated forklift time for internal operations. **Exclude ALL forklift activity/time/cost from supplier chargeback reports**, including zero-dollar line items.
- Supplier chargeback project report: linked orders, approved chargeable labor, employees/departments, parts replaced/quantities/cost, inspections/tests, evidence/photos, repair, rebox/return, paperwork, approved expenses; configurable rates, approvals, audit trail.
- Import/export Word, PDF, Excel forms/reports and entire work order/project packet. Revisions and original files traceable.

## Phase plan
### Phase 1 (starter code)
Auth, user admin, dashboards, six differentiated order types, assignment, multiple parts, part alias search, `.xlsx` Part Master preview/commit with duplicate review, drawing-folder import keeping original paths, manually controlled drawing mapping, revision snapshots, direct messaging. Local dev only.

### Phase 2
PostgreSQL migrations, secure cloud persistent storage, full access control/audit trail, supplier metadata, field-level validation, project linkage, task assignments, revisioned work instructions and form/template registry with attachment rules.

### Phase 3 — highest technical risk
Specialized browser Excel editing and workbook round-trip compatibility; exact formatting/formulas/conditional formatting, per-type completed form saving with user-provided filenames, controlled approvals and report exports. License/deployment review for spreadsheet editor.

### Phase 4
Labor and activity tracking, pallets, management-only forklift internal data, projects, cost rules and comprehensive supplier chargebacks with forklift *completely excluded*.

### Phase 5
Production hardening, performance/import scale tests, backup/recovery, monitoring, malware handling, role/security tests, multi-site workflow reviews and deployment after company IT approval.
