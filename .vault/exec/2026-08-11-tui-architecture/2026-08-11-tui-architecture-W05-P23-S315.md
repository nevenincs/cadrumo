---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:ea2cd80bb7efe5ad8ec3fd9d29c3f020eea4e6819eea38c4c33ccb1998da98ef'
step_id: 'S315'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Repair the stale class-name assertion a prior relocation left behind: `application/operations/tests/test_projection_services.py:737` asserts the unavailable secure-response authority's name starts with `_Unavailable`, but the `relocation:operations_public_modules` commit renamed the class to `UnavailableOperationSecureResponseAuthority` (`projection_services.py:243`) without updating the assertion, so two parametrised cases fail on a name that no longer exists -- evidence that relocation was not atomic; correct the assertion to the live public name, and check whether that same relocation left any other consumer behind rather than fixing only the site that happens to be failing

## Scope

- `src/cadrumo/application/operations/tests/test_projection_services.py`
- `with a read-only sweep of the relocation commit's other consumers`

## Changes

## Changes

- `M` `src/cadrumo/application/operations/tests/test_projection_services.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_projection_services.py -m unit -n0` -> `8 passed`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/operations/tests/test_projection_services.py` -> `pass`

## Notes

Four assertions read the bound authority's class name and required it to
start with an underscore-prefixed token. The class had been renamed to a
public name by an earlier relocation, so every one of them failed on a
spelling that no longer exists anywhere in the tree.

The fix asserts the TYPE rather than the spelling. That is not a cosmetic
preference: a name-matching assertion breaks on a rename and, worse, would
pass again if some unrelated class were later given a name with the same
prefix. `isinstance` cannot do either.

The assertions still discriminate rather than passing vacuously, and the
test proves it in place: the same `bind` call that is expected to yield an
unavailable authority on a re-bind is the one that returns a real bound
authority on its first successful call, a few lines above. Identical
arguments, opposite expectations, so a check that could not tell the two
apart would fail.

That the relocation which renamed the class did not update these four
consumers is the finding worth recording: the move was not atomic, and the
evidence sat in the suite as a persistent red rather than surfacing at the
time. The scope of this Step covered a read-only sweep of that relocation's
other consumers; no further stale references to the old name remain in the
tree.
