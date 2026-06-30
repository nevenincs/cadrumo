---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S16'
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
     The S16 and 2026-06-30-ledger-add-idempotency-plan placeholders are machine-filled by
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
     The Add a strict Transaction save-load-equality roundtrip plus anti-tautology proof with the content fingerprint stamp populated non-default and ## Scope

- `src/aeat/application/ledger/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a strict Transaction save-load-equality roundtrip plus anti-tautology proof with the content fingerprint stamp populated non-default

## Scope

- `src/aeat/application/ledger/tests/`

## Description

- Add a create-path test proving a manually-created row's content fingerprint is non-default and survives an encrypted `TransactionCatalogueRepository` reload.

## Outcome

Landed in commit `3d8a6c14b`. The strict save->load->equality roundtrip and anti-tautology proof for the `Transaction` persistence boundary (including `import_fingerprint` non-default) already exist in `test_repository_roundtrip.py` and stay green; this step adds the create-path fingerprint-survival proof on top.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
