---
tags:
  - '#adr'
  - '#linkage-design-audit'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - "[[2026-05-26-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-17-linkage-design-audit-plan]]"
  - "[[2026-05-18-linkage-design-audit-audit]]"
---

# `linkage-design-audit` ADR: `boundary-typed-contracts` (**status:** `accepted`)

This ADR records four related architectural decisions for the
`linkage-design-audit` plan, all ratifying the "contract typed
at the boundary" theme:

1. `casilla-values-collapse-projection-strategy` — collapse
   `CalculationRevision.casilla_values` into a derived projection
   over the typed `observations` envelope (authorises plan rows
   `P02.S09`, `P08.S36`, `P08.S37`).
2. `registry-error-typed-context-factories` — pin the context
   payload of `RegistryValidationError` and `RegistrySnapshotError`
   via classmethod factories so locales and CLI emit consume one
   named contract per error scenario (authorises plan rows
   `P05.S25`, `P05.S26`).
3. `json-envelope-migration-sequencing` — migrate the modelo
   work-lifecycle command JSON output from bare payload to the
   `SchemaEnvelope`-wrapped shape per-command incrementally,
   with the conformance test accepting both shapes during
   migration (authorises plan rows `P09.S40`, `P09.S41`,
   `P09.S42`, `P09.S43`, `P09.S44`).
4. `repair-integrity-cross-campaign-coordination` — scaffold
   compatible stubs of the `RepairRemediationDecision` family
   in `chore/eliminate-shims` to satisfy the linkage test
   surface today, while preserving the live-iva-compensation-
   wallet campaign's authority over the canonical implementation
   (authorises plan rows `P10.S45`, `P10.S46`, `P10.S47`,
   `P10.S48`, `P10.S49`).

## Decision 1: `casilla-values-collapse-projection-strategy` (**status:** `accepted`)

## Status

Accepted (autonomous self-review, 2026-05-26). Grounded against the
companion research note and the in-flight cross-campaign survey
recorded therein. No human-in-the-loop blocker; the staged-path
choice keeps every reversibility door open.

## Problem Statement

`CalculationRevision` currently carries two storage fields for the
per-casilla output payload:

- `casilla_values: Mapping[str, Decimal]` — the original flat
  mapping, persisted on every revision, threaded into
  `derive_calculation_revision_id` to compute the content-addressed
  SHA-256 identity.
- `observations: tuple[CasillaObservation, ...]` — the typed
  envelope carrying formula provenance (added by the dual-write
  campaign at commit `b995da5c8`), default-factory empty for
  backward-compat with revisions persisted before it landed.

The `linkage-design-audit` plan step `P02.S09` calls for
collapsing the flat field into a derived projection over the typed
envelope so the typed observations become the single source of
truth — matching the canonical pattern already established on
`RegistryModeloObservation` (R002) and `RegistryCalculationResult`
(P02.S08, commit `6963600c0`).

The collapse is constrained by content-addressed identity: every
already-persisted revision id was derived against the current hash
payload shape. Any change to the projection must produce a
byte-identical hash for the same logical state, or every catalogue
row mismatches its derived id and the content-addressing invariant
breaks.

The pre-flight pin landed in `P08.S35` (SHA-256
`5b78dd04e614a50fe448439b7fdb843f1e31afe76f9d424d0276866679dee7ca`
for a fully-populated derivation) is the regression anchor; the
decision below must keep this pin stable.

## Decision

Adopt a **staged two-strategy path**:

1. **Stage one (this wave):** keep `casilla_values` as a model field
   on `CalculationRevision`, but route both the constructor's
   id-derivation check and `derive_calculation_revision_id` through
   a single new derivation helper that materialises the
   `{casilla_id: Decimal}` projection from the typed `observations`
   envelope. The flat field becomes a denormalised cache enforced
   equal to the projection at construction time; the typed envelope
   becomes the **logical source of truth** even though both fields
   persist on the wire. Hash domain unchanged — the pinned SHA stays
   stable because the projection produces the same byte string.

2. **Stage two (separate ADR, future cycle):** schedule the full
   wire-shape collapse — drop `casilla_values` as a stored field,
   expose it as a derived `@property` over `observations` (mirroring
   `RegistryModeloObservation`), and migrate every persisted
   catalogue row to the typed-envelope-only payload. Gated behind a
   one-shot data migration ADR and behind one release cycle of
   stage-one running in production.

