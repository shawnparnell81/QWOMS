# Controlled work documents, requirements and forms

This is work-order document control, not a full QMS. Use synthetic records only until operational gates pass. No training or email module is supplied.

## Engineering-controlled originals

Import originals with their exact names and relative folders through Drawings & Files or Controlled revisions. Register a Drawing, Work instruction, Supporting document or Form template identity. Drawing identity/revision must come from Part Master data, never the filename. A drawing mapping creates a Draft. Work instructions/supporting files preserve original PDF/Word/Excel bytes; they are not transformed into replacement HTML documents.

Register each immutable revision against one original. Engineering/Management may register and submit it. A different Engineering employee reviews and approves it; Management cannot bypass Engineering and an author cannot self-review/approve. Decisions require reasons and appear in history. States are Draft → In Review → Reviewed → Approved; Engineering can reject or obsolete an approved issue. A new approval supersedes the prior approved issue. No API replaces/deletes a revision's bytes or identity. Rejected content needs a new revision label; correction/reconciliation tooling is limited.

New orders snapshot their drawing identity/revision/file. Missing revisions, pending approvals and superseded-at-creation drawings block execution/closure. Previously approved historical references remain pinned after later supersession; an obsolete original blocks further execution. For an Open order, Engineering can resolve an exact approved original matching its existing snapshot—never rewrite its identity to a newer revision. Legacy unapproved records are not automatically certified. Import reconciliation for changed existing Part Master drawing revisions remains a launch gate.

## Scoped work fields and instructions

In Work requirements, Engineering/Management publishes immutable rule versions for a type, optional subtype, optional family and optional physical part. Identify a physical part by searching any alias. Rules add work-specific fields/instructions and mandatory controlled documents to the existing six distinct type-specific forms; they do not replace the Excel form layouts or force identical jobs into generic templates.

Matching rules accumulate instructions/documents. A physical-part match outranks family scope; family outranks type-wide scope; a subtype narrows within those scopes. A more specific field definition replaces a broader definition with the same stable field identifier. Equally specific conflicting definitions are rejected for reconciliation. Administrators should use distinct identifiers for distinct measurements. Retire old rules and publish replacements; prior orders retain their full definitions/instructions, original document revision IDs and values.

Field types are text, finite decimal, whole number and approved choice, with optional units/bounds. Required fields can be due at creation, execution or completion. Results can be saved on the order while it is open/in progress; completed/closed records cannot be rewritten. Mutations record employee and before/after changes. Production may record only its assigned work. The server validates values and the rule versions the creator reviewed; a changed rule set forces refresh before creation.

## Blank masters and automatic attachments

Register a Form template with the original `.xlsx` and explicitly confirm it is blank. Container checks reject malformed/unsafe metadata, macros and oversized expansion; these checks are not malware scanning or proof of workbook fidelity. Engineering approves the immutable master through the same independent process. A single stored master per form revision is reused across actual orders. Publishing registry entries/rules creates **no blank work orders**.

Example: a rule for Fictional Shocks + Validation / FAI attaches the approved Shock Validation Form. A part-specific/subtype rule can select additional specialized forms and work instructions. A different family/type receives only its matching requirements. Mandatory documents without an approved current revision block order creation. Attachments pin the approved issue, checksum, original filename and completed category; a later template approval or folder/rule change does not rewrite existing order references. Older superseded masters remain accessible as historical originals.

The user can download an unchanged original copy. **In-browser editing is unavailable**; no generic editable grid or lossy conversion substitutes for it. Temporary synthetic demos can exercise upload/storage only. Any operational pilot requiring in-app workbook execution remains blocked by the exact-fidelity/licensing gates documented in `EXCEL_EDITOR_FEASIBILITY.md`.

## Completed forms and employee filenames

Upload a completed workbook to its attached form entry and explicitly enter its `.xlsx` filename. The upload's browser/generated filename is never substituted. No path components/control characters or leading/trailing whitespace are permitted; valid entered names/extensions/case are preserved. Files go to `Completed forms/<snapshotted category>/<employee filename>` and link to the actual work order and its project at save time. Category defaults distinguish Validation, Development, Inspection, Test, Repair, Weighing and Photos. Configure type/subtype folder overrides for future orders in Work requirements.

Duplicates within a category are rejected, even if bytes match; no overwrite or silent rename. Downloads verify original hashes. Completed file bytes are stored exactly as uploaded, separate from the blank master. Multiple named evidence uploads are retained until closure; there is no evidence-delete API. Completion requires all due fields and at least one saved completed file for every mandatory form. A withdrawn/obsolete attachment requires Engineering review, not a silent switch to a newer master.

This stage verifies container validity and byte/storage integrity, not whether every entered workbook result is correct or whether an uploaded workbook semantically matches the source layout. Editor/Excel compatibility and human acceptance remain mandatory. The demo database backend commits file bytes/metadata/audit together; local/S3 interrupted-write reconciliation is still required for operational storage. Project IDs on completed files record the association at save time; the work-order link remains permanent.

## Tests and remaining release gates

Automated tests cover missing revisions, approvals/roles/self-review, supersession, immutable pins, part/family/type/subtype differences, rule conflicts/version review, correct approved attachments, missing masters, exact filenames/folders, duplicates, master bytes, completion validation and audit rollback. Chromium checks exercise registration/review/approval, field/rule configuration, actual form attachment, completed upload/duplicate rejection, unchanged master bytes and completion.

Still required before company-wide production: all accepted labor/tasks/pallets/chargebacks/photography/group-messaging/report workflows, manual metadata/reconciliation, large imports/concurrency, malware controls, S3/provider validation, backup/restore, comprehensive site/record permissions/audit retention, account lifecycle/security review, exact workbook editing/licensing, representative original-form and user acceptance tests, and IT approval. None is deferred past production without explicit user agreement. A synthetic demo is not an operational pilot or full release.
