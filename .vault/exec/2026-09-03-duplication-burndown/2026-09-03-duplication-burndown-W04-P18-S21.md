---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:57ed14cf45b5e3f90e52c3bf2d1d80f7b7ec54bfa1182d81716fb60bf4373106'
step_id: 'S21'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Build a docstring cross-reference screen and burn down the references naming symbols the tree does not define, separating current drift from accurate statements about the past

## Scope

- `dev/quality/docstring_reference_targets.py`

## Changes

- `A` `dev/quality/docstring_reference_targets.py`
- `A` `dev/quality/tests/test_docstring_reference_targets.py`
- `M` `src/cadrumo/core/config.py`
- `M` `src/cadrumo/core/ledger_sort.py`
- `M` `src/cadrumo/entrypoints/cli/_common.py`
- `M` `src/cadrumo/application/aggregation/_renta_income_ledger.py`
- `M` `src/cadrumo/application/modelo/calculate_input.py`
- `M` `src/cadrumo/application/modelo/iva_wallet_seed.py`
- `M` `src/cadrumo/application/modelo/maritime_preview.py`
- `M` `src/cadrumo/application/modelo/work_addressing.py`
- `M` `src/cadrumo/application/transactions/diagnostics.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_constructs.py`
- `M` `src/cadrumo/domain/calculations/registry/counterpart_bindings.py`
- `M` `src/cadrumo/domain/contribuyente/keys.py`
- `M` `src/cadrumo/application/aggregation/_business_proportion.py`
- `M` `src/cadrumo/application/aggregation/_currency_predicates.py`
- `M` `src/cadrumo/application/aggregation/_iva_transaction.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings.py`
- `M` `src/cadrumo/application/aggregation/_renta_ledger.py`
- `M` `src/cadrumo/application/aggregation/errors.py`
- `verify:` `uv run --no-sync pytest dev/quality/tests/test_docstring_reference_targets.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo` -> `pass`

## Notes

Thirty-one further shipped modules were repointed in one sweep and are not
listed individually; the sweep changed docstring text only, verified by a diff
carrying no non-`:mod:` additions.

The count went 87 to 35. Roughly a third of that was the screen learning to
read what it was looking at rather than the tree changing: subscripted generics
(`Envelope[BlobManifest]` is two claims, not one unresolvable string), instance
attributes assigned as `self.x`, and `:mod:` roles written relatively. Each of
those was a false positive the screen had manufactured.

The rule that made the module sweep safe is the phrase "lived in". An earlier
attempt at the same sweep was reverted because it rewrote a sentence about
where code USED to live, turning a true statement about history into a false
one about the present. Skipping any line carrying that phrase separated 36
present-tense references, safely repointed, from 3 historical ones left exactly
as written. `_iter_validated_envelopes` was left for the same reason: its
sentence is past tense and correct.

Nothing here was guessed. Each repointing names a symbol confirmed to exist:
the builder was found through the test the docstring itself names, the
counterpart supplier through the source_kind filter its sentence describes, and
`ExternalConstants` because the docstring contradicted its own signature. Where
no replacement existed the citation was removed rather than invented -- twice,
for `is_sandbox_label` and a See Also entry pointing at a function that never
appears in the tree.

Two findings were not documentation defects at all. A rule slug in production
prose led to the vault-citation ratchet, and a second slug wearing a `:func:`
role showed that ratchet's own pattern was blind to role form.

## Closure

The count reached 4 correct references plus 1 unresolved, and a ratchet now
holds that floor: `dev/quality/docstring_reference_ratchet.py`, wired into the
static-check group and the suite, refusing in four directions like its
siblings.

The baseline is not a debt ledger. Four of its five entries are accurate
statements about the PAST -- what a module consolidated, why two read paths
were merged -- naming code that correctly no longer exists, and rewriting one
would make a true sentence false. The fifth is real: `tui/components/theme`
says its presentation tokens are delivered through `cadrumo_css_variables`,
which every Cadrumo App returns from `get_css_variables`, and neither exists.
That sits inside the deferred TUI cluster and is recorded separately so the
distinction is not lost.

Two things this Step is worth remembering for.

The end-to-end plant found a blind spot the unit tests would not have. The
gate was built, wired, and passing; planting a dangling reference in an
attribute docstring -- `X = ...` followed by a bare string, the form this
codebase documents constants with -- did NOT fail it, because
`ast.get_docstring` reaches only module, class and function docstrings. The
screen had never scanned that form at all. Fixing it surfaced the theme finding
above, which was pre-existing rather than new.

And roughly a third of the 87 was never tree drift. Subscripted generics read
as one unresolvable name, instance attributes never collected, relative `:mod:`
roles, roles wrapped across lines, and a from-import registering only the
imported symbols while leaving its own package unknown -- each a false positive
the screen manufactured. Every widening that fixed one carries a paired tooth
proving it still catches a genuine miss, because widening is the direction that
silently blinds a screen.

