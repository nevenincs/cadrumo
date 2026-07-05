---
tags:
  - '#exec'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S12'
related:
  - "[[2026-06-26-binding-adr-corpus-reconciliation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-adr-corpus-reconciliation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-06-26-binding-adr-corpus-reconciliation-plan placeholders are machine-filled by
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
     The RE-TARGET the 13 cross-campaign Status pointers from the apex to the phase+foundational ADRs per the re-target mapping (source-kind to phase-2.1 and ## Scope

- `carry to live-iva-compensation-wallet`
- `resolver-contract to calculation-source-connectivity`
- `future phase ADRs named in prose)`
- `.vault/adr/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# RE-TARGET the 13 cross-campaign Status pointers from the apex to the phase+foundational ADRs per the re-target mapping (source-kind to phase-2.1

## Scope

- `carry to live-iva-compensation-wallet`
- `resolver-contract to calculation-source-connectivity`
- `future phase ADRs named in prose)`
- `.vault/adr/`

## Description

- Reconstruct the execution record for the already-checked S12 row.
- Confirm the cross-campaign status-pointer retargets from the apex to phase and foundational ADRs.
- Verify current ADR status text for the carry anchor, routing/carry, carry-continuity, and per-ADR rework set.

## Outcome

- S12 is backed by landed evidence. The corpus no longer points at the rejected
  apex as canonical authority; affected status blocks name phase 2.1 for
  source-kind, the live IVA wallet ADR for compensacion carry, future phase 2.2
  for resolver-contract folding, future phase 2.3 for fold-in/carry, and future
  phase 2.4 for vocabulary/CLI.
- Representative evidence commits include `4c0e76a55d`, `d644ff01dc`,
  `7f6ce3d21e`, `c9432500c9`, `c2ff972dfd`, `cd0bc3e00d`, `648f290cb6`,
  `0ebf3fabe0`, `e511d8fed3`, `2ba5c1cc8d`, `ef2f812532`, `83e6a083a7`,
  `ce0f6990c8`, and `3edc8eba23`.
- No source code or plan checkbox was changed in this reconciliation pass.

## Notes

- Reconstructed on 2026-07-05 because the step was checked without an exec record.
- Evidence commands included `rg -n "central apex doc|future phase-2" .vault/adr`
  and targeted `git blame` over the status blocks for the carry anchor, routing
  carry, and carry-continuity ADRs.
