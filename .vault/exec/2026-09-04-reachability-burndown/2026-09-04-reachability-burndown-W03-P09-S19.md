---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:8f35470c60af9b9e5960121b063f503d614bb2813b5ec5bfcc5e32bb887f0926'
step_id: 'S19'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Resolve the _WHITESPACE_RE collision, where one module compiles a single-whitespace matcher and three compile a run matcher under the same name

## Scope

- `src/cadrumo`

## Changes

- `M` `src/cadrumo/core/text_fold.py`
- `M` `src/cadrumo/application/corpus_search/terminology.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/_adapter_utils.py`
- `M` `src/cadrumo/adapters/inbound/pdf/label_regex.py`
- `A` `src/cadrumo/core/tests/test_fold_for_matching_is_canonical.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/tests/test_fold_for_matching_is_canonical.py` -> `pass`
- `verify:` `uv run --no-sync lint-imports` -> `pass`

## Notes

The collision was two operations sharing one name. Three modules compiled a run pattern
and substituted a single space -- collapsing whitespace. The PDF label reader compiled a
single-whitespace pattern and substituted the empty string -- DELETING whitespace. A merge
on the name would have changed how PDF labels are matched.

The deleting pattern is therefore renamed `_WHITESPACE_TO_DELETE_RE`, named for its
operation, and left where it is. Nothing about the PDF reader changed but the name.

Underneath the collision sat real semantic duplication the textual detector cannot see.
`terminology._fold` and `_adapter_utils.normalize_response_text` were the SAME function:
fold diacritics, collapse whitespace, trim, casefold. They differed only in ordering the
casefold before or after the collapse, which is why neither the clone detector nor a name
search found them. Both now delegate to `fold_for_matching` in the module that already owns
`fold_diacritics`.

That module's docstring states callers compose their own trailing transform, so adding this
function was a deliberate narrowing of that rule rather than a contradiction of it: where
two callers compose the SAME transform, the composition earns a name. The docstring records
that.

Equivalence was measured before the merge, not assumed: the casefold orders agree across
Turkish dotted capital I, sharp S, digraphs, non-breaking space and the empty string, and
both call sites reproduce their previous output on every sample. 31 and 42 owning tests
pass, and the layered architecture holds at 11 contracts kept.

## Notes on the gate

The gate pins the property the merge rests on -- that casefolding before or after the
collapse agrees -- because if that ever stops holding, the two merged call sites were never
equivalent. It also asserts the fold COLLAPSES rather than deletes, which is the
distinction the renamed PDF pattern preserves.

Teeth proven by changing the canonical fold to delete instead of collapse: the gate exits
1, and exits 0 once restored.
