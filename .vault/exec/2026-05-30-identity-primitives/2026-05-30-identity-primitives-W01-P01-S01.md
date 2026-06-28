---
step_id: S01
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W01.P01.S01 — carve core/identity/_bucket.py

## Scope

Create the new `BucketId` alias module at `src/aeat/core/identity/_bucket.py`
per identity-primitives ADR Rule 5. The constraint shape
(`strip_whitespace=True`, `min_length=1`, `max_length=128`) is preserved
verbatim from the prior declaration in `src/aeat/domain/modelos/_ids.py`,
which remains in place until W01.P03.

## Outcome

`src/aeat/core/identity/_bucket.py` exists with the single
`BucketId = Annotated[str, StringConstraints(...)]` declaration and an
`__all__ = ("BucketId",)` export. The module docstring records why the
alias lives in `core/identity` (per-profile storage-container identity
above any single record domain).

## Verification

`uv run --no-sync python -c "from aeat.core.identity._bucket import BucketId; print(BucketId)"`
resolves the alias and prints the StringConstraints shape.

## Commit

`c92430bda` — feat(core/identity): add BucketId alias module
