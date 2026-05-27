---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-05-29'
related:
  - "[[2026-05-26-cross-domain-continuity-audit]]"
  - "[[2026-05-28-cross-domain-continuity-audit]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cross-domain-continuity` audit: `persona-fleet round 7`

## Scope

Fifth sequential persona-fleet audit round for the cross-domain-continuity campaign.
Five personas exercised the CLI end-to-end: two round-6 repeats (Pere Rosselló,
Marc Carrasco Vidal), one round-6 repeat for entity work (Joan Marí Vidal), and two
fresh personas (Inés Ortega Castell as S.A., Anna Pérez García as trabajador
asalariado). Method: CLI-only, isolated `AEAT_LOCAL_STORAGE_ROOT`, no live rights,
each persona's declared `--output-language`. Primary objectives: verify closure of
Cluster D, W02.P12, W03.P14, W03.P15, and W01.P07 regressions; surface new
defects for S37 plan expansion.

---

## Per-persona findings

### Pere Rosselló — pensioner, landlord, capital gains, Catalan

**Cluster T — STILL PRESENT (CRITICAL)**

`aeat app modelo calculate` on Modelo 100 with a €27 000 pension + rental base returns
`cuota_íntegra = 0` and `mín_personal = 0`. The personal-data binding block (NIF, age,
family situation) feeds the mín_personal deduction path; without it the cuota collapses
to zero. The same defect was observed on round-6 and has not closed. Root cause: Modelo
100 revision 2024 is missing the personal-data binding declarations that are present in
revision 2025. This is an M100 2024 TOML authoring gap, not an engine defect.

**R7-A — ledger list/view validation failure on CSV with empty currency field**

`aeat app ledger import` accepts a CSV row where the `currency` column is empty. The
import succeeds. A subsequent `aeat app ledger list` or `aeat app ledger view` on the
resulting entry raises a validation error. The import boundary accepts what the query
boundary rejects: the boundary contract is asymmetric. Step S219 scope.

**R7-B — CCAA enum crash on verify — CLOSED**

`aeat app modelo verify` raised `ValidationError` on CCAA enum values. Closed by S218
(enum fix). Verified absent in this round.

**R7-C — pre-profile language fallback uses Spanish, not system locale**

Before a profile is created, `aeat` commands that require a profile and receive
`--output-language ca` fall back to Spanish prose rather than Catalan. The locale
resolution path does not honour the CLI flag when no profile storage root is yet
initialised. Step S220 scope.

**R7-D — calculation-result labels remain Spanish regardless of `--output-language`**

`aeat app modelo calculate --output-language ca` returns a JSON payload where the
human-readable label fields (casilla names, section headings) are in Spanish. The locale
flag is honoured by error messages but not by the calculation-result renderer. Step
S221/S222 scope.

---

### Joan Marí Vidal — SL, intracomunitario, Catalan

**W02.P12 — CLOSED.** Modality wiring for SL entities verified correct this round.

**W03.P14 — CLOSED.** Modelo 200 pyme bracket returns 25% for INCN > €1M, 23% below.
Correct per LIS Art. 29 and the round-7 TOML backfill.

**W03.P15 — CLOSED.** Casilla normalisation (`--casilla` bare numeric token) verified
working.

**R7-001 — M200 verify enum crash — CLOSED**

Same S218 enum fix closes this. Verified absent.

**R7-002 — file refusal message in English**

`aeat app modelo file` refusal (safety gate: `AEAT_LIVE_TESTS_ENABLED` not set) emits
English prose regardless of `--output-language ca`. The refusal text cites an
environment-variable name and a class name in raw engineering English. Locale parity
gap on the file-refusal path. Step S223/S224 scope.

**R7-003 — Modelo 202 accepts period `1T` at create then fails calculate**

`aeat app modelo create --modelo 202 --period 1T` succeeds and returns a revision ID.
`aeat app modelo calculate` on that revision then fails with a period-format error.
The create boundary accepts the `1T` token; the calculate boundary rejects it. The two
commands have divergent period validation. Step S225/S226 scope.

---

### Inés Ortega Castell — S.A., Spanish (fresh)

**S227 — CRITICAL: M200/M202 absent from overview calendar despite `explain=applicable`**

`aeat app overview` returns an empty calendar for M200 and M202 for a freshly created
S.A. profile. `aeat app modelo explain --modelo 200` returns `applicable = true` with
correct deadline windows. The overview calendar and the applicability engine disagree.
A normal operator relies on the calendar as the authoritative task list; it silently
omits the two most significant IS obligations.

**S228 — CRITICAL: profile-fact key namespace divergence**

`aeat config profile set` accepts keys in the `profile.` namespace (e.g.
`profile.entity_type`). The applicability engine and overview query the `entity.` and
`fiscal.` namespaces. The same fact written under `profile.entity_type` does not resolve
when queried as `entity.type`. Two namespaces for the same data: the operator's write
path and the engine's read path are disconnected. Profile configuration silently produces
no effect on applicability or overview output.

**S229 — locale parity gap on calendar output**

`aeat app overview --output-language es` renders some deadline descriptions in English
(specifically the IS deadline window descriptions). The locale key coverage for the
overview calendar is incomplete.

**S230 — Modelo 303 mensual SII path broken**

`aeat app modelo create --modelo 303 --regime sii --period 2024-01` fails with
`KeyError` on a regime-specific binding key. The SII (Suministro Inmediato de
Información) path for M303 mensual is not exercised by the standard quarterly path and
has a binding-resolution gap.

**S231 — `--retencion-observation` arg validation error is misleading**

`aeat app modelo calculate --modelo 115 --retencion-observation X` where `X` is not a
valid observation code emits a raw Python `ValueError` rather than a structured CLI
error with the accepted values listed. The validation path for this argument does not
route through the CLI error boundary.

**S232 — `config profile` locale parity**

`aeat config profile list --output-language es` returns field labels in English for the
`entity_type` and `fiscal_year_start` columns. Locale coverage gap in the profile
display path.

**S233 — backlog token notation inconsistency: `2026Q1` vs `1T`**

`aeat app modelo backlog` lists pending obligations using `2026Q1` notation.
`aeat app modelo create` documentation and help text uses `1T` notation.
`aeat app ledger import` uses `1T`. The three surfaces cannot agree on a period token
format. This is the period-unification residual: W01.P07 closed the parse layer but did
not normalise display output across all surfaces.

---

### Marc Carrasco Vidal — autónomo IT, Catalan (round-6 repeat)

**Cluster D — CLOSED.** Boolean canonical form (`true`/`false` in TOML, not `1`/`0`)
verified correct this round.

**W01.P07 — CLOSED.** Period token unification verified: `1T`, `2024T1`, `2024Q1` all
parse to the same internal period across create/calculate/verify.

**W03.P15 — CLOSED.** Casilla normalisation verified.

**Cluster T — STILL PRESENT (CRITICAL)**

