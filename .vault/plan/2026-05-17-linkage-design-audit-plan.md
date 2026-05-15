---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace linkage-design-audit with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#linkage-design-audit'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-17'
# Complexity tier (mandatory for new plans).
# Allowed: L1 (Steps only), L2 (Phases above Steps),
# L3 (Waves above Phases above Steps), L4 (Epic above Waves
# above Phases above Steps; PM association required).
# Pre-existing plans without this field default to L2.
tier: L2
# Related documents as quoted wiki-links.
# Carries the AUTHORISING documents (ADR, research, reference,
# prior plan) for every Step in this plan; Steps inherit this
# chain; per-row reference footers do not exist.
related:
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
  - "[[2026-05-16-linkage-design-audit-audit]]"
  - "[[2026-05-16-linkage-design-audit-plan]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - The related: field carries the AUTHORISING documents (ADR, research,
       reference, prior plan) for every Step in this plan. Steps inherit this
       chain; per-row reference footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artefact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULT PLAN CLI:
     The `vault plan` CLI (vaultspec-core) is the canonical surface
     for structural manipulation of this plan document. Writers and
     executors MUST use `vault plan step add/insert/move/remove/
     check/uncheck/toggle/edit`, `vault plan phase add/move/remove/
     edit`, `vault plan wave add/move/remove/edit`, `vault plan epic
     intent`, and `vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `linkage-design-audit` `Wave 3: referential integrity and typed envelope (Phase 3 of linkage epic)` plan

Wave 3 of the linkage-design epic. Targets the remaining high-leverage
defect classes from the Issue Taxonomy v1 reference document that
Wave 1 (type-system uniformity) and Wave 2 (model consolidation) did
not address:

- T-01: untyped string-keyed cross-boundary value envelopes (Mapping[str, Decimal]).
- T-02: untyped selector sub-schemas (DataBindingDefinition.selector).
- T-03 + T-09: deferred validation and missing existence checks for the 21 typed IDs.
- T-06: architectural-boundary violations the three deferred import-linter contracts surface.
- T-07: CLI / operator output erasure (legal_refs not reaching operator).
- T-12: hand-authored data without schema coupling (BOE record specs).

Wave 1 promotion plan ranked these by leverage. The single highest-
impact intervention is the typed-envelope promotion at the canonical
drop site `src/aeat/application/modelo/_actions.py:817`, which closes
~22 inventory rows by preserving full formula provenance through to
persistence.

## Proposed Changes

Phase ordering follows the Wave 1 promotion plan's leverage ranking,
with referential-integrity gates and architectural enforcement first
(highest coverage-per-effort), then the typed envelope (largest
structural change), then operator-visibility surfacing.

## Steps

### Phase `P01` - referential integrity gate at registry load

Implement `_check_all_id_references` as a pydantic `model_validator`
on `RegistrySnapshot`. Walks the 21 typed IDs declared in `_ids.py`
and asserts existence in the snapshot at every registry load. Closes
T-09 (0 / 21 coverage) and most of T-03 in one implementation. The
single highest-leverage change in the entire taxonomy.

- [ ] `P01.S01` - declare ID-to-collection mapping and the validator function; `src/aeat/domain/calculations/registry/_validate.py`.
- [ ] `P01.S02` - wire validator into RegistrySnapshot constructor; `src/aeat/domain/calculations/registry/_snapshot.py`.
- [ ] `P01.S03` - add `aeat config repair` cross-domain integrity diagnostic; `src/aeat/application/diagnostics.py`.
- [ ] `P01.S04` - add structural pytest exercising the validator against the committed registry; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.

### Phase `P02` - typed cross-boundary value envelope

Define `CasillaObservation` model carrying `(casilla_id, value,
formula_id, legal_refs, source_refs, source_modelo, source_period,
source_filing_year)`. Replace `Mapping[str, Decimal]` on the three
primary cross-boundary models. Persist `engine_result.entries` in
`CalculationRevision` (the canonical R001 drop site). Migrate via
libcst codemod.

- [ ] `P02.S05` - define CasillaObservation typed envelope; `src/aeat/domain/calculations/registry/_bindings.py`.
- [ ] `P02.S06` - persist engine_result.entries in CalculationRevision; `src/aeat/application/modelo/_actions.py`.
- [ ] `P02.S07` - replace casilla_values on RegistryFilingObservation; `src/aeat/domain/calculations/registry/_bindings.py`.
- [ ] `P02.S08` - replace values on RegistryCalculationResult; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [ ] `P02.S09` - replace casilla_values on CalculationRevision; `src/aeat/domain/modelos/_calculation_revision.py`.
- [ ] `P02.S10` - migrate downstream consumers via libcst codemod; `src/aeat/`.
- [ ] `P02.S11` - add semgrep rule preventing Mapping[str, Decimal] regression on registry-tier models; `.semgrep/rules/no-mapping-str-decimal-on-registry.yml`.

### Phase `P03` - discriminated selector unions

Replace `DataBindingDefinition.selector: Mapping[str, str|int|...]`
with a discriminated Union of per-source pydantic models, keyed by
the sibling `source: Literal` field. Eliminates raw `.get()` call
sites across the binding handlers.

- [ ] `P03.S12` - declare per-source selector models; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `P03.S13` - convert DataBindingDefinition.selector to discriminated union; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `P03.S14` - update binding handlers to consume typed selectors; `src/aeat/domain/calculations/registry/_bindings.py`.
- [ ] `P03.S15` - eliminate raw selector.get() call sites in validators; `src/aeat/domain/calculations/registry/_validate.py`.

### Phase `P04` - hexagonal-direction enforcement

Resolve the three import-linter contracts deferred in Wave 2 P06.
Each requires refactor of an offending production path before its
contract can be activated.

- [ ] `P04.S16` - refactor domain.deadlines._profiles to remove application.wizard import; `src/aeat/domain/deadlines/_profiles.py`.
- [ ] `P04.S17` - refactor domain.profile._keys to remove application.wizard import; `src/aeat/domain/profile/_keys.py`.
- [ ] `P04.S18` - refactor core.errors to remove adapters.outbound import; `src/aeat/core/errors/__init__.py`.
- [ ] `P04.S19` - refactor core.i18n._render to remove application imports; `src/aeat/core/i18n/_render.py`.
- [ ] `P04.S20` - refactor domain.attachments._repository to remove adapters import; `src/aeat/domain/attachments/_repository.py`.
- [ ] `P04.S21` - activate domain-not-application import-linter contract; `.importlinter`.
- [ ] `P04.S22` - activate core-not-outer import-linter contract; `.importlinter`.
- [ ] `P04.S23` - activate full layered import-linter contract; `.importlinter`.

### Phase `P05` - CLI legal-grounding surfacing

Adopt the existing `SchemaEnvelope` infrastructure at CLI emit
sites. Add the `--explain` flag per the existing ADR convention so
the operator-facing surface prints `legal_refs` / `source_refs`
attached at the registry layer.

- [ ] `P05.S24` - apply emit_json_success to modelo work-lifecycle commands; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P05.S25` - add typed context keys to RegistryValidationError; `src/aeat/domain/calculations/registry/_errors.py`.
- [ ] `P05.S26` - add typed context keys to RegistrySnapshotError; `src/aeat/domain/calculations/registry/_errors.py`.
- [ ] `P05.S27` - implement --explain flag printing legal_refs in modelo formulas; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P05.S28` - surface legal_refs in review queue findings; `src/aeat/entrypoints/cli/_review.py`.

### Phase `P06` - hand-authored data structural coverage

Address T-12 from the taxonomy. BOE record specs in
`_RECORD_SPECS` tuples per modelo are hand-authored from BOE PDFs.
Parametrised pytest asserts byte-length and casilla-id integrity
against the registry snapshot. Adopt OpenFisca's `reference:
list[LegalRef]` per spec entry.

- [ ] `P06.S29` - add parametrised pytest for record-spec byte-length integrity; `src/aeat/adapters/outbound/aeat/export/_formats/test_record_specs.py`.
- [ ] `P06.S30` - add parametrised pytest for record-spec casilla-id resolution; `src/aeat/adapters/outbound/aeat/export/_formats/test_record_specs.py`.
- [ ] `P06.S31` - add reference field to RecordFieldSpec naming the source BOE Orden; `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`.

### Phase `P07` - close-out audit

- [ ] `P07.S32` - re-run linkage health dashboard and capture final state; `scratch/out/linkage_health.json`.
- [ ] `P07.S33` - regenerate feature index; `.vault/index/linkage-design-audit.index.md`.
- [ ] `P07.S34` - write Wave 3 close-out audit; `.vault/audit/`.

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorising documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

Hard ordering:

- P01 (referential integrity gate) is pure-additive; runs first to
  baseline the integrity guarantee before P02 changes the envelope.
- P02 (typed envelope) is the largest structural change; touches
  the registry, application, and CLI layers. Run after P01 lands so
  the validator can confirm new envelope correctness.
- P03 (discriminated selectors) is independent of P01 / P02 in
  scope - touches only DataBindingDefinition.selector. Can run in
  parallel with P02.
- P04 (hexagonal enforcement) is independent of P01-P03 in code
  scope - touches concrete production paths that violate hexagonal
  direction. Run in parallel with P02.
- P05 (CLI legal surfacing) depends on P02's typed envelope
  carrying legal_refs through to the persistence layer. Sequence
  after P02.
- P06 (record-spec coverage) is independent; can run any time
  after P01.
- P07 (close-out) sequences last.

Recommended dispatch: P01 first, then P02 + P03 + P04 + P06 in
parallel batches, then P05, then P07.

## Verification

Mission-success criteria:

- `_check_all_id_references` fires at every `RegistrySnapshot`
  construction; 0 / 21 ID type coverage becomes 21 / 21.
- `aeat config repair` cross-domain integrity diagnostic reports
  the new check status; CI ratchet gates green.
- `Mapping[str, Decimal]` is gone from `RegistryFilingObservation`,
  `RegistryCalculationResult`, `CalculationRevision`; semgrep
  regression rule blocks reintroduction.
- `engine_result.entries` survives into `CalculationRevision`
  storage; structural pytest asserts round-trip preservation of
  legal_refs through the CLI emit path.
- `DataBindingDefinition.selector` is a discriminated Union;
  `_relations.py` and `_bindings.py` no longer contain raw
  `selector.get(...)` call sites.
- All three previously-deferred import-linter contracts active:
  `domain-not-application`, `core-not-outer`, `layered`.
- `aeat app modelo formulas --explain` prints `legal_refs` /
  `source_refs` for the requested casillas.
- `_RECORD_SPECS` parametrised pytest covers all per-modelo
  modules.
- `just typecheck` continues passing (ty + pyright).
- `just lint-imports` reports all four contracts kept, 0 broken.
