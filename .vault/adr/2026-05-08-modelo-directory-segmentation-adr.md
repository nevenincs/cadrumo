---
tags:
  - '#adr'
  - '#calculation-truth-registry'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-modelo-100-bulk-segmentation-audit]]"
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
  - "[[2026-05-04-calculation-authority-evidence-tiering-research]]"
---
# modelo-directory-segmentation-adr

## Context

`registry/aeat/modelos/100.toml` reached 145,900 lines on
2026-05-08 and grows by ~10% per fiscal year. Single-file editing
became unreliable: line-targeted operations risk corruption, IDE
indexers stall, code review of cross-revision changes shows tens of
thousands of lines of pure noise (defaulted fields, identical casillas
duplicated across revisions). The bulk audit at
`[[2026-05-08-modelo-100-bulk-segmentation-audit]]` measured the
problem and proposed a phased remediation. This ADR formalizes the
directory-mode segmentation pattern landed in Phase 2 and specifies
the Phase 3 cross-revision deduplication contract.

## Decision

The canonical modelo storage layout supports two equivalent modes:

1. **Single-file mode** (existing pattern, retained):
   `registry/aeat/modelos/<id>.toml` declares `[modelo]` plus all
   `[revisions."<rev>"]` tables in one file.

2. **Directory mode** (new pattern, recommended for large modelos):
   ```
   registry/aeat/modelos/<id>/
     manifest.toml               # [modelo] table only — no revisions
     revisions/
       <rev>.toml                # one or more revisions per file
     shared/                     # Phase 3 (deferred)
       casillas.toml
       formulas.toml
       constructs.toml
       parameters.toml
       bindings.toml
       relations.toml
   ```

The two modes are mutually exclusive per modelo: a single modelo id
cannot exist as both `modelos/<id>.toml` AND `modelos/<id>/`. The
loader (`src/aeat/domain/calculations/registry/_loader.py`) raises
`RegistryLoadError` when both forms are present.

`load_modelo_file(path)` and `load_modelo_directory(path)` produce
byte-identical `ModeloDefinition` objects from equivalent input. All
downstream consumers (validator, snapshot builder, scenario runner,
CLI introspection) treat them interchangeably.

### When to use directory mode

A modelo SHALL migrate to directory mode when any of the following
holds:

- The single file exceeds 30,000 lines.
- The modelo has discrete annual revisions and ≥3 revisions cataloged
  (i.e. growing toward unbounded).
- Bulk-edit operations against the file produce IDE / git-diff /
  review-pipeline degradation.

A modelo SHOULD remain in single-file mode when:

- The file is under 5,000 lines.
- The modelo uses a single forward-compatible revision (e.g.
  `2009-y-siguientes`) with no plan to split per year.

### Manifest contract

`manifest.toml` declares the modelo-level metadata only. The TOML
must satisfy the following invariants:

- `[modelo]` table is REQUIRED with at least the fields the loader's
  `ModeloDefinition` schema requires (`id`, `label`, etc.).
- `[revisions]` table or `[revisions.X]` array is FORBIDDEN. The
  directory loader raises `RegistryLoadError` if encountered.
- `[legal]`, `[sources]`, `[legal_refs_catalogue]` tables are
  FORBIDDEN (same constraint as single-file mode — local catalogues
  belong in `registry/aeat/legal/*.toml` only).

### Revision file contract

Files under `revisions/` declare per-revision data. Each file:

- MUST declare at least one `[revisions."<id>"]` table (or its
  `[revisions."<id>".X]` array variants for casillas / formulas /
  etc.).
- MUST NOT redeclare `[modelo]` — that is manifest-only.
- MUST NOT declare local `[legal]` / `[sources]` / `[legal_refs_catalogue]`
  catalogues.
- MAY declare multiple revision ids in the same file (the migration
  script preserves this flexibility), but a single revision id MUST
  appear in exactly one file across the directory.

The loader merges all `revisions/*.toml` files in lexicographic order
of file path. The merged result is identical to a single-file modelo
with all the same revision tables.

### Discovery contract

`load_registry_tree` discovers modelos by:

1. Iterating `modelos/*.toml` (existing single-file pattern).
2. Iterating `modelos/<dir>/` and loading each that contains a
   `manifest.toml` at its root.

A modelo id discovered in both forms raises `RegistryLoadError`.
Adding/removing modelo files invalidates the loader's
fingerprint-based cache.

## Phase 3: cross-revision shared block (deferred)

The audit measured 1,476 of 2,254 unique casilla IDs in modelo 100
(65%) repeating verbatim across all 6 revisions. Phase 3 introduces a
`shared/` directory under directory-mode modelos to factor out this
duplication.

### Shared file contract

