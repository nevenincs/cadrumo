---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S19'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The Consolidate the duplicate _require_transaction guard in _review_projection onto the canonical in _actions_common and ## Scope

- `src/aeat/application/ledger/_review_projection.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Consolidate the duplicate _require_transaction guard in _review_projection onto the canonical in _actions_common

## Scope

- `src/aeat/application/ledger/_review_projection.py`

## Description

- Keep the canonical `_require_transaction` in `application/ledger/_actions_common.py`.
- Remove the byte-identical copy from `_review_projection.py` and import the
  canonical from `_actions_common`; ruff pruned the now-unused
  `TX_BUCKET_NAMESPACE` / `TransactionNotFoundError` imports.

## Outcome

Two identical application-ledger guards collapsed to one; the single call site is
unchanged. The shared function is confirmed identity-equal across modules; 5
review tests pass, ruff + collect-only clean. Landed as commit `e62799969`.

## Notes

The domain-layer `domain/transactions/_service._require_transaction` (no
application namespace context) is a distinct error shape and stays separate —
application cannot be imported from domain.
