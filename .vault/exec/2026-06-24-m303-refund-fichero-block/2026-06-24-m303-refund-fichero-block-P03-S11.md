---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-06-25'
modified: '2026-06-25'
step_id: 'S11'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---




# Add an end-to-end refusal case asserting a refund disposition with an empty refund-account is refused, not emitted as an empty DID page

## Scope

- `src/aeat/application/modelo/tests`

## Description

- Confirm the P02 unit coverage in the modelo export test exercises the refund-account refusal only at the component level (the header composer plus the registry render), not the full public export path.
- Add a dedicated end-to-end refusal test in a new file under the modelo tests folder, distinct from the P02-entangled export test, driving the full public export path.
- Seed a real registry-backed, engine-computed, verified-complete negative-credit Modelo 303 revision for a REDEME-enrolled filer using the shared non-entangled public helpers (first-period wallet reconciliation, calculate, cross-period clean-state seeding, verify), reusing the refund-election e2e idiom.
- Assert the engine produced a genuine negative result and that the shared disposition resolver classifies the verified revision as a refund (devolucion) — never hand-forcing the disposition.
- Drive the full public export with a REDEME profile carrying NO refund account and assert the typed refund-account-missing error is raised AND neither the operator-visible output nor the atomic-rename .tmp sidecar is written.

## Outcome

- The new end-to-end test passes: the full export path refuses a refund filing with no account on file before any byte is written, so no empty cuenta-devolucion block reaches disk.
- The test is non-tautological: the negative result is engine-produced, the refund disposition is read from the real resolver, and the refusal plus the no-bytes-written guarantee are asserted against the real public export.
- ruff, ruff-format, and ty are clean on the new file.

## Notes

- S11 needed a NEW file: the P02 unit test drives the header composer and the registry render directly, so it proves the refusal logic but not the full public export behaviour — specifically that no fichero (and no .tmp sidecar) is written. The new e2e covers exactly that public-path guarantee. The new file reuses only shared public helpers and does not import the P02-entangled private export-test helpers.
- The export header composer requires the operator name facts (surnames and name) before reaching the refund-account block, so the seeded operator profile carries those; the absent fact under test is deliberately the refund account alone.
