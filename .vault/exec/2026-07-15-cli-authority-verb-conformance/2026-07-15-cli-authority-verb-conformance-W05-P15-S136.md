---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S136'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S136 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Replace verify-recovery terminology with config recovery verify in the recovery contract and ## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace verify-recovery terminology with config recovery verify in the recovery contract

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`

## Description

- Read the recovery contract in the named facade module and confirm the retired verify-recovery verb terminology is gone.

## Outcome

The named surface cites the accepted `aeat config recovery verify` verb in its periodic custody-test contract, and no `config verify-recovery` terminology survives in the module.

The internal function name that verifies a recovery mnemonic is a domain-layer symbol rather than operator verb terminology, so it is correctly untouched by this Step; the Step governs the cited CLI grammar, not the name of the function implementing the check.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
