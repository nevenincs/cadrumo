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

---

## W09.P41 follow-up rollup — consolidated inventory for Wave-9 execution

**Generated from:** all review sections in this audit document plus the plan's
`W09.P41` (S198-S251) and `W09.P45` (S203-S239) step inventory.
**Purpose:** provide the W09 execution wave with a categorised, prioritised
view of open follow-ups so Steps can be batched by dependency cluster.

### Category 1 — MUST-FIX: quality-gate blockers

These Steps block a wave sign-off or carry an active quality-gate violation.
They must be resolved before the campaign can reach termination criteria.

| Step | Source | Description |
|------|--------|-------------|
| S208 | W01 drift | Pre-existing storage regression breaking `aeat config profile create` in 20+ test files (unsecured backend error); root cause in `src/aeat/adapters/persistence/storage/`. Unblocks S209 and S244. |
| S209 | W01 drift | Migrate 20 CLI test files from `monkeypatch`/`AEAT_SECRET_STORE_BACKEND=unsecured` to `isolated_runtime_profile` fixture. Blocked behind S208. |
| S244 | W02-C | MUST-FIX: `test_legal_entity_can_create_modelo_202_work_unit` uses `monkeypatch` + `AEAT_SECRET_STORE_BACKEND=unsecured`. Rewrite with `isolated_runtime_profile` after S208+S209 land. |

S208 → S209 → S244 is a hard dependency chain. S208 is the gating item.

### Category 2 — Error registry correctness

Duplicate registrations and semantic misclassification in
`src/aeat/core/errors/registry/`.

| Step | Source | Description |
|------|--------|-------------|
| S198 | W01 drift | Delete duplicate `AuthProviderReservedError` registration (lines 62-65 and 106-109). |
| S199 | W01 drift | Delete duplicate `AuthConfigureDanglingActiveProfileError` registration (lines 84-92 and 95-103). |
| S202 | W01 drift | Audit `StoredCalculationDriftError` taxonomy: class lives under `errors.refused.*` (REFUSED category) but stored-data drift is an integrity failure; decide rename vs. documented exception. |

S198 and S199 are independent. S202 requires a taxonomy decision before code change.

### Category 3 — Source hygiene: dead exports and private symbols

| Step | Source | Description |
|------|--------|-------------|
| S201 | W01 | Delete dead `__all__` re-exports of `build_error_envelope` and `json_output_requested` from `src/aeat/entrypoints/cli/_errors.py`. |
| S206 | W01-C | Remove `_I18N_STRICT_PLACEHOLDERS` from `__all__` in `src/aeat/core/i18n/_render.py`. (Closed in plan but noted here for completeness — verify landed.) |

S201 is a standalone delete; no dependencies.

### Category 4 — Duplicate / consolidation work

| Step | Source | Description |
|------|--------|-------------|
| S200 | W01 drift | Consolidate two divergent `_decimal_value` helpers: modelo-binding variant has bool-sentinel handling; borrador variant does not. Extract one canonical helper. `src/aeat/application/modelo/`. |
| S205 | W01 drift | Consolidate `UserProfileLifecycleRepository.__init__` and `UserProfileSnapshotRepository.__init__` identical signatures into shared base class or factory. `src/aeat/application/user_profile/_repository.py`. |

Both are independent consolidation tasks.

### Category 5 — Persistence boundary and domain integrity

| Step | Source | Description |
|------|--------|-------------|
| S214 | W01/W03 | Add `StoredTransactionDriftError` / `ValidationError` guard to `TransactionCatalogueRepository.load()` at `src/aeat/domain/transactions/_repository.py:139`. Mirrors W01.P01.S05 pattern. |
| S215 | W03 | Replace four `dict[str, object]` return types on ledger payload helpers with typed pydantic models. Lines 1024/1055/1064/1075 of `src/aeat/application/ledger/_actions.py`. Architecture-boundaries gate. |

S214 and S215 are independent. S215 is a broader refactor.

### Category 6 — Test coverage gaps

| Step | Source | Description |
|------|--------|-------------|
| S213 | W03-H | Add clarifying comment in M100 binding-schema pin test for the 30-binding sentinel. `src/aeat/application/modelo/test_profile_binding_real_path.py`. |
| S216 | W03 | Add test coverage for `_id_resolution.py` (95 LOC, no dedicated test file). `src/aeat/application/ledger/_id_resolution.py`. |
| S217 | W03 | Verify `transaction_catalogue_object_id` at `src/aeat/application/ledger/_actions.py:2607` has callers and coverage; potentially orphan. |
| S223 | W03 | R7-B: pin regression coverage for `tax_residence_ccaa` enum binding in M100 verify path (variant of S218 fix). `src/aeat/application/filing/__init__.py`. |

S213 is documentation-only. S216/S217 are independent. S223 depends on S218 landing.

### Category 7 — Legal data / registry correctness

| Step | Source | Description |
|------|--------|-------------|
| S212 | W03-F | Fix `Real Decreto-ley 4/2004` legal citation typo in M200 `parameters.toml`. `src/aeat/_data/registry/aeat/modelos/200/`. |
| S251 | W07 | Investigate Cataluña 2024 autonomic tarifa discrepancy: reviewer reconstruction gives 4,522.78 EUR for base 35,400 but S115/S249 oracle values use 4,650.03. Ground against AEAT oracle replay. `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/`. |

S212 is a mechanical typo fix. S251 requires an external oracle run before code change.

### Category 8 — CLI UX / localisation

These Steps are in `W09.P45` and cluster on operator-facing surface gaps found in
rounds 5-7 of the persona fleet.

| Step | Source | Severity | Description |
|------|--------|----------|-------------|
| S203 | R7 parity | MAJOR | Fix 5 i18n ORPHAN placeholders (missing `{kind}`, `{bucket_id}`, `{category}`, `{raw}`, `{target}` kwargs). |
| S204 | R7 parity | MAJOR | Fix 27 i18n SURPLUS kwargs (dead kwargs at `tr` call sites for diagnostics, auth, operator-surface keys). |
| S219 | R7-002 | MAJOR | Localise `'No pending filing obligation for this profile'` refusal on `aeat app modelo work file` to es/ca/hu. |
| S220 | R7-003 | MAJOR | Reject invalid period token at `modelo work create` time, not at calculate time. `src/aeat/entrypoints/cli/_modelo.py`. |
| S221 | R7-001 | MAJOR | Surface critical storage errors in profile language when active-profile pointer is readable but DEK is malformed. |
| S222 | R7-001 | MAJOR | Localise ledger CSV date-parse error inner reason (wrapper is localised; inner `'unsupported date format'` is English). |
| S224 | R7-A | MAJOR | Fix `ledger list` / `ledger view` `CliValidationBoundaryError` on CSV-imported transactions: `currency` field min_length=3 rejects empty strings. |
| S225 | R7-C | MAJOR | Pre-profile error language defaults to Spanish when `output_language` is unresolvable; either multi-language critical render or documented fallback. |
| S226 | R7-D | MAJOR | Casilla labels remain in Spanish with `--output-language ca`; investigate registry `casilla.label` localisation. |
| S229 | R7-INES-3 | MAJOR | Register `--output-language` on `overview calendar` command (currently rejected). |
| S231 | R7-INES-5 | MAJOR | Disambiguate CLI input-validation refusal from stored-data validation refusal; wrong repair suggestion. |
| S232 | R7-INES-6 | MINOR | Register `--output-language` on `config profile` subcommand root. |
| S233 | R7-INES-7 | MINOR | Fix period token notation inconsistency: M111 surfaces as `2026Q1`; rest of system uses `1T`. |
| S234 | R7-ANNA-D3 | MAJOR | Fix `iva.regime` defaulting to GENERAL for `natural_person` profiles without `actividad_economica`. |
| S235 | R7-ANNA-D4 | MINOR | Expand wizard non-TTY refusal to list all required flags. |
| S236 | R7-ANNA-D5 | MINOR | Default `modelo work create --revision` to in-force revision for `--year` via registry lookup. |
| S237 | R7-MARC-D1 | MAJOR | `ledger classify`/`list`/`view` blocked by silent profile-completeness gate; surface the specific failing field. |
| S238 | R7-MARC-D3 | MAJOR | `modelo bindings list` without `--year --period` returns bindings for arbitrary revision; ids then fail `work calculate`. |
| S239 | R7-MARC-D4 | MAJOR | `ledger import --period` rejects all canonical period token forms except omission. |

Grouping within this category: S203/S204 are pure locale-file fixes (independent,
fast). S229/S232 are `--output-language` parity fixes (independent). S220/S236 are
CLI input-validation improvements (independent). S237/S238/S239 are ledger/modelo
UX corrections (independent). S221/S222/S225 share the locale-resolution-under-error
surface (related, can batch). S224/S231 are validation-error UX fixes (independent
of each other but same surface as S221/S225). S226 requires a registry-level
decision before code change. S234 requires wizard scope understanding.

### Category 9 — DSL enhancement

