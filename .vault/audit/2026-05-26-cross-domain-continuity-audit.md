---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-05-26'
related:
  - "[[2026-05-26-cli-testimonial-audit]]"
  - "[[2026-05-21-cli-testimonial-audit]]"
  - "[[2026-05-26-corporate-tax-runtime-plan]]"
  - "[[2026-05-21-taxpayer-type-applicability-plan]]"
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cross-domain-continuity` audit: `round-6 cross-domain continuity audit + systemic drift catalog`

## Scope

Consolidated audit of round-6 cross-domain testimonials and the
parallel discovery sweep that grounds each observed failure to the
exact backing module / file / function and catalogues systemic drift
across the codebase.

This audit is the substrate for a remediation epic that will work
cross-domain (ledger ↔ modelo ↔ filing-record ↔ overview), cross-
year (multi-revision deadline windows + prior-period filings) and
cross-period (quarterly / annual reconciliation + IVA-wallet
compensation + IRPF year-end projection). The remediation plan
covers structural correctness of these three continuity axes.

## Methodology

- **Five persona testimonials**, each spanning ledger import +
  modelo work + export + cross-period verification: Marc (autónomo
  IT + EU intracom + USD overseas), Laia (e-commerce + OSS + UK
  exports), Pere (pensioner + landlord, no business), Núria
  (gestor managing five profiles, switching + export/import + multi-
  profile filing history), Joan (S.L. + employees + EU intracom +
  non-EU SaaS). Personas operate the real `aeat` CLI only, no source
  reading, isolated `AEAT_LOCAL_STORAGE_ROOT`, no live AEAT rights.
- **Four per-persona code-grounding passes** (Sonnet) locate the
  exact backing file:line for each observed failure and identify
  drift in each touched area.
- **Nine codebase-slice drift sweeps** (Haiku) comb the codebase
  file-by-file for the explicit forbidden patterns enumerated by
  `aeat-architecture-boundaries` and `aeat-source-hygiene`:
  duplication / redeclaration, re-export with no value, compatibility
  shim / deprecation alias, stub / skeleton code, dead code, name
  shadowing, drift between sibling implementations.

This document is iterative — as additional groundings and sweeps
land their findings are appended to the relevant root-cause cluster.
The audit's structure is stable; only the catalogue under each
cluster grows.

## Persona fleet — round 6

| Persona | Tax shape | Headline result |
|---|---|---|
| Marc Quintana | Autónomo IT + EU intracom + USD overseas | 3 BLOCKER + 6 MAJOR — ledger validation loop, Modelo 130 missing current-quarter ledger pathway, verify rubber-stamps empty drafts, calendar omits 130, CSV drops currency at aggregation, no 130→100 projection, no 303 box-59 binding |
| Laia Morera | Autónoma e-commerce + EU OSS + UK exports | 3 BLOCKER + 7 MAJOR — ledger classify refuses no-op, ledger list/view/update generic-refusal loop, modelo work calculate rejects caller bindings, OSS/369 unreachable, 349 ignores intracom acquisitions, UK exports invisible, no bulk classify, no IVA-wallet, postcode→CCAA misinference |
| Pere Roselló | Pensioner + landlord (no business) | reported (Pere persona) — pending |
| Núria Roca | Gestor managing 5 profiles | 2 BLOCKER + 3 MAJOR — profile export is identity-only (no ledger / work-units / revisions / filings), import mints fresh UUID, review queue active-profile-only, modelo list shows full registry not applicable subset, Modelo 200 rate sensitivity unverified |
| Joan Vidal | S.L. + employees + EU intracom + non-EU | 5 BLOCKER + 5 MAJOR — Modelo 200 fails on Decimal-channel boolean binding, unrendered error template + missing tramo for SL, no input casilla for base imponible, Modelo 202 modality gate inverted (routes 480k INCN to Art. 40.3 not 40.2), verify rejects same period token calculate accepted, calendar omits 200/202/190 for legal entity, no work-unit export verb |

The corporate-tax-runtime plan reported `8/8 Steps complete (100%)`
before this round began. Joan's testimony makes plain that the
structural tests passed at the graph-wiring level while the real CLI
binding-resolution path never reached production-quality. The plan-
complete claim was premature; the regressions are now grounded and
clustered in this audit.

## Root-cause cluster index

| Cluster | Theme | Headline impact |
|---|---|---|
| A | Ledger CLI validation boundary — generic refusal masks domain detail | Ledger list/view/update/classify dead-end loop for every operator |
| B | Duplicated applicability rules — stale application copy vs canonical domain | Every applicability fix shipped to the wrong file; cross-domain drift on the most central rule table |
| C | Calendar ↔ registry deadline-window data gaps | Applicable modelos silently absent from agenda / calendar / backlog across multiple years and modelos |
| D | Corporate-tax-runtime runtime regressions — boolean canonical mismatch + unrendered error + inverted modality gate + casilla input gap | S.L. operators cannot calculate Modelo 200 end-to-end and Modelo 202 routes to the wrong modality |
| E | Profile export scope — bundle ships identity only | Multi-profile portability and gestor handover broken |
| F | Profile import non-idempotent — fresh UUID per import | Round-trip and re-import lose identity |
| G | Verification rubber-stamps substantively empty drafts | Operators told their filing is `verificado_completo` when it computes from no real income |
| H | Modelo 130 income-side ledger aggregation gap — no resolver, asymmetric coverage | A real autónomo cannot feed their income into Modelo 130 from the ledger |
| I | Boolean canonical contract drift — wizard `"true"` vs binding `"True"` | Boolean profile facts silently fail Decimal-channel coercion when sourced from real wizard runs |
| J | Cross-period / cross-year continuity gaps — no 130→100 projection visible at bindings layer, 390↔303 untestable, IVA-wallet not surfaced as a query verb | Operators cannot trace year-end position from quarterly fillings without manual re-aggregation |
| K | i18n / locale parity holes — generic-refusal text, mixed-language payloads, untranslated `next_action` mid-sentence | Catalan and Hungarian operators get partial Spanish or raw engineering English |
| L | Dead stored data / dual default declarations / ghost comments | Profile schema bloat, drift risk between independent default sources |
| M | Identity validation divergence — two parallel CIF validators with different acceptable-letter sets | Same CIF accepted by one validator path and rejected by the other |
| N | Verify-path period-resolver vs calculate-path period-resolver divergence | Same period token accepted by create+calculate, rejected by verify on the same modelo |
| O | (placeholder) — systemic drift catalogue across the remaining seven slice sweeps | Filled as Haiku discovery agents land |

## Cluster A — Ledger CLI validation boundary

**Personas hit:** Laia (B1, B2), Marc (M-MARC-6).

**Symptom.** `aeat app ledger list`, `view`, `update`, `classify`,
`allocate`, `split` refuse with a single opaque text: `"L'entrada
de l'ordre no ha superat la validació. Executa 'aeat config repair'
o restableix l'estat del perfil."` Re-running `aeat config repair`
reports "everything ok" and produces no fix, so the refusal-and-
config-repair pair forms an infinite loop. `aeat app ledger review`
and `status` work on the same data, proving the underlying state is
fine.

