---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:549908b0df76dc3e6f08869d909d787c14d095ad695cb43c648ed0f44a56fc9c'
step_id: 'S166'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Relocate the classification policies, external-layout fixture models and borrador extractor selection onto public modules, and repoint the storage lazy map's string module paths

## Scope

- `src/cadrumo/`

## Changes

- `A` `src/cadrumo/core/classification/policies.py`
- `A` `src/cadrumo/tests/fixtures/external_layout_candidates/models.py`
- `A` `src/cadrumo/adapters/inbound/borrador/_extractors/selection.py`
- `M` `src/cadrumo/adapters/persistence/storage/__init__.py`
- `A` `src/cadrumo/adapters/inbound/justificante/_parsers/text_extraction.py`
- `M` four namespaces inert; 78 consumers repointed
- `verify:` `pytest core/classification + core/redaction -n 0 -m ""` -> 18 passed
- `verify:` `--collect-only` -> 28935 collected, 6 errors, all pre-existing and peer-owned

## Notes

`core.classification` is the largest relocation so far: ten symbols, 77
consumers, and the whole sensitivity and redaction policy vocabulary.

### A lazy map in an unrelated package, keyed by STRING

Moving `SensitivityClass` broke 622 collections through
`adapters.persistence.storage`, which re-exports it. Its lazy map stores module
paths as string literals -- `"....core.classification"` -- so the rewrite
updated the one real `import` statement in that file and left five string
entries pointing at a module that no longer holds the symbol.

No AST import scan can see those, by construction: they are data, not imports.
The parent-first guard did not fire either, because storage is not an ancestor
of `core.classification` -- it is a peer package reaching across the tree.

So the guard learned the wrong shape from the earlier case. The real rule is not
"a parent may read through a child" but "ANY package may re-export from ANY
other, by import or by string, and both are consumers". The string form is the
dangerous half because it is invisible to the tooling and fails only at
attribute-access time.

### The half-retirement window

`justificante._parsers` refused mid-run on a test importing a private
`_TEXT_CACHE`, and the refusal came AFTER the namespace had already been made
inert -- the tool writes the namespace before it walks consumers, so a late
refusal leaves the package exporting nothing with its consumers still pointing
at it. Restored from committed content.

The ordering is wrong and worth fixing before the next batch: consumers should
be validated in full, then written, and the namespace emptied last. A tool that
can refuse must refuse before it mutates anything.

### The ordering was fixed, and it changed the answer

The tool now collects and validates every consumer edit before writing anything;
the new module and the emptied namespace are written last. Re-running
`justificante._parsers` against the fixed ordering left the namespace completely
untouched on refusal, which is the behaviour the earlier run should have had.

Then the refusal itself turned out to be the tool's, not the code's. It mapped
only PUBLIC names, so a test importing `_TEXT_CACHE` looked like a name that had
not moved -- when in fact every top-level definition moves together and a
private one moves just as surely. Mapping private names too completed the
relocation: seven symbols, and `pytest justificante` green at 167.

Worth noting because the refusal was persuasive. It named a real symbol and a
real file, and the honest-looking reading was "a consumer depends on a private
that should not leave the namespace". The actual fact was that the tool could
not see half of what it was moving.
