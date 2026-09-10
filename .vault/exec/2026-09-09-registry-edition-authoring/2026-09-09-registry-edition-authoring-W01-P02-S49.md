---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:f02b6f1c2690e9ff5b4675460601416846275610aebb40fab35f35e14ba62e46'
step_id: 'S49'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] DONE. The chaining tool was rewritten and the corpus restated: 2,509 unchainable rather than 2,734, and 273 contradicted chains rather than 345 or 260. Two corrections it surfaced must carry into the seeder. First, the box number must come from the dedicated printed-number field ONLY — falling back to the record-design metadata field when it holds a plain integer reintroduces the original error, because a one-byte wire campo declares exactly that, and it produced a false refusal. Second, the modelo-level tripwire must require a substantial predecessor set and bounded expansion, or it fires on ordinary growth where a small edition precedes a large one and wrongly holds every chain in four modelos.

## Scope

- `dev/registry/analysis`

## Changes

- `M` `.vault/plan/2026-09-09-registry-edition-authoring-plan.md`

## Notes

The rewritten chaining tool is a scratch script, not a committed one. Its two corrections — box number from the dedicated printed-number field only, and a tripwire needing a substantial predecessor set — were carried into the S06 Step row.
