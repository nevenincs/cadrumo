---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S11'
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
     The S11 and 2026-06-30-ledger-add-idempotency-plan placeholders are machine-filled by
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
     The Update the --idempotency-key CLI help text through the locale CLI to state that a stable key is required per logical add and the keyless path is append-only and ## Scope

- `src/aeat/locales/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the --idempotency-key CLI help text through the locale CLI to state that a stable key is required per logical add and the keyless path is append-only

## Scope

- `src/aeat/locales/`

## Description

- Rewrite `cli.ledger.add.idempotency_key_help` in en/es/ca/hu to state the retry-safety contract: passing the same key again is a safe no-op so retries do not duplicate the row, and omitting the key appends a deliberate duplicate.

## Outcome

Landed in commit `c8b592971`. Hand-edited at the existing key (the locale CLI's full reconciliation would otherwise pull unrelated peer-campaign keys into the commit); parity and honesty gates pass.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