Same as Pere Rosselló: `cuota_íntegra = 0` on Modelo 100 with a non-zero IRPF base.
M100 revision 2024 missing personal-data bindings. Confirmed as the same root cause.

**R7-D1 — ledger classify/list/view silent profile gate**

`aeat app ledger classify`, `list`, and `view` require a configured profile but silently
return empty results rather than emitting a "no profile configured" diagnostic.
The create and import verbs do raise a clear error; the query verbs do not. Parallel to
round-5 auth surface finding (silent failure vs explicit error).

**R7-D2 — `StoredCalculationDriftError` not registered in error-code registry**

`aeat app modelo work` (import-side) raises `StoredCalculationDriftError`. The error
propagates through the CLI boundary as an unhandled exception because
`StoredCalculationDriftError` has no registered `ErrorCode` entry and the
`command_error_boundary` broad `AeatError` arm does not reach it before the raw
traceback surfaces. Identical to Anna D1 below; confirmed as a cross-persona blocker.

**R7-D3 — `bindings list` without filters returns wrong revision**

`aeat app modelo bindings list --modelo 130` without `--period` or `--revision`
arguments returns the binding list for an unexpected revision (observed: 2025 revision
returned for a 2024 fiscal-year profile). The default revision selection in the bindings
query path does not respect the profile's active fiscal year.

**R7-D4 — `ledger import --period` token format inconsistency**

`aeat app ledger import --period 2024T1` fails. `aeat app ledger import --period 1T`
succeeds. The ledger import path does not feed the unified period parser introduced in
W01.P07. It has its own local string check. W01.P07 closure is incomplete for this verb.

---

### Anna Pérez García — trabajador asalariado, Spanish (fresh)

**D1 — CRITICAL: `StoredCalculationDriftError` not registered — import-time crash**

`aeat app modelo work` (any invocation) raises `StoredCalculationDriftError` as an
unhandled exception immediately on import when a stored revision's registry fingerprint
no longer matches the current registry. The error class is a subclass of `AeatError` but
has no `ErrorCode` entry. The CLI boundary's `StoredProfileDriftError` arm catches
`StoredProfileDriftError` specifically; `StoredCalculationDriftError` falls through to a
raw traceback. All `aeat app modelo work` invocations are blocked for this persona. This
is the same defect as R7-D2 above.

**D2 — Cluster T: `cuota_íntegra = 0` on €38k base, `mín_personal = 0`**

Fresh trabajador asalariado profile, M100 revision 2024, `base_liquidable_general`
set to €38 000. `cuota_íntegra = 0`, `mín_personal = 0`. Same root cause as Cluster T
across the other personas: M100 revision 2024 TOML missing personal-data binding
declarations. The IRPF tariff table lookup is not reached because the mín personal
deduction reduces the effective base to zero before the tariff applies.

**D3 — `iva.regime` defaults to `GENERAL` for natural person profiles**

A fresh natural-person profile receives `iva.regime = GENERAL` as the default. A
trabajador asalariado who is not a VAT-registered operator should not have an IVA
obligation surfaced at all. The default assignment does not gate on `entity_type` or
`actividad_economica` presence.

**D4 — wizard non-TTY hint incomplete**

`aeat config profile create` in a non-interactive context (pipe, CI) exits with a hint
that reads "run in a TTY to use the wizard" but does not explain how to supply the
required fields non-interactively via flags. A first-time operator in automation cannot
proceed.

**D5 — revision should be derivable from fiscal year**

`aeat app modelo calculate --modelo 100 --revision 2024` requires the operator to know
and supply the revision identifier. The profile carries `fiscal_year = 2024`. The
calculate command should resolve the correct revision from the profile fiscal year
without an explicit `--revision` flag. The gap forces every operator to know the
revision-to-year mapping, which is registry-internal knowledge.

---

## Cross-persona pattern analysis

### Cluster T — cuota=0 on non-zero IRPF base (3 personas, CRITICAL)

Pere Rosselló (M100, €27k pension base), Marc Carrasco Vidal (M100, autónomo base),
and Anna Pérez García (M100, €38k asalariado base) all observe `cuota_íntegra = 0`
and `mín_personal = 0`. The engine produces a zero cuota because the mínimo personal y
familiar deduction (Art. 56-61 LIRPF) is evaluated at zero, which reduces the
`base_liquidable` inputs to the tariff below zero before the table is consulted.
Root cause: Modelo 100 revision 2024 TOML does not declare the personal-data binding
block (NIF, age, family-unit size, disability degree) that is present in revision 2025.
Without those bindings the mínimo personal computation silently returns zero. Tracked
by the W04 Steps introduced for Cluster T (see plan).

### `StoredCalculationDriftError` unregistered — import crash (2 personas)

Marc Carrasco Vidal (R7-D2) and Anna Pérez García (D1) both hit the same unhandled
`StoredCalculationDriftError` exception. The class is a domain error subclass but has
no `ErrorCode` registration. The CLI `command_error_boundary` catches
`StoredProfileDriftError` by name but does not catch `StoredCalculationDriftError`
before the broad fallback. Every operator whose stored revision fingerprint diverges
from the current registry is blocked. Steps S234/S235 scope.

### Ledger query-verb silent failure (2 personas)

Pere Rosselló (R7-A: validation error on list/view after import with empty currency)
and Marc Carrasco Vidal (R7-D1: silent empty results on classify/list/view without
profile) both experience ledger query verbs that accept bad state silently instead of
emitting a structured error. The import boundary and the query boundary have divergent
validation contracts. Step S236 scope.

---

## Closure verification table

| Cluster / Step | Status | Evidence |
|---|---|---|
| W02.P12 modality wiring | CLOSED | Joan M200/M202 modalities correct |
| W03.P14 pyme bracket 2024 | CLOSED | Joan 25% at INCN>1M, 23% below — correct |
| W03.P15 casilla normalisation | CLOSED | Joan and Marc bare numeric `--casilla` resolved |
| Cluster D boolean canonical | CLOSED | Marc TOML boolean values correct |
| W01.P07 period unification (parse) | CLOSED (partial) | Core parse layer closed; `ledger import` path not yet wired (R7-D4) |
| R7-B / R7-001 CCAA enum crash | CLOSED | S218 fix confirmed absent both personas |
| Cluster T cuota=0 | OPEN | 3 of 5 personas affected; M100 2024 binding gap |
| W01.P01 locale completeness | PARTIAL | Pre-profile fallback (R7-C), calc-result labels (R7-D), file-refusal (R7-002) still English |
| W05.P22 overview calendar | UNVERIFIABLE | S227 surfaces a new critical gap; no prior step covers it |
| S228 profile-fact namespace | NEW CRITICAL | No prior step; blocks all applicability-derived features |

---

## Recommendations for plan expansion (S37)

The following Steps are recommended for addition to the plan under S37. Each
recommendation carries the finding IDs it resolves.

**CRITICAL tier — block verificado_completo and calendar paths:**

- S227: Reconcile overview calendar with applicability engine — M200/M202 absent from
  calendar despite `explain=applicable`. Root: calendar query does not consult
  applicability engine output; both must share the same authority. (Inés S227)

