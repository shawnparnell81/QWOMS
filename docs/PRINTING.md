# QWOMS printing — development implementation

**Status:** Added to the long-lived development branch; not deployed to the existing Render synthetic demo. Browser and Python regression tests must pass in the preview before release.

## Printing by screen or file type

- **Any QWOMS screen** (Dashboard, Work Orders, Create Order, Projects, Part Master, Drawings, Documents, reports, admin, messaging): use **Print page** in the top-right header. Prints the current visible view, including entered-but-not-yet-submitted form field values. It does not save or submit a form.
- **Individual work orders**, all six types: use **Print work order** on the detail page or the universal top-right Print page action.
- The print stylesheet hides navigation/sidebar, buttons, chat actions, dialog controls and other on-screen chrome; printed work order tables and sections remain readable. It inserts a print heading identifying the page and current account.
- **Imported Excel workbook forms**: use **Print form** inside the workbook editor to print the currently selected sheet, including recalculated supported formulas and conditional colors. The editor synchronizes the draft then opens a dedicated print view in a new tab. The tab opens during the user gesture to avoid popup-blocker issues. Switch to another sheet to print that sheet separately. Browsers may still require popups/printing to be allowed.
- **Original PDFs and supported images**: use **Open original to print** when viewing the resource in the Validation/FAI workspace; the browser's native print dialog handles the original file.
- **Other native documents** (e.g. Word): print the current QWOMS listing or download/open the original document and use its native application print capabilities. An embedded fidelity-preserving Word print engine has not been built.

## Important limits

- Printing the current page is not the same as printing every hidden tab or the whole original multi-sheet workbook.
- Original Excel print metadata stays in the source XLSX, but browser display/print does not yet match every Excel function, font, page break, print title, chart or page setup feature. Export the original/filled XLSX and print in Microsoft Excel if exact native layout is required.
- Print actions do **not** auto-generate or change user-entered filenames, work orders, revision history or evidence. Printing is read-only. Sensitive operational pages should be printed only on approved company printers.

## Verification

- JavaScript syntax parsed successfully for changed modules: `app/static/app.js`, `app/static/workspace.js`, `app/static/print.js`, `app/static/free-editor.js`, `tests/browser/print.cjs`.
- New Playwright test: `node tests/browser/print.cjs` (requires approved synthetic browser test environment/credentials) checks dashboard printing, preservation/restoration of unsaved form data, Orders register and print-media visibility. **Not yet executed against a running preview in this task.**
- New API test: `python -m pytest tests/test_dashboard_redesign.py -q` checks actual work-order counts and completed labor hours, not invented dashboard numbers. **Not yet executed in this task.**
- Before user acceptance: print all six work-order detail layouts, controlled drawing PDFs, workbook PASS/FAIL sheets (including images), and multipage reports from a real browser. Confirm paper orientation, pagination, background color printing and basic keyboard accessibility; record differences.

The previous Render deployment remains unchanged; no PR is open. This change is for the in-progress user-approved interface redesign.