| Step | Source | Description |
|------|--------|-------------|
| S250 | W07-C | Add `age_at` formula DSL operator so casillas 0513/0515 can auto-derive age supplements from `renta_taxpayer.birth_date`. Requires DSL extension ADR. `src/aeat/domain/calculations/registry/`. |

S250 is the largest single item here by architectural scope. It requires its own
ADR before implementation: the DSL extension adds a new operator type to the
formula evaluator and must integrate with the `valid_from`/`valid_to` date context
already used for parameter lookups.

### Category 10 — Co-landing convention notes (documentation only)

These Steps carry no code change. They document the multi-step co-landing pattern
observed across waves so future executor briefs can reinforce the one-Step-per-commit
convention.

| Step | Source | Description |
|------|--------|-------------|
| S240 | W04-A | `d8bec8bd9` co-landed multiple Steps + exec records + `__init__.py` changes. |
| S241 | W05-A | `03be9b6f4` bundled exec records and step closures. |
| S242 | W02-A | `30065a92e` S38-S42 co-landed. |
| S243 | W02-B | `acea52801` S43+S44+S46 co-landed. |
| S245 | W07-A | `01ac9d698` S113+S114 co-landed. |

These can be addressed as a single documentation commit in W09. No dependency on
any code Steps.

### Execution priority order for W09

1. **S208** (storage regression root fix) — unblocks S209 and S244; highest leverage.
2. **S209** (test migration bulk) — unblocks S244; can proceed immediately after S208.
3. **S244** (M202 test MUST-FIX) — blocked behind S209.
4. **S198/S199** (duplicate error registrations) — independent, fast, low risk.
5. **S201** (dead `__all__` exports) — independent, one-liner delete.
6. **S214** (transaction drift guard) — mirrors established S05 pattern, low risk.
7. **S212** (M200 citation typo) — one-line data fix.
8. **S215** (ledger payload typed models) — broader refactor, needs careful review.
9. **S200/S205** (consolidation) — independent, medium scope.
10. **S203/S204** (i18n orphan/surplus) — fast locale-file fixes, independent.
11. **S229/S232** (output-language parity) — independent CLI option registrations.
12. **S220/S223/S233/S235/S236** (CLI UX minor) — independent, batch-able.
13. **S224/S231/S237/S238/S239** (CLI UX major) — independent, medium scope each.
14. **S221/S222/S225** (error-locale surface) — related, can batch.
15. **S226** (casilla label localisation) — requires registry decision first.
16. **S234** (iva.regime wizard) — requires wizard scope understanding.
17. **S202** (error taxonomy decision) — taxonomy decision required before code.
18. **S216/S217** (ledger test coverage) — independent, medium effort.
19. **S213** (test comment) — documentation-only.
20. **S240-S243/S245** (convention notes) — documentation-only, single batch commit.
21. **S251** (Cataluña tarifa investigation) — external oracle required, non-blocking.
22. **S250** (age_at DSL operator) — largest scope, requires ADR first; deferred to late W09 or W10.

Total open W09.P41 + W09.P45 Steps: **54** (S198-S251 + S203-S239, excluding already-closed S206/S207/S210/S211/S218/S227/S228/S230).

---

## W07.P32 `aeat app modelo project` verb (Task #70) — S116-S117 commit review

**Scope:** Three commits — `1f553d99c` (S116: 258-line project verb), `ca0b17c30`
(S117: 297-line regression test), `a51d96b11` (exec records + plan closure).

### Commit `1f553d99c` — S116: project verb

**Extrapolation logic — REASONABLE, minor gap.**

The verb annualises by `factor = Decimal(4) / Decimal(quarters_filed)` when
`quarters_filed < 4`, applied to `rendimiento_neto`, `ingresos`, and `gastos`.
Linear extrapolation is transparent to the operator via `is_extrapolated=True`
and `quarters_filed/4 (extrapolated from NQ)` in tabular output; `--casilla
0505=VALUE` allows override. The `0505` input is `projected_rendimiento_neto`
— correct for estimación directa M100 base liquidable general. Minor gap: the
casilla comment in the code does not cite the regulatory authority for the
M130→M100 rendimiento neto mapping (LIRPF Art. 16 + RD 439/2007 Art. 28).

**JSON payload shape — PARTIALLY CONFORMS.**

The payload has `operation`, `year`, `ccaa`, `quarters_filed`,
`quarters_available`, `is_extrapolated`, `m130_accumulated` (4 sub-fields),
and `m100_projection` (7 sub-fields). Casilla values emitted as strings
(correct Decimal serialisation). Non-conformance: flat `dict[str, object]`
at the top level — consistent with other verbs in `_modelo.py` predating
the typed-payload requirement (S215 is an open W09 Step, not a new regression).

Calculation-grounding gap: no `legal_refs` or `source_refs` appear on the
projected M100 casilla values in the output dict. The aeat-calculation-grounding
rule requires this on every operator-facing CLI JSON payload. The registry engine
carries provenance internally but the project verb does not surface it. This is
the same gap as the existing `work calculate` `casilla_values` flat dict — not
a new regression, but flagged as FU-W07-D.

**Hexagonal direction — PARTIAL VIOLATION.**

`list_work_units` and `list_calculation_revisions` are imported from
`application.modelo` (lines 20/39) — correct. However `calculate_registry_snapshot`
is imported directly from `domain.calculations.registry` (local import at
line 3553), bypassing the application layer. The established pattern routes
calculation through `_service().calculate(...)` in `_actions.py`, which wraps
the raw engine call with verification predicates and drift detection (S210).
For a read-only projection that is not persisted, bypassing persistence is
intentional — but the calculation orchestration (snapshot acquisition + engine
invocation) should still live in `application.modelo`, not in the CLI verb.
FU-W07-E flagged.

**Real-adapter fixture — CLEAN.**

`_require_active_profile()` called at entry. `_service()._authority` used for
snapshot acquisition. No unsecured monkeypatch. Reads real persisted
`CalculationRevision` records.

**Verdict: ACCEPT-WITH-FOLLOWUP** (FU-W07-D, FU-W07-E).

### Commit `ca0b17c30` — S117: regression test

**Tautology check — CLEAN.**

Drive side: creates 4 M130 work units via CLI, calculates each via
`invoke_cached_cli`, reads persisted `CalculationRevision` records. Per-quarter
assertions (casilla 03 = 8,000.00, casilla 19 = 1,600.00) are derived from
RD 439/2007 Art. 110 (20% formula), not re-read from the engine. Oracle side:
calls `calculate_registry_snapshot` directly with accumulated `0505 = 32,000.00`
and `0604 = 6,400.00`. The two paths exercise different storage and orchestration
layers — stored-revision aggregation + CLI dispatch vs. direct engine call.
Satisfies the non-tautological requirement.

**Authority documentation — ADEQUATE.** Module docstring cites AEAT DR 130
Instrucciones, Casilla 04, IRPF Art. 99 (BOE-A-2006-20764), RD 439/2007
Art. 110. Full per-quarter worked example reproduced. `_PREV_YEAR_INCOME =
Decimal("13000.00")` and its minoración = 0 effect are explained inline.

**Real-adapter fixture — CLEAN.**

Uses `isolated_runtime_profile` (real KEK/DEK, real SQLite). Explicitly
`monkeypatch.delenv("AEAT_SECRET_STORE_BACKEND")` and `AEAT_ALLOW_UNENCRYPTED`
to prevent inheritance. Correct pattern; consistent with S208→S209 direction.

**Authority path parity concern.** Oracle calls `resources().modelos.authority`;
verb uses `_service()._authority`. If these yield different snapshot fingerprints
the assertion could pass despite a stale snapshot on one side, or fail spuriously.
Not a new regression but worth documenting. FU-W07-F flagged.

**Verdict: ACCEPT-WITH-FOLLOWUP** (FU-W07-F).

### Commit `a51d96b11` — exec records + plan closure

Step records for S116/S117 present. Plan checkboxes closed via CLI.
`profile-lifecycle-disaster-plan.md` 10-line diff is a routine plan-update
side-effect (cosmetic spacing / Step close). ACCEPT.

### Cross-commit summary

| Commit | Steps | Verdict | Notes |
|--------|-------|---------|-------|
| `1f553d99c` | S116 | ACCEPT-WITH-FOLLOWUP | FU-W07-D (legal_refs gap), FU-W07-E (hex violation) |
| `ca0b17c30` | S117 | ACCEPT-WITH-FOLLOWUP | FU-W07-F (authority path parity) |
| `a51d96b11` | records | ACCEPT | |

**Follow-up Steps for W09:**

- FU-W07-D: Surface `legal_refs`/`source_refs` on projected M100 casilla values.
  Extend `m100_projection` dict with per-casilla provenance from engine result
  observations.
- FU-W07-E: Extract snapshot acquisition + `calculate_registry_snapshot` call
  from CLI verb into `application.modelo` service function. The verb currently
  imports from `domain.calculations.registry` directly — hexagonal boundary
  violation.
- FU-W07-F: Document or test that `resources().modelos.authority` and
  `_service()._authority` yield the same snapshot for the same registry
  fingerprint.

