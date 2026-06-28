---
step_id: S665
tags:
  - "#exec"
  - "#codebase-solidification"
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-31-codebase-solidification-audit]]"
---

# codebase-solidification W26.P58.S665 — Invoice-import dict-splat cluster

## Outcome

`InvoiceRowPayload` TypedDict already existed in `_importing.py`. The `[misc]`
errors arose from splatting untyped JSON/CSV dicts into the TypedDict constructor.

Fix: replaced all three `InvoiceRowPayload(**...)` constructor splats with
`cast(InvoiceRowPayload, dict(...))` at the three decode boundaries:

- Line 126: JSON object decode
- Line 128: JSON array item decode
- Line 132: CSV row decode

`CAST-RATIONALE-WIRE-PAYLOAD-*` markers added inline. `cast` added to
`typing` import. All three `# type: ignore[misc]` removed.

Design choice: `cast` at the decode boundary (TypedDict already present;
explicit-kwargs approach would require enumerating all `NotRequired` fields
for each decode path, adding fragility vs. the TypedDict boundary).

Allowlist paydown: 3 entries removed.
