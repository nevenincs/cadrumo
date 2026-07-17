---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Migrate the ledger evidence and audit family help and risk metadata to the accepted grammar and ## Scope

- `src/cadrumo/application/operator_surface/_help.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the ledger evidence and audit family help and risk metadata to the accepted grammar

## Scope

- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Remove the orphaned `modelo.audit.replay` command-risk declaration from `_risk_table.py`.
- Remove the never-emitted `MODELO_AUDIT_REPLAYED` (`modelo.audit.replayed`) member from the `BucketEventType` enum (zero consumers; the report-only replay verb emitted a command envelope, not this event).

## Outcome

- The operator help/risk surface no longer carries any reference to the retired replay verb; the `ledger.link` risk entry is unchanged (link is retained, now invoice-only). Risk-table parity + operator-surface contract suites pass on this surface (58 passed; the lone failure is exec-authcert-p04's `config rekey`->`config passphrase change` custody rename, out of this feature). Buckets domain suite 19 passed; ruff clean. Commit `d001678a0e`.

## Notes

- `_help.py` carried no removed-grammar references (the audit/link help text lives in the locale catalogues and CLI decorators, addressed in S13/S07).