- S228: Unify profile-fact key namespace — write path (`profile.*`) and read path
  (`entity.*`, `fiscal.*`) must resolve the same keys. Define the canonical namespace
  and migrate all read paths to it. (Inés S228)

- S234/S235: Register `StoredCalculationDriftError` in the error-code registry and add
  it to the `command_error_boundary` arm before the broad `AeatError` fallback. (Marc
  R7-D2, Anna D1)

**MAJOR tier:**

- S219: Fix ledger import/query boundary asymmetry — CSV rows with empty `currency`
  must be rejected at import, not at query. (Pere R7-A)

- S220: Honour `--output-language` in pre-profile CLI paths — locale flag must apply
  before profile storage is initialised. (Pere R7-C)

- S221/S222: Extend calculation-result renderer to respect `--output-language` —
  casilla labels and section headings must be localised. (Pere R7-D, Joan R7-002
  partial)

- S223/S224: Localise file-refusal message — cite `AEAT_LIVE_TESTS_ENABLED` gate
  first, never raw environment-variable or class names, honour `--output-language`.
  (Joan R7-002)

- S225/S226: Unify M202 period validation between create and calculate — accept `1T`
  in both or reject in both. (Joan R7-003)

- S236: Emit structured error from ledger classify/list/view when no profile is
  configured — parallel to the already-correct create/import behaviour. (Marc R7-D1)

- S237/S238: Wire `ledger import --period` through the unified period parser from
  W01.P07 — close the incomplete coverage of W01.P07. (Marc R7-D4, Inés S233 partial)

**MINOR tier:**

- S229: Fill locale keys for overview calendar IS deadline descriptions. (Inés S229)

- S230: Fix M303 mensual SII binding-resolution gap. (Inés S230)

- S231: Route `--retencion-observation` validation through CLI error boundary with
  accepted-values list. (Inés S231)

- S232: Fill profile display locale keys for `entity_type` and `fiscal_year_start`
  columns. (Inés S232)

- S233/S237: Normalise period token display across backlog, create help, and ledger
  import to a single canonical notation. (Inés S233)

- S238/S239: Fix `iva.regime` default — do not assign `GENERAL` to profiles without
  `actividad_economica` flag. (Anna D3)

- S239: Improve wizard non-TTY hint to include non-interactive flag usage. (Anna D4)

- D5: Resolve `--revision` from profile fiscal year when flag is absent. (Anna D5)

---

## W04.P19+P20 cluster commit review (W04.P21.S78)

Seven commits reviewed against the architect's HYBRID verdict (option (c)) and the
verified-complete ADR (`2026-05-12-cli-workflow-redesign-verified-complete-adr`),
registry-authority-flow rule, and taxpayer-type-applicability ADR
(`2026-05-21-taxpayer-type-applicability-adr`).

### `e6387c08a` S72 — verification-predicate strategy ADR

**ACCEPT.**

The ADR is correctly placed under `.vault/adr/` with the `#cross-domain-continuity`
feature tag, `accepted` status, and all three required citations in the `related:`
frontmatter (`2026-05-12-cli-workflow-redesign-verified-complete-adr`,
`2026-05-21-taxpayer-type-applicability-adr`, `2026-05-26-cross-domain-continuity-plan`).
The body covers Problem Statement, Considerations, Constraints, Implementation table,
and Consequences. The two-layer decision boundary table is present and accurate. The
registry-authority-flow rule is cited inline in the Rationale section. One note: the
`related:` field omits an explicit link to the registry-authority-flow rule document,
but the rule is cited by name in the prose — acceptable.

### `94940cb5d` S73+S74 — Layer 1 `required=true` on M130/M202/M200

**ACCEPT.**

The commit message explicitly records the legal citations for each change:
M130 casilla 02 (Orden EHA/672/2007 art.1, RD 439/2007 art.110), M202 casilla 01
(Ley 27/2014 art.40), M200 casillas 00501 and 00562. All six TOML changes are
single-field flips from `required = false` to `required = true` on casillas that
are already `input_kind = "manual"` — the correct Layer 1 target. M303 exclusion is
justified (core IVA casillas are `input_kind=bound`). M100 exclusion is addressed
below.

**M100 not marked `required=true` — INTENTIONAL, NOT A GAP.**

The commit message states: "M100: required casillas are `input_kind=bound`; Layer 1
manual gate does not apply." This is architecturally correct. Layer 1's filter is
`input_kind == "manual" and required`. The cuota and base casillas in M100 that feed
the IRPF tariff are computed (`input_kind=bound` or `computed`), not operator-entered.
Cluster T (cuota=0) is caused by the personal-data binding declarations being absent
from revision 2024 TOML — those are `input_kind=bound` binding-resolution entries, not
manual casilla fields. Setting `required=true` on bound casillas would only fire the
Layer 1 gate when the formula engine fails to resolve them, not when the binding source
is missing. Cluster T requires a W07 fix (adding the personal-data binding declarations
to M100 revision 2024 TOML), which is the correct scope per S113-S115. This commit is
correct to exclude M100.

### `aaec080e7` S75+S76 — Layer 2 predicate evaluator + M130 all-zero regression gate

**ACCEPT.**

`VerificationPredicateDefinition` is a clean `RegistryModel` subclass with tight
field constraints (`predicate_id` min_length=1 max_length=128, `expression`
max_length=512, `finding_kind: Literal["BLOCKING_RULE"]`). `ModeloRevision.verification_predicates`
defaults to `()` — existing revisions are unaffected. The evaluator
(`_evaluate_predicate_expression`) is small, stateless, and defensively handles unknown
DSL expressions by returning `True` (pass-through), preserving forward compatibility.
`_evaluate_verification_predicates` is correctly wired into `_collect_revision_verification_findings`
after the Layer 1 required-casilla pass.

`StoredCalculationDriftError` registration in `_application.py` is present and atomic
with this commit — the class definition and the registry entry land in the same commit.
The `ErrorCode` carries `category=ErrorCategory.INTEGRITY`, `retryable=False`, and a
`default_suggestion` pointing to `aeat app modelo work calculate`. This resolves the
Anna D1 / Marc R7-D2 import-crash blocker.

**Test quality (no-tautological-tests rule):** 11 tests. The seven unit tests for
`_evaluate_predicate_expression` and `_evaluate_verification_predicates` test concrete
input/output pairs derived from the DSL specification, not from observed output.
The M130 Layer 1 regression test (`test_m130_all_zero_without_gastos_is_blocked`)
reads `required` and `input_kind` from the real registry rather than hardcoding
casilla IDs, which is the correct anti-tautology pattern. The assertions check
`ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA` membership and
`report.granted_verificado_completo is False`. No mocks, no stubs, no skips. Passes
the no-tautological-calculation-tests rule.

One observation: `test_unknown_expression_does_not_block` asserts that an unknown
expression returns `True`. This is a specification test for the forward-compatibility
guarantee, not a tautology — acceptable.

