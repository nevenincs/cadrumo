---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:250f18ba6e9ea6f2563b300909f4f098da86432c70f43deaada3d00834b22471'
step_id: 'S73'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render scalar controls only from the admitted permitted surface, delegate every lexeme to ModeloEditParseRequestV1, preserve zero, false, clear, override removal, and unchanged distinctions, and block review on an unresolved locale-tagged lexeme

## Scope

- `src/cadrumo/entrypoints/tui/modelo/edit/fields.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/edit/fields.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/edit/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/edit/tests/test_fields.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/edit/tests/__init__.py`
- `verify:` `ruff check` over the package -> `All checks passed`
- `verify:` `pytest` -> `NOT RUN; see below`

## Notes

PARTIAL: the module and its tests are written and lint clean; the tests are
UNVERIFIED and the row stays open until they run.

THE FOUR DISTINCTIONS THE ROW NAMES ARE KEPT APART, each for a stated reason:
- UNCHANGED: `touched` is set by interaction and never inferred from a value.
  A control whose text happens to equal the declared value has still not been
  answered, and inferring otherwise stages an intent nobody made.
- ZERO and FALSE: answers that stage a typed value. Treating an empty-looking
  value as nothing would silently drop a declaration.
- CLEARED: stages a removal, which is not the same as never having answered.
- UNRESOLVED: stages nothing AND blocks review. Reviewing around unparsed text
  would submit the value the field held BEFORE the operator typed over it while
  the screen shows what they typed, so the submission and the surface would
  disagree and only the surface is visible.

Every lexeme goes to the session, which parses it through the contract's own
parse request. This module holds exactly one thing the application layer
cannot: text the operator has typed and the contract has not accepted.

TWO CORRECTIONS MADE DURING THE BUILD, both the same error caught early:
- The module first resolved the locale itself through an `active_locale()` that
  DOES NOT EXIST. The locale is now supplied by the surface that rendered,
  which is also the correct design: the language a lexeme is parsed in must be
  the language the operator was shown, or a language switch makes the parse
  disagree with the screen.
- `writable_scalars()` had to be added to the session facade, because otherwise
  this module would have read `baseline.permitted_surface` and held contract
  records after all -- reintroducing through the back door exactly what the
  operator's boundary ruling removed.

WHY THE TESTS ARE UNRUN, and it is a measurement judgement rather than a
blocker: four consecutive collection attempts produced four DIFFERENT missing
symbols -- `core.storage_taxonomy`, `core.authority_grade`,
`core.filing_projection_ref`, then `source_diagnostics_for` from
`aggregation._source_mesh`. A peer sweep is rewriting the tree wholesale: 1685
source files changed within two minutes and 4708 uncommitted modifications
under `src/cadrumo`. Any result now would describe that sweep's instant rather
than this module. Run the package's tests once the tree is quiet.

VERIFIED 2026-08-31, once the tree settled. The peer sweep landed: churn fell from 1685 files in two minutes to 3, and `application/aggregation/__init__.py` -- which was importing four symbols from `_source_mesh` that a relocation had moved to `source_resolution_operations.py` -- was repaired by its owner.

- `verify:` `pytest entrypoints/tui/modelo/edit` -> `7 passed`
- `verify:` `pytest test_edit_session.py + entrypoints/tui/modelo/edit` -> `14 passed`

The second run matters as much as the first: it re-exercises W06.P12b.S72's facade AFTER a tree-wide sweep rewrote roughly 4,700 files underneath it, so the session and the fields are proven against the settled tree rather than the one they were written against.

Waiting rather than retrying was the right call and is worth recording as method. Six consecutive collection attempts produced six DIFFERENT missing symbols -- `core.storage_taxonomy`, `core.authority_grade`, `core.filing_projection_ref`, `source_diagnostics_for`, `core.storage_taxonomy_locations`, `core.auth_provider` -- each resolving as the next appeared. That is the still-being-produced signature, where the per-attempt tell looks identical to an unenumerated population but the remedy is the opposite: enumerate harder and you measure the sweep; wait and the question answers itself.
