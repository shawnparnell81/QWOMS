# Early specialized browser Excel feasibility — 2026-11-04

**Result: candidate identified and exercised; exact fidelity FAILED in this tested configuration. In-app workbook editing is not delivered or approved for launch.** No vendor code/license key is committed or included in the QWOMS application image. The evaluation ran only on loopback with a synthetic workbook.

## Candidate and evidence

MESCIUS **SpreadJS 19.2.5** plus **Client-Side Excel IO 19.2.5** is a specialized browser spreadsheet engine, not a generic HTML grid. Official npm packages document native XLSX input/output, formulas, conditional formatting, validation and printing. Its real browser engine imported the fixture, calculated `IF(B5>=AcceptanceMinimum,"PASS","FAIL")`, produced PASS at 12 and FAIL at 8, and exported an XLSX. A library API was used to change the synthetic input value in Chromium; a complete employee editing interface was **not** integrated or tested.

Sources inspected: [SpreadJS package/readme](https://www.npmjs.com/package/@mescius/spread-sheets/v/19.2.5), [Excel IO package/readme](https://www.npmjs.com/package/@mescius/spread-excelio/v/19.2.5), each package's `SPREADJS-EULA.pdf` (February 2026 text), and shipped TypeScript API declarations for `IO.open`/`IO.save`. Direct vendor websites were denied by this environment's network policy, so current pricing and broader supported-feature details were not independently verified. An attempted official ONLYOFFICE README URL returned 404; no claim is made about that editor's tested compatibility or licensing.

## Actual synthetic round-trip

The committed generator includes two worksheets, named-range formula, PASS-green/FAIL-red conditional rules, merged ranges, dimensions, validation/dropdown, image, freeze panes, print area/titles, A4 landscape and fit settings. Original and exported workbooks were inspected with openpyxl **after** the real browser editor processed them; openpyxl was not used as a stand-in for editing or formula calculation.

- Passed in this sample: import/export execution, formula calculation in the browser, formula text/named range, merges, validation ranges/formula/error metadata, print area and freeze panes.
- The comparison reported **26 feature differences**, including an added Evaluation Version sheet, changed font/color metadata and explicit row heights, column widths `28 → 28.00390625`, `18 → 18.00390625`, `20 → 20.00390625`, missing image (`1 → 0`), lost landscape/A4/fit/title print properties, and changed conditional-fill metadata (green/red became black in the exported rules).
- The source fixture used openpyxl's six-digit RGB inputs, which serialize with `00` alpha. This may explain some color differences; it does not justify ignoring them. Future tests must cover both opaque Excel ARGB colors and this representation. Additional vendor printing/picture modules or supported import/export options also need investigation before assigning a root cause to image/print loss.
- Evidence is in `docs/evidence/excel-trial-roundtrip.json`. Differences are reported explicitly, not normalized away to make a passing test. Evaluation artifacts are not a production-quality export.

## Licensing and deployment

The inspected EULA defines a developer to include an automated device using the software. It describes developer-seat licensing and separate annual/perpetual deployment licensing covering the purchased hostnames/domains/applications; add-ons may need separate licenses. Section 3 limits evaluation to 30 days and prohibits distribution or commercial use of software developed under the evaluation license. Trial output is visibly modified by an evaluation sheet. Do not remove the marker, invent a key, or ship this trial with the hosted demo.

Obtain written vendor confirmation of the correct developer/automated-agent, deployment, domain, add-on and internal multi-site terms and quote **before** commercial integration. No purchase, paid service or license commitment was made. Free-only Render authorization does not authorize buying an Excel editor. A local evaluation is not a deployment license.

## Next acceptance gate

Evaluate a correctly configured licensed/trial environment with required modules and representative synthetic cases, then company-approved representative original forms before any operational pilot that depends on in-app Excel. Test real user edits, calculations, visible PASS/FAIL colors, merged geometry, validations, images, print/PDF layout, worksheets/names, and Microsoft Excel reopen/round-trip behavior. Compare semantic properties and rendered output; also test unsupported functions, external links, macros, protection and large workbooks. Document every incompatibility. No lossy generic-grid fallback is acceptable. All accepted Excel requirements remain release-critical under AGENTS.md.
