---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S15'
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
     The S15 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The Promote one canonical storage_validation_error to storage/errors.py and redirect the seven duplicate storage-module copies, removing the duplicate defs and message-key constants and ## Scope

- `src/aeat/adapters/persistence/storage/errors.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Promote one canonical storage_validation_error to storage/errors.py and redirect the seven duplicate storage-module copies, removing the duplicate defs and message-key constants

## Scope

- `src/aeat/adapters/persistence/storage/errors.py`

## Description

- Add a canonical `storage_validation_error(message)` factory plus the shared
  `_STORAGE_VALIDATION_MESSAGE_KEY` constant to
  `src/aeat/adapters/persistence/storage/errors.py`, beside `StorageValidationError`.
- In each of the seven storage submodules (`crypto/_encrypted_columns.py`,
  `envelope/_envelope.py`, `runtime.py`, `secret_store/_secret_store.py`,
  `master_key/_bucket_session.py`, `master_key/_idle_timeout.py`,
  `master_key/_recovery.py`) import the canonical factory under the existing
  private name (`storage_validation_error as _storage_validation_error`) and
  delete the local duplicate `def _storage_validation_error` and its
  `_STORAGE_VALIDATION_MESSAGE_KEY` constant.
- Normalise with `ruff check --fix` + `ruff format` (it split the aliased
  import into its own `from ..errors import (...)` statement and dropped the
  now-unused `Final` import in two files).

## Outcome

Seven byte-identical factory copies and seven duplicate constants removed for one
canonical home; all 37 call sites unchanged (alias preserves the private name).
Behaviour-preserving — 842 storage tests pass, ruff clean, collect-only clean
(855 collected). Landed atomically as commit `ed35290e1`.

## Notes

The canonical factory is public (`storage_validation_error`) and imported under a
private alias to keep call-site privacy and a zero-diff call surface. Found by the
whole-tree structural symbol sweep, not semantic search — recorded in the audit as
the higher-yield instrument for the identical-small-helper duplication class.
