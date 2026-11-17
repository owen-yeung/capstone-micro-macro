# Bid price / duration field audit

Benchmark rows: 499

| Field | Non-empty rows | Projects | Comparable now |
|---|---:|---:|---|
| contract_amount | 126 | 68 | False |
| contract_duration | 98 | 61 | False |
| actual_duration | 66 | 47 | False |

Frozen-28 simulated bids: 295; quotation parsed 295; schedule parsed 200.

Status: `blocked_pending_benchmark_field_confirmation`.

Required before claiming reasonableness validation:

- Confirm currency and amount unit for contract_amount vs simulated quotation
- Confirm whether contract_duration is calendar months and package-scoped
- Join only same case + same role/package; do not compare whole-project totals to package bids
- Exclude rows marked 无法获取 or otherwise non-numeric
