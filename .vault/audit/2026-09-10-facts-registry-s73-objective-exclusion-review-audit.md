---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:7e2a1388e7c7ef3c89650626279997f5c23bba31b12e0d3be7f68e30845132ee'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---



# `facts-registry` audit: `S73 objective-estimation exclusion review`

## Scope

Reviewed W03.P13.S73 only: Article 31 and DT 32 captures and source rows, authored temporal threshold facts, final legal-parameter adapter retirement, and focused tests. Excluded concurrent loader and authority work.

## Findings

### final-adapter-retirement-leaves-provider-tests-impossible | high | Existing provider tests assert the retired adapter's facts

S73 correctly removes the final four IDs from `LEGAL_PARAMETER_FACT_IDS`, making the adapter empty. `test_legal_parameter_provider.py` still asserts four IDs, resolves one retired ID through the empty catalogue, takes the first element of that empty catalogue, and indexes the retired fact family. The dedicated authored-fact test passes, but the existing provider suite cannot pass after the retirement. Current collection is additionally obstructed by the unrelated concurrent loader relocation; that does not remove the stale assertions, which fail once imports are restored.

## Recommendations

Resolve `final-adapter-retirement-leaves-provider-tests-impossible` before accepting S73. Replace adapter-projection tests with an explicit empty-provider/retirement contract, remove scalar-resolution assumptions belonging to the former adapter, and retain only provider registration and empty-result behavior that remains meaningful.
