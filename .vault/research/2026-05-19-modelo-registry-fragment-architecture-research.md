---
tags:
  - '#research'
  - '#modelo-registry-fragments'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-15-corpus-registry-packaging-research]]'
---



# `modelo-registry-fragments` research: making AEAT modelo registry definitions reviewable

This research investigates the remaining registry file-size blocker after the
first mechanical modelo splits. The immediate issue is not only cross-revision
duplication. M200 still has one revision file at 132,896 lines. The registry
needs a smaller authoring representation that compiles to the existing strict
runtime schema.

## Findings

### Current corpus state

The physical file-size blocker remains concentrated in two modelos:

- M200 `2024-y-siguientes`: 132,896 lines, 3,215 casillas, one formula, one
  binding, one export layout containing 77 records and 6,531 fields.
- M100 year revisions: 17,348 to 25,632 lines each, with 1,531 to 2,235
  casillas per revision and repeated formula/binding/relation patterns.

M200 is not large because it has calculation complexity. It is large because it
stores record-design/export layout and casilla mapping data verbatim in one
revision file:

- export layout blocks account for about 90,753 lines;
- casilla blocks account for about 38,589 lines;
- one construct block accounts for about 3,245 lines;
- parameters, formulas, bindings, relations, schedules, deadlines, and links are
  comparatively small.

The most obvious split boundary is therefore by record kind, not by revision:
`revision.toml` should hold revision metadata, while casillas, export layouts,
formulas, bindings, relations, constructs, and validation/reference surfaces
should be authorable as separate fragments.

### Existing code architecture

The current loader already has a useful architecture: both single-file and
directory-mode modelos are parsed into raw TOML dictionaries, then validated
into `ModeloDefinition` and `ModeloRevision`. This means a fragment system can
be implemented as a pre-validation merge and can keep the public schema stable.

Primary blast radius:

- `_loader.py`: file discovery, TOML reading, merge rules, cache fingerprints,
  layout-collision checks.
- `_schema.py`: should remain stable if fragments compile into the same raw
  revision payload.
- `_validate.py`: should remain stable because it validates the merged object
  graph, not the authoring layout.
- `_snapshot.py`: should remain stable because it consumes validated
  `ModeloRevision`.
- registry tests: directory-mode loader tests, committed modelo tests, schema
  hygiene, catalogue verification, referential integrity, wheel-bundling tests.

One existing risk is already present: application filing runtime cache
fingerprinting only scans `legal/*.toml` and `modelos/*.toml`; it misses
directory-mode manifest/revision TOMLs and would also miss future fragments.

### Reference systems

OpenFisca keeps legal parameters reviewable by mapping domain paths to small
YAML files. A parameter such as `tax_on_salary.public_sector.rate` lives at a
matching path under `parameters/`, with dated values, metadata, units, and legal
references. Complex scales are still declarative through bracket structures.

Sources:

- https://openfisca.org/doc/coding-the-legislation/legislation_parameters.html
- https://openfisca.org/doc/openfisca-python-api/parameters.html
- https://openfisca.org/doc/coding-the-legislation/reforms.html

PolicyEngine keeps the same OpenFisca-style tree but tightens metadata:
parameter/node metadata includes labels, references, units, periods, uprating,
and structured references.

Sources:

- https://policyengine.github.io/policyengine-core/usage/parameters.html
- https://policyengine.github.io/policyengine-core/_modules/policyengine_core/parameters/parameter.html
- https://raw.githubusercontent.com/PolicyEngine/policyengine-us/main/policyengine_us/parameters/gov/irs/capital_gains/rates.yaml

Tax-Calculator/ParamTools demonstrates the opposite tradeoff: a compiled
defaults JSON can carry schema metadata, values, validators, sections, and
reform patches. It is good for runtime, less good as a review surface. Its useful
lesson is the separation between defaults, schema metadata, and compact reform
patches.

Sources:

- https://taxcalc.pslmodels.org/api/parameters.html
- https://raw.githubusercontent.com/PSLmodels/Tax-Calculator/master/taxcalc/policy_current_law.json
- https://raw.githubusercontent.com/PSLmodels/Tax-Calculator/master/taxcalc/reforms/2017_law.json
- https://paramtools.dev/parameters

JSON Schema guidance supports modular schemas with stable identifiers, `$defs`,
external `$ref`, and bundling for distribution. The relevant architectural
lesson is to keep development files modular while preserving one bundled
compiled artifact for consumers.

Source:

- https://json-schema.org/understanding-json-schema/structuring

### Design implications

The AEAT registry should move to an authoring-tree plus compiler architecture:

