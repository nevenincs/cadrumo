---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:1832f78255dfd03cb9388a32f61a2f360a57cfbf06919d7c2dfe05ba1af1789f'
step_id: 'S51'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Extend the non-negative count adoption to the remaining domain, application and adapter sites once the shared tree is quieter

## Scope

- `src/cadrumo/`

## Changes

- `M` 241 fields across 72 domain, application and adapter modules adopt `NonNegativeInt`
- `M` `pyproject.toml` -- the `S105` per-file ignore repointed to the module that now holds the enum
- `M` `src/cadrumo/adapters/outbound/storage/tests/test_foundation.py`
- `verify:` field schema byte-identical to the hand-spelled bound in validation AND serialization mode; all three forms accept 0 and refuse -1
- `verify:` `--collect-only` -> 28998 collected, 0 errors
- `verify:` `pytest adapters/outbound/storage/tests -n 0 -m ""` -> 268 passed (4 live-test guards refuse without CADRUMO_LIVE_TESTS_ENABLED)

## Notes

Only two forms were rewritten, both proven identical to the canonical before
anything was touched:

    n: int = Field(ge=0)
    n: Annotated[int, Field(ge=0)]

A field carrying any FURTHER constraint was left alone. 317 sites matched the
shape; 241 were rewritten. The 76 left are not the same bound, and collapsing
them would have silently widened or narrowed a contract -- the exact defect this
campaign removes, committed in its name.

The equivalence check nearly produced a false negative. Comparing whole model
schemas reported them as differing, because the models used for the comparison
have different names and the title carries into the schema. Comparing the FIELD
schema shows byte-identical output in both validation and serialization mode.
A check that compares more than the thing under test answers a different
question and reports it in the same words.

### A ruff ignore pinned to a filename

`pyproject.toml` carried
`"src/cadrumo/core/classification/__init__.py" = ["S105"]`, suppressing a false
positive on a `SECRET = "secret"` sensitivity-class member. Relocating that enum
to `policies.py` left the ignore pointing at a file that no longer holds it, and
the false positive resurfaced.

Repointed rather than answered with an inline `noqa`. The project already uses
`noqa: S105` with a reason for genuine one-off false positives, but a path-scoped
ignore that already exists should follow its subject rather than be replaced by
a second mechanism.

Worth noting as a relocation consequence in its own right: a config entry keyed
by filename is a consumer of that filename, and no import scan sees it.

### A facade-surface gate repaired

`test_storage_package_public_surface_keeps_factory_and_manifest_helpers_private_backends_hidden`
asserted nine symbols on the storage package root's `__all__`, which the earlier
retirement emptied.

Its two halves survive the retirement differently. The contracts-are-public half
now resolves each symbol at its defining module. The backends-are-private half
was strengthened rather than kept: against an inert namespace `not hasattr(root,
backend)` is vacuously true, so the test now also asserts the backends are
absent from each contract module.

All nine contracts live in underscore-private modules, so the rewritten test
pins WHERE they live without blessing that shape -- it is the subject of the
open mirror-manifest publicising step, and the test now gives that move
something to move against.
