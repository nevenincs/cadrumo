---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S12'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-add-idempotency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-06-30-ledger-add-idempotency-plan placeholders are machine-filled by
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
     The Update the agent-harness ledger persona or skill instruction to mandate passing a stable idempotency key on every ledger add, citing only the live CLI surface and ## Scope

- `src/aeat/_data/agent/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the agent-harness ledger persona or skill instruction to mandate passing a stable idempotency key on every ledger add, citing only the live CLI surface

## Scope

- `src/aeat/_data/agent/`

## Description

- Add a ledger-groomer persona instruction mandating a stable `--idempotency-key` on every `aeat app ledger add`, so an uncertain retry is a safe no-op rather than a duplicate row, and to omit the key only for a deliberate genuinely-identical movement.
- Add `add` to the persona's ledger tool scope.

## Outcome

Landed in commit `497ccbb81`. Cites only the live CLI surface; the rule-surface conformance gate (`test_rule_surface_conformance.py`) passes.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
