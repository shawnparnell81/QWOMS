# Local-only specialized Excel evaluation

This is an investigation harness, **not an application feature or deployment dependency**. Do not publish vendor trial assets or use company workbooks. Review vendor evaluation terms before use. No license key is embedded, and trial markers must remain intact.

1. Install `tests/excel/requirements.txt` in the development venv.
2. In an external temporary directory, download official `@mescius/spread-sheets@19.2.5` and `@mescius/spread-excelio@19.2.5` using `npm pack`. Extract into `spread/` and `io/`, retaining their `package/` directories and licenses. Copy `evaluate.html` into that directory. The HTML expects exactly those relative paths. It imports the native workbook into the real engine; nothing is rendered as a generic replacement form.
3. Generate the input with `.venv/bin/python tests/excel/synthetic_workbook.py '/temporary/path/Fictional Shock Validation.xlsx'`.
4. Serve that external directory on loopback port 8890 only with Python's HTTP server. Do not expose it publicly.
5. Set `QWOMS_EXCEL_INPUT`, `QWOMS_EXCEL_OUTPUT`, optional `QWOMS_CHROMIUM_PATH`, `QWOMS_EXCEL_EVAL_URL` and `QWOMS_EXCEL_SCREENSHOT`, then run `node tests/excel/evaluate.cjs` (Playwright from `tests/browser` or the development runtime).
6. Run `.venv/bin/python tests/excel/compare_roundtrip.py input.xlsx output.xlsx`. Read the actual differences. A successful export alone is not an acceptance pass.

The recorded initial configuration imports only the workbook engine and Excel IO. Additional supported modules/options and opaque-color fixtures must be investigated. Current results and limits are in `docs/EXCEL_EDITOR_FEASIBILITY.md`. Do not commit proprietary libraries or treat the fixture's openpyxl structure as proof of Excel fidelity.

## Native IO diagnostic (19.2.5)

The additional official `@mescius/spread-sheets-io` package exposes workbook `.import()`/`.export()` and is distinct from legacy `@mescius/spread-excelio`. Evaluate it locally with matching print/shapes modules; do not mix versions, ship trial assets or remove evaluation markers. Extract official npm tarballs to `spread/`, `native-io/`, `print/`, `shapes/` under the temporary evaluation directory, retaining vendor EULAs. Copy `evaluate-native.html` there and point `QWOMS_EXCEL_EVAL_URL` at that local page. Review required module/add-on licensing before any commercial integration.

Generate separate fixtures with `synthetic_workbook.py /tmp/opaque.xlsx --opaque-colors` and `/tmp/both.xlsx --opaque-colors --matching-conditional-background`. These flags create new synthetic compatibility cases; never change an original company master to hide an incompatibility. Keep the original foreground-only and six-digit cases in the acceptance matrix.

The comparator now reports `comparison_version: 2` and checks image anchor types, cell offsets/extents and edit behavior in addition to image bytes/dimensions. V1 evidence counts omitted those anchor changes; compare counts only with the same signature version and input. Neither comparison calculates formulas or establishes visual/print fidelity. Native IO preserved this sample's image bytes and start cell, but changed the anchor representation. Its foreground-only conditional fills failed; the separate matching-background case retained fills. See the feasibility record for actual results and remaining failures.