The staged path was chosen over a one-shot Strategy-B-only landing
because:

- Stage one closes the **P02.S09 logical intent** (typed envelope
  is canonical for derivation) with zero wire-shape risk and zero
  data migration. The 27 construction sites need only `observations=`
  passed alongside `casilla_values=`; both fields land in storage.
- Stage two is properly framed as **what it actually is**: a
  persistence-boundary migration deserving its own ADR with explicit
  upcast semantics for historical rows that lack `observations`.
  Forcing it through P02.S09 conflates two concerns and creates a
  data-migration crisis inside what should be a refactor.
- Reversibility is preserved at every step. If stage two surfaces
  an unanticipated downstream coupling, stage one can run
  indefinitely without harm — the typed envelope is canonical, the
  flat field is a derived cache.

## Consequences

### Stage one (this wave, plan rows `P02.S09` + `P08.S37`)

- `_outputs_for_hash(observations)` helper lands in
  `aeat.domain.modelos._calculation_revision` materialising the
  canonical `{casilla_id: Decimal}` projection. Pure function,
  trivially testable, used by both the model validator and the id
  derivation.
- `derive_calculation_revision_id` signature unchanged at the boundary;
  internally re-routed through the helper when called from the
  constructor (`CalculationRevision._enforce_invariants`). External
  callers that still pass `casilla_values=` keep working unchanged.
- `CalculationRevision._enforce_invariants` re-derives `casilla_values`
  from `self.observations` (when populated) and asserts equality
  with the persisted field. Mismatch raises
  `ModeloValidationError` — turns silent drift into a load-time
  refusal.
- 27 construction sites unchanged for the `casilla_values=` argument;
  the 12+ already passing `observations=` gain the new validator
  guard for free.
- 4 roundtrip suites stay green — fixture shapes unchanged.
- W09.P20 cross-module-import gate stays green — no public surface
  changed.
- The P08.S35 hash-stability pin stays green — projection is
  byte-identical to the current inline projection in
  `derive_calculation_revision_id`.

### Stage two (separate ADR, future cycle)

- New ADR: `casilla-values-flat-field-retirement` — declares the
  data migration semantics, the upcast rule for historical rows
  with no `observations`, and the JSON-schema bump.
- Roundtrip suites re-baseline against the typed-envelope-only
  payload.
- Storage envelopes (encrypted catalogue rows) migrate; one-shot
  upcast on read for rows persisted under stage-one.
- `_outputs_for_hash` helper retained as the canonical projection;
  hash signature unchanged.

## Compliance with established mandates

