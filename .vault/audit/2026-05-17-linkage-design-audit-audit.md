---
tags:
  - '#audit'
  - '#linkage-design-audit'
date: '2026-05-17'
modified: '2026-05-17'
related:
  - "[[2026-05-17-linkage-design-audit-plan]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
---



# `linkage-design-audit` audit: `Wave 3 close-out: referential integrity + envelope + hexagonal contracts`

## Scope

Wave 3 of the linkage-design epic. Targeted the highest-leverage
remaining defect classes after Waves 1 (type-system uniformity) and 2
(model consolidation):

- T-01 (untyped value envelope) and T-07 (CLI output erasure) — the
  canonical drop site at `_actions.py:817`.
- T-02 (untyped selector sub-schema) — DataBindingDefinition.selector.
- T-03 (deferred validation) and T-09 (missing existence check) — 21
  typed-ID coverage.
- T-06 (architecture-boundary violation) — three deferred import-linter
  contracts.
- T-08 (unused typed JSON contract) — SchemaEnvelope adoption.
- T-12 (hand-authored data) — BOE record-spec coupling.

Plan: 7 Phases, 34 Steps, L2 tier. All Steps closed.

## Findings

### Headline numbers

- T-09 coverage: **0 / 21 → 21 / 21**. Every typed-ID reference in the
  registry is now walked at every `RegistrySnapshot` construction by
  `_check_all_id_references`. `aeat config repair` ships a new
  `registry.integrity` diagnostic.
- T-01 coverage: canonical `Mapping[str, Decimal]` envelope replaced
  with `CasillaObservation` carrying full provenance
  (casilla_id, value, formula_id, legal_refs, source_refs,
  source_modelo, source_period, source_filing_year, operand_refs,
  operand_values). `engine_result.entries` now persists into
  `CalculationRevision`. The canonical R001 drop site is structurally
  fixed.
- T-02 coverage: **0 / 3 → 3 / 3**. `DataBindingDefinition.selector`
  is a pydantic discriminated `Union` over 8 per-source models keyed
  by `source: Literal[...]`. Raw `.get()` call sites in
  `_validate.py`, `_relations.py`, and tests eliminated.
- T-06 coverage: import-linter contracts active: `no-renta-in-registry`
  (Wave 2 P04), `domain-not-application` (Wave 3 P04 S21),
  `core-not-outer` (Wave 3 P04 S22), `layered` (Wave 3 P04 S23). All 4
  contracts kept, 0 broken.
- T-08 coverage: 14 modelo work-lifecycle commands now use the typed
  `SchemaEnvelope` via `_emit_envelope` helper; 15
  `@register_schema`-decorated payload models in
  `_modelo_payloads.py`. The `--explain` flag prints `legal_refs` on
  `aeat app modelo formulas` and `aeat app review view`.
- T-12 coverage: parametrised pytest scaffold in place at
  `_formats/test_record_specs.py`. Auto-discovers `modelo_*` spec
  modules; tests will run when the first spec module lands. The
  `RecordFieldSpec` model gained a `reference: tuple[str, ...]` field
  per OpenFisca's pattern.
- ty check: 0 diagnostics across `src/aeat/`.
- pyright real-bug tier in `src/aeat/domain` and `src/aeat/application`
  remains at 0. The 162-error annotation-completeness ratchet baseline
  is unchanged.

### Phase-by-phase

- **P01** — `_check_all_id_references` validator declared in
  `_validate.py`, wired into `build_snapshot`, surfaced via the
  `registry.integrity` diagnostic. 25 structural tests cover
  every typed-ID slot plus the diagnostic JSON surface.
- **P02** — `CasillaObservation` typed envelope defined.
  `RegistryFilingObservation.observations`,
  `RegistryCalculationResult.observations`, and
  `CalculationRevision.observations` replace the prior `casilla_values`
  / `values` mappings. `@computed_field` properties preserve
  backward-compatible read shapes. Drop site at `_actions.py:817`
  fixed. Semgrep rule
  `no-mapping-str-decimal-on-registry.yml` blocks reintroduction.