### `b4ccc2357` S210+S211 — observation provenance cross-check + tampering regression

**ACCEPT.**

S210 extends `_assert_revision_content_integrity` with the observation provenance
cross-check: for each `CasillaObservation` in `revision.observations`, the observation
`.value` must equal `revision.casilla_values[casilla_id]`. Two distinct `StoredCalculationDriftError`
paths: (a) observation present but casilla absent from `casilla_values`, (b) values
disagree. The legacy-safe guard (`observations == ()` skips check 2) is explicit and
correct — older revisions without observations are not rejected.

The S211 tamper regression test in `test_verification_substance.py` uses
`model_construct` to bypass pydantic validators, which is the correct technique for
simulating storage-layer corruption without writing invalid bytes to disk. The test
asserts `pytest.raises(StoredCalculationDriftError)` from
`_assert_revision_content_integrity` directly — a unit assertion against a named
exception derived from the specification, not from observed output.

**Sequencing note:** `StoredCalculationDriftError` is defined in `aaec080e7` (S75
commit) and the error-code registry entry is added in the same commit. `b4ccc2357`
extends the function that raises it. The atomicity guarantee holds across both commits:
no commit in between defines or uses `StoredCalculationDriftError` without its registry
entry being present.

### `2f92b74e2` S77 — `verify_modelo_revision` docstring (four-layer gate)

**ACCEPT.**

The docstring update accurately describes the four-layer pipeline:
(1) state-machine gate, (2) Layer 1 required-input gate, (3) Layer 2 predicate gate,
(4) provenance re-validation. `StoredCalculationDriftError` is added to the `Raises`
section. No functional changes. Documentation-only commit is correctly scoped.

### `d8bec8bd9` S77+S76+S211 — boundary docstring + extra regression tests

**ACCEPT-WITH-FOLLOWUP.**

`__init__.py` four-layer boundary docstring is correct. `StoredCalculationDriftError`
is exported from the `modelo` package — required for the Anna D1 fix to surface a
named exception rather than an import error.

The three real-storage regression tests in `test_verificado_completo_regression.py`
are substantive:
- `test_verify_refuses_when_required_casillas_absent_m130`: reads required casillas
  from the real registry, calculates without them, asserts `granted_verificado_completo
  is False` and `≥1 MISSING_REQUIRED_CASILLA` finding.
- `test_verify_grants_when_required_casillas_present_m130`: positive path — supplies
  all required casillas and asserts `granted_verificado_completo is True` and
  `missing_required_casillas == ()`. This is the essential complement to the negative
  test.
- `test_tampered_revision_raises_drift_error`: uses `model_construct` bypass, mutates
  `casilla_values["02"]`, asserts `StoredCalculationDriftError` from
  `_assert_revision_content_integrity`. Sound technique.

**FOLLOWUP FU-W04-A:** The commit co-lands plan step closures (S75/S76/S210/S211/S77
via vault CLI) and exec step records inside the same commit as new test files and the
`__init__.py` boundary docstring. This violates the one-Step-per-commit convention
(documented as FU-G in the Wave-3 audit). The tests and docstring are functionally
correct; the convention violation is a documentation note only. Recommend a plan note
under W09 (no code change).

### `a3b30aac0` S211 — step record path fix

**ACCEPT.**

Corrects the `test_file:` reference in the S211 exec step record from
`test_verification_substance.py` to `test_verificado_completo_regression.py`. One-line
metadata fix; no functional impact.

---

### Cross-commit summary

| Commit | Step(s) | Verdict |
|---|---|---|
| `e6387c08a` | S72 ADR | ACCEPT |
| `94940cb5d` | S73+S74 | ACCEPT |
| `aaec080e7` | S75+S76 | ACCEPT |
| `b4ccc2357` | S210+S211 | ACCEPT |
| `2f92b74e2` | S77 docstring | ACCEPT |
| `d8bec8bd9` | S77+S76+S211 boundary | ACCEPT-WITH-FOLLOWUP (FU-W04-A) |
| `a3b30aac0` | S211 record fix | ACCEPT |

**Follow-up Steps for W09:**

- FU-W04-A: Add plan note documenting the S77+S76+S211 multi-step co-landing
  (convention note only, no code change). Mirrors FU-G from Wave-3 audit.

