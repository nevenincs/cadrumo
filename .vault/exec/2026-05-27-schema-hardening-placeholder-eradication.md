---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-placeholder-eradication-plan]]'
  - '[[2026-05-27-schema-hardening-label-artifact-inventory]]'
  - '[[2026-05-27-schema-hardening-m100-revision-drift-research]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `schema-hardening` `placeholder-eradication`

Removed unresolved format placeholders from the committed casilla-label
corpus and promoted the detector from advisory inventory to a hard
registry-scope validation gate.

## Description

The prior advisory inventory found 266 unresolved format placeholders, all in
Modelo 100 revision 2021 casilla labels. The cleanup was intentionally
mechanical and limited to label text:

- `{0}` was normalized as a whitespace separator, with adjacent whitespace
  collapsed around the placeholder.
- `{2}X{2}`, `{2}UR{2}`, and `{2}RU{2}` were normalized to quoted marker text
  based on neighboring annual revision labels.

No casilla ids, sections, data types, semantic roles, legal references,
formulas, bindings, source references, loader behavior, or schema semantics
were changed.

The resulting committed corpus has zero unresolved label placeholders. The
generic validator now reports any future `{name}` or `{number}` placeholder in
a casilla label through registry-scope validation instead of allowing a new
baseline to accrete.

## Deferred Edges

M100 revision 2021 casilla `0580` still carries a suspected semantic label
issue noted during cleanup review. That was not corrected here because this
slice only removes unresolved formatting artifacts.

## Tests

Final passing gates:

`uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_label_artifacts.py src/aeat/domain/calculations/registry/_validate_registry_scope.py src/aeat/domain/calculations/registry/test_label_artifacts.py`

Result: passed.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_label_artifacts.py -q`

Result: 5 passed.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_label_artifacts.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`

Result: 47 passed.

`rg "\{0\}|\{2\}" src/aeat/_data/registry/aeat/modelos/100/revisions/2021/casillas -n`

Result: no matches.

`collect_label_artifact_findings` over the bundled AEAT registry returned
zero findings.

Initial broader gate, not swallowed:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`

Result: 76 passed, 1 failed. The failure is unrelated to this placeholder
slice: `StoredTransactionDriftError` is missing a declared ErrorCode registry
entry during import of the transaction error registry through the user-profile
path.

## Follow-up: Empty Revision Eradication

The next placeholder class was registry definitions with a revision but no
casillas. A bundled registry scan found exactly three such definitions:
`151`, `714`, and `721`. Each carried legal/source authority and, for `721`,
deadline windows, but no casilla payload, formulas, bindings, or extraction
surface.

Those definitions were removed from the normal modelo registry. Their legal
and source catalogue entries remain available, and the CLI work-creation
refusal tests continue to assert that local unsupported work units are refused
with the governing legal authority instead of falling through to a generic
unknown-modelo crash.

The registry validator now rejects any future zero-casilla revision with a
generic failure: `revision must declare at least one casilla`. The committed
corpus test asserts there are no zero-casilla revisions in the bundled registry.

Passing focused gates:

`uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_revision_identity.py src/aeat/domain/calculations/registry/_validate_revision_sections.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/entrypoints/cli/test_modelo_151_stub_refusal.py src/aeat/entrypoints/cli/test_modelo_714_stub_refusal.py src/aeat/entrypoints/cli/test_modelo_721_stub_refusal.py src/aeat/entrypoints/cli/test_overview_explain_verb.py`

Result: passed.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_schema.py -q`

Result: 76 passed.

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_151_stub_refusal.py src/aeat/entrypoints/cli/test_modelo_714_stub_refusal.py src/aeat/entrypoints/cli/test_modelo_721_stub_refusal.py src/aeat/entrypoints/cli/test_overview_explain_verb.py -q`

Result: 15 passed.

Direct registry scan after deletion returned no zero-casilla revisions and no
registered `151`, `714`, or `721` modelo definitions.

Broader gate, not swallowed:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Result: 156 passed, 3 failed. The failures are existing cross-WIP surfaces
outside this empty-revision slice: Modelo 130 no longer emits calculated target
`03` in `test_committed_registry`, and M100 2024/2025 registry validation is
failing on `ley-35-2006:art-52` / `irpf_reduccion_prevision_social_total`
semantic-role drift.

## Follow-up: Reviewability Creep Gate

Post-split baseline:

- Largest registry TOML: `legal/irpf.toml`, 2,948 lines.
- Largest modelo TOML: `modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002.toml`, 1,618 lines.
- Longest registry TOML line: `legal/is.toml`, 884 characters.

The committed-corpus reviewability gate now enforces a hard ceiling of 5,000
lines per TOML file and 1,200 characters per TOML row, plus a tighter baseline
watch that fails if the current largest file crosses 3,500 lines or the widest
row crosses 1,000 characters. This leaves headroom for small regulatory updates
while making a return to 100k-line registry artifacts impossible without an
explicit test failure.

Passing gates:

`uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_registry_reviewability.py`

Result: passed.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`

Result: 2 passed.

## Follow-up: Cross-WIP Registry Gate Repair

The broader registry hardening gate exposed three shared-worktree edges after
the empty-revision and reviewability commits:

- M100 revisions 2024 and 2025 had a cross-revision drift failure for the
  prevision-social reduction total casilla data type.
- The committed M130 snapshot test still expected target `03` as a calculated
  formula output even though the current registry shape sources it through a
  binding.
- The new M303 autoconsumo profile input needed the profile schema `money`
  field type, construct-level LIVA art. 9/art. 79 propagation, and an
  official-guidance source citation for the profile-derived binding/formula.

The repair kept the validators strict. The LIVA art. 79 required-text needle was
aligned with the local BOE corpus phrase `gastos de personal`; the M303 binding
and formula now cite the official Modelo 303 BOE form source; and the construct
legal refs include the articles introduced by the autoconsumo casillas.

Passing gates:

`uv run --no-sync pytest src/aeat/domain/user_profile/test_schema.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress src/aeat/domain/calculations/registry/test_committed_registry.py::test_committed_modelo_130_registry_snapshot_is_calculable -q`

Result: 8 passed.

`uv run --no-sync ruff check src/aeat/domain/user_profile/_schema.py src/aeat/domain/user_profile/test_schema.py src/aeat/domain/calculations/registry/test_committed_registry.py`

Result: passed.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`

Result: 161 passed.
