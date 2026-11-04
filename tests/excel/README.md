# Local-only specialized Excel evaluation

This is an investigation harness, **not an application feature or deployment dependency**. Do not publish vendor trial assets or use company workbooks. Review vendor evaluation terms before use. No license key is embedded, and trial markers must remain intact.

1. Install `tests/excel/requirements.txt` in the development venv.
2. In an external temporary directory, download official `@mescius/spread-sheets@19.2.5` and `@mescius/spread-excelio@19.2.5` using `npm pack`. Extract into `spread/` and `io/`, retaining their `package/` directories and licenses. Copy `evaluate.html` into that directory. The HTML expects exactly those relative paths. It imports the native workbook into the real engine; nothing is rendered as a generic replacement form.
3. Generate the input with `.venv/bin/python tests/excel/synthetic_workbook.py '/temporary/path/Fictional Shock Validation.xlsx'`.
4. Serve that external directory on loopback port 8890 only with Python's HTTP server. Do not expose it publicly.
5. Set `QWOMS_EXCEL_INPUT`, `QWOMS_EXCEL_OUTPUT`, optional `QWOMS_CHROMIUM_PATH`, `QWOMS_EXCEL_EVAL_URL` and `QWOMS_EXCEL_SCREENSHOT`, then run `node tests/excel/evaluate.cjs` (Playwright from `tests/browser` or the development runtime).
6. Run `.venv/bin/python tests/excel/compare_roundtrip.py input.xlsx output.xlsx`. Read the actual differences. A successful export alone is not an acceptance pass.

The recorded initial configuration imports only the workbook engine and Excel IO. Additional supported modules/options and opaque-color fixtures must be investigated. Current results and limits are in `docs/EXCEL_EDITOR_FEASIBILITY.md`. Do not commit proprietary libraries or treat the fixture's openpyxl structure as proof of Excel fidelity.