- **AEAT calculation grounding rule** ("persist typed envelopes, not
  flat scalar mappings"): stage one makes the typed envelope the
  logical source of truth; stage two completes the wire-shape
  alignment. The rule's intent is satisfied at decision time even
  though wire shape carries both fields for one release cycle.
- **Roundtrip discipline rule** ("strict pydantic equality across
  every persistence boundary"): the model validator's
  re-derivation-then-compare turns the flat field into a
  load-time-verified cache; any save/load drift fails at load time
  with `ModeloValidationError`. Hash-stability pin
  (P08.S35) plus the validator assertion together cover both
  directions.
- **Hexagonal direction**: change is confined to
  `aeat.domain.modelos`; no application or adapter import edges
  shift.
- **Anti-tautology**: the helper is pure and exercised by the
  pinned SHA test; if the helper drifts, the pin fails. No
  hand-derived test values introduced.

## Risks accepted

- **One release cycle of dual persistence**: revisions persisted
  during stage one carry both `casilla_values` and `observations`
  on the wire. The validator enforces consistency at load time, so
  drift surfaces immediately, but the storage envelope is larger
  than the eventual stage-two shape. Acceptable for one cycle.
- **Validator strictness on historical rows**: revisions persisted
  before the typed envelope landed (`observations` empty) will
  pass the validator trivially (no projection to compare).
  Acceptable — those rows pre-date the typed envelope and cannot
  be retroactively enriched without a parallel calc replay.

## Plan linkage

This ADR authorises plan steps:

- `linkage-design-audit P02.S09` (collapse `CalculationRevision.casilla_values`
  to derived-from-observations projection at the hash boundary)
- `linkage-design-audit P08.S36` (close-out step naming this ADR)
- `linkage-design-audit P08.S37` (execute stage one against the
  P08.S35 pin)

Stage two is deferred to a separate ADR
`casilla-values-flat-field-retirement` scheduled after one release
cycle of stage one running in production.

## Decision 2: `registry-error-typed-context-factories` (**status:** `accepted`)

### Problem Statement

`RegistryValidationError` and `RegistrySnapshotError` are raised
across 29 production sites in
`src/aeat/domain/calculations/registry/` each passing an ad-hoc
`context` dict via the `AeatError` base class. Downstream
consumers (the `aeat.core.errors._registry.resolve_error_message`
template renderer, CLI JSON emit via `SchemaEnvelope`, the i18n
translation layer that references context keys by name in locale
files) all assume specific keys exist but no contract pins them.
A key rename today silently breaks one locale per cycle.

The companion research note's key inventory shows 14 distinct
context keys clustered into roughly six canonical raise scenarios
(unknown parameter, unknown binding, dispatch-key resolution,
unsupported op, bracket coverage, casilla referenced-before-eval).

### Decision

Adopt **Strategy R: classmethod factories per canonical raise
scenario** on `RegistryValidationError` and
`RegistrySnapshotError`. Each factory takes typed kwargs and
builds both the error message and the canonical context dict.
The existing `raise RegistryValidationError(message, context=...)`
shape stays valid during migration; new raises route through the
factories. The locale layer and CLI emit gain one named contract
per error scenario.

Migrate **highest-traffic scenarios first**: the canonical
factory set covers the unknown-parameter, dispatch-key-unknown,
unsupported-op, bracket-coverage, and casilla-referenced-before-eval
families. The 4-key tail (one-off raises with single-use keys
like `filing_date`, `computed`) stays ad-hoc until a downstream
consumer pins them — pulling them all up-front would inflate the
factory surface beyond the actual contract.

Strategy R chosen over:
- **Strategy P (key constants)** — too weak; constants don't
  enforce that callers pass them together. A constant for
  `"casilla_id"` doesn't help if a caller passes `casilla` instead.
- **Strategy Q (pydantic context model)** — overkill for the
  current usage; pydantic-validating the context payload at raise
  time adds runtime cost on the error path (when the system is
  already failing) without proportional gain over factory methods
  that name the scenario explicitly.

### Consequences

- `RegistryValidationError.for_unknown_parameter(parameter_id=...)`
  returns a constructed error with canonical `context={"parameter_id": ..., ...}`
  and the templated message keyed for the i18n locale layer.
- Same pattern for `for_dispatch_key_unknown`, `for_unsupported_op`,
  `for_bracket_no_coverage`, `for_casilla_referenced_before_evaluation`,
  `for_unknown_input_casillas`, `for_computed_supplied_as_input`,
  `for_unknown_external_value` (binding / relation variants),
  `for_lookup_dispatch_arg_kind`, `for_lookup_dispatch_arg_count`.
- `RegistrySnapshotError.for_modelo_not_registered(modelo_id=...)`
  covers the single canonical scenario at `_authority.py:51`.
- Existing raise sites convert to factory calls row by row; an
  anti-tautology test asserts every committed raise site routes
  through a factory (no naked `RegistryValidationError(...)`
  construction with `context=` outside the error module).
- Locale files (`src/aeat/locales/*.yml`) keep their existing
  template keys; the factories pin the kwargs that flow into the
  templates so locale renames are caught by the type checker
  rather than at user-facing render time.

### Compliance with established mandates

- **AEAT calculation grounding rule**: legal_refs / source_refs
  flowing through error context now have a named place to live;
  `RegistryValidationError.for_casilla_constraint_violation`
  carries them explicitly.
- **No tautological tests** rule: the factory exercise tests
  assert against external authorities — locale template render
  output and the `error.context` dict shape — not against the
  factory's own internals.
- **Hexagonal direction**: change confined to
  `aeat.domain.calculations.registry._errors`; no application or
  adapter import edges shift.

### Risks accepted

- **Migration churn on 29 raise sites**: row-by-row conversion is
  mechanical but touches many files in the registry package. The
  factory shape stays additive (old constructor signature still
  works) so the migration is non-breaking; out-of-tree consumers
  unaffected.
- **Tail of one-off context keys stays ad-hoc**: the four-key tail
  identified by the research (filing_date, computed, etc.) remains
  on the bare `context=` path until a downstream consumer pins
  them. Acceptable — no consumer currently needs them.

### Plan linkage

This decision authorises plan steps:

- `linkage-design-audit P05.S25` (typed factories on
  `RegistryValidationError`)
- `linkage-design-audit P05.S26` (typed factories on
  `RegistrySnapshotError`)

`P05.S27` (`--explain` flag implementation) and `P05.S28`
(legal_refs on review-queue findings) inherit the existing
`2026-05-13-cli-workflow-redesign-explain-legal-ref-convention-adr`
authority — no new architectural decision required at those rows.

## Decision 3: `json-envelope-migration-sequencing` (**status:** `accepted`)

### Problem Statement

Today's `aeat` CLI work-lifecycle commands emit bare JSON
payloads via `_emit(ctx, payload, lines)` (`_common.py:46`).
The canonical contract per `aeat.core.json_contract.emit_json_success`
wraps the payload in a `SchemaEnvelope` (`schema_version`,
`command`, `result`, `warnings`). The `2026-04-25-json-output-contract`
audit documents the gap: "newly registered emitters do not use
[the envelope]: they write raw objects or arrays directly from
command code".

The typed `OutputSchema` subclasses and `@register_schema(...)`
decorators are already in place at `_modelo_payloads.py` for the
11 work-lifecycle commands. The missing piece is the emit-site
routing — a contract-breaking change to the CLI JSON output
shape that re-baselines every downstream JSON-shape test pinned
by `test_json_schema_conformance.py:167-169` plus the per-command
surface tests.

The companion research note's third-topic section catalogues the
sequencing options (whole-surface flip / per-command incremental
/ dual-emit compatibility window).

### Decision

Adopt **Strategy B — per-command incremental migration** with a
**short-lived dual-shape conformance mode** as the bridge:

1. Update `test_json_schema_conformance` to accept BOTH the
   envelope shape and the bare-payload shape during the migration
   window, gated by a per-command `MIGRATED_COMMANDS` set
   declared in the conformance test itself.
2. Migrate one work-lifecycle command per commit, adding the
   command's canonical path string (e.g. `"modelo.work.calculate"`)
   to `MIGRATED_COMMANDS` in the same commit. Update every
   per-command surface test that probes the JSON output to expect
   the envelope shape for the migrated command.
3. The 11-command surface migrates over 11 commits; each commit
   is internally consistent and bisect-friendly.
4. Once every work-lifecycle command is migrated, remove the
   `MIGRATED_COMMANDS` gate from the conformance test and tighten
   the assertion to envelope-only for the work-lifecycle surface.
   Other CLI surfaces (`registry`, `audit`, `overview`, etc.)
   remain bare-payload until their own per-surface migration
   ADRs.

Strategy B chosen over:

- **Strategy A (whole-surface flip in one commit)** — concentrates
  risk and review burden; a single commit touches 11 commands
  plus 30+ test files. The bisect cost when a regression sneaks
  through is high.
- **Strategy C (dual-emit compatibility window in `_emit` itself)**
  — bakes a permanent dual-shape into the emit helper, eroding
  the "envelope is the contract" intent the json-output-contract
  audit established. Convenient short-term, but the dual shape
  outlives the migration and weakens the contract.

### Consequences

- **First commit lands the infrastructure**: extend
  `test_json_schema_conformance` with the `MIGRATED_COMMANDS` set
  + dual-shape acceptance helper. Empty set; no command migrated
  yet. The conformance test stays green against the existing
  bare-payload shape.
- **Per-command commits** then add one entry to `MIGRATED_COMMANDS`
  AND migrate the corresponding command's emit site AND
  re-baseline its surface tests. The proof-of-pattern landing is
  `aeat app modelo work calculate` (the canonical work-lifecycle
  command, recently touched by P02.S08).
- **Conformance test surface** stays green at every commit
  boundary — that's the contract the per-command incremental
  approach buys.
- **Locales unaffected** — the JSON envelope keys (`schema_version`,
  `command`, `result`, `warnings`) are not user-facing translatable
  strings; the locale layer continues to render the wrapped
  `result` payload as before.
- **`emit_json_success`'s `warnings=` arg** — work-lifecycle
  commands today don't emit non-fatal warnings; the migration
  passes `warnings=None` for now. Per-command warning-emission
  scopes belong to future ADRs.

### Compliance with established mandates

- **AEAT calculation grounding rule**: legal_refs / source_refs
  surfaced via the `--explain` ADR convention continue to render
  inside the envelope's `result` key — unchanged shape from the
  consumer perspective beyond the wrapper.
- **No tautological tests** rule: the conformance test's dual-shape
  mode asserts against external authorities — the actual command
  output bytes and the registered schema's JSON Schema — not
  against the migration's own state.
- **Hexagonal direction**: change is confined to
  `aeat.entrypoints.cli` (per-command emit sites) and the
  conformance test surface; no domain or adapter import edges
  shift.
- **Anti-tautology**: each per-command commit's surface test
  must assert against the actual rendered JSON bytes including
  the envelope shape, not against the per-command payload model
  in isolation.

### Risks accepted

- **Dual-shape conformance window**: during the 11-commit
  migration the conformance test accepts both shapes. A
  regression in an unmigrated command that accidentally emits an
  envelope (or vice versa) would pass the conformance test until
  surface tests catch it. Acceptable for a bounded window;
  mitigated by per-command surface tests asserting the exact
  expected shape.
- **Per-command commit cost**: 11 commits is non-trivial review
  load. The benefit is bisect-friendly migration history.

### Plan linkage

This decision authorises plan steps:

- `linkage-design-audit P09.S40` (research note extension —
  already landed at the `2026-05-26-linkage-design-audit-research`
  third-topic section)
- `linkage-design-audit P09.S41` (this ADR section)
- `linkage-design-audit P09.S42` (proof-of-pattern: migrate
  `aeat app modelo work calculate` + conformance dual-shape
  infrastructure)
- `linkage-design-audit P09.S43` (migrate remaining 10
  work-lifecycle commands per the per-command sequencing)
- `linkage-design-audit P09.S44` (close the dual-shape window —
  remove `MIGRATED_COMMANDS` gate, tighten conformance to
  envelope-only for the work-lifecycle surface)

## Decision 4: `repair-integrity-cross-campaign-coordination` (**status:** `accepted`)

### Problem Statement

The W09.P20 cross-module-import gate carries 4 baseline entries
for `RepairRemediationDecision`, `RepairRemediationDecisionRepository`,
`repair_remediation_decision_id`, and `build_repair_policy_command_surface_catalog` —
all imported by two test files in `chore/eliminate-shims`
(`test_runtime_migrated_repositories.py` and `test_repair_policy_coverage.py`)
but not defined in `src/aeat/application/repair_integrity.py` on
this branch.

The live-iva-compensation-wallet campaign's exec record
`2026-05-22-live-iva-compensation-wallet-w05-p02-s01.md`
documents that those symbols ARE landed in that campaign's
working tree with full preserve / quarantine / rebuild /
export-required semantics, encrypted AUDIT-class secure-object
persistence, and content-addressed decision ids. The work
hasn't propagated to `chore/eliminate-shims` yet.

The mono-worktree mandate from the user pulls this previously-
deferred coordination work back into scope; the companion
research note's fourth-topic section catalogues the three
options (wait for upstream / scaffold compatible stubs / pull
production code wholesale).

### Decision

Adopt **Strategy Q — scaffold compatible stubs** matching the
exec-record-documented public contract and the test surface's
imports. The four symbols land in `src/aeat/application/repair_integrity.py`
as additive code; the live-iva-compensation-wallet campaign's
full implementation supersedes via standard merge resolution
once their work lands.

Stub shape (recovered from the test surface and the exec record):

- `RepairRemediationDecision` — pydantic `BaseModel` with
  fields: `decision_id`, `namespace`, `row_digest_hex`,
  `decided_at`, `reason`, `likely_origin`, `replacement_evidence`,
  `verified_evidence_refs`, `mutation_authorized` (literal
  `False`).
- `RepairRemediationDecisionRepository` — class exposing
  `save_decision(decision)`, `load_decision(decision_id)`,
  `list_decisions()` (decision-time descending). Persists to
  encrypted AUDIT-class secure-object rows in a profile-local
  namespace.
- `repair_remediation_decision_id(*, ...)` — pure function
  returning the content-addressed SHA-256 id from the same
  field set the model carries, with `decided_at` deliberately
  excluded so re-runs of the same logical decision produce
  the same id.
- `build_repair_policy_command_surface_catalog()` — returns a
  tuple of repair-policy surfaces whose `command_path` strings
  match the CLI command registry.

Strategy Q chosen over:

- **Strategy P (wait for upstream)** — preserves cross-campaign
  hygiene but defers indefinitely; the W09.P20 baseline carries
  the 4 entries until then; the linkage test surface stays
  broken at collection time when those tests are exercised.
- **Strategy R (pull production code wholesale)** — copies the
  other campaign's WIP design into this branch before they've
  committed it, violating the "do not stomp WIP" discipline
  from the parallel-worktree memory. Even though the
  mono-worktree mandate authorises cross-campaign work, the
  WIP-stomp ban is a separate discipline preserved for
  authorship attribution.

### Consequences

- Stubs land as a single commit at `repair_integrity.py`. The
  module's existing functions (`build_repair_integrity_report`,
  `build_repair_list_report`) stay untouched.
- W09.P20 gate's silent-fix detector demands the baseline trim
  immediately; the 4 entries leave `_BASELINE_BROKEN_IMPORTS`.
- The two consumer test files (`test_runtime_migrated_repositories.py`
  and `test_repair_policy_coverage.py`) now collect and exercise
  the stubs.
- `test_runtime_migrated_repositories.py` was deferred under
  P08.S39 because it couldn't collect; this ADR re-opens that
  verification.
- When the live-iva-compensation-wallet campaign's full
  implementation merges, the stubs become a no-op detour; the
  campaign's richer semantics (statutory_multiplier, evidence
  verification flows, etc.) win on merge if the public shape
  diverges; if the shapes match, the merge is a no-op.