**Backing implementation.**
- `src/aeat/entrypoints/cli/_errors.py:69-95` — `CliValidationBoundaryError.__init__`
  wraps any leaked `pydantic.ValidationError` with the locale key
  `errors.refused.refused_cli_validation_boundary` and the
  suggestion `aeat config repair`.
- `src/aeat/entrypoints/cli/_errors.py:144-186` —
  `command_error_boundary` decorator catches a bare `ValidationError`
  and emits the wrapper irrespective of whether the underlying error
  is a CLI-input failure or a stored-data deserialisation failure.
- `src/aeat/entrypoints/cli/_common.py:78` — `_state()` is the
  bootstrap entry point for every command that needs the active
  profile; it has no local `ValidationError` guard, so a schema-
  mismatch on `Envelope[UserProfileRecord].model_validate_json` at
  `src/aeat/application/user_profile/_repository.py:136` falls all
  the way out to the generic boundary.
- `src/aeat/entrypoints/cli/_ledger.py:282` —
  `_patch_from_options` constructs a `ManualLedgerTransactionPatch`
  from only the non-None CLI flags.
- `src/aeat/application/ledger/_actions.py:2195-2207` —
  `_command_from_patch` nullifies all classification-adjacent fields
  (`category_id`, `taxable_base`, `iva_rate`, `iva_amount`,
  `irpf_category`, `prorrata_reference`) when the new classification
  is BUSINESS. If the stored record is already BUSINESS, the
  resulting patch is field-for-field identical and
  `_mutation_signature` at line 3094 sees no change; line 1199-1203
  raises `TransactionValidationError("manual ledger update must
  change at least one ledger field")`. Operator cannot confirm or
  re-apply a classification.
- `src/aeat/entrypoints/cli/_ledger.py:396, 535` — `ledger_add`
  and `ledger_classify` have local `_ledger_validation_bad` catches
  that DO extract specific field errors. `ledger_update` (line 422),
  `ledger_list` (1322), `ledger_view` (1352), `ledger_allocate`
  (591), `ledger_split` (795) do NOT have local handlers and fall
  back to the generic boundary's opaque message.

**Drift in area.** `entrypoints/cli/_errors.py:402` `__all__` re-
exports `build_error_envelope` and `json_output_requested` defined
elsewhere; no consumer imports them from `_errors`. Unneeded re-
exports per source-hygiene.

