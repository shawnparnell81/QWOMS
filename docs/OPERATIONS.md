# Labor, pallets and chargeback ledger milestone

Use **Labor & pallets** and choose a work order. Record your own timer, or a timezone-aware historical start plus duration. The server prevents overlapping intervals and simultaneous timers for one employee; different employees may work concurrently. Recorded span is the earliest-to-latest completed labor interval, while person-hours sum each employee's duration. Recorded span is not the entire work-order lifecycle elapsed time.

Management may correct completed time with an audit reason and approve recoverable labor at an explicit hourly rate in cents. A correction removes approval and rate so the entry requires approval again. Running timers cannot be approved, and work orders cannot close with an active timer. New work on completed/closed orders is refused. Production employees can use operational records only on their assigned orders. Current timer ownership is enforced by the backend.

Register user-entered pallet IDs, quantities, original bins and condition. Record each movement with destination, disposition and reason; choose Returned and confirm the return bin/reason. Historical movements remain intact. A stale current-location assertion fails and requires refresh. This milestone moves whole pallets; it does not yet split pallets or adjust inventories.

Management separately records actual/estimated internal forklift seconds. No driver accounts exist. That ledger is omitted from the project chargeback query and creates no report lines, even at zero cost. Labor activities exclude forklift and recoverable expense descriptions explicitly identifying forklift are rejected. Management enters replacement-part and expense quantities/cents, then explicitly approves them.

Project chargebacks show approved labor and costs across currently linked orders. Hourly rates are stored on approved labor entries, the employee department is captured when labor is recorded, and each labor line rounds to cents using decimal half-up arithmetic. Money values are integer cents; no supplier currency/tax policy is assumed. The on-screen report uses the same backend calculation and includes no forklift ledger data.

## Still mandatory before full operations acceptance

Task assignment/history and task-linked time, complete work-order lifecycle elapsed timing, inactive employee timer recovery, split-pallet/material inventory reconciliation, supplier identity/currency/rate policy, report evidence/packet linking, downloadable Word/PDF/Excel reports, approval/adjustment acceptance at scale, and cross-site record isolation remain unfinished. This is an integrated ledger milestone, not completion of all accepted operations requirements or production approval. Exact in-app Excel fidelity remains a separate failed gate; completed-file upload does not satisfy it.