```
registry/aeat/modelos/<id>/shared/
  casillas.toml      # [[shared.casillas]] arrays
  formulas.toml      # [[shared.formulas]] arrays
  ...
```

Each shared file declares one or more arrays under the `shared` table:

```toml
[[shared.casillas]]
id = "0003"
number = "0003"
label = "Rendimientos del trabajo dineraria"
section = ["...", "..."]
applies_to_revisions = ["2020", "2021", "2022", "2023", "2024", "2025"]
legal_refs = ["..."]
source_refs = ["..."]
```

The `applies_to_revisions` field is REQUIRED on every shared element.
It declares which revisions the element belongs to. The loader
materializes the element into each named revision's in-memory
`ModeloRevision` at load time.

### Override semantics

A revision file MAY declare per-revision overrides for shared
elements:

```toml
[[revisions."2025".casillas_overrides]]
id = "0003"
label = "Rendimientos del trabajo dineraria (2025 update)"
```

The loader merges overrides field-by-field on top of the shared
declaration before validation. An override:

- MUST identify the shared element by `id`.
- MAY redefine any field (label, section, data_type, legal_refs,
  source_refs, etc.) declared on the shared element.
- MUST NOT introduce fields not present on the shared element's
  schema.
- MUST be declared in the revision file matching its `applies_to_revisions`.

### Validation invariants for Phase 3

- A shared element id MUST NOT collide with a revision-local element
  id of the same kind.
- An override MUST reference a shared element that exists.
- Every casilla referenced by a formula / binding / construct in a
  revision MUST resolve through (shared + per-revision overrides +
  revision-local declarations).
- The audit script's renta-scoped citation walker continues to scan
  `formulas` / `parameters` / `bindings` / `relations` across the
  merged in-memory revision, unchanged.

### Phase 3 estimated saving

For modelo 100 with 1,476 stable IDs across 6 revisions and ~9 lines
per casilla block: ~80,000 line reduction (collapsing 8,856 duplicate
blocks to 1,476 shared declarations).

After Phase 1 (defaults) + Phase 2 (split) + Phase 3 (shared):
~50,000 total lines (down from 145,900). Largest single file:
~5,000 lines.

## Consequences

**Positive**:
- Per-file size is now bounded by the largest single revision (not
  by the modelo's total lifetime). 2025 today: 23,775 lines (vs
  145,900). Future 2026, 2027 revisions land as new files instead of
  appending to one.
- Code review for a single-revision change touches one file, not the
  monolithic 145K-line file.
- IDEs (VS Code, JetBrains) handle 24K-line files comfortably; 145K
  was at the edge of indexer behavior.
- The directory pattern is repository-conventional: the
  `corpus/aeat_official/disenos_registro/<modelo>/` directories
  already use this layout for source documents.
- Phase 3 collapses cross-revision redundancy without information
  loss — every casilla is still validated against the same schema.

**Negative**:
- Two parallel storage layouts. New contributors must understand
  both. Mitigated by the equivalence test
  (`test_loader_directory_mode.py`) which asserts they produce
  identical results across 6 real modelos.
- Migration is a single-shot per modelo. Reverting requires a
  symmetric merge script (not currently authored). Mitigated by the
  audit-document-then-execute sequencing.
- Phase 3's override semantics introduce a layer of inheritance the
  reader must trace. Mitigated by enforcing strict invariants
  (shared element ids unique, override fields validated against
  shared element's schema).

**Neutral**:
- The audit pipeline (`scripts/audit_renta_scope.py`) loads modelo
  100 via tomllib directly today, not via the registry loader. The
  audit script must be updated to discover modelos in directory
  mode. This is a follow-up task, scoped per the audit's "next
  actions" section. Not a blocker for the Phase 1 + 2 landing.

## Status

`accepted — Phase 1 + Phase 2 executed`

- Phase 1 (pydantic defaults sweep) landed in commit `81c162c3`:
  145,900 → 115,168 lines (-21%).
- Phase 2 (directory split + loader extension) landed in commits
  `148c84f7` (loader) and `758fc637` (migration): largest single
  file dropped from 115,168 → 23,775 (-79%).
- Phase 3 (shared block + overrides) is approved in design but
  deferred for execution. Triggers: the next migration of an
  annual-revision modelo with ≥3 revisions, or when modelo 100's
  per-revision files exceed 25,000 lines individually.

## Follow-ups

- Update `scripts/audit_renta_scope.py` to use the registry loader
  (or equivalent directory discovery) instead of hardcoded
  `modelos/100.toml` path.
- Add a CLI command (`aeat registry inspect modelo <id>`) that
  prints the loaded `ModeloDefinition` summary and reports which
  storage layout is in use.
- Document the directory-mode pattern in the
  `registry/aeat/modelos/README.md` (does not exist yet).
- Consider authoring a directory-to-single-file inverse migration
  script for emergency revertability.