- **P03** — 8 per-source pydantic selector models declared.
  `BindingSelector = Annotated[Union[...], Field(discriminator="source")]`
  replaces the untyped mapping. `_sel()` / `_selector_dict()` helpers
  bridge legacy callers while the discriminated union takes over.
- **P04** — five production paths refactored to eliminate
  hexagonal violations: `core/errors/_registry.py` uses `core.i18n`
  for translation; `core/i18n/_render.py` adopts the
  `register_profile_language_resolver` callback pattern;
  `domain/profile/_keys.py` uses a `register_profile_keys()`
  injection function; `domain/attachments/_repository.py` is
  Protocol-only with the concrete store moved to
  `adapters/persistence/storage/attachment.py`;
  `domain/profile/conftest.py` registers profile keys via side-effect
  import for domain test fixtures. Three import-linter contracts
  activated.
- **P05** — `SchemaEnvelope` adopted across modelo work-lifecycle
  commands. Typed `context` dicts on `RegistryValidationError` raise
  sites in `_bindings.py` and on `RegistrySnapshotError` raise sites
  in `_authority.py`, `_temporal.py`, `_constructs.py`. `--explain`
  flag on `aeat app modelo formulas` and `aeat app review view`
  prints `legal_refs` in text mode; JSON payload always carries them.
  `ReviewQueueRow.legal_refs` field populated from
  `FindingReviewItem.source.references_rules`.
- **P06** — `_RECORD_SPECS` integrity-test scaffold ready at
  `_formats/test_record_specs.py` (byte-length + casilla-id resolution
  + auto-discovery). `RecordFieldSpec.reference: tuple[str, ...]`
  field added.
- **P07** — this audit.

## Recommendations

1. **Wave 4 scope** is now scaffolded at
   `.vault/plan/2026-05-18-linkage-design-audit-plan.md` covering the
   28 still-open inventory rows. Phases P01..P11 target CLI relation
   support (F11), CLI typed IDs (F21), sensitivity classification on
   schema (F4), capability-driven gates (J class), M100 registry data
   backfill (F15, F16), identity propagation (F14, F20), workflow
   step typed details, form-numeric casilla bridge (F10), cross-modelo
   mechanism unification (F12, F13), residual export coverage, and
   close-out. Wave 4 P09.S30 (OracleId typed alias) landed in main
   thread alongside this Wave; Wave 4 P06 (identity propagation) was
   dispatched in parallel with Wave 3 P05.

2. **Annotation-completeness ratchet** — the 162-error pyright
   baseline (predominantly `reportMissingParameterType`,
   `reportPrivateUsage` on tests, `reportUnusedFunction` on fixtures)
   remains. Track count downward over time without making it gating in
   CI. The Unknown-family rules are not currently enabled in
   `pyrightconfig.json` and are a separate workstream.

3. **CLI typed-envelope adoption** — 14 modelo work-lifecycle commands
   now use `_emit_envelope`. The remaining CLI commands (under
   `aeat config`, `aeat app registry`, `aeat app review` partial)
   should adopt the same pattern in a follow-up phase.

4. **Documented-irreducible suppressions** at the end of Wave 1 (3
   `ty: ignore[invalid-assignment]` for stdlib logging protocol; 1
   `cast(Callable[P, R], ...)` in CLI errors caching; pydantic
   `__iter__` dunder shims) remain. These are protocol-imposed
   irreducibilities and should be revisited only if upstream typing
   stabilises.

5. **Health-dashboard tool** at `scratch/linkage_health.py` is now the
   canonical ratchet metric. Six gates: ty, pyright (per package),
   import-linter, suppression inventory, pydantic audit. Should be
   wired into the development loop alongside the existing `just
   typecheck` / `just lint-imports`.
