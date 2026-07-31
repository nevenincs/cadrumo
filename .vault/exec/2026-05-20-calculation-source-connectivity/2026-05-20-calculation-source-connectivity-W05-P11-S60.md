---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:3bf4cd7c097e3f08cdff426d1f4ea01137ff23f696211a3a7663d740c76701fc'
step_id: 'S60'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Run calculation grounding audit for provenance and legal refs

## Scope

- `src/aeat/application/modelo`

## Description

- Run the calculation-grounding audit on the settled registry: confirm provenance / legal_refs / source_refs are preserved through every calc-source boundary.

## Outcome

PASS — 25/25 green. The typed `CasillaObservation` envelope carries operand_refs/operand_values/legal_refs/source_refs across the domain persistence boundary; the revision `source_provenance` survives the encrypted secure-object roundtrip with a corrupt-payload anti-tautology proof; ledger filing evidence preserves per-row legal_refs/source_refs; and the source-mesh calculation path preserves provenance end to end. No grounding gap on the calc-source surface. Recorded in the campaign closeout audit.

## Notes

Run in the settle-window once the modelo-145 export write paused and the registry loaded stably (no `RegistryLoadError`). No code action — grounding invariants hold.
