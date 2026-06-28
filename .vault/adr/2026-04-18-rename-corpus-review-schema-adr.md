---
tags:
  - '#adr'
  - '#rename-corpus-review'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-rename-corpus-review-research]]'
---

# `rename-corpus-review` adr: rename corpus review fields to definition-scoped names | (**status:** `accepted`)

## Problem Statement

Issue `#225` must free the bare `reviewed_by` namespace before the Kent review
workflow lands. Today `CasillaRecord`, `Manual`, `Section`, and `Rule` all use
`reviewed_by` / `reviewed_at` for developer review of AEAT corpus definitions.
Those names shadow the intended future meaning of user-filing review and make
the current corpus metadata read like Kent already approved his own filing.

## Considerations

- `src/aeat/domain/casillas/` and `src/aeat/domain/manuals/` both parse raw JSON directly
  into strict Pydantic models, so any rename changes both constructors and the
  on-disk JSON contract.
- `save_casillas()` serializes through `model_dump(mode="json")`, which means
  field names on the models control the emitted corpus keys without a second
  translation layer.
- Three committed casilla corpus files still use `reviewed_by` /
  `reviewed_at`; local developer worktrees may also contain stale JSON with the
  legacy keys.
- The change must stay tightly scoped to definition-review metadata. Other
  review-style fields in unrelated domains are out of scope.

## Constraints

- The canonical repository state must stop emitting the old names in checked-in
  corpus, tests, CLI output, and contributor docs.
- The issue is scoped to the repository-owned corpus and test fixtures, not to
  preserving stale local JSON files created before the rename.
- `aeat.domain.manuals` has no production writer for structured `Manual` / `Section` /
  `Rule` JSON, so the implementation cannot rely on automatic rewrite for any
  local manual structures outside the repository.

## Implementation

- Rename the affected model fields to `definition_reviewed_by` and
  `definition_reviewed_at` in `src/aeat/domain/casillas/models.py` and
  `src/aeat/domain/manuals/_schema.py`.
- Update verification messages, CLI output, tests, and contributor docs to use
  the definition-scoped names consistently.
- Rewrite the checked-in `corpus/casillas/*.json` files in this branch so the
  repository no longer advertises the old namespace.
- Treat stale local JSON that still uses `reviewed_by` / `reviewed_at` as
  unsupported after this change. Operators must rewrite or regenerate those
  files before loading them on the renamed schema.

## Rationale

This keeps the rename honest. The issue exists to clear the namespace, not to
carry an indefinite backwards-compatibility layer for development-only corpus
artifacts. Rewriting the checked-in casilla corpus and tests is enough to move
the canonical repository state onto the new contract. Stale local JSON is an
acceptable break because `aeat.domain.manuals` has no production rewrite surface for
structured records, and carrying parser aliases would preserve the ambiguity the
issue is trying to remove.

## Consequences

- Code, tests, CLI text, and docs become explicit that these fields track
  developer review of corpus definitions, not Kent review.
- Old local JSON files using `reviewed_by` / `reviewed_at` stop loading until
  they are rewritten to the new keys.
- Downstream code must use the new attribute names immediately; partial renames
  will fail type checks and tests.
- If a future domain also wants definition-review metadata, it should use the
  explicit `definition_reviewed_*` terminology rather than reusing the bare
  `reviewed_*` namespace.
