---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S13'
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
     The S13 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Migrate the four locale catalogues for the ledger evidence and audit families through the locales CLI and ## Scope

- `src/cadrumo/locales/en.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Migrate the four locale catalogues for the ledger evidence and audit families through the locales CLI

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Remove the orphaned `cli.ledger.link.evidence_id_help` and `cli.ledger.link.errors.missing_target` keys across all four locale catalogues (their `tr()` calls were removed with the invoice-only link cutover in S07).
- Update `cli.ledger.link.help` and `cli.ledger.link.errors.invoice_not_found` values in all four catalogues to stop citing the retired `link --evidence-id` grammar and route purchase-evidence attachment to `aeat app ledger attach`.
- Land the change own-keys-only via a HEAD-anchored apply-cached drive: edit HEAD-clean copies in scratch, generate per-language patches, `git apply --cached` (index) + `git apply` (working tree), so the operator's live P04-door passphrase/recovery locale WIP in the same four files is not swept. Verified the cached diff carried only the link keys and zero passphrase/recovery keys; validated the edited YAML parses and the link keys are clean in all four languages.

## Outcome

- The four catalogues no longer carry the retired link-evidence keys, and the link help/error prose routes evidence to `attach`; ledger-evidence-atomicity reaches 17/17. Commit `59ba31fcef`.

## Notes

- INCIDENT (adjudicated, accepted, no data lost): the finalization used `git commit -- <4 .yml>` (a pathspec commit), which — per the `pathspec-commit-takes-working-tree` behaviour — captured the WORKING-TREE content of those paths, bypassing the correct apply-cached index. As a result `59ba31fcef` captured the operator's live P04-door passphrase/recovery locale keys in addition to the intended link keys. Scope contained: the commit touched only the four `src/cadrumo/locales/*.yml`; the operator's code door WIP (`_contract.py` and everything else) was untouched and remained uncommitted. NO data was lost — the operator's locale keys are present in HEAD, mis-attributed to this SHA rather than a later operator commit. The provenance defect is cosmetic; the operator's door completes normally when they commit their code, which must NOT re-add the locale keys (already in HEAD). Team-lead adjudicated ACCEPT: `59ba31fcef` is buried under two later commits, so `--amend` is impossible and a revert/rebase would risk losing the operator's keys (their working tree no longer carries them). The correct finalization was a verified NO-pathspec index commit; immediate honest reporting and stopping before any reset/revert/amend was the intended discipline.
