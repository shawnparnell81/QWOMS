# Personal Administrator and employee capabilities

Administrator is independent of department. Management is not Administrator. New employees have no import or Engineering approval grants. Administration lists disabled accounts and explicit capabilities; checked capabilities are saved with the Administrator's current password. System Administrators have every import capability; Engineering decisions require both Engineering department and an explicit `engineering.approve` grant. Existing independent-review rules still apply.

Import categories: `import.part_master` (preview and commit), `import.drawings` (folder and mapping), `import.form_masters`, `import.work_instructions`, `import.supporting_documents`, `import.other`. Controlled identity/revision registration requires the matching import right. Completed order evidence is a separate work execution operation, not permission to import masters. Every API checks permissions against the current account. Permission changes revoke all recipient sessions and write capability-level grant/revoke events plus before/after account audit records.

## First production installation

On a backed-up, migrated database, run `python -m app.bootstrap PERSONAL_USERNAME --display-name "Your name"` from the trusted installation console. Enter a unique password twice at the hidden prompts. There is no web signup, default password or production employee seeding. The first claim is serialized and audited; further claims fail even if the administrator later becomes inactive. Only the Administrator can create employees or appoint another Administrator. Last-active Administrator demotion/deactivation fails; accounts have no delete endpoint, preserving history.

## Existing installations and deployment gate

Migration 0008 adds denied defaults to **every existing account**; it never infers owner identity from Management, username or demo credentials. Before deployment, back up database/files, rehearse migration and the personal owner claim against a restored isolated copy, reconcile legacy users and independently assign Engineering approvers. Existing synthetic demo bootstrap does not silently promote existing accounts. A fresh demo seed gives only `demo.manager` Administrator and explicitly assigns `demo.engineer` approval; production seed remains prohibited.

Do not deploy this migration to Render automatically. A safe rollout requires a tested backup/restore, an owner claim plan, maintenance/auto-deploy control, matching application/schema versions and a rollback rehearsal. Migration downgrade removes all admin/grant data: restoring the pre-change database plus matching application image is the safer rollback; neither is authorized on the live demo in this task. Tests prove schema upgrade/downgrade and denied defaults, not hosted backup recovery.
