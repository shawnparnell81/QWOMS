# Interactive Excel workbook editing in QWOMS

> **Historical milestone.** The owner has ruled out paid spreadsheet licenses. The active default is the working free editor described in `FREE_WORKBOOK_EDITOR.md`; commercial pricing/experiments below are retained historical evidence, not a purchase recommendation or current dependency.

A real Collabora Online Calc editor now opens inside QWOMS from an approved attached blank master. This is an implemented local synthetic-test workflow, not a fidelity certification or a change to the live Render demo. Editor support is disabled unless explicitly configured; no SpreadJS trial libraries, keys or vendor binaries are included in the QWOMS image.

## Hands-on review now

The current attached cloud environment has a synthetic review app on **http://127.0.0.1:8020** and a local office service on port 9980. These are loopback development addresses inside that environment, **not public hosted URLs and not the user's PC localhost**. Open them in the attached environment's browser. The generated review login is in the private, ignored `work/excel-editor/reviewer.credentials`; do not paste its contents into chat. The seeded work order is `VAL-SYNTHETIC-EDITOR-001` and its project is Synthetic Excel hands-on review.

1. Open the work order and choose **Open blank master in Excel editor**. Close the vendor's welcome window and optionally skip its onboarding tour. The original Shock Validation and Measurements sheets are present.
2. Enter `12` in B5: C5 calculates PASS and turns green. Enter `8`: C5 calculates FAIL and turns red. D5 retains its PASS/FAIL list validation and original error message. Formulas, worksheet tabs, merges, formatting and the embedded image are real spreadsheet content.
3. Enter your completed `.xlsx` filename in the QWOMS toolbar and choose **Save completed workbook**. The editor first persists its measurements. QWOMS then displays measured differences from the master. Review those differences, acknowledge **for synthetic testing**, and Save again. Nothing silently rewrites the original. The saved file uses the order's designated category and links to its work order/project.
4. Duplicate filenames fail instead of overwriting. Return to the order, choose **Reopen in workbook editor**, and export with an explicitly entered filename. Existing completed files stay immutable; a further permanent save needs another name. Completed/closed orders open completed workbooks read-only.
5. **Print** invokes the office engine's workbook printing, not a printout of the surrounding webpage. The tested workbook produces two PDF pages; its first page is A4 landscape and includes the measurement and calculated result.

## Reproduce a fresh local review

Install the existing Python requirements and browser test dependencies first. The script always uses an isolated SQLite file under the review root, never an inherited production DATABASE_URL.

```sh
PYTHONPATH=. .venv/bin/python scripts/run_excel_review.py
```

In a separate terminal, on a machine with the managed Docker daemon and appropriate network/CA configuration:

```sh
docker compose --env-file work/excel-editor/office-review.env -f deploy/compose.excel-review.yaml up -d
```

Do not start a second service while the current review instance already occupies port 9980. The compose file pins the official amd64 CODE manifest digest `sha256:808410e77b8695a35b93c7638fbba07c10cf0ba8307141b460248f18ab6e5c55`. In this environment, the normal large-blob download stalled; bounded HTTP Range requests through the configured proxy retrieved the same public image. Every compressed blob and uncompressed layer was checked against the official manifest/config before local loading. The resulting image ID is `sha256:751ec74aeb6d3a39f11b17a5ffe726be92eb97bfc3ccbcc41ce9b8db4e9315e0`, locally tagged `qwoms-collabora-review:verified`. A local compose override can select that verified tag via `QWOMS_REVIEW_OFFICE_IMAGE`. No network policy bypass, paid service or external deployment was used.

```sh
node tests/browser/editor.cjs
PYTHONPATH=. .venv/bin/python tests/excel/verify_editor_artifacts.py
```

The browser test uses actual keyboard entry and original validation prompts, employee naming, duplicate denial, saved-file reopening, XLSX download and the actual office PDF response. The artifact verifier checks resulting values/formulas/caches, images, names/merges/validation/printing, green/red cell pixels, master checksum and order/project links. Python inspects artifacts; it is not the editor or formula calculator. All fixtures are synthetic. The setup script's `--seed-only --review-root work/ANOTHER_REVIEW` option was separately checked to select the approved master through the real attachment rules.

## Measured results and limits

Real Chromium tests passed for `12 → PASS → RGB(0,176,80)` and `8 → FAIL → RGB(255,0,0)`. Invalid D5 input displayed the original Choose PASS or FAIL error; the valid value PASS persisted. Both the exported workbook and the export after reopening retain B5=12, the original named-range IF formula, cached PASS, D5=PASS, both sheets, the two merged regions, one image with unchanged bytes, validation, the original print titles/area and A4 landscape fit-to-width=1. The original master checksum stays unchanged. The actual office-generated PDF includes `12.00 PASS` and a 40×20 image at 96 DPI.

**Exact fidelity remains FAILED: 26 raw differences in both export and reopen/export.** Full evidence is in `docs/evidence/excel-collabora-interactive.json`. The differences include conditional fill serialization (foreground/solid representation changes to background fills), font metadata, explicit alignment defaults and row heights, header/footer margin values changing from 0.5 to about 0.511811 inches, and explicit defaults on the second sheet. These are reported, not normalized away. Not every serialization difference necessarily changes appearance, but native Microsoft Excel rendering/resizing and representative original-form acceptance have not established equivalence. Calibri is requested by the source; the official image includes Carlito/Liberation font files and no proprietary fonts were installed. No exact font rendering claim is made.