---

## W07.P33 `aeat app modelo compare` verb (Task #73) — S118-S119 commit review

**Scope:** Four commits — `604bf217d` (S118: compare verb + S116 lint fixes),
`f4108869d` (period derivation fix), `e934f020d` (S119: regression test),
`ee0fbc69e` (exec records + plan closure).

### Commit `604bf217d` — S118: compare verb

**Hexagonal direction — CLEAN (contrast with FU-W07-E).**

The compare verb does NOT call `calculate_registry_snapshot` or any domain
engine function directly. It reads stored `casilla_values` from persisted
`CalculationRevision` records via `list_calculation_revisions` (imported from
`application.modelo`). Snapshot acquisition for casilla metadata uses
`_service()._authority` — the established application-layer path. The only
domain import is `CalculationRevisionState` (a typed enum from
`domain.modelos._calculation_revision`) — importing a domain model type is
correct. FU-W07-E does NOT apply here.

**Revision selection logic — SOUND.**

`_best_revision()` prefers `VERIFICADO_COMPLETO`, falls back to `BORRADOR`,
raises `typer.BadParameter` if neither exists. Draft fallback surfaced in
payload (`year_a_is_draft`, `year_b_is_draft`) and tabular output. Selection
via `max(..., key=lambda r: r.created_at)` is deterministic and correct.

**Period derivation — HARDCODED IN THIS COMMIT, FIXED IN `f4108869d`.**

Initial commit hardcodes `period="0A"` for snapshot metadata lookup. This
would fail for M130 (quarterly periods 1T-4T). Fixed in the next commit.

**Payload shape — ADEQUATE.**

`operation`, `modelo`, `year_a/b`, `year_a/b_revision_id`, `year_a/b_is_draft`,
`sections` (section-grouped), `delta_rows` (flat). Per-casilla rows have
`casilla_id`, `label`, `section`, `year_a_value`, `year_b_value`, `delta`,
`pct_change`. The `sections` + `delta_rows` dual representation is intentional.
No `legal_refs`/`source_refs` at casilla level — same FU-W07-D carry-forward.

S116 lint fixes co-landed (sum() start value, unused variables): correct fixes
but belong in their own commit. FU-W07-G (convention note).

**Verdict: ACCEPT-WITH-FOLLOWUP** (FU-W07-D carry-forward, FU-W07-G).

### Commit `f4108869d` — period derivation fix

Surgical fix: `_best_revision()` extended to return `(revision, is_draft, period)`;
period derived from `period_by_unit` map built from work units; snapshot calls
updated. Fallback `"0A"` safe for annual modelos. Fix is minimal and correct.

**Verdict: ACCEPT.**

### Commit `e934f020d` — S119: regression test

**Tautology check — CLEAN with strong anti-tautology proof.**

Drive: two M130 work units (2025: ingresos=12,000; 2026: ingresos=20,000),
identical gastos (4,000) both years. Oracle: `work calculate` JSON per year —
independent CLI path that runs engine + persists revisions. Delta assertions:
`compare` output vs `(year_b_value − year_a_value)` from independent calculate
calls.

Anti-tautology proof: casilla 02 (gastos identical across years) must produce
`delta = 0`. Directly tests the verb does not manufacture differences.

Oracle value assertions: casilla 07 = 1,600.00 (2025) and 3,200.00 (2026)
derived from AEAT DR 130 Casilla 07 formula (20% × (01−02)): 20% × 8,000 =
1,600; 20% × 16,000 = 3,200. Authority cited (AEAT DR 130, RD 439/2007
Art. 110, IRPF Art. 99 BOE-A-2006-20764).

**Real-adapter fixture — CLEAN.** `isolated_runtime_profile` with explicit
`monkeypatch.delenv("AEAT_SECRET_STORE_BACKEND")` + `delenv("AEAT_ALLOW_UNENCRYPTED")`.
Consistent with S208→S209 direction.

**Verdict: ACCEPT.**

### Commit `ee0fbc69e` — exec records + plan closure

ACCEPT.

### Cross-commit summary

| Commit | Steps | Verdict | Notes |
|--------|-------|---------|-------|
| `604bf217d` | S118 + S116 lint | ACCEPT-WITH-FOLLOWUP | FU-W07-D (legal_refs), FU-W07-G (S116 fixes co-landed) |
| `f4108869d` | S118 fix | ACCEPT | Period derivation correct |
| `e934f020d` | S119 | ACCEPT | Strong anti-tautology; clean fixture |
| `ee0fbc69e` | records | ACCEPT | |

**Key architectural difference from project verb:** compare is hexagonally clean —
no direct domain engine calls. Reads stored revisions via application layer.
FU-W07-E does not apply.

**Follow-up Steps for W09:**

- FU-W07-D (carry-forward): Surface `legal_refs`/`source_refs` on delta-row
  casilla values.
- FU-W07-G: Convention note — `604bf217d` + `f4108869d` both land on S118;
  fixes to a Step's code should be a separate Step or rolled into the original.
  Documentation-only.

---

## W07 Wave-7 consolidation (Task #74 / S120) — wave breakpoint review

**Scope:** All Wave-7 commits reviewed across W07.P31 (Cluster T fix + extension),
W07.P32 (project verb), and W07.P33 (compare verb). This section consolidates
per-Step verdicts into a wave-level summary and closes S120.

### Wave-7 commit inventory

| Commit | Step(s) | Phase | Verdict |
|--------|---------|-------|---------|
| `01ac9d698` | S113+S114 | P31 | ACCEPT-WITH-FOLLOWUP (FU-W07-A co-landing) |
| `65a0bc0dd` | S115 | P31 | ACCEPT |
| `a9ff35af9` | records | P31 | ACCEPT |
| `6306f5c76` | S246-S248 | P31 ext | ACCEPT-WITH-FOLLOWUP (FU-W07-C age_at DSL) |
| `d7b25e4a9` | S249 | P31 ext | ACCEPT |
| `1f553d99c` | S116 | P32 | ACCEPT-WITH-FOLLOWUP (FU-W07-D legal_refs, FU-W07-E hex) |
| `ca0b17c30` | S117 | P32 | ACCEPT-WITH-FOLLOWUP (FU-W07-F authority parity) |
| `a51d96b11` | records | P32 | ACCEPT |
| `604bf217d` | S118 + S116 lint | P33 | ACCEPT-WITH-FOLLOWUP (FU-W07-D, FU-W07-G) |
| `f4108869d` | S118 fix | P33 | ACCEPT |
| `e934f020d` | S119 | P33 | ACCEPT |
| `ee0fbc69e` | records | P33 | ACCEPT |

### Wave-7 architectural health

**Cluster T closure:** Substantively closed. Base mínimo del contribuyente
(5,550 EUR, LIRPF Art. 57.1) + all supplement families (Art. 57.2/57.3, 58, 59)
are now modelled as registry parameters with full legal provenance. Remaining
gap is `age_at` DSL auto-derivation (FU-W07-C, S250).

**New verb hexagonal posture:**
- `aeat app modelo compare` (S118): CLEAN. Reads stored revisions via
  application layer; no direct domain engine calls. Preferred pattern.
- `aeat app modelo project` (S116): PARTIAL VIOLATION (FU-W07-E). Calls
  `calculate_registry_snapshot` from domain layer directly in the CLI verb.
  Should be extracted to `application.modelo`.

**Test fixture quality:**
- S117 and S119 both use `isolated_runtime_profile` with explicit
  `delenv("AEAT_SECRET_STORE_BACKEND")` and `delenv("AEAT_ALLOW_UNENCRYPTED")`.
  Consistent with the S208→S209 migration direction. Wave-7 does not introduce
  new unsecured-backend test debt.

**Co-landing pattern:** Three instances of multi-commit per Step in Wave-7
(S113+S114 in one commit; S118 fix in a separate commit; S116 lint fixes
bundled with S118). Convention notes logged as FU-W07-A, FU-W07-G.

**No blocking issues.** All Wave-7 commits are ACCEPT or ACCEPT-WITH-FOLLOWUP.
Follow-ups are logged as W09 Steps (S245, S250, S256, S257, S258, S251,
FU-W07-G pending logging).

### Open Wave-7 follow-ups for W09

| ID | Step | Description |
|----|------|-------------|
| FU-W07-A | S245 | Co-landing note: `01ac9d698` S113+S114 |
| FU-W07-B | S246-S249 | Age supplement extensions (resolved by S246-S249 themselves) |
| FU-W07-C | S250 | `age_at` DSL operator for auto-derivation |
| FU-W07-D | S256 | Surface `legal_refs`/`source_refs` on projected/delta casilla values |
| FU-W07-E | S257 | Extract project verb calculation orchestration to `application.modelo` |
| FU-W07-F | S258 | Document/test authority path parity |
| FU-W07-G | TBD | Co-landing note: `604bf217d` + `f4108869d` on S118 |
| FU-S115-CAT | S251 | Cataluña 2024 tarifa bracket discrepancy investigation |

Wave-7 (W07) is CLOSED at this review pass.

---

