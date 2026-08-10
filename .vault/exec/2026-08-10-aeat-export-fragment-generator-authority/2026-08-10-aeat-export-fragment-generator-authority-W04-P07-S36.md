---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d990aa50150878790d9ab01260f286b578373a044afaecacbaa30974b95043a5'
step_id: 'S36'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Replace the spanning Modelo 303 revision with five explicit revision/source bindings: `2023`, `2024-hasta-08-y-2t`, `2024-desde-09-y-3t`, `2025`, and `2026-y-siguientes`. Prove production period-token selection at every early, late, annual, and future boundary, negative cross-token refusal, year-only 2024 ambiguity refusal, and exactly one matching record-design source reference per selected revision without a date-only selector, source-period duplication, alias, bridge, or legacy fallback

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Replace the spanning Modelo 303 registry tree with five explicit record-design revisions and exact quarterly and monthly selector partitions.
- Bind every new revision to its unique official source and parity fixture; remove the retired spanning revision without an alias, bridge, or fallback.
- Validate period-wise cross-model source coverage through the canonical relation validator, including the historical observation boundary.
- Correct the Módulos legal/source authority for 2023 and 2024 and replace the fabricated HAC/819/2024 authority with the official BOE-A-2024-16129 article evidence, its canonical LF corpus file, and regenerated extraction sidecars.
- Keep HAC/819/2024 only as late-2024-and-later record-design grounding; remove it from formula, casilla, and extraction-profile facts where it does not establish a calculation value.
- Add negative source, selector, legal-window, legacy-id, and relation-coverage assertions that fail if a retired or date-only surface reappears.

## Outcome

Modelo 303 now selects exactly one concrete revision and one concrete record-design source for each supported filing token: 2023, January through August or first and second quarter 2024, September through December or third and fourth quarter 2024, 2025, and 2026 onward. The source selector cannot substitute the retired spanning revision, a date-only window, or an unrelated source.

The correction also removed the false BOE-A-2024-6840 authority and its fabricated corpus from live runtime data. The official replacement is BOE-A-2024-16129, published 5 August 2024 and effective 6 August 2024; its article unit is scoped only to the record-design modification. A structural live-surface scan found no retired M303 revision, old HAC identifier, old BOE identifier, or obsolete corpus artifact.

Focused verification passed:

- Complete Modelo 303 registry suite: 48 passed.
- Relation closure and handoff suites: 26 passed.
- Catalogue applicability, law coverage, and coherence gates: 3 passed.
- Legal required-text and anchor verification gates: 6 passed.
- Normative corpus LF and extraction-sidecar freshness gates: 3 passed.
- Scoped Ruff and basedpyright: clean with zero errors and warnings.
- Independent Luna review: no critical, high, or medium findings.

## Notes

- Historical execution, ADR, and plan records retain their original references to the retired revision and fabricated authority. They are archival evidence rather than live code or registry data and were deliberately not rewritten in this step.
- The broader relation-closure suite remains blocked by unrelated Modelo 349 export-layout drift. The revision-span test timed out, and the transitional-rate suite remains blocked by unrelated `ModelRevision` export-layout drift; neither was masked or changed here.
- No compatibility path, legacy alias, bridge, or fallback was added.