### Compliance with established mandates

- **AEAT calculation grounding rule**: not directly impacted —
  repair_integrity is about secure-object persistence policy,
  not calculation provenance.
- **Roundtrip discipline rule**: the stub `RepairRemediationDecisionRepository`
  must satisfy strict pydantic equality across save/load (the
  test_runtime_migrated_repositories suite asserts this). Stubs
  use the same `SecureObjectRepository` infrastructure the
  existing `repair_integrity.py` functions use.
- **Hexagonal direction**: change confined to
  `aeat.application.repair_integrity`; no application or
  adapter import edges shift.
- **No live AEAT submission**: stubs are read-only planning
  records; `mutation_authorized` is hard-typed to `False`.

### Risks accepted

- **Scaffold drift**: the live-iva-compensation-wallet campaign
  may evolve the field shape between this commit and their
  eventual landing. If their landing keeps the names but
  changes the field set, the merge resolves naturally — the
  test files that consume the symbols are in this branch and
  will fail loudly under any incompatible shape change.
- **Duplicate authorship surface**: two campaigns now write to
  `repair_integrity.py`. Mitigated by the additive nature of
  the stubs (no overlap with existing functions) and by the
  exec record providing a documented design to align against.

### Plan linkage

This decision authorises plan steps:

- `linkage-design-audit P10.S45` (research note extension —
  already landed at the `2026-05-26-linkage-design-audit-research`
  fourth-topic section)
- `linkage-design-audit P10.S46` (this ADR section)
- `linkage-design-audit P10.S47` (land the four stub symbols
  in `repair_integrity.py`)
- `linkage-design-audit P10.S48` (trim `_BASELINE_BROKEN_IMPORTS`
  entries; gate's silent-fix detector demands it)
- `linkage-design-audit P10.S49` (re-verify the previously-
  deferred `test_runtime_migrated_repositories.py` roundtrip
  suite; closes the P08.S39 deferral)