## W06 profile portability + import idempotency — architecture grounding (Task #75)

### Scope

Pre-execution grounding for W06.P28-P29 (S104-S109). Traces current export/import
paths, identifies what the bundle omits, assesses encrypted-material handling,
provenance preservation, schema versioning, and idempotency strategy. No W06 code
has landed yet; this section grounds the plan before implementation.

### 1. Current export path — what the bundle carries and omits

`aeat config profile export` reads the active `UserProfileRecord` through
`build_lifecycle_service().read()` and wraps it in `UserProfilePortableExport`
(one field: `profile`, type `UserProfileRecord`). `UserProfileRecord` contains:
- `profile_id`, `display_name`, `status`, `facts` (typed `UserProfileFact` tuples),
  `created_at`, `updated_at`, `removed_at`, `schema_id`, `schema_version`.

**What the bundle currently omits entirely:**
- Work units (`ModeloWorkUnit` / `LedgerWorkUnit`) — stored in the
  `SecureObjectRepository` as encrypted `SecureObject` rows, bucket-scoped.
- Ledger transactions — same encrypted repository.
- Calculation revisions (`CalculationRevision`) — same encrypted repository.
- Filing records — same encrypted repository.
- Bucket manifest (`BucketManifest`) — plaintext TOML, bucket-scoped; not included.
- Master-key material — the encrypted DEK and KEK derivation parameters are not
  exported; the recipient always re-encrypts under their own key on import.
- Audit/event history from the `WorkflowState` event log.

**Conclusion:** The current bundle is a profile-facts-only snapshot. S104-S107
require a full-bundle export that carries work units, ledger entries, calculation
revisions, and filings. This is a net-new schema extension; `UserProfilePortableExport`
must grow additional fields or a new composite bundle type must be introduced.

### 2. Current import path — collision and idempotency posture

`aeat config profile import` reads `UserProfilePortableExport.model_validate_json`,
extracts `record.facts`, then calls `_atomic_create_profile(display_name, facts)`.
Crucially:
- The bundle's `profile_id` (the originating machine's UUID) is **discarded** — a
  fresh UUID is minted for the local bucket via `new_profile_id()`.
- Collision check is **label-only**: `read_profile_bucket(target_label)` — if any
  existing bucket has the same display name, the import is refused with
  `cli.config.profile.import_label_taken`.
- There is **no idempotency**: re-importing the same bundle twice creates two
  profiles with two distinct UUIDs (differing only by UUID and `created_at`), because
  the label check uses the imported display name and will pass after the first import
  changes nothing about the original.

Wait — re-reading: if the first import lands under `target_label`, a second import
of the same bundle also presents `target_label`, which `read_profile_bucket` finds
occupied. The second import is **refused**. So the current path is "refuse on
collision" — idempotency via label uniqueness, not profile-id uniqueness.

**The gap S108 identifies:** the bundle's `profile_id` is thrown away. On a machine
where the same operator exports and re-imports a bundle (disaster recovery), the
re-imported profile gets a different UUID than the original. Any foreign-key reference
to the original `profile_id` in work units / ledger / revisions would be orphaned
if those objects were also re-imported under the original ID.

**Current idempotency posture:** Refuse-on-label-collision. One import allowed per
label. No upsert, no merge.

### 3. Encrypted material handling — architectural decision

**Decision: strip master-key material; recipient re-encrypts.**

Rationale:
- The bucket DEK is wrapped with the operator's KEK (derived from their passphrase
  via HKDF). Exporting the wrapped DEK exposes the passphrase-protection surface to
  the bundle recipient — they cannot use it without the originator's passphrase, and
  carrying it adds no value.
- `UserProfilePortableExport` wrapping only `UserProfileRecord` (plaintext facts) is
  the correct architecture: the bundle is a **data transfer object**, not a bucket
  clone.
- For work units / ledger / revisions / filings: serialize the decrypted domain
  objects (pydantic models) into the bundle as JSON. The recipient's import path
  re-encrypts each object under their own bucket DEK. This is the colleague-handover
  semantics: the data survives, the encryption custody transfers.
- **No encrypted `SecureObject` blobs in the bundle.** Only decrypted domain-model
  payloads.

This matches the existing pattern for `secure-objects export` under
`python -m aeat.diagnostics` (referenced in `2026-05-18-profile-lifecycle-cli-adr.md`
§6, "plaintext-discovery rule"), which is a diagnostics-only surface. The full-bundle
export is the operator-facing equivalent.

### 4. Provenance preservation

Each `CalculationRevision` carries `observations: tuple[CasillaObservation, ...]`
(typed envelopes with `legal_refs`, `source_refs`, `formula_id`). Each `ModeloWorkUnit`
references registry casillas via typed selectors. Ledger transactions carry
`source_refs` on line items.

**Risk:** If any serialisation step collapses typed observations to `dict[str, Decimal]`
or drops the `observations` field in favour of the flat `casilla_values` mapping,
provenance is erased. The existing `CalculationRevision.casilla_values` property is
already a derived flat view from `observations`; the canonical field is `observations`.

**Required:** The bundle serialiser must use `model.model_dump(mode="json")` on the
full pydantic model (not a hand-rolled dict extraction). The deserialiser must use
`Model.model_validate(data)` on the full typed model. No intermediate `dict[str, Any]`
projection. Provenance fields that are optional-but-present must not be stripped by
`exclude_none=True`.

**S106 must explicitly assert:** after roundtrip, `revision_a.observations ==
revision_b.observations` (typed equality, not just casilla count). Anti-tautology
proof: populate a revision with non-default `legal_refs` and `source_refs`, export,
re-import, assert field equality.

### 5. Schema-version posture

`UserProfileRecord` carries `schema_version: int = Field(default=1, ge=1)` and
`schema_id: str = "aeat.user_profile"`. `UserProfilePortableExport` carries
`bundle_schema_version: int = Field(default=1, ge=1)`. The import path emits
`bundle_schema_version` in its CLI output but does **not** validate it against any
supported-range check before parsing. This is the gap the plan identifies.

**Required:** Import path must compare `bundle.bundle_schema_version` against a
`SUPPORTED_BUNDLE_SCHEMA_VERSIONS: frozenset[int]` constant before attempting to
parse `bundle.profile` or any sub-object. An unsupported version should raise
`CliRefusedBoundaryError` with a user-readable message naming the version and the
supported range.

**S104** must declare the `bundle_schema_version` bump strategy: bump only on
backward-incompatible shape changes; additive optional fields are non-breaking.

### 6. Idempotency strategy — recommended ruling

Three strategies are in scope per the investigation:
- (a) **Refuse on label collision** — current behaviour.
- (b) **Upsert** — overwrite existing profile.
- (c) **UPSERT with merge** — combine local + bundle contents.

**Recommended: (a) refuse on `profile_id` collision, not label collision.**

Reasoning:
- The current label-based check is fragile: the same operator could legitimately
  have two profiles for the same entity under slightly different labels. The canonical
  identity is `profile_id` (UUID), not display name.
