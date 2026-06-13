---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S06'
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
     The S06 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The Add one shared resolve_repository_bucket_id helper parameterised by error_type as the single explicit-or-active-bucket resolver and ## Scope

- `src/aeat/core/identity/_bucket.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add one shared resolve_repository_bucket_id helper parameterised by error_type as the single explicit-or-active-bucket resolver

## Scope

- `src/aeat/core/identity/_bucket.py`

## Description

- Add `resolve_repository_bucket_id(bucket_id, *, error_type)` to
  `src/aeat/core/_bucket_pointer_io.py` (alongside `resolve_active_bucket_id`),
  carrying the shared `no_active_profile_bucket` message key and the blank /
  missing reason contexts.
- Type the error factory parameter as `type[AeatError]` via a `TYPE_CHECKING`
  import (annotation-only; no runtime import, no cycle), since the helper only
  constructs the passed-in `error_type`.
- Export the helper through `aeat.core` (`__init__` TYPE_CHECKING import block,
  `__all__`, and the lazy `__getattr__` allowlist).

## Outcome

Single canonical home for the explicit-or-active-bucket resolution now exists
in `core`. Import smoke-test green; ruff clean.

## Notes

The originating Step row guessed the scope path as
`src/aeat/core/identity/_bucket.py`; the correct home is
`src/aeat/core/_bucket_pointer_io.py` (it owns `resolve_active_bucket_id`, the
primitive this helper composes). Recorded here rather than rewriting the Step
row.
