---
tags:
  - '#plan'
  - '#rename-corpus-review'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-rename-corpus-review-research]]'
  - '[[2026-04-18-rename-corpus-review-schema-adr]]'
  - '[[2026-04-18-rename-corpus-review-adr-audit]]'
---

# `rename-corpus-review` `implementation` plan

Rename corpus-definition review metadata in the casillas and manuals surfaces so
the bare `reviewed_*` namespace is no longer used for developer review. Rewrite
the checked-in corpus, tests, and contributor docs onto the new
`definition_reviewed_*` contract, and treat stale local JSON on the old names as
unsupported after the change.

## Proposed Changes

Update the strict Pydantic schemas in `aeat.domain.casillas` and `aeat.domain.manuals`,
propagate the new names through verification/CLI text, and rewrite the checked-in
casilla corpus JSON. The repository-owned surfaces move in one cut; no
parse-time alias layer is kept for stale local JSON.

## Tasks

- `Phase 1 - Rename the schema contract`
  1. Update the casillas and manuals models to expose
     `definition_reviewed_by` / `definition_reviewed_at`.
  1. Update verification and CLI wording to the definition-scoped names.

- `Phase 2 - Rewrite repo-owned fixtures and corpus`
  1. Rewrite the checked-in `corpus/casillas/*.json` files to the new keys.
  1. Update all affected unit tests and inline JSON fixtures in
     `src/aeat/domain/casillas/` and `src/aeat/domain/manuals/`.
  1. Update contributor-facing documentation that still advertises the old
     names.

- `Phase 3 - Verify regressions`
  1. Add or update coverage proving the renamed schema, verification messages,
     and serialized corpus all use `definition_reviewed_*`.
  1. Run the affected casillas and manuals unit tests.
  1. Run the full test suite to confirm no unrelated parser or CLI regressions.

## Parallelization

The rename is mostly serial because the schema, verification messages, JSON
fixtures, and tests all depend on the final field contract. Documentation and
fixture rewrites can proceed once the schema names are settled, but verification
must happen after the full rename lands.

## Verification

- Canonical serialization and checked-in corpus files emit only
  `definition_reviewed_by` / `definition_reviewed_at`.
- Casillas and manuals review gates still fail when the definition-review
  metadata is blank or missing.
- Old-key payloads are intentionally unsupported after the rename, and the
  repository no longer contains them in committed corpus or tests.
- Targeted unit suites for `src/aeat/domain/casillas/` and `src/aeat/domain/manuals/` pass.
- The full repository test suite passes without introducing new skips, mocks, or
  weakened assertions.