**Remediation scope.** (a) Split `CliValidationBoundaryError` into
input-validation and stored-data-validation variants with distinct
locale keys and remediation hints (operator's stored profile may
have drifted; `config repair` is read-only and not the fix). (b)
Wire `_ledger_validation_bad` (or an equivalent per-command field
extractor) on every ledger CLI verb. (c) Make `_command_from_patch`
no-op classification a confirmable operation (e.g. a
`--reaffirm`/`--allow-no-op` flag, or simply do not zero out
classification-adjacent fields when the operator did not supply
them — only zero the ones explicitly cleared). (d) Trim the
`_errors.py:402` `__all__`.

## Cluster B — Duplicated applicability rules: stale application copy vs canonical domain

**Severity.** Highest — this is the single most central rule table
in the engine; every recent Q1 / corporate-tax-runtime fix edited
the wrong copy.

**Backing implementation.**
- `src/aeat/application/overview/_applicability.py:534, 1079` —
  `_MODELO_APPLICABILITY_RULES` dict and `derive_modelo_applicability`
  function, the version exercised by the CLI overview and the
  applicability guard on `modelo work create`.
- `src/aeat/domain/calculations/registry/_applicability.py:536,
  1093` — full duplicate of the same dict and function. The
  domain version is the **SUPERSET**: it adds `Modelo202Modality`,
  `Modelo202ModalityVerdict`, `derive_modelo_202_modality`, and
  `iter_modelo_applicability_rules`. The application version is the
  stale copy. Neither delegates to the other.
- `src/aeat/domain/calculations/registry/applicability.py` — a thin
  re-export façade that exports PRIVATE symbols
  (`_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS`, `_INCOMPLETE_*`,
  `_MODELO_APPLICABILITY_RULES`) through `__all__`. Source-hygiene
  rule explicitly forbids private-symbol re-exports.

**Knock-on effects across the audit.**
- Cluster C (calendar / agenda) — the calendar uses one version,
  the deadline-engine's `applicability_conditions` use registry
  data, neither references the other. Three sources of truth on
  "does modelo X apply?".
- Cluster G (verify rubber-stamping) — the verification path does
  not re-consult the applicability rules at all, so a profile that
  the applicability layer would mark `INCOMPLETE_UNRULED` still
  reaches `verificado_completo`.
- Round-6 Modelo 369 / OSS missing rule (Laia M-OSS) — the rule
  table at the canonical (domain) location is consulted by registry
  tests; the rule table at the stale (application) location is
  consulted by the CLI. Adding a rule in one place leaves the other
  silently absent.

**Remediation scope.** Consolidate to a single authoritative rule
table in the domain layer (`domain/calculations/registry/_applicability.py`)
and replace the application-layer file with a thin re-export of the
public surface only. Delete the private-symbol re-exports from the
façade. Add a single regression test that asserts the rule set is a
unique source. Re-run every Q1 / corporate-tax-runtime rule
addition against the canonical table — verify nothing was silently
lost when the duplicate diverged.

## Cluster C — Calendar ↔ registry deadline-window data gaps

**Personas hit:** Marc (M-MARC-1 — Modelo 130 absent from calendar
in 2025), Laia (Modelo 390 absent despite `applicable: true`), Joan
(Modelo 200 / 202 / 190 absent from corporate calendar).

**Root cause is registry data, not code.** `build_overview_calendar`
at `src/aeat/application/overview/__init__.py:488-525` iterates
covered years and calls `deadline_engine.compute(profile, year)`
for each year; the engine returns no obligation row when no
`deadline_windows` are registered for that modelo+year. The
applicability rule may say `APPLICABLE` but the calendar emits
nothing because the join is at the deadline-engine level.

- `src/aeat/_data/registry/aeat/modelos/130.toml:1507-1581` — all
  four `deadline_windows` entries have `filing_year = 2026`. Zero
  windows for 2025 in `130.toml`. An autónomo who runs `overview
  calendar --from 2025-01-01 --to 2026-12-31` gets no 130 rows for
  any 2025 quarter.
