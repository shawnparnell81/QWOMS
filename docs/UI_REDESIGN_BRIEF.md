# QWOMS — visual redesign brief / restore the original dashboard vision
Date: 2026-11-04
Status: Design requirement for review, **not yet implemented or user approved**.

## Original product distinction — important user clarification

The user's existing software has a dense row of work-category tabs and is **primarily a time-tracking application**. QWOMS must be original rather than a visual or structural copy. It is a connected Quality Department operations platform bringing together work-order creation and tracking, employee labor, parts/drawings, work instructions, document revisions, Excel forms in-app, photographs, files and **videos**. Use the old app's categories as a real-world work taxonomy, not as a screenshot to reproduce. Support accessible classifications/filters for Validation/FAI, Repair/Rework, Inspection, Warranty, Salt Spray Test, Development, Rebox, Test, Weight, Research, Production, Open and Completed Work Orders, while retaining the six accepted canonical top-level types with flexible subtypes and purpose-built layouts.

The signature UI should be a usable **single work-order workspace**: assignment/status, parts and approved drawing references, correctly selected instructions and Excel form, photo/file/video evidence, timeline, recorded time/measurements, and completion/reporting. This integrated experience differentiates QWOMS from the old time tracker. Keep the modern, slightly playful but rigorously professional visual direction. Wait for the user's sample validation workbook before claiming Excel visual or functional parity.

## Why this matters

The user specifically reports that the live Render interface is substantially less polished than the visuals shown in the **original QWOMS concept discussion** and that the original images inspired the entire project. The current UI may be functional but does not meet their appearance expectations. Treat visual quality and visual acceptance as an essential part of QWOMS, not an optional cosmetic cleanup.

Earlier conversation context preserved the content of the original envisioned dashboard (but **not the actual reference image pixels**):
- prominent quality-operations dashboard headed "QUALITY MANAGEMENT SYSTEM" (the actual product remains **Quality Work Order Management**, not a full QMS);
- KPI tiles for **Total Work Orders, Labor Hours, In Progress, Completed**;
- prominent category navigation/actions for **FAI, Inspections, Validations, Repairs, Re-inspections, Customer Complaints, Supplier Quality** (map these to the agreed SIX order types and subtypes rather than creating extra top-level types);
- clear **Recent Work Orders** table with work-order number, part number, type and status.

The numerical examples from the initial illustration were only concept art; use real queries in the working app, never hardcoded illustrated numbers. The original images have not been recovered and should be requested as visual references if exact matching is needed.

## Visual/UX acceptance targets

1. Transform the present prototype into a **polished desktop-first internal operations application**. Design should feel like an intentional modern product: strong typography and hierarchy, well-spaced cards and tables, refined light/dark contrast, consistent radius/spacing, purposeful icons, clear status/priority hierarchy and careful interaction feedback. Avoid a generic generated-dashboard look. Use accessible colors and contrast.
2. Main dashboard: distinctive top header with QWOMS identity, four live KPI blocks (Total Work Orders, Labor Hours, In Progress, Completed), prominent category/type/subtype shortcuts, a useful Recent Work Orders register, and a clear My Assigned Work section. Labor Hours must be sourced from genuine tracking data and labeled **not yet available** until its source is implemented; never invent or substitute estimated values. Management vs assigned-user views can be differentiated.
3. Work type screens **must visibly and functionally differ** for Validation/FAI, Inspection, Test, Repair, Weighing, Photos. Distinct compositions, contexts and fields by part family/physical part/subtype—no six identical card arrangements with only a title/color change. Show the required drawing and attached evidence naturally in each workflow.
4. Work order details: show progress, assigned employees with avatars, due/priorities, controlled drawing revisions and approval status, required instructions, task timing, actual attachments, employee-chosen filenames and activity history. Make it efficient for daily Quality Department operations.
5. Forms/Excel: provide a professional usable workspace with workbook tabs and familiar editing affordances when the licensed, proven-fidelity editor is available. Do not claim editing exists before implementation/fidelity checks.
6. Administration: clear owner-specific screens for creating users, roles, sites and per-person import/approval capabilities (all employee imports denied by default) without overwhelming technical vocabulary.
7. Mobile/tablet: sensible responsive behavior; desktop is the primary use case. Avoid horizontal clipping and inaccessible sidebar navigation.
8. Preserve backend behavior, data migration, security/CSRF/session boundaries and all accepted feature rules. UI design changes must not silently override user-chosen information.
9. Visual quality assurance: produce screenshots of actual application at 1440×900 and 1280×720 for Dashboard, Orders, six work type screens, Part Master, Administration, and a controlled form view. Perform user review/sign-off against the **original visual references** before treating design as accepted.

## Workflow

- Do **not** rush to deploy a speculative redesign to the only live demo. Build it on `development/qwoms-complete-build`, retain the one-final-PR policy and coordinate with other Codex tasks.
- Show an updated actual-browser preview/screenshot for feedback before broad styling passes. Ask the user to provide one or more original concept images if available; text-only reconstruction cannot guarantee visual fidelity.
- The user also wants a single login, complete QWOMS workflows and immediate testing. Fixing appearance must not cause functionality regression or postpone the Excel blocker indefinitely.

## Confirmed visual personality — modern, professional, subtly fun (2026-11-04)

The user clarified that the original visual references appealed to them because they add **a little fun** to an otherwise professional operations system. Do not turn QWOMS into a sterile enterprise tool or a childish, gamified app. The target is a modern, approachable, credible product people enjoy using daily.

- **Light, crisp workspace:** white cards, soft neutral/blue-gray canvas, modest depth, clean borders, readable sans-serif typography and generous but efficient spacing; balanced density for operators and managers.
- **Restrained personality:** tasteful indigo/blue primary accents with a small set of complementary, purposeful colors (e.g., green for complete/pass, amber for pending/review, red for failure/blockers, violet for validation/testing). Bright accents only where they convey work type, actions or status.
- **Engaging elements:** clear refined icons, polished task tiles, human avatars, subtle hover/selection feedback, well-crafted empty states, friendly labels and occasional micro-interactions. Avoid distracting animations, novelty emojis, mascot overload, meaningless gradients or excessive decoration.
- **Informative visuals:** functional Kanban/task lanes, concise charts, progress bars, status chips, completion percentages and activity timelines **only when actual persisted data supports them**. Never invent totals, labor hours, deadlines or trend percentages to replicate illustrative artwork.
- **High-fidelity modules:** dashboard can feel visually energetic; controlled-document approvals, drawings and validation forms must still feel rigorous, trustworthy and easy to audit. Chat should be familiar, clear and human, while remaining work-appropriate.
- **Consistency:** use one coherent design system across Dashboard, Work Orders, Projects, Parts & Drawings, Documents, Messaging and Administration, with distinctive but coordinated work-type treatments. Preserve keyboard access, contrast, responsive behavior and real task efficiency.
- **Design review:** compare actual browser screenshots against the six original user-supplied visual references (workspace Kanban, controlled-doc feature table, split-pane QMS documents, chat, module map, revision control). Use the references for creative direction, not for copying trademarks, branding or unsupported features. The screenshots show training and broader QMS controls that are outside the approved QWOMS scope.

