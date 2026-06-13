---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-placeholder-eradication-plan]]'
  - '[[2026-05-27-schema-hardening-label-artifact-inventory-exec]]'
  - '[[2026-05-27-schema-hardening-m100-revision-drift-research]]'
---



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

## Tracking Inventory: Registry Hardening Pathways

This inventory is a sequencing guard. It records which discovered pathways are
already governed by existing vault artefacts and which must not proceed without
a plan or ADR update.

### Already tracked

- Generic revision-fragment authoring is governed by the accepted fragment ADR
  and the fragment-architecture research. Current loader support compiles
  revision fragment directories into the existing runtime schema, and the
  directory-mode loader tests cover fragment equivalence, scalar redeclaration,
  local-catalogue rejection, export-record merging, construct-member merging,
  stale sibling rejection, fragment inventory, and multi-revision single-file
  prevention.
- Validator modularisation is tracked in the schema-hardening plan P05. The
  agreed substrate is bounded helper modules plus the existing public registry
  validation entrypoints, not an opportunistic rewrite.
- Reviewability creep is tracked in this plan P05 and enforced by committed
  TOML line-count and row-width gates. Further registry growth must pass those
  gates rather than relying on review discipline.
- Placeholder labels and empty revision payloads are tracked in this plan
  P01-P04. Future `{name}` or `{number}` casilla-label placeholders and
  zero-casilla revisions are validator failures.
- Cross-revision casilla drift is tracked through the drift validator and its
  committed-corpus gate. Repairs to `label`, `section`, `data_type`,
  `semantic_role`, and `legal_refs` drift must be source-grounded registry
  corrections, not suppressions.
- M200 fragmentation is already landed as the proof that the 100k-line class of
  registry file is not acceptable. The active fragment architecture ADR remains
  the governing decision for further splits.
- Per-modelo standardisation is tracked through the existing model-specific
  schema-hardening plans for M036, M115, M184, M190, M193, M308, M309, M322,
  M347, M353, M360, M390, M720, and M840, plus prior M130 and M131 plans.
- M303 autoconsumo/profile binding work is tracked by its task exec record and
  by the cross-WIP repair section above. It is not a new generic registry
  architecture.

### Requires a plan refresh before implementation

- The next fragmentation target must be selected from current committed
  line-count, revision-count, and layout-mode evidence. The previous candidate
  list has moved because M200 and several standardisation slices have already
  fragmented large surfaces.
- Remaining single-file or partially fragmented modelos must be handled through
  the generic fragment loader path. No model-specific schema definitions or
  loader branches should be added.
- Validator-module size must continue to be watched against the P05 baseline. If
  `_validate.py` or helper modules grow again, the next slice should first
  rebalance modules and tests under the existing public entrypoints.
- Source/evidence failures discovered by broader gates should be fixed in the
  legal/source catalogue or modelo registry data with exact required-text
  grounding. They should not weaken evidence-tier validation.

### Requires a future ADR before implementation

- M100 compile-time template expansion remains a decision, not an
  implementation permission. Physical fragmentation is already allowed by the
  fragment ADR; template expansion would add a new authoring compiler feature
  and must get its own ADR before code or TOML changes.
- Any move from module-level validator helpers to a `validate/` package is a
  compatibility decision if it changes public exports or import boundaries. The
  current plan allows further extraction only while preserving the existing
  registry validation API.

## Follow-up: Fragmentation Target Refresh

The current branch is materially diverged from `origin/main`
(`origin/main...HEAD` reports 53 commits on `origin/main` not in this branch and
3,256 commits on this branch not in `origin/main`). No merge, rebase, reset,
checkout, or stash operation was attempted in this shared worktree. The target
refresh below is therefore scoped to the active branch's tracked registry files.

Registry TOML tracking evidence:

- 26 tracked modelos are in directory layout.
- 42 tracked revision sources use fragment-directory layout.
- 0 tracked revision sources use `revisions/<id>.toml` revision-file layout.
- 0 tracked multi-revision modelos remain in single-file layout.
- Largest tracked registry TOML under `modelos`: 1,618 lines
  (`200/.../0028-modelo-200-page-019.part-002.toml`).