- Modelo 390 — similar single-file `*.toml` with no 2025
  `deadline_windows` registered (Laia's grounding confirmed).
- Modelo 200 / 202 — Joan reports corporate calendar omits these.
  The Modelo 202 deadline windows are uncommitted foreign WIP at
  audit time; Modelo 200's `0a` annual window for 2024 fiscal year
  exists but Joan's `overview calendar` shows none.

**Drift in area.** Two parallel mechanisms decide "does Modelo X
apply to this profile": the seed table in
`application/overview/_applicability.py` AND
`applicability_conditions` declared on each `deadline_window` in
the registry TOML. Neither mechanism references the other. For
Modelo 130 the deadline-window-level condition correctly tests
`professional_income_withholding_ge_70pct`; the seed-table rule
does not consult that fact. `_GATING_FIELDS` in
`overview/__init__.py:365-393` is a manually maintained hard-coded
dict that lacks the `professional_income_withholding_ge_70pct →
("130",)` entry, so when an operator leaves that fact unset no
warning fires.

**Remediation scope.** (a) Backfill the missing `deadline_windows`
across the modelos identified (R1 + the 2025 / 2026 corporate
calendar). (b) Unify the two applicability mechanisms — the
canonical applicability rules consume the registry's
`applicability_conditions` directly so the join is single-sourced.
(c) Replace `_GATING_FIELDS` hard-coding with a derivation from the
registry's `applicability_conditions` field list. (d) Add a calendar-
side diagnostic when an `APPLICABLE` modelo has no deadline window
for the requested year — silent drop is the failure mode.

## Cluster D — Corporate-tax-runtime runtime regressions

**Personas hit:** Joan (B-JOAN-1 through B-JOAN-5), Núria (M3
unverified rate sensitivity).

This cluster confirms that the corporate-tax-runtime plan's
`8/8 Steps complete` claim was scoped to structural tests that did
not exercise the real CLI binding-resolution path.

### D.1 — Decimal-channel binding receives lowercase boolean string

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/bindings.toml:44-50` —
  binding `modelo-200-2024-profile-new-entity-flag` declares
  channel = Decimal, selector reads
  `taxpayer.new_entity_first_two_profit_periods`.
- `src/aeat/domain/deadlines/_models.py:288-292` — the profile fact
  is typed `bool | None`.
- `src/aeat/application/wizard/_persistence.py:38-39` — wizard
  canonical of `bool` is lowercase string `"true"` / `"false"`.
- `src/aeat/application/modelo/_profile_binding.py:108-126` —
  `_decimal_value` checks `stripped == "True"` and `stripped ==
  "False"` (Python `str(bool)` capitalisation). Falls through to
  `Decimal("true")` → `InvalidOperation` → `ProfileBindingResolutionError`.
- Tests `domain/calculations/registry/test_modelo_200_cuota_integra_lanes.py:252-305`
  pass `Decimal("1")` directly in `binding_values`, **bypassing the
  profile→binding resolution path**. That is why the test suite
  passed while real CLI exercise failed.

### D.2 — Unrendered error template on missing tramo

- The raise site emits `"El parámetro escalonado {parameter_id} no
  tiene tramo válido para {as_of}."` — `{parameter_id}` and
  `{as_of}` literally not substituted. Localised-string formatter
  bypass. Located in `domain/calculations/registry/_formula_runtime.py`
  bracket-table lookup path.
- The dispatch table for `lookup_bracket_by_entity_type` against
  Joan's profile (`sl`, INCN 480k, new-entity false) does not
  resolve a tramo — the general 25 % path that should fall through
  is not finding the parameter via the bracket op. Either the
  dispatch table routes the `sl` sub-form to a `bracket_table`
  parameter that lacks 2024 brackets, OR the formula composition
  routes a scalar-rate sub-form through the bracket-only op (which
  P02.S05 explicitly rejects).

### D.3 — Modelo 200 has no input casilla for base imponible

- `--casilla 552=85000` rejected: `Identificadores de casilla de
  entrada desconocidos: 552`. With no ledger pathway and no input
  casilla, an operator cannot supply the base imponible — Modelo
  200 is structurally unreachable end-to-end for a profile without
  classified IS-eligible income flowing through some other path.

### D.4 — Modelo 202 modality gate inverted

- Joan's INCN 480k < 6M threshold → Art. 40.2 should be active,
  Art. 40.3 dormant. Calculate produced Art. 40.3 = `-21250.00`
  against an empty base and Art. 40.2 = `0.00`. The gate registered
  by P02.S07 is either keyed on the wrong predicate, inverted in
  the formula composition, or not wired to the Art. 40.2 path at
  all. Backing: `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/`
  formulas + applicability_conditions. Joan grounding agent still
  in flight; precise location will be appended.

### D.5 — Verify rejects same period token calculate accepted

- `aeat app modelo work create --modelo 202 --period 1P` succeeds;
  calculate produces a draft; verify rejects with `cannot map filing
  period '1P' to a registry period`.
- Round-4 #40 (`845d402331`) added `1P/2P/3P` arms to
  `period_start_date` / `period_end_date` in `src/aeat/domain/period.py`
  and to `_FILING_PERIOD_ORDINALS` in `application/modelo/_actions.py`.
  The verify path has its own period-resolver that was not updated.
  Two implementations of the same operation, divergent — see also
  Cluster N.

**Remediation scope.** (a) Make `_decimal_value` accept both
canonical-storage `"true"` / `"false"` and Python `str(bool)`
`"True"` / `"False"`, OR (cleaner) introduce a typed boolean channel
on bindings so the runtime never tries to read a bool as Decimal.
(b) Fix the formula-runtime localised-string formatter to actually
substitute `{parameter_id}` / `{as_of}`. (c) Audit the
`lookup_bracket_by_entity_type` dispatch table for Modelo 200 sub-
form coverage — every sub-form must route to a registered parameter
of the right type. (d) Provide a Modelo 200 input surface for the
base imponible (either casilla input descriptors marked
`input_kind = "manual"` for casilla 552, or a ledger-driven
contable-resultado binding). (e) Verify the Modelo 202 modality
gate predicate; correct any inversion; ensure Art. 40.2 path is
reachable below the INCN threshold. (f) Unify the verify-path
period resolver onto the calculate-path one — single source of
period token mapping. (g) Re-run the corporate-tax-runtime tests
through the **real profile→binding resolution path** so the bool /
Decimal mismatch and similar boundary defects cannot recur.

## Cluster E — Profile export scope (partial bundle)

**Persona hit:** Núria (B1).

- `src/aeat/entrypoints/cli/_config/__init__.py:1167` —
  `config_profile_export` wraps a `UserProfileRecord` in
  `UserProfilePortableExport` and writes JSON.
- `src/aeat/domain/user_profile/_values.py:132, 261` —
  `UserProfileRecord` carries only `profile_id`, `display_name`,
  `status`, `facts`, timestamps. `UserProfilePortableExport` carries
  only `bundle_schema_version`, `exported_at`, `profile`. No ledger,
  work-unit, calculation-revision, filing-record, or bucket-content
  fields exist anywhere in the export type tree.
- Bundle inspection across five exports confirmed 0 ledger entries,
  0 work units, 0 calculation revisions, 0 filings, 0 bucket
  artefacts. ~7 KB identity-only payload.

**Secrets handling.** Confirmed safe — zero
`master_key`/`private_key`/`password`/`secret`/`salt`/`dpapi`/`ciphertext`
tokens in any bundle. The "send to a colleague" path does not leak
encryption material.

**Remediation scope.** Add a bundled-export schema that includes
work units, calculation revisions (encrypted-at-rest, or with the
master key omitted requiring the recipient to re-encrypt on
import), ledger entries, and filing records. Document the schema-
version bump. Audit on import for confidentiality requirements.

## Cluster F — Profile import non-idempotent

**Persona hit:** Núria (B2).

- `src/aeat/entrypoints/cli/_config/__init__.py:1268-1272` — comment
  is explicit: "An imported bundle becomes a fresh local profile
  with its own minted UUID identity; the bundle's stored profile_id
  was the identity on the originating machine and is not reused."
- `src/aeat/entrypoints/cli/_config/__init__.py:716` —
  `_atomic_create_profile` always calls `new_profile_id()` →
  `str(uuid4())` unconditionally.
- No idempotency token, no `--preserve-identity` flag, no hash-of-
  facts dedupe. Re-importing the same bundle creates a second
  profile with a new UUID.

**Remediation scope.** Add an idempotency mode to the import path
that respects the bundle's `profile_id` when no local profile of
that id exists, and refuses (or upserts) when one does. The current
"always mint" semantics is defensible for some use cases but should
not be the only option.

## Cluster G — Verification rubber-stamps substantively empty drafts

**Persona hit:** Marc (B-MARC-2).

- `src/aeat/application/modelo/_actions.py:1975-2020` —
  `_required_input_casillas_for_revision` collects only casillas
  where `casilla.input_kind == "manual" and casilla.required`.
  Returns `(required, optional)`.
- `src/aeat/_data/registry/aeat/modelos/130.toml` — every casilla
  is declared `required = false`. The set of casillas marked
  `required = true` is empty.
- `src/aeat/application/modelo/_actions.py:2285-2287` —
  `_classify_verification_outcome` checks `has_blocking = any(...)`.
  Empty required set means `has_blocking = False`, returns
  `(COMPLETE, granted_verificado_completo = True)`.
- A Modelo 130 with casillas 01-18 all zero, casilla 19 = -100,
  and no real ledger evidence is granted `verificado_completo`.

**Architectural note.** Two distinct verification code paths exist:
`application/verification/_verify.py` is the PDF declaracion cross-
check path; `application/modelo/_actions.py:verify_modelo_revision`
is the work-unit gate path. Both use the word "verify" in their
public API. Documented boundary risk.

**Remediation scope.** Extend `_required_input_casillas_for_revision`
to consult substantive predicates declared by the registry on a
per-modelo basis (e.g. "Modelo 130 casilla 01 must be non-zero if
the profile carries `actividad_economica` income category"). Or
mark the relevant Modelo 130 casillas as `required = true` so the
existing structural check fires. Decision is registry-data shaped;
either path is acceptable, but the rubber-stamp must close.

## Cluster H — Modelo 130 income-side ledger aggregation gap

**Persona hit:** Marc (B-MARC-1).

- `src/aeat/_data/registry/aeat/modelos/130.toml:341-347, 495-505,
  1389` — Modelo 130 declares exactly two bindings, both with
  `source = "previous_filing"`. Zero `ledger_*` source bindings.
- `src/aeat/_data/registry/aeat/modelos/130.toml:61-62, 74-75` —
  casilla 01 ("Ingresos") and casilla 02 ("Gastos") are
  `input_kind = "manual"`, no binding, no formula. The operator is
  expected to type cumulative income/expenses manually.
- `src/aeat/application/aggregation/_modelo_bindings.py:103, 159` —
  two sibling resolvers exist: `LedgerIvaAggregationResolver` (IVA
  income via 303 bindings) and `LedgerRentaExpenseAggregationResolver`
  (Modelo 100 expense side). No `LedgerRentaIncomeAggregationResolver`
  for IRPF actividad-económica income.

**Drift in area.** `application/aggregation/_iva_ledger.py:394` and
`application/aggregation/_renta_ledger.py:271` each carry an
independent `currency != "EUR"` guard with identical structure and
issue codes — silent non-EUR exclusion at aggregation time.
RawTransaction stores currency correctly (`adapters/inbound/financial/providers/_csv.py:254`)
but the aggregators drop non-EUR rows with no FX conversion.

**Remediation scope.** Add a `LedgerRentaIncomeAggregationResolver`
covering the IRPF actividad-económica income side; bind Modelo 130
casilla 01 to it. Decide and implement an FX-conversion contract
for non-EUR transactions (either at import time or at aggregation
time, but a single contract — not silent exclusion). Replace the
duplicated `currency != "EUR"` guards with a shared predicate.

## Cluster I — Boolean canonical contract drift

**Severity.** High — this is the root cause behind Joan B-JOAN-1
and Núria M3.

- `src/aeat/application/wizard/_persistence.py:38-39` — wizard
  canonical of `True` is lowercase string `"true"`. Test
  `test_persistence_canonical.py:118` explicitly asserts
  `_parse_canonical(question, "True") is False` to lock the
  canonical contract.
- `src/aeat/application/modelo/_profile_binding.py:115` —
  `_decimal_value` checks `stripped == "True"` (capital T, Python
  `str(bool)`). Lowercase `"true"` falls through to
  `Decimal("true")` and raises.
- Two layers have independent and incompatible boolean string
  contracts. The wizard side guards its canonical with a regression
  test; the binding side never received the memo.

**Remediation scope.** Adopt the wizard canonical (lowercase) as
the project's single boolean string form. Update `_decimal_value`
and any sibling coercion to accept the canonical. Add a project-
wide test asserting the canonical is unique. Better — replace the
string-Decimal coercion path with a typed boolean channel on
profile bindings so this string-shape contract never needs to be
matched across layers.

## Cluster J — Cross-period / cross-year continuity gaps

**Personas hit:** Marc (M-MARC-4 130→100 visibility, M-MARC-1
130-not-in-calendar), Laia (M-iva-wallet, M-390 ↔ 303), Pere
(pending — cross-period 2024 vs 2025 grounding), Joan (M-200
across fiscal years).

- 130→100 projection binding `renta-2025-modelo-130-pagos-fraccionados`
  exists at `modelos/100/revisions/2025/bindings/0039-...toml` but
  resolves to zero/absent until 130s are filed; an operator who
  wants a year-end Renta projection from quarterly 130s has no
  visible path because the binding is hidden behind a previous-
  filing source that requires filed records to populate.
- IVA-wallet compensation surface — the binding
  `modelo-303-compensacion-pendiente-anteriores` is `source =
  "previous_filing"` but no `aeat app modelo wallet-balance` /
  similar verb exists to query current state.
- 390 ↔ 303 reconciliation — untestable in round-6 because of
  Cluster A ledger refusal; remediation depends on A.
- Cross-fiscal-year — Pere's 2024-vs-2025 grounding check (the
  gestor's 1.250 EUR figure for Pere's 2024 Renta) is still in
  flight.

**Remediation scope.** (a) Surface 130→100 projection as a
discoverable command (e.g. `aeat app modelo project --target 100
--from-revision <130s>`). (b) Add an IVA-wallet query verb. (c)
Once Cluster A clears, exercise 390 ↔ 303 explicitly with a real
operator scenario. (d) Add a `cross-year compare` verb for prior-
period vs current-period sanity. (e) Document the cross-period
binding chain (which `previous_filing` source feeds which casilla
on which forward modelo).

## Cluster K — i18n / locale parity holes

- `auth login` refusal text in round-5 audit cited the raw
  `AEAT_CERTIFICATE_PATH` env-var name and the `CertificateBundle`
  class name (closed by round-5 cluster `02740156d`, but new
  Catalan / English text could still mix layers).
- Núria reported `next_action` strings dropping out of Catalan
  into English mid-sentence on Cl@ve Móvil mismatch.
- Round-6 personas with `--output-language ca` repeatedly saw
  Spanish or English text appearing in fields adjacent to Catalan
  text (Joan `--casilla` rejection, Marc `overview status`).
- Modelo 200 cuota refusal `"El parámetro escalonado {parameter_id}
  no tiene tramo válido para {as_of}."` is both un-interpolated AND
  routed through localisation — two failure modes in one message.

**Remediation scope.** Catalogue every operator-facing message in
the auth + modelo + ledger surfaces; ensure each is fully localised
in es / en / ca / hu. Confirm the localised-string formatter
substitutes braces (`{parameter_id}` etc.) instead of emitting them
literally.

## Cluster L — Dead stored data / dual default declarations / ghost comments

**Independent confirmation across two grounding agents and one
Haiku sweep.**

- `application/wizard/_setup_answers.py:41` — `address_postcode`
  is collected by the wizard, serialised to the profile under
  `contact.postcode`, and stored — but no downstream computation
  consumes it. Dead stored data.
- `application/wizard/_setup_answers.py:106` and
  `application/wizard/_catalogue.py:569` — `IVARegime.GENERAL`
  declared as default in BOTH places. Two independent sources.
- `application/wizard/_setup_answers.py:130` and
  `application/wizard/_catalogue.py:661` — `CCAA.MADRID` same dual-
  default pattern.
- `application/user_profile/__init__.py:275` — ghost comment
  `# ProfileExportBundle consolidated onto UserProfilePortableExport
  (domain).` references a class that no longer exists. No
  deprecation enforcement.
- `application/user_profile/__init__.py:33` — `from . import
  _language_resolver as _language_resolver` private-name re-export
  for a registration side-effect. Fragile pattern: linters often
  remove side-effect imports as "unused".
- `domain/user_profile/_registry_contract.py:307` — `_profile_binding_selectors
  = profile_binding_selectors` — dead private alias, no consumers.
- `application/workflow/_models.py:227, 242` —
  `active_bucket_id_or_raise` and `require_active_bucket_id` have
  identical bodies. Docstring describes a "companion" without
  explaining the behavioural difference. Duplication.
- `application/state_projection.py:610-615` —
  `_LEDGER_PREFLIGHT_BINDING_SOURCES` is a hard-coded frozenset of
  binding-source identifiers; no registry-side verification
  enforces consistency if registry definitions rename a source.

**Remediation scope.** Delete each dead alias / dead stored
field / ghost comment. Replace dual defaults with a single shared
constant. Decide the registration-side-effect contract for
`_language_resolver` (explicit `register()` call, or an opt-in
import in a known initialiser). Merge the two `active_bucket_id`
helpers. Replace the hard-coded preflight set with a registry-
sourced derivation.

## Cluster M — Identity validation divergence

**Severity.** Cross-domain behavioural defect — a CIF starting
with `K` is accepted by one validator and rejected by the other.

- `src/aeat/core/identity/_documents.py:32` —
  `_CIF_KIND_LETTERS = "ABCDEFGHJNPQRSUVW"` (missing K).
- `src/aeat/core/identity/_tax_id.py:23` — `_CIF_LEADERS =
  "ABCDEFGHJKLMNPQRSUVW"` (with K).
- `validate_identity()` (from `_documents.py`) rejects K-leading
  CIFs; `validate_spanish_tax_id()` (from `_tax_id.py`) accepts
  them. Both are re-exported through `core/identity/__init__.py`.

**Remediation scope.** Consolidate to a single canonical CIF-
letter constant in a single module; have every validator consume
it. Add a regression test asserting the K-letter behaviour is
unified.

## Cluster N — Verify-path period-resolver vs calculate-path period-resolver divergence

**Persona hit:** Joan (B-JOAN-5).

Round-4 #40 (`845d402331`) added `1P/2P/3P` period arms to the
calculate side (`domain/period.py` and `_FILING_PERIOD_ORDINALS`
in `application/modelo/_actions.py`). The verify path has its own
period-resolver function that was not updated. Same operation,
divergent implementations.

**Remediation scope.** Replace the verify-path period resolver
with a call to the same function the calculate path uses; delete
the divergent copy.

## Cluster O — (placeholder) Systemic drift catalogue

This section is appended to as the remaining Haiku discovery
agents land. Slices in flight:
- `domain/calculations/registry/`
- `domain/` (non-registry: deadlines, modelos, transactions,
  user_profile, filing)
- `application/ledger/` + `application/aggregation/`
- `application/modelo/` + `application/filing/` +
  `application/calculations/` + `application/verification/`
- `application/overview/` + `application/workflow/` +
  `application/review/`
- `adapters/`
- `entrypoints/cli/`
- `_data/registry/aeat/` (TOML coverage / channel-vs-type / legal_refs)

The drift already catalogued (Clusters A, B, H, I, L, M, N) is the
floor; the remaining sweeps will add to it.

## Cross-domain continuity hot spots

Drawing from the clusters above, the remediation epic must hold
the following continuity contracts:

1. **Ledger ↔ modelo binding** — every modelo with current-period
   ledger-driven casillas must declare a `ledger_*_aggregation`
   binding (Cluster H: Modelo 130 income side). Add a registry-
   integrity test that for every applicable modelo, the casillas
   the formula consumes have a real resolved binding for a
   representative profile.
2. **Applicability ↔ deadline-engine** — single source of truth
   for "does Modelo X apply to this profile" (Cluster B + C). The
   seed table and the per-window `applicability_conditions` are
   the same data expressed twice; pick one.
3. **Profile ↔ binding canonical** — single boolean canonical
   string form across wizard, persistence, and binding-resolution
   layers (Cluster I); typed-channel approach preferred.
4. **Filing-record ↔ projection** — work units, calculation
   revisions, and filing records must travel with the profile
   bundle (Cluster E) and survive a round-trip import (Cluster F).
5. **CLI verb consistency** — every operator-facing verb that can
   fail validation must report the failing field and a real
   remediation, not the generic `config repair` signpost
   (Cluster A).

## Cross-year / cross-period consistency hot spots

1. **Deadline-window backfill** — every modelo applicable in
   `year - N` must have registered deadline windows for that year
   (Cluster C: Modelo 100 2024, Modelo 130 2025, Modelo 390 2025,
   Modelo 200/202 corporate calendar).
2. **`previous_filing` chain integrity** — every `previous_filing`
   binding must reference a `source_modelo` and `source_output`
   that exist on the snapshot, with a regression test asserting
   resolvability across all current revisions.
3. **Activity-start-date gate (round-4 #41) ↔ multi-year backlog**
   — confirmed working in round-4; verify it holds on Pere's
   cross-period scenario once that persona lands.
4. **Modality / state-dependent rates** — the corporate-tax-runtime
   period-state (new-entity-first-2-profit-periods, INCN-based
   micro-empresa identification) must be honoured by formula
   composition AND by the calendar AND by the modality gate
   (Cluster D + J).
5. **Cross-period CLI surfaces** — IVA-wallet balance,
   pre-Renta projection, prior-period audit query — all currently
   non-discoverable; verbs needed.

## Recommendations — outline for the remediation epic

The remediation is an L4 epic (Epic > Wave > Phase > Step) spanning
multiple distinct workstreams. Tentative wave decomposition:

- **Wave 1 — Stabilisation**: close Cluster A (ledger CLI boundary)
  + Cluster I (boolean canonical) + Cluster M (CIF letter set) +
  Cluster N (verify period resolver). These are short-scoped fixes
  with high leverage; they unblock all other personas hitting the
  ledger surface and the boolean coercion mismatch.
- **Wave 2 — Applicability and calendar consolidation**: close
  Cluster B (duplicate rules) + Cluster C (calendar data + the
  applicability ↔ deadline-engine unification). One canonical
  applicability source.
- **Wave 3 — Corporate-tax-runtime hardening**: close Cluster D
  (the four D.* regressions) — re-run the corporate-tax-runtime
  test suite through the real profile→binding path so similar
  regressions cannot ship undetected.
- **Wave 4 — Verification semantics**: close Cluster G (rubber-
  stamp) by extending the verify contract beyond "required casillas
  present" to include substantive predicates declared on the
  registry.
- **Wave 5 — Ledger surface completion**: close Cluster H (Modelo
  130 income side resolver, FX-conversion contract) and the bulk-
  classify / classification-enums gap.
- **Wave 6 — Profile portability**: close Cluster E (full-bundle
  export) and Cluster F (idempotent import).
- **Wave 7 — Cross-period surfaces**: close Cluster J (visible
  projection verbs, IVA-wallet balance, cross-year query).
- **Wave 8 — Localisation parity + hygiene**: close Cluster K
  (i18n) and Cluster L (dead data / ghosts / duals).
- **Wave 9 — Systemic drift cleanup**: drive the catalogue in
  Cluster O to completion as remaining Haiku sweeps land.

Wave 1 lands first because every other wave is blocked by the
ledger surface being usable. The epic's external project-management
association will be declared in the epic intent block of the plan
document when it is authored.

The epic plan will be authored separately under
`.vault/plan/<date>-cross-domain-continuity-plan.md` with
`tier: L4` and an explicit project-management association per the
plan-hardening ADR.

## Outstanding inputs (this audit is iterative)

- Pere Roselló persona testimonial (in flight).
- Joan corporate-tax-runtime grounding agent (in flight).
- Seven Haiku drift sweeps in flight (domain registry, domain rest,
  ledger + aggregation, modelo + filing, overview + workflow,
  adapters, entrypoints/cli, registry data).

Each will be appended to the relevant cluster as it lands. The
audit's structure is stable.
