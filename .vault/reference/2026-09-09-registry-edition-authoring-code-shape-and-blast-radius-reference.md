---
tags:
  - '#reference'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d20d414d441cc1ea5cc3cf9982d1598dd9c407e0446875955fdca5957eefae5d'
related: []
---

# `registry-edition-authoring` reference: `code shape and blast radius`

The concrete code surface an edition-relative authoring change touches: where a materialiser
would sit, what reads the registry, how the caches behave, and what each associated rename would
cost. Compiled from a read-only sweep of `src/cadrumo/` and `dev/registry/` on the `fix/registry-gen`
working tree. Counts are reproducible sweeps adequate for sequencing, not a substitute for
reading a call site before editing it.

## Summary

### The materialiser seam

In `src/cadrumo/domain/calculations/registry/_loader_internals.py`, `_load_modelo_revisions`,
`_merge_revision_file` and `_merge_revision_directory` assemble raw dictionaries per edition, and
`_build_modelo_definition_from_data` turns them into typed objects. An expander producing the
same merged mapping leaves that function's signature, its return type, and everything above it in
`loader.py` and `authority.py` untouched.

### Consumers pass through one chokepoint

Roughly 100 non-test consumers obtain registry data through the validated authority and receive
typed objects. Every direct file read of the registry data root sits inside the registry
package's own loader: `_loader_internals.py`, `loader_cache.py`, `_loader_revision_fragments.py`,
`convenio.py`, `facts/loader.py`. Other TOML reads in `src/cadrumo/` address unrelated catalogues.

The genuine direct readers are development tooling under `dev/registry/` — analysis modules,
conformance stamping, the generation pipeline. They read raw files and need deliberate updating.

### Caches key on files, not on rows

The registry identity stamp, the compiled artefact cache, the validation verdict cache and the
validation memoisation key on file-granular fingerprints — path, size, modification time, content
digest — plus code-version hashes. None keys on row shape. All are documented as derived and
rebuildable with no migration. Fingerprinting must key on the physical edition files actually
read; keying on expanded output would break self-invalidation.

Three fact-provider fingerprint collectors formerly refused a registry lacking their declaration
file, preventing any partial tree from being fingerprinted. Guards have landed in
`domain/categories/registry.py`, `domain/iva/rates.py` and `domain/iva/recargo_equivalencia.py`.

### Identity types by concept

| Concept | Canonical definition | Adoption |
| --- | --- | --- |
| Casilla identifier | `core/casilla_id.py` | ~4,500 typed against 19 bare |
| Casilla declaration | `registry/schema_surfaces.py` | 27 fields, one definition |
| Edition identifier | `registry/ids.py` | ~60 typed against ~5 bare |
| Modelo number | three types, none canonical across layers | 131 typed against 1,086 bare |

Casilla identity is the best-typed concept in the codebase and needs no consolidation. It is
edition-local: no type expresses a casilla qualified by its modelo and edition, and consumers
needing global uniqueness improvise bare tuple keys. The corpus uses five identifier grammars —
numeric, dotted, kebab, token, page-qualified — under one permissive regular expression.

Lineage is carried by `continuidad_id`, declared on 20.5% of rows and absent from 25 of 33
multi-edition modelos.

### Blast radius of associated renames

| Target | Code symbols | Persisted data | Tests | Rating |
| --- | --- | --- | --- | --- |
| Consolidate modelo number | ~5,870 src, ~459 dev | 97 model fields change a serialised shape | 1,024 files | XL by volume, risk in 97 |
| Export family to wire | ~1,113 | 2,878 files, 29,339 table headers, 96 directories | 632 | XL on disk, L in code |
| Revision to edition | 335 src, 1,504 dev | 92,616 table headers, 129 filenames, 58 directories | 153 | largest mechanical migration |
| Wire addressing columns | 7 fields plus a discriminator | 634 files | 34 | L |

For the modelo number, only 97 of ~1,245 typed declarations are model fields that change a
serialised shape; the rest are function parameters. For both renames the persisted surface
outweighs the code surface by roughly 25 to 30 times by file count, so they should ride on a
change already rewriting those files. `projection_ref` is a declared addressing column with zero
occurrences in the live corpus.

`application/modelo/work_addressing.py` defines an unrelated saved-calculation identifier with
181 uses whose name collides with the edition concept. It must be excluded from any rename sweep.

### Fragment merge semantics

`revision.toml` is required per edition. Fragments sort by full path, and each may declare only
its own section; governance fields in a fragment are refused. Seventeen sections merge by bare
concatenation with no duplicate-identifier check at load — that check lives one layer later in
validation. Export layouts merge by layout then record identifier with duplicate field
identifiers refused. Scalars are first-writer-wins.

Numeric filename prefixes are enforced unique per section but are not load-bearing for emission:
record order comes from a declared `order` field, and at least one shipped file's prefix and
declared order disagree. The `export/` directory name is an alias for `export_layouts` reconciled
in `_loader_revision_fragments.py`, which is also where the distinction between a generated and a
hand-transcribed layout is erased.

### Verification surface

Registry protection on the per-push path is authority validation plus an oracle audit. The
development screens and the invariant gates promoted from them run only in a dispatch-only
workflow. Approximately thirty assertions across twelve test files assert that the live corpus
still contains findings; those must be converted before any promotion, or cleaning the corpus
would fail the build.

### Shipped but unread

The generator writes a derivation record per generated edition carrying each field's originating
sheet, row, cell, ordinal and raw source cell. Thirty-two ship inside the package. Production
reads nothing from them: the only reference is a predicate stopping the loader refusing the tree
for containing a non-TOML file.