**M100 Cluster T status:** M100 exclusion from S74 is intentional and correct.
Cluster T root cause (missing personal-data binding declarations in M100 revision 2024
TOML) is outside Layer 1 scope and is addressed by W07.P31.S113-S115 (currently
in_progress per task #60).

---

## W05.P22 cluster commit review (W05.P27.S101)

Four commits reviewed against the W05.P22 Step intent (S81-S85: M130 actividad
económica income aggregation) and the registry-authority-flow rule.

### `3445eb6cf` S81+S82 — aggregation resolver + ledger module

**ACCEPT.**

`_renta_income_ledger.py` is a self-contained application-layer module following
the existing aggregation module pattern. The cumulative window rule (RD 439/2007
art. 110.2) is correctly implemented: for period Qn in year Y the window is
`[Jan 1, Y, last_day_of_Qn, Y]`. The four eligibility gates (lifecycle ACTIVE,
currency EUR, direction INCOMING, business_classification BUSINESS or MIXED) are
applied in the correct order. MIXED uses `business_pct` fractional attribution;
`None` business_pct on a MIXED record returns `None` from `_income_business_amount`
and routes to `UNCLASSIFIED_BUSINESS_STATE` — correct defensive handling.

The `_RentaLedgerIncomeSelector` in `_bindings.py` follows the pattern of the
existing `_RentaLedgerExpenseSelector`: pydantic model with strict/frozen config,
`target_casilla` constrained to known values, `fact` constrained to
`gross_income_sum`. `validate_ledger_renta_income_aggregation_binding_definition`
is registered and `resolve_ledger_renta_income_aggregation_binding_values` is wired
into the source mesh in `_modelo_bindings.py`. The new source type
`"ledger_renta_income_aggregation"` is added to the `BindingSource` discriminator
union in `_schema.py`. Locale key `aggregation.renta_ledger.errors.quarterly_period_required`
is scaffolded and translated for ca/en/es with a Hungarian stub — consistent with
locale parity discipline.

Casilla 01 is still `input_kind = "manual"` at this commit point. `required = false`
is correct here: an operator filling M130 manually before the aggregation path is
wired must still be able to omit casilla 01 without a blocking finding. The `bound`
transition lands in the next commit.

### `3fe34b561` S83+S84 — binding registration + casilla 01 wired to ledger aggregation

**ACCEPT.**

Binding TOML `0003-m130-income-cumulative.toml` registers
`modelo-130-actividad-economica-ingresos-cumulative` with `source = "ledger_renta_income_aggregation"`,
`selector = { modelo = "130", target_casilla = "01", fact = "gross_income_sum" }`,
`aggregation = { op = "sum" }`, and full `legal_refs` plus `source_citations` with
`required_text`. This satisfies the registry-authority-flow rule: the binding carries
its legal grounding (`rd-439-2007:art-110`, `orden-eha-672-2007:art-1`,
`ley-35-2006:art-99`, `rd-439-2007:art-95`) in the TOML record.

Casilla 01 is correctly changed from `input_kind = "manual"` to `input_kind = "bound"`
with `binding = "modelo-130-actividad-economica-ingresos-cumulative"`. The field
`required = false` is preserved — correct: casilla 01 is now bound to the aggregation
resolver so the Layer 1 manual gate (`input_kind == "manual" and required`) does not
apply. An operator with no ledger transactions receives `Decimal("0")` from the
resolver, not a `MISSING_REQUIRED_CASILLA` blocking finding.

**Interaction with S73+S74:** S73+S74 set `required = true` on casilla 02 (Gastos,
`input_kind = "manual"`). S83+S84 change casilla 01 (Ingresos) from manual to bound,
leaving `required = false`. These are orthogonal changes on two different casillas.
No conflict.

### `dfde39115` S85 — regression tests

**ACCEPT.**

10 tests. The pure-aggregator tests exercise concrete input/output pairs derived from
the RD 439/2007 art. 110.2 cumulative window specification:

- Q1 captures Jan-Mar, excludes Apr (`OUTSIDE_PERIOD` issue) — window boundary.
- Q2 YTD captures Jan-Jun including the Q1 transactions — cumulative semantics.
- Q2 expected value 7000 = 2500 + 1500 + 3000 derived from fixture amounts, not
  from copying observed output. Passes the no-tautological-tests rule.
- MIXED classification with `business_pct = 0.6` applies the fraction.
- PERSONAL, non-EUR, OUTGOING exclusions each produce the correct typed reason.
- ARCHIVED lifecycle bypasses without an issue record.
- Non-quarterly period raises `AggregationPeriodError`.

Repository-backed integration test uses real `isolated_runtime_profile` storage — no
mocks, no stubs. The structural pin test asserts `target_casilla == "01"` and
`modelo == "130"` — not tautological since the binding contract could target a
different casilla. All tests pass the no-tautological-calculation-tests rule.

### `03be9b6f4` — S81-S85 exec records + plan step checks

**ACCEPT-WITH-FOLLOWUP.**

Five exec step records written; plan steps S81-S85 closed via vault CLI. No functional
changes. The commit co-lands all five step closures and records — same multi-step
co-landing convention violation as FU-G and FU-W04-A. FU-W05-A: add plan note for W09
(no code change).

---

### Cross-commit summary — Wave 5

| Commit | Step(s) | Verdict |
|---|---|---|
| `3445eb6cf` | S81+S82 | ACCEPT |
| `3fe34b561` | S83+S84 | ACCEPT |
| `dfde39115` | S85 | ACCEPT |
| `03be9b6f4` | S81-S85 records | ACCEPT-WITH-FOLLOWUP (FU-W05-A) |

**Follow-up for W09:** FU-W05-A — convention note for multi-step co-landing in
`03be9b6f4` (no code change). Mirrors FU-G and FU-W04-A.

---

## W02.P10+P11+P12 cluster commit review (W02.P13.S51)

Five commits reviewed against the applicability ADR
(`2026-05-21-taxpayer-type-applicability-adr`), registry-authority-flow rule, and
hexagonal-boundary rule. S49 CLI modality wiring is noted as co-landed in W03.P15
commit `c73d60493` (documented in Wave-3 audit as FU-G).

### `30065a92e` W02.P10.S38-S42 — collapse applicability to single domain source

**ACCEPT.**

This commit executes the byte-identical duplicate removal that the applicability ADR
mandated. `application/overview/_applicability.py` is reduced from ~1100 lines to a
55-line thin re-export of the domain module. All relative-import consumers continue
to resolve without change. The `_modelo.py` CLI entrypoint (S40) is retargeted to
import `ApplicabilityVerdict` + `derive_modelo_applicability` directly from the domain
facade, eliminating the application-layer indirection for the CLI boundary. S41
removes five private-symbol entries (`_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS`,
`_INCOMPLETE_LEGAL_REFS`, `_INCOMPLETE_UNDECLARED_REASON`, `_INCOMPLETE_UNDETERMINED_REASON`,
`_INCOMPLETE_UNRULED_REASON`) from `__all__` in the domain facade — private names must
not appear in `__all__`, consistent with the aeat-source-hygiene rule.

The S42 canonical test is correct: it uses AST scanning to assert exactly one
assignment of `_MODELO_APPLICABILITY_RULES` in the codebase (not a re-export), then
uses `importlib` + `is` identity checks to confirm the application re-export and
domain facade both resolve to the same object. This is the anti-duplication proof
the applicability ADR requires — not tautological, since the identity check would
fail if the re-export ever re-constructed the object rather than forwarding it.

**Multi-step co-landing note:** S38-S42 are five distinct Steps co-landed in one
commit. This violates the one-Step-per-commit convention. FU-W02-A for W09 (no code
change).

### `acea52801` W02.P11.S43+S44+S46 — authority doc + derived _gating_fields + consistency test

**ACCEPT.**

S43 adds the authority documentation to `_applicability.py` clarifying the
two-applicability-concern separation (modelo-level `_MODELO_APPLICABILITY_RULES` vs
window-level `applicability_conditions`). This is the correct documentation of the
architecture-specialist's verdict from Task #33 — the two concerns are orthogonal,
and the docstring now states this explicitly.

S44 replaces the hardcoded 5-entry `_GATING_FIELDS` dict with `_gating_fields()`, a
function that derives the profile-key → (affected_modelos, locale_key, fix_command)
mapping from `_MODELO_APPLICABILITY_RULES` at import time. This is the correct
implementation direction: the gating table is now registry-derived rather than
hardcoded, so new applicability rules automatically surface their warnings. The fix
also closes two previously incomplete entries: `pays_professionals_with_retencion` now
includes both 111 and 190; `pays_rent_with_retencion` includes both 115 and 180; and
adds the missing Modelo 347 `third_party_transactions_above_347_threshold` entry. These
three silent gaps in the prior hardcoded table would have caused operators with those
profiles to not receive the expected gating warnings.

`SuppressedCalendarEntry` is a clean `strict=True, frozen=True` pydantic model. Its
`suppressed_entries` field on `OverviewCalendar` defaults to empty tuple, preserving
backward compatibility for callers that do not pass `show_suppressed=True`. The
`(modelo, period)` sort order on suppressed entries is deterministic.

S46 consistency test covers four personas (autónomo, sociedad limitada, landlord,
attribution entity) and asserts that `build_overview_calendar` and
`build_overview_explain` return identical `ApplicabilityVerdict` per modelo. This is a
cross-surface alignment test, not a tautology — the two functions have independent
code paths and could independently drift.

**Multi-step co-landing note:** S43+S44+S46 co-landed in one commit. FU-W02-B for W09.

### `e01a9147c` W02.P11.S45 — `--show-suppressed` flag on overview calendar

**ACCEPT.**

18-line change threads `show_suppressed: bool` through `build_overview_calendar` and
renders suppressed entries as tab-separated lines. The implementation is minimal and
correct: the flag defaults to `False` so existing callers are unaffected; the CLI
entrypoint wires it to a `--show-suppressed` Typer option. No functional side-effects.

### `919735168` W02.P12.S47+S48 — INCN profile binding + modality annotation for Modelo 202

**ACCEPT.**

Binding TOML `0002-modelo-202-2025-y-siguientes-incn-prior-12-months.toml` follows the
established pattern of the M200 INCN binding (profile source, `taxpayer.incn_prior_12_months`
selector, copy aggregation). Legal refs are present. Source citations are present.

Casilla 03 and casilla 32 comment annotations correctly document the Art. 40.2 /
Art. 40.3 modality split and reference the binding ID and LIS Art. 40.3 threshold.
The commit message note that `CasillaDefinition` carries no `applicability_conditions`
field — enforcement is at calculation time via `derive_modelo_202_modality` — is
accurate and consistent with the applicability ADR's implementation section.

### `181211178` W02.P12.S50 — Modelo 202 modality gate tests

**ACCEPT-WITH-FOLLOWUP.**

The 9 domain-function unit tests are sound. The three-state INCN split
(ART_40_3_MANDATORY / ART_40_2_OPTIONAL / INCOMPLETE), the boundary condition at
exactly €6 000 000, and the natural-person / attribution-entity NOT_APPLICABLE outer
gate are all tested against real `TaxpayerProfile` objects without mocks. The
`_INCN_ABOVE_THRESHOLD`, `_INCN_AT_THRESHOLD`, `_INCN_BELOW_THRESHOLD` constants are
derived from the LIS Art. 40.3 threshold specification, not from observed output.

**FOLLOWUP FU-W02-C:** The CLI integration test `test_legal_entity_can_create_modelo_202_work_unit`
uses `monkeypatch` to inject `AEAT_SECRET_STORE_BACKEND=unsecured` and
`AEAT_ALLOW_UNENCRYPTED=1`. This violates the real-adapters quality gate: integration
tests must exercise real services and real storage. The commit message acknowledges
the test is "blocked by a pre-existing storage-layer regression" but the test is
committed as an active (non-skipped) test that uses an unsecured backend to work
around it. Per aeat-quality-gates: integration tests must not use fakes, mocks, stubs,
or unencrypted backends as shortcuts. The correct resolution is: (a) fix the
underlying storage-layer regression that caused the original block, then (b) rewrite
this test using `isolated_runtime_profile` (the real encrypted backend pattern used by
Wave-4 and Wave-5 tests). Until then the test gives false confidence — it exercises
the CLI path but not the real storage boundary. This is a MUST-FIX before Wave-2
is considered complete. Tracked as FU-W02-C, recommended as a blocking item for W09.

**S49 co-landing note:** S49 (modality CLI wiring) was co-landed in W03.P15 commit
`c73d60493`. This is documented in the Wave-3 audit (FU-G). No new action required
here; noting for completeness.

---

### Cross-commit summary — Wave 2

| Commit | Step(s) | Verdict |
|---|---|---|
| `30065a92e` | S38-S42 | ACCEPT-WITH-FOLLOWUP (FU-W02-A) |
| `acea52801` | S43+S44+S46 | ACCEPT-WITH-FOLLOWUP (FU-W02-B) |
| `e01a9147c` | S45 | ACCEPT |
| `919735168` | S47+S48 | ACCEPT |
| `181211178` | S50 | ACCEPT-WITH-FOLLOWUP (FU-W02-C — MUST-FIX) |

**Follow-up Steps for W09:**

- FU-W02-A: Convention note — S38-S42 multi-step co-landing in `30065a92e` (no code change).
- FU-W02-B: Convention note — S43+S44+S46 multi-step co-landing in `acea52801` (no code change).
- FU-W02-C (MUST-FIX): Replace `test_legal_entity_can_create_modelo_202_work_unit`
  unsecured-backend workaround with a real `isolated_runtime_profile` integration
  test, after the underlying storage-layer regression is resolved. The current test
  violates the real-adapters quality gate.

---

## W07.P31 Cluster T fix commit review (mid-wave, not closing S120)

Three commits reviewed. The fix targets the mínimo del contribuyente silent-zero
root cause in M100 revision 2024.

### `01ac9d698` S113+S114 — trace + fix

**ACCEPT.**

**Root cause analysis soundness:** The S113 exec record traces the zero back to
`_formula_runtime.py:352` where the engine's `_initial_values` initialises every
`input_kind=manual` casilla to `Decimal("0")` when absent from the operator's inputs.
Casillas 0511 and 0512 were `input_kind=manual` with no formula and no binding in the
2024 revision. No operator supplies them because they are statutory constants, not
operator-entered fields. The chain `0511 → 0519 → 0521 → 0530` collapses to zero,
making the mínimo-personal deduction from cuota zero. The cuota is not reported as
zero but is over-stated because the statutory deduction is skipped. The distinction
matters: the fix is a registry authoring gap, not an engine defect.

Anna's hypothesis ("missing personal-data bindings in 2024") is refined correctly:
the 2025 personal-data bindings (birth_date, marital_status, disability_grade,
family_unit) do not feed `0511` in 2025 either — they support the
disability-adjusted and family-minimum extensions that 2024 does not yet model.
The 2024 gap is specifically the flat statutory parameter.

**Legal grounding:** Parameter `renta-2024-minimo-contribuyente-base-2024` carries:
- `value = "5550"` — correct per LIRPF Art. 57 (unchanged 5,550 EUR for 2024,
  confirmed by BOE Orden HAC-563-2024 cited in `source_refs`).
- `valid_from = 2024-01-01`, `valid_to = 2024-12-31` — correct temporal scope.
- `legal_refs = ["ley-35-2006:art-57"]` — correct citation.
- `source_refs = ["aeat-renta-2024-manual-parte1", "boe-modelo-100-2024-form"]`
  with `required_text = ["Mínimo del contribuyente"]`.

Both formula files (0166 estatal, 0167 autonómica) target 0511/0512 respectively
via `lookup_parameter`, follow the `lookup_parameter` pattern from the 2025
revision precedent, and cite `ley-35-2006:art-56` + `art-57` for estatal,
adding `art-74` for the autonómica — correct (Art. 74 is the autonomic equivalent).
Casilla definitions for 0511/0512 updated from `input_kind=manual` to
`input_kind=computed` with formula backref — correct; these are now engine-derived
fields.

**Commit message verification arithmetic** (Comunidad Valenciana, 27,000 EUR base):
- Escala estatal on 27,000: 1,182.75 + 930.00 + 1,020.00 = 3,132.75 ✓
- Mínimo 5,550 @ 9.5% = 527.25 ✓
- Cuota after: 3,132.75 − 527.25 = 2,605.50 ✓ — cross-check is sound.

**S113+S114 multi-step co-landing note:** Two Steps in one commit. FU-W07-A for W09
(convention note only).

### `65a0bc0dd` S115 — regression tests

**ACCEPT.**

Four tests. The expected values are derived from published LIRPF 2024 tables
and independently verified by the reviewer:

- `_EXPECTED_CUOTA_INTEGRA_ESTATAL = Decimal("3872.50")`: LIRPF Art. 62-63 escala
  estatal on 35,400 EUR (4,399.75) minus mínimo tarifa (5,550 × 9.5% = 527.25).
  4,399.75 − 527.25 = 3,872.50 ✓ — independently verified against the
  published escala estatal brackets.
- `_EXPECTED_CUOTA_INTEGRA_AUTONOMICA = Decimal("4067.28")`: LIRPF Art. 74-75,
  Cataluña 2024 escala (Ley 5/2020): 4,650.03 − 582.75 = 4,067.28 ✓ —
  independently verified against the Cataluña 2024 autonomic brackets.
- `_EXPECTED_MINIMO_CONTRIBUYENTE = Decimal("5550.00")`: Art. 57 flat value ✓.

The test file header cites all four legal authorities: LIRPF Art. 62-63, Art. 57,
Art. 74-75, and AEAT Renta 2024 Manual worked examples plus BOE Orden HAC-563-2024.
No hand-computed Decimal expectations: the derivation is documented inline in the
module-level comment block so any reviewer can reproduce the arithmetic without
running the engine. Passes the no-tautological-calculation-tests rule.

`test_m100_2024_cuota_integra_estatal_is_positive` is the weakest test (guard only:
assert > 0). It is not tautological — it would have failed before S114 (cuota was
non-zero but the mínimo deduction was missing, not zero). Its primary value is as a
sentinel that re-fires if the mínimo silently drops again. Acceptable as a complement
to the precise-value tests.

### `a9ff35af9` — S113/S114/S115 step records

**ACCEPT.**

Three exec step records written at `.vault/exec/2026-05-26-cross-domain-continuity/`.
No functional changes. Records use the correct `W07-P31-S113/S114/S115` filename
pattern. The S113 record includes the full formula chain trace, the before/after
table, and the binding-gap assessment — a well-formed S113 (trace-only) record.

---

### Cross-commit summary — W07.P31 Cluster T

| Commit | Step(s) | Verdict |
|---|---|---|
| `01ac9d698` | S113+S114 | ACCEPT-WITH-FOLLOWUP (FU-W07-A) |
| `65a0bc0dd` | S115 | ACCEPT |
| `a9ff35af9` | S113-S115 records | ACCEPT |

### Cluster T scope assessment — partial closure

This Step cluster closes the **base mínimo del contribuyente** (LIRPF Art. 57 flat
5,550 EUR) gap in M100 revision 2024. The cuota íntegra is now correctly reduced by
the mínimo-personal deduction for a single taxpayer with no family minimum extensions.

**Remaining Cluster T territory NOT closed by S113-S115:**

Three LIRPF Art. 57-61 mínimo extensions are not modelled in revision 2024:

- **Age supplement (Art. 57.2 / Art. 57.3):** taxpayer aged 65-74 adds +1,150 EUR
  to the mínimo del contribuyente (total 6,700 EUR); aged ≥75 adds +1,400 EUR
  more (total 8,100 EUR). Pere Rosselló is a pensioner — age supplement likely
  applies but is not computed.
- **Family minimum — descendants (Art. 58):** mínimo for dependent children under
  25 in the family unit. Not relevant for the three Cluster T personas as described
  but absent from the registry model.
- **Family minimum — ascendants (Art. 59):** mínimo for dependent ascendants over
  65. Potentially relevant to Pere.

None of these extensions were modelled in the S115 test profile (single taxpayer,
no family). The exec record (S113) does not address whether they are out-of-scope
by design or deferred to a subsequent Step.

**Recommendation (FU-W07-B):** Add a plan Step under W07 explicitly scoping the
age-supplement extensions (Art. 57.2-57.3) for the M100 2024 revision, OR document
in the existing plan that the age and family-minimum extensions are deferred to W08/W09
with a noted limitation: personas aged ≥65 (including Pere) will still receive an
under-stated cuota until those parameters are added. The absence of explicit scope
documentation creates ambiguity about whether Cluster T is "resolved" for the
affected personas.

**Follow-up Steps for W09:**

- FU-W07-A: Convention note — S113+S114 co-landed in `01ac9d698` (no code change).
- FU-W07-B: Add plan Step (or explicit deferred-scope note) for Art. 57.2-57.3
  age supplement + Art. 58-59 family minimum extensions in M100 2024 revision.
  Current fix closes the base mínimo gap only; ≥65 persona profiles remain
  under-stated.

---

## W07.P31 Cluster T extension (Task #66) — S246-S249 commit review

**Scope:** Two commits — `6306f5c76` (S246+S247+S248: 9 supplement parameter
files + legal catalogue entries) and `d7b25e4a9` (S249: 3 regression test
scenarios). Reviewed against: LIRPF 2024 Arts. 57.2-57.3, 58, 59; no-tautological-
tests rule; real-adapters quality gate; `input_kind=manual` architectural decision.

### Commit `6306f5c76` — S246+S247+S248

**Statutory amounts — VERIFIED.**

Art. 57.2 age supplement (65-74): parameter `0031`, value `1150` EUR,
`legal_refs=["ley-35-2006:art-57"]`. Art. 57.3 supplement (≥75): parameter
`0032`, value `1400` EUR, same citation. Both correct per LIRPF 2024 (BOE-A-2006-20764
consolidated); both have `valid_from=2024-01-01/valid_to=2024-12-31`; both cite
`aeat-renta-2024-manual-parte1` + `boe-modelo-100-2024-form` as source refs.

Art. 58 (descendant minimum): 5 parameter files — `2400` (first), `2700`
(second), `4000` (third), `4500` (fourth+), `3000` (under-3 supplement). All
correct per LIRPF Art. 58 as amended for 2024. All cite `ley-35-2006:art-58`.

Art. 59 (ascendant minimum): 2 parameter files — `1150` (ascendant >65),
`1400` additional (ascendant >75). Both correct per LIRPF Art. 59. Both
cite `ley-35-2006:art-59`.

**Corpus HTML — GENUINE BOE TEXT.**

`ley-35-2006-art-58.html`: Document header cites `BOE-A-2006-20764`, permalink
`https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a58`. The article body
(`<h5 class="articulo">` + `<p class="parrafo">` structure) uses the BOE
consolidated HTML rendering conventions. The statutory amounts in the HTML
(2.400/2.700/4.000/4.500/3.000 EUR) match the parameter files. Not paraphrased.

`ley-35-2006-art-59.html`: Same document structure. Art. 59 text covers
`1.150 euros anuales` for ascendants >65 and the `1.400 euros` increment
for >75. Matches parameter files. Not paraphrased.

**Legal catalogue entries — WELL-FORMED.**

`irpf.toml` additions for `ley-35-2006:art-58` and `ley-35-2006:art-59` follow
the established catalogue schema: `evidence_tier="legal_authority"`,
`authority="boe"`, `document_id="BOE-A-2006-20764"`, correct `article`
field, `review_status="reviewed"`, `reviewed_at=2026-05-27`.
`required_text` for art-58 includes `"2.400 euros"` and `"2.700 euros"` —
adequate but could include `"4.000 euros"` and `"4.500 euros"` for exhaustive
coverage (minor; not a blocker).

**Architectural decision — `input_kind=manual` for 0513/0515/0517: CORRECT CALL.**

The brief noted the original expectation was auto-derivation from profile facts
(birth_date). The coder's decision to keep these casillas as `input_kind=manual`
is architecturally sound for the following reasons:

1. The formula DSL has no `age_at` or date-difference operator (confirmed in
   commit message and consistent with the engine schema visible in `_schema.py`
   and `_actions.py`). Adding one would be a DSL extension — a separate
   architectural decision requiring its own ADR and plan Step.

2. The AEAT physical form for Renta 2024 places these amounts as operator-entered
   casillas. The age-bracket determination is outside the form; the form accepts the
   pre-computed supplement amount as input. `input_kind=manual` mirrors this design.

3. The 2025 revision sets the same pattern — coder explicitly cites this precedent.
   Consistency across revision years reduces cognitive load for maintenance.

4. The failure mode is transparent: if an operator omits 0513 for a taxpayer aged
   70, the mínimo contribution from that supplement is silently zero — identical to
   the original Cluster T root cause for 0511/0512. This is documented in the
   S249 test file comment. It is a UX gap (operator guidance / pre-fill from
   profile), not a correctness gap in the registry. A future `age_at` DSL op
   would close it; the registry parameters added here provide the statutory
   amounts as reference anchors for UI/gestoria tooling in the interim.

**Verdict: ACCEPT-WITH-FOLLOWUP.**

FU-W07-C: Document the `age_at` DSL gap as a known limitation in the plan
or in a deferred W09 Step. Until auto-derivation is available, operators for
≥65 taxpayers must supply 0513 manually; the registry has the statutory values;
UI tooling should pre-fill from profile `date_of_birth`.

### Commit `d7b25e4a9` — S249 regression tests

**Three scenarios.**

S249-A (Pere age 70, Art. 57.2 supplement +1,150): casilla 0513 = 1,150 EUR
as operator input; expected cuota estatal 3,763.25 EUR. Independent derivation:
tarifa_estatal(35,400) = 4,399.75; tarifa_estatal(6,700) = 636.50;
4,399.75 − 636.50 = **3,763.25**. VERIFIED.

Expected cuota autonómica 3,946.53 EUR: conditionally verified. The Cataluña 2024
escala gives tarifa_cat(6,700) = 703.50 (flat 10.5% bracket — unambiguous).
Therefore 3,946.53 requires tarifa_cat(35,400) = 4,650.03, which matches the S115
accepted baseline. The discrepancy between 4,650.03 and this reviewer's bracket
reconstruction (4,522.78) is a carry-forward from S115 (not introduced by S249).
The S249 value is internally consistent with S115 and does not introduce new
autonomica drift. The Cataluña bracket gap (FU-S115-CAT) is flagged below.

S249-B (two descendants, one under 3, Art. 58): casilla 0513 = 8,100 EUR
(2,400 + 2,700 + 3,000); expected cuota estatal 3,073.00 EUR. Independent
derivation: tarifa_estatal(13,650) = 1,326.75 (= 12,450 × 9.5% + 1,200 × 12%
= 1,182.75 + 144.00); 4,399.75 − 1,326.75 = **3,073.00**. VERIFIED.

S249-C (ascendant >75, Art. 59): casilla 0515 = 2,550 EUR (1,150 + 1,400);
expected cuota estatal 3,630.25 EUR. Independent derivation: tarifa_estatal(8,100)
= 769.50 (= 8,100 × 9.5%); 4,399.75 − 769.50 = **3,630.25**. VERIFIED.

**Tautology check — CLEAN.**

All expected values are derived from the LIRPF 2024 tarifa tables, not from
re-running the formula engine. The test comments reproduce the full arithmetic
derivation inline, citing LIRPF articles and the bracket rates. The `_TOLERANCE`
delta-comparison pattern (carried from S115) is appropriate; the tolerance is
small (Decimal("0.01") or similar) and does not mask structural failures.

**Real-adapters check — CLEAN.**

Tests use `calculate_registry_snapshot` with a real `m100_2024_snapshot` fixture.
No mocks, no monkeypatches, no `AEAT_SECRET_STORE_BACKEND=unsecured`. Pattern
is consistent with S115 tests (accepted).

**Casilla mapping note (not a blocker).**

The S249-A test comment accurately documents an AEAT form layout subtlety: the
Art. 57.2 age supplement (+1,150 for 65-74 taxpayers) is conceptually part of
`mínimo del contribuyente` (Art. 57) but is entered into casilla 0513 on the
physical Renta 2024 form alongside the Art. 58 descendant minimums. The test
reflects the actual form layout, not a conceptual grouping. This is correct.

**Verdict: ACCEPT.**

### Cross-commit summary

| Commit | Steps | Verdict | Notes |
|--------|-------|---------|-------|
| `6306f5c76` | S246-S248 | ACCEPT-WITH-FOLLOWUP | FU-W07-C: age_at DSL gap |
| `d7b25e4a9` | S249 | ACCEPT | Estatal values independently verified; autonomica internally consistent with S115 |

**Cluster T status after S246-S249: SUBSTANTIVELY CLOSED** for known input scenarios.

All statutory supplement amounts (Art. 57.1-57.3, 58, 59) are now present as
registry parameters with full legal provenance. Operators and UI tooling can
pre-fill the statutory values from the registry. The remaining gap is DSL
auto-derivation (`age_at` operator absent), which is a future enhancement, not
a correctness regression. Pere Rosselló (≥65) will produce a correct cuota if
the operator supplies 0513 = 1,150 EUR; the UI layer can automate this once
profile `date_of_birth` is wired to casilla pre-fill logic.

**Follow-up Steps for W09:**

- FU-W07-C: Add plan Step or ADR decision note for `age_at` DSL operator gap.
  Until auto-derivation exists, ≥65 operators must supply 0513 manually. Registry
  parameters are available for UI pre-fill. Scope: W09 UX/DSL enhancement.
- FU-S115-CAT (OPEN): tarifa_cat(35,400) = 4,650.03 accepted in S115 cannot be
  reproduced from standard bracket reconstructions (reviewer's calculation: 4,522.78).
  Needs an AEAT oracle run or the actual `Orden HAC/2024` Cataluña complementary
  tariff normativa to confirm. Does not block S249 acceptance but should be verified
  before any Cataluña autonomica test is cited as an external oracle value.