- Largest tracked total modelo footprint: M100 at 134,503 lines across 12,824
  TOML fragments and 6 fragmented revisions.

Top tracked modelos by total TOML lines:

- M100: 134,503 total lines, largest fragment 1,598 lines, 6 fragmented revisions.
- M200: 134,244 total lines, largest fragment 1,618 lines, 1 fragmented revision.
- M303: 9,960 total lines, largest fragment 1,532 lines, 2 fragmented revisions.
- M202: 7,936 total lines, largest fragment 790 lines, 3 fragmented revisions.
- M131: 6,019 total lines, largest fragment 624 lines, 4 fragmented revisions.
- M232: 5,234 total lines, largest fragment 688 lines, 2 fragmented revisions.

Conclusion: there is no current line-count-driven "next split" comparable to
M200. The remaining structural decision is M100 authoring duplication: physical
fragments are already in place, but template expansion would be a new compiler
feature and remains blocked on a future ADR.

## Follow-up: M100 Template Decision

P07.S22 decision: keep M100 on physical fragments only for now. The accepted
fragment architecture ADR already allows physical fragmentation and explicitly
defers template expansion to a later ADR. Current M100 drift research shows that
non-overlapping annual revisions have mixed drift causes: legal-reference
retrofit debt, legitimate annual label evolution, repurposed numeric casilla
ids, and extraction-normalisation debt.

Compile-time templates would need to know which repeated casilla ids represent
the same regulatory concept across years and which ids are annual repurposings.
The current schema has no generic continuity/evolution contract for that
distinction, and adding M100-specific template rules would violate the registry
hardening constraint against ad-hoc per-modelo definitions.

No template-expansion ADR is created in this slice because the decision is not
to add a new authoring compiler feature yet. The next ADR-class substrate is a
generic casilla continuity/evolution model for non-overlapping annual revisions;
until that exists, M100 remains explicit fragmented TOML and template expansion
stays blocked.

## Follow-up: Validator Module Reviewability Gate

P07.S23 decision: do not elevate `registry/_validate.py` and helpers to a
`validate/` package in this slice. Current line-count discovery shows the
validator surface is already below the P05 handoff baseline:

- `_validate.py`: 203 lines against a 204-line P05 baseline after extracting
  cache storage to `_validate_cache.py`.
- Largest current helper: `_validate_revision_sections.py` at 249 lines against
  a 252-line P05 baseline.
- All current `_validate*.py` helpers are below the package-elevation concern
  threshold; the largest non-baselined helper is also below 300 lines.

The first reviewability test run exposed real Python-count growth that
PowerShell line counting had hidden: `_validate.py` and
`_validate_revision_identity.py` were over their P05 ceilings. The slice
rebalanced those modules by moving cache storage and calculation-completeness
manifest validation into bounded helper modules before accepting the gate.

The compatibility boundary, if package elevation becomes necessary later, is to
preserve the public `RegistryValidator` export through
`aeat.domain.calculations.registry.__init__` and preserve direct private-module
imports used by existing tests only until they are migrated. No production
caller should import helper modules directly.

This slice adds a real filesystem gate in
`test_registry_reviewability.py`: P05-named validator modules may not exceed
their recorded P05 line-count baselines, and any new `_validate*.py` helper is
capped at 300 lines. Future validator growth must therefore extract/rebalance
before it can merge.

## Follow-up: Casilla Continuity Contract Research

P07.S24 research is persisted in
`2026-05-27-schema-hardening-casilla-continuity-contract-research`. The finding
is that M100 template expansion should not proceed until the schema has a
generic continuity/evolution contract for non-overlapping annual revisions.

The recommended next architectural substrate is not a template compiler. It is
an ADR for explicit continuity metadata, with hard validation only after a
modelo opts into the contract. Repeated casilla ids and annual labels are
insufficient identity evidence because current M100 drift includes legitimate
annual evolution, legal-reference retrofit debt, extraction normalisation debt,
and real id repurposing.