The comparator deliberately excludes measurement values because employees are supposed to change them. It measures selected structural/style features and image anchors, not every possible OOXML feature or visual difference. Its acknowledgement is permission to save a **synthetic test copy**, not approval for company use. Large forms, complex functions/charts/protection and native Microsoft Excel reopen remain acceptance work. External links, active/embedded programs and external-fetch formulas are refused rather than silently removed. Drafts expire after two hours; production retention/cleanup and resource sizing still need operational validation.

The initial automated run was invalidated by a delayed welcome overlay and incomplete typing. Its files were not accepted as proof. The corrected test explicitly closes the vendor welcome control, skips the optional tour, waits for cell selection, and independently verifies output cell values, cached results and pixels. The final evidence is from that corrected run. No trial watermark or source workbook was modified to improve results.

## Architecture and deployment controls

Migration 0010 adds employee-owned temporary workbook drafts. Their content is separate from both blank masters and completed records. A random WOPI credential is stored only as a hash, expires with its draft and is bound to the initiating revocable account session. Account deactivation/session revocation, assignment changes and withdrawn templates are checked on callbacks. Cookie/CSRF-protected application APIs control creation, launch, filing and export. WOPI has narrowly scoped bearer authentication and locks; its credentials cannot read/write any master or another employee's draft. Callback query tokens are removed from the application access-log scope. Production office/proxy logs must also redact bearer URLs.

The browser accepts save acknowledgements only from the configured editor origin and frame. Completed filing waits for the office Save acknowledgement, then checks draft version and uses the existing audited, duplicate-safe storage path. Import permissions are not required to execute an approved attached form. Assigned Production employees may edit; unassigned Production employees and other employees' draft access are rejected. Closed-order writes are blocked. General cross-site/company isolation and independent security review are not certified by these tests.

Configure `QWOMS_OFFICE_ENABLED`, office public/internal URLs, callback origin and application origin only in an approved installation. HTTPS is mandatory unless `QWOMS_OFFICE_LOCAL_DEVELOPMENT=true` is explicitly selected. The provided plain-HTTP loopback profile is **not** a production configuration.

Do not push/deploy this branch automatically. Local commits `895c099` and `19f46aa` remain preserved. Deployed `55c7b3e` and its native-IO research are preserved locally at `preservation/hosted-55c7b3e`. The histories diverge after `d58d6f0`: deployed owner permissions use `permissions`/SystemAuthority while local milestones use `capabilities`, and both define a different revision 0008. Before any hosted editor release, reconcile those histories/schemas without losing existing grants, rehearse on a backed-up isolated clone, test migrations/storage/locks and restore rollback, and obtain approval for the chosen editor deployment/license. No live Render migration, environment change, push or deployment was performed here.

## Licensing and public pricing checked 2026-11-04

- **Collabora CODE**: the upstream [COPYING](https://github.com/CollaboraOnline/online/blob/main/COPYING) specifies MPL 2.0. The official [CODE page](https://www.collaboraonline.com/code/) and [subscriptions](https://www.collaboraonline.com/subscriptions/) list the development/home/testing edition as free and do not recommend it for production. MPL notices/source obligations apply to covered code if distributed/modified; no vendor code is bundled or modified here. Local synthetic testing incurred no license purchase. CODE's free status is not a support/SLA or fidelity guarantee.
- **Supported Collabora Online**: the official subscriptions page lists Business up to 99 users at **USD $3.40 per user/month** (also €3 / £2.60) and Enterprise 100+ users at a custom quote, with support/security/update services. QWOMS custom WOPI embedding, applicable minimums, billing period, deployment footprint and final total need a written vendor quote/terms confirmation; the displayed number is not a purchased QWOMS license or final quote. Vendor contact/purchase/deployment requires user authorization; none was made.
- **SpreadJS**: official [pricing](https://developer.mescius.com/spreadjs/pricing) lists an internal/non-commercial developer + one annual hostname bundle at **USD $1,999**, and a separate annual hostname at **$1,499** (3–5 hostnames $4,999). Developer and deployment licensing are separate concepts; optional add-ons may cost more. The Designer Ribbon deployment add-on is listed at $1,299 per hostname/year if selected. Verify developer/automated-device seats, native Excel IO/modules, multi-site/domain/staging rights, renewals and taxes in a written quote. The inspected evaluation EULA is time-limited and prohibits commercial distribution/use under evaluation; its files remain outside the app/deployment. No purchase or deployment is authorized by this work.

The legacy SpreadJS image-import option was retested with unchanged synthetic originals: both settings retain zero pictures and black conditional fills, with 20 raw differences. The fetched deployed branch's native IO research is a different API path: it retains image bytes but still reports conditional-format/anchor/print differences; those findings were not overwritten or misrepresented as resolved. This implementation chooses a real alternative editor rather than shipping a failing trial SDK.

**Next action:** the Quality Manager can now perform the local synthetic hands-on workflow above. After feedback, obtain approval for an isolated hosted review deployment and the selected production editor terms, reconcile the deployed/local schema histories on a restored clone, and only then propose a concrete deployment/rollback change. Exact fidelity and native Excel acceptance remain explicit gates.

## Integrated workspace follow-up

The Validation/FAI screen now embeds this editor with persistent context and original equipment-PDF upload/viewing. See `VALIDATION_WORKSPACE_IMPLEMENTATION.md` for dynamic XLSX import/matching, screenshots and complete tests. The comparator now examines all styled cells, replacing the earlier fixed synthetic probes. The latest standalone shock run measures **31** raw differences (integrated shock30, pump21, injector15, previously unknown three-sheet layout25); the historical 26-difference report above remains preserved under its narrower comparator. Exact fidelity is still failed, despite verified measurements/formulas/colors/images/printing. No new licensing approval or deployment is implied.
