---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S60'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S60 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Run calculation grounding audit for provenance and legal refs and ## Scope

- `src/aeat/application/modelo` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run calculation grounding audit for provenance and legal refs

## Scope

- `src/aeat/application/modelo`

## Description

- Run the calculation-grounding audit on the settled registry: confirm provenance / legal_refs / source_refs are preserved through every calc-source boundary.

## Outcome

PASS — 25/25 green. The typed `CasillaObservation` envelope carries operand_refs/operand_values/legal_refs/source_refs across the domain persistence boundary; the revision `source_provenance` survives the encrypted secure-object roundtrip with a corrupt-payload anti-tautology proof; ledger filing evidence preserves per-row legal_refs/source_refs; and the source-mesh calculation path preserves provenance end to end. No grounding gap on the calc-source surface. Recorded in the campaign closeout audit.

## Notes

Run in the settle-window once the modelo-145 export write paused and the registry loaded stably (no `RegistryLoadError`). No code action — grounding invariants hold.