- Authoring files are small, path-scoped, and grouped by semantic record kind.
- A deterministic loader/compiler merges them into the existing
  `ModeloDefinition`/`ModeloRevision` schema.
- Public runtime APIs do not expose fragments.
- Equivalence tests prove that a split authoring tree produces the same object
  graph as the monolithic revision it replaces.
- File fingerprints include every TOML file read by the compiler.

This avoids a schema rewrite in the runtime domain while still solving the human
reviewability problem.

### Candidate layout

For directory-mode modelos, support both today’s layout and a new fragment
layout:

```text
modelos/200/
  manifest.toml
  revisions/
    2024-y-siguientes/
      revision.toml
      parameters.toml
      casillas/
        0000-identificacion.toml
        0100-liquidacion.toml
        ...
      formulas.toml
      bindings.toml
      relations.toml
      export/
        manifest.toml
        page-001.toml
        page-002.toml
        ...
      workbook_parity.toml
      application_links.toml
      constructs.toml
      dependency_classifications.toml
```

The compiler maps these fragments to the exact current TOML shape:

- scalar revision metadata from `revision.toml`;
- array record kinds appended from fragments in deterministic path order;
- export layout records/fields appended from `export/*.toml`;
- duplicate scalar keys rejected;
- duplicate ids rejected by existing schema/validator gates;
- local `[modelo]`, `[legal]`, `[sources]`, and catalogue tables forbidden in
  fragments.

The current `revisions/<id>.toml` file layout can remain supported as a legacy
compiled-source mode while migrated modelos adopt `revisions/<id>/...`.

### M200-specific path

M200 should be migrated first because it is the blocker:

1. Implement fragment loader support with no data migration.
2. Add loader equivalence tests that build a fragment layout in a temp dir and
   compare the resulting `ModeloDefinition` against the current directory-mode
   revision file.
3. Split M200 by record kind:
   - metadata and small surfaces in `revision.toml`;
   - casillas into section-scoped files;
   - export layout into one manifest and one file per page/record;
   - constructs into one construct file or construct-family files.
4. Run object-equivalence against the current M200 revision file before deleting
   the monolithic revision file.

This should reduce the largest file from 132,896 lines to roughly the largest
record/page fragment, likely under 4,000 lines, without changing runtime
semantics.

### M100-specific path

M100 needs a second phase after physical fragmentation. Its issue is repeated
year-to-year content. The safe version is not inheritance in the runtime schema;
it is template expansion at compile time:

- keep year-specific revisions explicit;
- introduce authoring templates only for stable repeated families such as
  formulas, bindings, relations, and stable casilla groups;
- require generated ids to be deterministic and visible in compiled output;
- keep `data_type`, `semantic_role`, constraints, and year-specific legal/source
  differences as explicit overlays.

The M100 template phase should wait until M200 physical fragmentation is proven.

### Rejected options

Do not add runtime inheritance to `ModeloRevision`. It would expand the blast
radius into every snapshot, validator, and consumer.

Do not replace TOML with a database or generated Python module. That would solve
line counts while losing reviewable legal data and making provenance harder to
diff.

Do not emit generated compiled TOML into source control as a second source of
truth. If a compiled cache is needed later, it should be build output with an
equivalence check, not the canonical registry.

Do not flatten concurrent `data_type` or `semantic_role` work. Fragmentation
must preserve those fields byte-for-byte during migration.

## Recommended ADR decision

Adopt a fragment-authoring compiler for directory-mode modelos. The compiler is
part of `_loader.py`, produces the current schema objects, and is guarded by
round-trip equivalence tests. M200 is the pilot. M100 template expansion is a
follow-on decision after M200 proves the authoring-tree model.

## Proposed implementation slices

1. Loader fragment support:
   - support `revisions/<id>/revision.toml` plus sibling fragment TOMLs;
   - recursively fingerprint all directory-mode TOML files;
   - update application filing runtime cache fingerprinting.

2. Fragment equivalence tests:
   - synthetic multi-fragment fixture;
   - real M200 temp split fixture compared to current monolithic revision;
   - duplicate scalar/duplicate revision/local catalogue rejection tests.

3. M200 migration:
   - split casillas by section;
   - split export layout by page/record;
   - preserve metadata and all legal/source refs exactly;
   - delete `revisions/2024-y-siguientes.toml` only after equivalence passes.

4. Corpus guard:
   - add a max-lines gate for registry TOMLs, with a temporary ceiling that
     permits existing M100 files until their own fragmentation lands.

5. M100 research/ADR follow-up:
   - quantify stable casilla/formula/binding templates;
   - decide whether templates are worth introducing or whether physical
     fragmentation is sufficient.
