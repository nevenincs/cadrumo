---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S19'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-ports-inversion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-07-02-arch-remediation-ports-inversion-plan placeholders are machine-filled by
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
     The Assert zero production domain-to-adapters pinned entries remain in the ledger via the count-ratchet gate landed by the gates-ratchet campaign and ## Scope

- `.importlinter` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assert zero production domain-to-adapters pinned entries remain in the ledger via the count-ratchet gate landed by the gates-ratchet campaign

## Scope

- `.importlinter`

## Description

- Assert zero production `domain -> adapters` pinned entries remain in the importlinter ledger now that every domain repository sits behind a port.
- Add `test_zero_production_domain_to_adapters_edges` to the ledger gate: it scans every contract's ignore edges, filters out test-file sources (`.tests.` / `.conftest`), and asserts the remaining production `domain.* -> adapters.*` set is empty — a hard zero, not a ratchet.
- Keep the existing `test_domain_to_adapters_pin_count_does_not_grow` ratchet for the test-edge total.

## Outcome

Complete in commit `be5ca85b22`. Grep of the ledger confirms zero production `domain.* -> adapters.*` edges; the new gate passes (ledger test 4/4 green). `lint-imports` shows no `domain -> adapters` violation anywhere in the broken layered output (the layered breakage is the pre-existing, separately-tracked application -> adapters wiring). A production domain -> adapters edge reappearing now fails this gate loudly rather than being absorbed as an ignore.

## Notes

Landed together with S20 in the same closeout commit `be5ca85b22` (both edit `.importlinter`; S19 also edits the ledger test). Committed with an explicit pathspec verified via `git diff --cached` before commit.