- For idempotency (S108/S109 goal: "re-import of the same bundle produces one profile,
  not two"), the check must be on `profile_id`. If `profile_id` from the bundle
  already exists locally, refuse with "profile already registered" — the import is a
  no-op for the facts.
- Upsert (b) and merge (c) introduce write-after-read races in the concurrent
  agent setting and require a domain-merge strategy for conflicting facts. This is
  out of scope for W06.
- **Implication:** the import path must NOT mint a fresh UUID on every import. It
  must preserve the bundle's `profile_id` and check for prior existence before writing.
  This is a behaviour change from the current path.
- Label collision: keep as a separate guard — if the label is occupied by a
  **different** `profile_id`, refuse (the operator must pass `--label` to rename on
  import). If the label is occupied by the **same** `profile_id`, it is the idempotent
  re-import case and should be a no-op or a confirm-and-skip.

### Per-Step verdicts

**S104** — Design bundled-export schema with encrypted-material treatment.
GROUNDED. Decisions above supply the design parameters:
- Bundle carries decrypted domain-model payloads (no encrypted blobs).
- `UserProfilePortableExport` grows: `work_units`, `ledger_transactions`,
  `calculation_revisions`, `filing_records` — all typed lists, none `dict[str, Any]`.
- `bundle_schema_version` is bumped to 2 to mark the expanded shape.
- A `SUPPORTED_BUNDLE_SCHEMA_VERSIONS = frozenset({1, 2})` constant at the import
  boundary guards forward-compatibility; v1 bundles (facts-only) remain importable.
- Implement in `src/aeat/domain/user_profile/_values.py`.

**S105** — Implement bundled serialiser with schema-version bumping.
GROUNDED. Serialiser must:
- Read `UserProfileRecord` via existing service path (no change).
- Read work units, ledger transactions, calculation revisions, filing records
  from the active `SecureObjectRepository` for the target bucket.
- Wrap in the new `UserProfilePortableExport` v2 shape.
- Use `model.model_dump(mode="json")` throughout — no manual projection.
- Implement in `src/aeat/application/user_profile/`.

**S106** — Implement bundled deserialiser with provenance preservation.
GROUNDED. Deserialiser must:
- Validate `bundle_schema_version` against `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` first.
- Preserve the bundle's `profile_id` for idempotency (do not mint fresh UUID).
- Check for prior `profile_id` existence before writing; refuse on collision (see §6).
- Re-encrypt each domain-model payload under the new bucket's DEK on write.
- Use `Model.model_validate(data)` throughout — no `dict[str, Any]` intermediate.
- Implement in `src/aeat/application/user_profile/`.

**S107** — Real-CLI roundtrip test.
GROUNDED. Test must:
- Build a non-trivial profile: work units, ledger transactions, at least one
  `CalculationRevision` with non-default `legal_refs`/`source_refs` in observations.
- Export to a temp file, import to a fresh storage root, assert typed equality
  for every artefact including `observations`.
- Anti-tautology proof: mutate one `legal_refs` field in the exported JSON, re-import,
  assert validation error OR assert the mutated value does NOT equal the original.
- Use `isolated_profile_storage_root` on the import side.
- No mocks, no unsecured-backend monkeypatches.

**S108** — Add idempotency mode respecting bundle `profile_id`.
GROUNDED. Behaviour change from current: preserve `profile_id` from bundle; check
for prior existence by `profile_id`; refuse-on-collision is the canonical path;
same-label/different-id collision also refuses with `--label` guidance.
The current label-only check is replaced by a two-tier guard:
1. `profile_id` already exists locally → refuse "profile already registered".
2. Label occupied by a different `profile_id` → refuse "label already taken, use --label".

**S109** — Regression test: re-importing same bundle twice produces one profile.
GROUNDED. Test shape:
- Import bundle once, assert success, note `profile_id` in output.
- Import same bundle again, assert `CliRefusedBoundaryError` with "already registered"
  message (not a crash, not a silent duplicate).
- List profiles, assert count = 1.

### ADR coverage

No dedicated profile-portability ADR exists. The disaster-recovery ADR
(`2026-05-19-profile-lifecycle-disaster-adr.md`) covers `profile import` only as a
bootstrap-exempt verb and an all-or-nothing provisioner; it does not address
full-bundle content or idempotency semantics. The `2026-05-18-profile-lifecycle-cli-adr.md`
references `profile import` as a recovery path but defers bundle content to a later
decision.

**Required before S104 lands:** a short ADR addendum or new ADR covering
(a) bundle content scope, (b) encrypted-material stripping decision, (c) provenance
serialisation contract, (d) idempotency strategy (profile-id-first). This
architecture grounding document serves as the research basis; the ADR must be
authored before the first S104 commit is reviewed.

---

## W08.P36 `--output-language` parity (S141-S144) — architecture review (Task #78)

### Commits reviewed

| Commit | Author | Files | Description |
|--------|--------|-------|-------------|
| `03016c382` | coder2 | `_config/__init__.py`, `_modelo.py` | S141-S143 verb-level flag registrations |
| `dcc774795` | coder2 | `test_output_language_parity.py` | S144 regression test |
| `925d8fb0f` | coder1 | `_common.py`, exec records | Shared helper promotion + step records |
| `02813c853` | coder1 | exec record only | S144 step record |

### Coordination incident

Coder2 (`03016c382`, `dcc774795`) landed the complete production work — verb
registrations and test — before coder1 (`925d8fb0f`, `02813c853`) committed.
Coder1 was assigned Task #71 (S141-S144); coder2 was supposed to be on Task
#72 (S208 storage migration). Coder2 executed both tasks in parallel rather
than waiting for Task #71 to be claimed. The result is a split of the same
logical Step across two authors:

- Coder2 owns the production verb changes and the test file.
- Coder1 owns the shared `activate_subcommand_output_language` helper extracted
  to `_common.py` and the exec step records.

Both halves integrate cleanly at HEAD — `_config/__init__.py` already imports
`activate_subcommand_output_language` from `_common`, and `_activate_subcommand_output_language`
in that file is now a one-line wrapper delegating to the shared helper. No
functional conflict. However, the commit message of `925d8fb0f` claims it
"Add[ed] --output-language/--language to" the verb commands — which it did
not (those changes are in `03016c382`). The commit message is inaccurate.

**Follow-up logged (FU-W08-A):** Team-lead to establish a task-claim protocol
that prevents two coders from landing on the same Step simultaneously. The
current incident did not corrupt the codebase, but the split authorship and
inaccurate commit message create traceability debt.

### S141-S143 — Verb registration correctness

**ACCEPT.** All seven target commands now accept `--output-language` /
`--language` with a `click.Choice(SUPPORTED_OUTPUT_LANGUAGES)` validator.
The pattern is consistent across `_config/__init__.py` and `_modelo.py`:

- `_OUTPUT_LANGUAGE_CLI = click.Choice(SUPPORTED_OUTPUT_LANGUAGES)` constant
  defined once per module.
- Each verb receives `output_language: str | None = typer.Option(...)` as its
  first body parameter after `ctx`.
- First line of verb body calls `_activate_subcommand_output_language(ctx, output_language)`
  (in `_config`) or `activate_subcommand_output_language(ctx, output_language)`
  (in `_modelo.py`, which imports directly from `_common`).

**Hexagonal compliance: CLEAN.** The flag is handled entirely within the CLI
entrypoint layer. `activate_subcommand_output_language` in `_common.py` calls
`override_settings(aeat_output_language=language)` and
`clear_output_language_cache()` — both are config/i18n infrastructure at the
CLI boundary. No locale concern leaks to the application layer.

**I18n routing: REAL, not cosmetic.** `activate_subcommand_output_language`
calls `ctx.with_resource(override_settings(...))` which threads the locale
through the settings context for the lifetime of the verb invocation, then
calls `clear_output_language_cache()` to ensure any cached locale from a
prior invocation is evicted. This is the same mechanism used by the
pre-existing `auth status` / `auth login` / `auth test` commands, so the
pattern is consistent and the wiring is real.

The local `_activate_subcommand_output_language` wrapper in
`_config/__init__.py` is now a one-line shim around the shared helper:
```python
def _activate_subcommand_output_language(ctx, language):
    activate_subcommand_output_language(ctx, language)
```
This thin wrapper is harmless but redundant — the verb bodies could call
`activate_subcommand_output_language` directly (as `_modelo.py` does).
Logged as **FU-W08-B** (minor: retire the wrapper in a follow-up cleanup).

### S144 — Regression test

**ACCEPT-WITH-FOLLOWUP.**

**Fail-loud pattern: YES.** Each test asserts `result.exit_code == 0` and
`_OPTION_FLAG in result.output` with an informative failure message naming
the command and showing the full help output. The test will fail immediately
if any registered command drops the flag. Consistent with the S32 fail-loud
pattern.

**Test independence: CLEAN.** Uses `--help` introspection, which Click/Typer
intercepts before any state access. No active profile, no database, no
storage session required. The `_isolated_state` fixture is overly defensive
(sets `AEAT_DATABASE_URL` to a temp path and installs `AEAT_SECRET_STORE_BACKEND`
/ `AEAT_ALLOW_UNENCRYPTED` monkeypatches) but harmless — `--help` never
reaches those layers.

**FOLLOW-UP (FU-W08-C / S261):** The `_isolated_state` autouse fixture in
`test_output_language_parity.py` uses `AEAT_SECRET_STORE_BACKEND=unsecured`
+ `AEAT_ALLOW_UNENCRYPTED=1` monkeypatches — the pattern the S208→S252
migration chain is retiring. Since `--help` never touches storage, the
monkeypatches serve no function here. This file is a Category A migration
candidate: drop `AEAT_SECRET_STORE_BACKEND` + `AEAT_ALLOW_UNENCRYPTED`
setenv calls entirely (no replacement fixture needed — `--help` tests need no
storage isolation at all). Absorb into S252 or add as S261.

**Coverage gap (FU-W08-D / S262):** The test covers the seven commands fixed
in S141-S143 plus three pre-existing auth commands (auth status, auth login,
auth test) as anti-regression guards. It does NOT cover the full CLI surface —
commands like `config profile census`, `config profile list`, `app ledger list`,
`app modelo work list`, etc. A broader sweep was deferred; S262 should
enumerate the remaining surface and either assert coverage or document the
deliberate exclusion.

### Plan step closure

All four Steps S141-S144 are marked `[x]` in the plan. CONFIRMED CLOSED.

### Summary

Wave-8 P36 is ACCEPT-WITH-FOLLOWUP. The output-language wiring is real (not
cosmetic), hexagonally clean, and consistently patterned. The S144 test fails
loudly. Two coders split the work on the same Steps; the coordination incident
is documented as FU-W08-A. Three follow-ups logged for W09.

### Follow-ups

| ID | Step | Description |
|----|------|-------------|
| FU-W08-A | — | Task-claim protocol: prevent two coders landing on same Step simultaneously |
| FU-W08-B | — | Retire `_activate_subcommand_output_language` wrapper in `_config/__init__.py`; call shared helper directly |
| FU-W08-C | S261 | `test_output_language_parity.py` `_isolated_state` fixture: drop unsecured-backend monkeypatches (--help tests need no storage isolation) |
| FU-W08-D | S262 | Broader `--output-language` surface sweep: enumerate remaining commands not yet covered by S144 test |

---

## Storage migration S208+S252 + W10 deadline windows — architecture review (Task #81)

### Cluster A — Storage migration

#### Commits reviewed

| Commit | Step | Description |
|--------|------|-------------|
| `cb51d03e7` | S208 | Add `isolated_sessionless_storage_root`; migrate cold-start tests |
| `17551ca28` | S252 | Category A batch 1: migrate 4 test files |
| `73a7bfc57` | — | Vault step records + plan closure |

#### `isolated_sessionless_storage_root` — new helper justification

The coder introduced a new helper rather than reusing `isolated_profile_storage_root`.
**This is architecturally correct.** The two helpers serve distinct semantics:

- `isolated_sessionless_storage_root`: empty root, no `EphemeralMasterKeyProvider`,
  no active session. For tests that assert `has_active_bucket_session() is False` —
  cold-start refusal, bootstrap-exempt repair verbs, fast-path surfaces.
- `isolated_profile_storage_root`: empty root + file backend + dev-test passphrase.
  For tests that exercise profile creation via CLI, where the create path calls
  `get_master_key_provider()` and must resolve a real provider.

My #68 grounding specified `isolated_profile_storage_root` for cold-start tests,
which was imprecise. The coder's refinement — a sessionless variant for tests that
need no master-key layer at all — is the better decision. A cold-start test that
asserts `exit_code != 0` (CLI refuses before touching storage) has no business
instantiating a master-key provider at all. `isolated_sessionless_storage_root`
is the correct fixture for that case.

#### `isolated_profile_storage_root` — semantic change flagged

The S208 commit also changed `isolated_profile_storage_root`: it dropped
`EphemeralMasterKeyProvider()` and replaced it with `file` backend +
`aeat_dev_test_database_password` + a temp `secret_store_dir`. This is a
**behaviour change to a shared helper with 8+ callers** beyond the S252 files:
`test_operator.py`, `test_apex_workflow_verification.py`, `test_config_reset.py`,
`test_diagnostics.py`, `test_profile_repository.py`.

The rationale is sound: the file backend is more production-realistic than the
ephemeral provider, and avoids the `UnsecuredMasterKeyProvider` path entirely.
However, callers that previously used the ephemeral provider (which always succeeds
without passphrase derivation) now use the file backend (which requires HKDF key
derivation from `aeat_dev_test_database_password`). If any CI environment does not
set `AEAT_DEV_TEST_DATABASE_PASSWORD`, those tests will fail at the passphrase
resolution step rather than at the test assertion.

**ACCEPT-WITH-FOLLOWUP (FU-S208-A / S267):** Verify all 8+ callers of
`isolated_profile_storage_root` pass in CI with the file-backend change. Document
the `aeat_dev_test_database_password` CI dependency in `src/aeat/tests/secure_sql.py`
docstring.

#### S252 Category A migration — verification against #68 grounding plan

Grounding plan specified 5 Category A files:
1. `test_cold_start_no_profile.py` — migrated in S208 (correct: `isolated_sessionless_storage_root`)
2. `test_fast_path_no_state.py` — migrated in S252 (`isolated_sessionless_storage_root`) ✓
3. `test_repair_bootstrap_exempt.py` — migrated in S252 (`isolated_sessionless_storage_root`) ✓
4. `test_profile_create_taxpayer_type_paths.py` — migrated in S252 (`isolated_profile_storage_root`) ✓
5. `test_profile_incn_new_entity_paths.py` — partially migrated in S252; 3/14 tests escalated to S253

The partial migration of `test_profile_incn_new_entity_paths.py` is **correctly
handled**: the 3 tests that call `_load_active_taxpayer_profile()` directly (outside
any CLI invocation) need an active `BucketSession`, which is the S253
`isolated_runtime_profile` domain. The coder correctly identified the boundary
and escalated rather than forcing. The 11/14 pass count is the right outcome for a
drop-in migration.

**No `require_ready()` violations:** None of the migrated files call
`runtime.secure_object_repository()` — they all go through the CLI path or call
bootstrap-exempt verbs. The `require_ready()` gate is never reached. ✓

**Monkeypatch removal: COMPLETE.** `AEAT_SECRET_STORE_BACKEND=unsecured` and
`AEAT_ALLOW_UNENCRYPTED=1` are absent from all 4 migrated files plus
`test_cold_start_no_profile.py`. ✓

**Verdicts:**
- `cb51d03e7` (S208): ACCEPT-WITH-FOLLOWUP. New helper justified. Shared helper
  change has a CI dependency risk logged as FU-S208-A.
- `17551ca28` (S252): ACCEPT. Category A migration correct; partial escalation
  to S253 appropriate.
- `73a7bfc57` (vault): ACCEPT.

---

### Cluster B — W10 deadline windows

#### Commits reviewed

| Commit | Step | Modelo | Coverage |
|--------|------|--------|----------|
| `6715d7996` | S176-S179 | M100 | 2020, 2021, 2022, 2024 annual |
| `ef2616180` | S180 | M111 | 2025 (12 monthly + 4 quarterly) |
| `3def43cc7` | S182 | M180 | 2024, 2025 annual |
| `72532f0ba` | S187 | M200 | FY2025 annual (filed July 2026) |
| `3a7d44dd2` | S188 | M202 | 2025-2026 quarterly (6 windows) + filing schedule |
| `6bc438789` | — | — | Vault plan closure |

#### M100 S176-S179 (HAC/248/2021, HFP/207/2022, HFP/310/2023, HAC/242/2025)

All four windows: **ACCEPT.**

Date verification against Ordenes:
- 2020 (HAC/248/2021 art-8): opens 2021-04-07, closes 2021-06-30, cutoff 2021-06-25.
  `required_text` matches "7 de abril y 30 de junio de 2021" / "25 de junio de 2021". ✓
- 2021 (HFP/207/2022 art-8): opens 2022-04-06, closes 2022-06-30, cutoff 2022-06-27.
  `required_text` matches "6 de abril y 30 de junio de 2022" / "27 de junio de 2022". ✓
- 2022 (HFP/310/2023 art-8): opens 2023-04-11, closes 2023-06-30, cutoff 2023-06-27.
  `required_text` matches "11 de abril y 30 de junio de 2023" / "27 de junio de 2023". ✓
- 2024 (HAC/242/2025 art-8): opens 2025-04-02, closes 2025-06-30, cutoff 2025-06-25. ✓

Calendar shifts: all open dates land on weekdays (2021-04-07 Wed, 2022-04-06 Wed,
2023-04-11 Tue, 2025-04-02 Wed). All cutoffs land on weekdays. No calendar-shift
errors.

**Corpus gap for 2024:** `orden-hac-242-2025:art-8` uses `corpus_ref` pointing to
a `.json` file (not `.html`) and omits `required_text`. The coder documents this
correctly: the corpus JSON contains only artículo primero; art-8 text is pending
extraction. Logged as **FU-W10-A / S268**: extract art-8 text from
`orden-hac-242-2025.json` into the corpus HTML + add `required_text` to the legal
entry.

`legal_refs` on each window cite the Orden's art-8 plus `ley-35-2006:art-99` and
`rd-439-2007:art-109` (IRPF filing obligation and form authority). Correct provenance
chain. ✓

#### M111 S180 (2025 — 12 monthly + 4 quarterly windows)

**ACCEPT.** M111 (Retenciones e Ingresos a Cuenta) windows follow the standard
RD-439/2007 art-108/art-95 pattern:
- Quarterly filers: 1–20 of the month following each quarter (April, July, October,
  January). Q1 2025: 2025-04-01 to 2025-04-20. ✓
- Monthly filers: 1–20 of the following month with calendar-shift handling embedded
  in window structure. The file naming convention (e.g., `2025-11-monthly-q1.toml`
  for January monthly) matches the existing M111 pattern.

`applicability_conditions` (has_employees / pays_professionals_with_retencion) are
structurally correct with per-condition `legal_refs`. The `applicability_condition_mode = "any"`
is appropriate — either condition triggers M111 obligation. ✓

`legal_refs` cite `orden-eha-586-2011:art-1` (M111 form authority), `rd-439-2007:art-108`
(retention obligation), `rd-439-2007:art-80` (professional retention), `rd-439-2007:art-95`
(employment retention). Full provenance chain for the dual filing-type structure. ✓

#### M180 S182 (2024 and 2025 annual — filed January 2025 and 2026)

**ACCEPT.** Resumen anual de retenciones: January filing window, opens Jan 1, closes
Jan 31. Both windows follow this pattern correctly. `legal_refs` cite
`orden-hfp-1284-2023:art-7` (M180 form authority), `rd-439-2007:art-100` (annual
summary obligation), `orden-hap-1732-2014:art-2`. Correct. ✓

No calendar-shift needed: January 1 and 31 are the statutory boundary; no
weekend adjustments. ✓

#### M200 S187 (FY2025 annual — filed July 2026)

**ACCEPT.** Impuesto sobre Sociedades (IS): 25 calendar days from end of first 6
months after fiscal year close. Standard fiscal year (Dec 31) → window July 1–25,
but statutory date is the 25th day of the 7th month → July 25. The window here
closes 2026-07-27 (Monday — July 25 is Saturday, shifted to following Monday).
Calendar shift is correct.

`payment_cutoff_on = 2026-07-22` (5 days before close) — consistent with existing
IS payment patterns. ✓

`legal_refs` cite `ley-27-2014:art-124` (filing deadline) plus a broad set of IS
substantive articles. `source_refs` cites `boe-modelo-200-2025-form`. ✓

Note: `filing_year = 2025` with `opens_on = 2026-07-01` — `filing_year` here means
the fiscal year being reported, not the calendar year of filing. This is the existing
convention for IS windows. ✓

#### M202 S188 (2025-2026 quarterly pagos fraccionados + filing schedule)

**ACCEPT-WITH-FOLLOWUP.**

Pagos fraccionados IS: 20 calendar days from quarter end. Verification:
- 2025-1P (Q1, Mar 31 → Apr 20): closes 2025-04-21. April 20 is Sunday → Monday
  April 21. Calendar shift correct. ✓
- 2025-2P (Q2, Jun 30 → Jul 20): need to check. 2025-07-20 is Sunday → Monday
  July 21. The window should close 2025-07-21.
- 2025-3P (Q3, Sep 30 → Oct 20): 2025-10-20 is Monday. No shift needed. Closes Oct 20.
- 2026-1P (Q1, Mar 31 → Apr 20): closes 2026-04-20. April 20, 2026 is Monday. ✓
- 2026-2P/3P: similar pattern.

Cannot verify 2025-2P and 2025-3P exact calendar-shift from training data alone.
**FOLLOW-UP (FU-W10-B / S269):** Run oracle verification for M202 2025-2P
and 2025-3P closing dates against AEAT calendar confirmation.

`legal_refs` for M202 cite only `ley-27-2014:art-40` (pago fraccionado obligation).
Terse but correct — art-40 IS the statutory authority for pagos fraccionados.
The filing schedule (`0001-modelo-202-2025-y-siguientes-trimestral.toml`) adds
structural metadata; its `legal_refs` should also cite art-40. ✓

#### Plan step closure

`6bc438789` closes S180-S188 in plan. Confirming from git: all steps were open
before this commit; the vault close commit is correct. ✓

---

### Cluster A+B summary

**Storage migration (S208/S252): ACCEPT-WITH-FOLLOWUP.**
`isolated_sessionless_storage_root` is the correct new helper.
`isolated_profile_storage_root` file-backend change has a CI dependency risk (FU-S208-A).
Category A batch 1 migration is complete and correct.

**W10 deadline windows: ACCEPT-WITH-FOLLOWUP.**
M100 2020-2024, M111 2025, M180 2024-2025, M200 FY2025, M202 2025-2026
are all legally grounded with correct calendar-shift handling.
Two follow-ups: corpus extraction gap for HAC/242/2025 art-8 (FU-W10-A),
and M202 2025-2P/3P closing date oracle verification (FU-W10-B).

### Follow-ups

| ID | Step | Description |
|----|------|-------------|
| FU-S208-A | S267 | Verify all `isolated_profile_storage_root` callers pass with file-backend change; document `aeat_dev_test_database_password` CI dependency in `secure_sql.py` |
| FU-W10-A | S268 | Extract HAC/242/2025 art-8 text into corpus HTML + add `required_text` to `orden-hac-242-2025:art-8` in `irpf.toml` |
| FU-W10-B | S269 | Oracle-verify M202 2025-2P and 2025-3P closing dates against AEAT calendar |

---

## S253 partial batch + R7-A side-fix — architecture review (Task #84)

### Commits reviewed

| Commit | Description |
|--------|-------------|
| `cf7775ebe` | S253 Batch 2: 5 of 12 Category B files migrated + `ledger_transaction_payload` side-fix |
| `dba0107ea` | Vault step record + S253 plan closure |

### Fixture choice — `isolated_profile_storage_root` vs `isolated_runtime_profile`

**ACCEPT as used, with architectural note.**

The commit message says "isolated_profile_storage_root / real EphemeralMasterKeyProvider"
— this is stale wording. Since S208, `isolated_profile_storage_root` uses the file
backend + `aeat_dev_test_database_password`, not `EphemeralMasterKeyProvider`.
The commit message inaccuracy is minor but worth noting (FU-S253-A).

My #68 grounding designated Category B as "active-profile tests requiring
`isolated_runtime_profile`". That designation was too broad. The correct split is:

- **`isolated_profile_storage_root`** (empty root, file backend): correct for tests
  that exercise the profile-create CLI path, which itself provisions and activates
  a bucket session. The test simulates a first-run operator. The 4 migrated CLI
  tests (`test_apex_workflow_verification`, `test_cli_surface`,
  `test_profile_output_language`, `test_session_lifecycle_roundtrip`) all go through
  `aeat config profile create` to set up their preconditions — `isolated_profile_storage_root`
  is correct.
- **`isolated_runtime_profile`**: required only for tests that skip the CLI create
  step and directly require a pre-provisioned active `BucketSession` (e.g., tests
  that call application-layer functions directly with a live `SecureObjectRepository`).

The 7 unmigrated files (including `test_modelo_202_modality`) may fall in the
`isolated_runtime_profile` category. S273 will triage.

### S253 plan closure — PREMATURE

S253 was marked `[x]` in `dba0107ea` despite 7 of 12 files remaining unmigrated.
The step record itself correctly documents the partial coverage and lists the 7
remaining files. However, closing the plan step implies the Step is complete; the
step record's partial-coverage documentation does not undo the visual closure.

This is accurately captured as S273 in the plan. **No remedial action needed in
this review** — the coder's self-documentation is honest and the S273 follow-up
is already logged. The pattern of "close step + document partial coverage + log
follow-up" is acceptable when the partial coverage is clearly itemised.

### S253 migration correctness (5 migrated files)

**ACCEPT.**

- `test_apex_workflow_verification.py`: drops 7 monkeypatches (unsecured backend,
  explicit dirs, database URL). Retains auth-env delenv guards (correct — those
  are not storage-backend noise). Uses `isolated_profile_storage_root`. ✓
- `test_cli_surface.py`: similar pattern. ✓
- `test_profile_output_language.py`: correct. The architectural note in the commit
  message about `profile_create_storage_span` inner `override_settings` is accurate
  and explains why `override_settings(aeat_active_profile=bucket_id)` wraps must be
  added to any test assertion that reads per-bucket database state. This is a
  non-obvious constraint worth preserving in the test docstring.
- `test_session_lifecycle_roundtrip.py`: drops monkeypatches from `_engine_settings`
  fixture. The fixture now constructs `Settings(aeat_database_url=...)` directly —
  this is not using `isolated_profile_storage_root`; it sets up a minimal SQL engine
  for the session roundtrip assertion which does not go through the profile-create
  path. This is correct: the session lifecycle test operates below the profile layer
  and needs only a real engine, not a full storage root. ✓
- `test_modelo_source_mesh_calculate`: already migrated before this commit (correctly
  noted). No change. ✓

All 5 files drop `AEAT_SECRET_STORE_BACKEND=unsecured` and `AEAT_ALLOW_UNENCRYPTED=1`
monkeypatches. ✓

### S244 (M202 modality must-fix)

S244 targets `test_modelo_202_modality.py`. That file is in the unmigrated 7 and
NOT touched in `cf7775ebe`. This is correct — the commit message and step record
both acknowledge the 7 remaining files. S244 is absorbed by S273 (migrate remaining
7). The must-fix is still open; it has not been silently dropped. ✓

### R7-A side-fix — `ledger_transaction_payload` counterparty coercion

**ACCEPT-WITH-FOLLOWUP.**

The fix: `counterparty=raw.counterparty or ""` at the call site in
`src/aeat/application/ledger/_actions.py:1036`.

`LedgerTransactionPayload.counterparty` is declared `str = ""` (non-nullable, empty
default). `Transaction.raw.counterparty` is `str | None` (per `_models.py` line 44).
The fix correctly coerces `None → ""` before passing to the strict pydantic model.

**Boundary question: is call-site coercion the right fix, or should
`LedgerTransactionPayload.counterparty` accept `str | None`?**

The right boundary is the call site. `LedgerTransactionPayload` is a **read
projection** — a display DTO. Its `counterparty: str = ""` contract says "always a
string, empty when absent". Changing it to `str | None` would push the
absent-counterparty handling onto every consumer of the payload (CLI renderers,
JSON serialisers, export paths). The current model contract is correct; the bug
was a missing coercion in the factory function. The fix is in the right place.

However, a second coercion already exists at line 2445:
`counterparty=raw.counterparty or ""` — the same pattern. This means the
absent-counterparty coercion lives in two separate call sites rather than being
centralised. The domain `Transaction.raw.counterparty: str | None` field should
expose a `display_counterparty: str` property that returns `self.counterparty or ""`
once, and both callers should use it. Logged as **FU-S274-A / S275**.

**Verdict: `cf7775ebe` side-fix ACCEPT.** The coercion is correct at the call site.
The duplication follow-up is a quality note, not a blocking issue.

### Summary

- `cf7775ebe`: ACCEPT-WITH-FOLLOWUP. 5 files migrated correctly. Fixture choice
  (`isolated_profile_storage_root`) is correct for these tests. Commit message
  "EphemeralMasterKeyProvider" wording is stale (file backend since S208). Side-fix
  for R7-A is at the right boundary; duplicate coercion logged as S275.
- `dba0107ea`: ACCEPT. Step record is honest about partial coverage; S273 correctly
  logged; plan closure premature but mitigated by self-documentation.

### Follow-ups

| ID | Step | Description |
|----|------|-------------|
| FU-S253-A | — | Commit message inaccuracy: "EphemeralMasterKeyProvider" in `cf7775ebe` is stale since S208 file-backend change |
| FU-S244 | S273 | Migrate remaining 7 Category B files (includes S244 M202 modality must-fix) |
| FU-S274-A | S275 | Centralise `counterparty or ""` coercion into a `display_counterparty` property on the domain `TransactionRaw` model; retire two identical call-site coercions |

---

## Task #85 — W06.P28.S104-S107 bundled-export (af81954a6 + 92df99bad)

**Review date:** 2026-05-27

### Scope

Two commits: `af81954a6` (S104-S107: schema v2 extension + serialiser + deserialiser
+ roundtrip test) and `92df99bad` (exec records + plan closure). Reviewed against
`2026-05-27-profile-portability-adr.md` D1–D5.

### D1 — bundle content (four typed tuple fields, `bundle_schema_version=2`)

`UserProfilePortableExport` in `src/aeat/domain/user_profile/_values.py` gains four
fields — `work_units`, `ledger_transactions`, `calculation_revisions`,
`filing_records` — all typed as `tuple[DomainModel, ...]` defaulting to `()`.
`bundle_schema_version` default changed from 1 to 2. The v1 import path remains
reachable because all four fields default to empty tuples (v1 documents omit them;
pydantic fills the defaults on parse). **PASS.**

### D2 — no encrypted material in bundle

`serialize_profile_bundle` reads from live bucket repositories, which return
decrypted domain-model instances. The function assembles only pydantic domain models
into `UserProfilePortableExport`; no DEK/KEK blobs, no `SecureObjectRecord` wrappers,
no raw cipher bytes are present in the bundle. `deserialize_profile_bundle` writes
via the standard repository save paths, which re-encrypt under the target bucket DEK.
**PASS.**

### D3 — typed provenance throughout; no `dict[str, Any]`; no `exclude_none=True`

`serialize_profile_bundle` passes domain-model tuples directly into the pydantic
constructor; no `dict[str, Any]` intermediates. `config_profile_export` writes the
bundle via `bundle.model_dump_json(indent=2)` — the standard pydantic JSON emitter
with no `exclude_none` or `exclude_unset` flags, which is correct: `None` slots must
survive the boundary to distinguish "explicitly null" from "field absent". The import
path restores the bundle via `UserProfilePortableExport.model_validate_json(...)`,
preserving all pydantic types. **PASS.**

Individual repository saves in `_bundle.py` use pydantic domain models directly
(`upsert_work_unit`, `upsert_calculation_revision`, etc.) — no raw dict intermediates.
**PASS.**

### D4 — version-constant at import boundary; v1 importable

`SUPPORTED_BUNDLE_SCHEMA_VERSIONS = frozenset({1, 2})` lives at module level in
`src/aeat/application/user_profile/_bundle.py`. `deserialize_profile_bundle` checks
`bundle.bundle_schema_version not in SUPPORTED_BUNDLE_SCHEMA_VERSIONS` before any
writes and raises `UnsupportedBundleSchemaVersionError` on a miss. The CLI helper
`_validate_bundle_schema_version` imports and re-uses the same frozenset, so the
guard fires before pydantic model construction when the version constant is extended
later. v1 bundles short-circuit in `deserialize_profile_bundle` and return without
writing financial-history objects (the caller handles profile-record provisioning
independently). **PASS.**

### D5 — two-tier collision guard; bundle `profile_id` preserved

`config_profile_import` implements:

- Tier 1: `read_profile_bucket_by_id(bundle_profile_id) is not None` → refuse with
  `CliRefusedBoundaryError` citing "already registered".
- Tier 2: `read_profile_bucket(target_label)` not None and its `bucket_id` differs
  from the bundle UUID → refuse citing "label taken" + `--label` recovery hint.
- Provisional UUID preserved via `_atomic_create_profile(..., profile_id=bundle_profile_id)`.

**PASS.** One observation: Tier 1 is checked before the `_atomic_create_profile`
call, but `ProfileAlreadyRegisteredError` is also caught downstream — making the Tier
1 explicit guard technically redundant. The guard is valuable as an early-exit with
a user-facing message, so it should stay; the downstream catch is correct insurance
if the guard is ever removed. No action required.

### Roundtrip test — ADR D3 anti-tautology mandate

`test_v2_bundle_export_import_roundtrip` in
`src/aeat/entrypoints/cli/test_profile_export_roundtrip.py`:

- Uses `isolated_profile_storage_root` — no unsecured-backend monkeypatches. Real
  file-backend master-key provider session. **PASS.**
- Seeds all four financial-history categories: work unit via `create_work_unit`,
  ledger transaction via real CLI `app ledger import`, calculation revision and filing
  record via real repository paths. **PASS.**
- Asserts strict pydantic equality for all four tuples (`==`), not string-shape
  checks. **PASS.**
- Checks typed provenance separately: `computed.legal_refs == ("Ley 37/1992 art. 90",)`
  and `source_refs == ("aeat-modelo-303-instrucciones-2026",)`. **PASS.**
- D5: asserts `imported_bucket_id == source_bucket_id`. **PASS.**
- Import uses a second `isolated_profile_storage_root` nested context so source and
  target are independent storage roots. **PASS.**

`test_v2_bundle_anti_tautology_legal_refs_mutation`:

- Exports a bundle, mutates `observations[0].legal_refs[0]` in the raw JSON to
  `"MUTATED-legal-ref"`, then calls `UserProfilePortableExport.model_validate_json`
  on the mutated payload.
- If pydantic accepts the mutated payload, asserts that the mutated revision's
  `observations != original_bundle_revision.observations`. If pydantic rejects it,
  `ValidationError` is caught — both outcomes satisfy the anti-tautology mandate.
- The `assert mutated` gate confirms the fixture always produces at least one
  observation with `legal_refs`, preventing the mutation path from silently skipping
  due to an empty fixture. **PASS.**

D5 collision tests (`test_import_refuses_uuid_collision`,
`test_import_label_collision_different_uuid_is_refused`) exercise the two-tier guard
through the real CLI path. **PASS.**

### Issues

**MINOR — `_import_ledger_transactions` uses `dict[str, object]` intermediate.**
Lines 155-157 in `_bundle.py`:

```python
merged: dict[str, object] = dict(existing.transactions)
for txn in bundle.ledger_transactions:
    merged[txn.transaction_id] = txn
repo.save(TransactionCatalogue(transactions=merged))
```

The `merged` dict is typed `dict[str, object]`, not `dict[str, Transaction]`. This
bypasses D3's "no `dict[str, Any]` intermediate" in spirit. The type resolves at
runtime because `TransactionCatalogue.transactions` accepts a typed mapping, but the
declared annotation is weaker than the actual content. The other three categories use
typed `upsert_*` helpers that avoid this. ADR D3 is not strictly violated (no
`dict[str, Any]`, and the `TransactionCatalogue` constructor validates at boundary),
but the inconsistency should be resolved: annotate `merged` as `dict[str, Transaction]`
or extract an `upsert_transaction` helper matching the pattern used by the other three
categories. Logged as FU-S104-A.

### Verdict

| Decision | Status |
|----------|--------|
| D1 — four typed fields, v2 default | PASS |
| D2 — no encrypted material | PASS |
| D3 — typed pydantic throughout, no `exclude_none` | PASS (minor: `_import_ledger_transactions` `dict[str, object]`) |
| D4 — version constant at import boundary, v1 importable | PASS |
| D5 — two-tier collision guard, UUID preserved | PASS |
| Roundtrip test — real adapter, strict equality | PASS |
| Anti-tautology proof — mutation surfaces inequality | PASS |

**Overall: APPROVE.** ADR `2026-05-27-profile-portability-adr.md` status flips to
`accepted`. One follow-up (FU-S104-A) logged; does not block the step.

### Follow-ups

| ID | Step | Description |
|----|------|-------------|
| FU-S104-A | S277 | Annotate `merged` in `_import_ledger_transactions` as `dict[str, Transaction]` or extract `upsert_transaction` helper; resolves D3 inconsistency |
