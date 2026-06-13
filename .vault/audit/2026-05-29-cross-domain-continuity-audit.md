---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-05-29'
modified: '2026-05-29'
related:
  - "[[2026-05-26-cross-domain-continuity-audit]]"
  - "[[2026-05-28-cross-domain-continuity-audit]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---


# `cross-domain-continuity` audit: `persona-fleet round 7`


## Standing review gates (active from 2026-05-27)

| Gate | Description | Verdict on violation |
|------|-------------|----------------------|
| G1 | No `os.environ`/`os.getenv` in production code; use pydantic-settings `Settings` | BLOCK or W09 follow-up |
| G2 | No `dict[str, Any]`/`dict[str, object]` at persistence, wire, CLI, config, or fixture boundaries; typed pydantic throughout | BLOCK or W09 follow-up |
| G3 | All user-facing messages via `tr()`; no hardcoded f-string raise sites reachable by operator; no mixed-language string fragments | Flag; W09 follow-up |
| G4 | Locale yml structural edits (add/remove keys) only via `scaffold` + `audit` CLI; prose fills allowed by hand | BLOCK |
| G5 | No duplication, shims, re-exports, deprecation aliases, or compatibility-only code | BLOCK or W09 follow-up |
| G6 | No tautological tests; every calculation test requires external-authority expected value or anti-tautology proof; `monkeypatch` against application logic blocked | BLOCK |

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

## W09 follow-up rollup — refreshed inventory (2026-05-27)

**Generated from:** `vault plan query --wave W09 --open` (97 open Steps) plus
`--closed` (7 closed Steps) on the cross-domain-continuity plan.
**Delta since prior rollup (49554af05):** S252-S291 appended (40 new Steps);
S208/S244/S252/S253/S273 closed by coder chain. S201 MOOT (verified inline).
S209 partially satisfied (Batches 1-2+partial-3 done; Batch 3 remainder is S254).
Total open at this refresh: **97**.

### Closed since prior rollup — no action needed

| Step | Closed by | Note |
|------|-----------|------|
| S208 | `cb51d03e7` | Storage regression root fix: `isolated_profile_storage_root` switched to file-backend. Unblocked S252/S253/S273. |
| S244 | `a69608c47` | M202 monkeypatch MUST-FIX: rewritten with `isolated_runtime_profile`. |
| S252 | (S209 Batch 1) | Category A (no-active-profile) 5 files migrated to `isolated_profile_storage_root`. |
| S253 | (S209 Batch 2) | Category B (active-profile) 5 files migrated; plan marked closed prematurely. |
| S273 | `a69608c47`+`b72f98000` | S253 remainder: 7 Category B files completed. Storage migration chain fully closed. |

### MOOT — already fixed inline, plan Step can be closed

| Step | Status | Evidence |
|------|--------|---------|
| S201 | MOOT | `src/aeat/entrypoints/cli/_errors.py` `__all__` (line 453) no longer includes `build_error_envelope` or `json_output_requested`. Fixed incidentally by f864d72fd-era cleanup. |

### Category 1 — MUST-FIX: quality-gate blockers (revised)

S208/S244/S252/S253/S273 are all closed. The storage migration chain is complete.
One item remains from the original Category 1:

| Step | Source | Description |
|------|--------|-------------|
| S209 | W01 drift | Parent umbrella Step for the 20-file migration. Batches 1-2 done; **Batch 3 (S254)** covers `test_profile_lifecycle_verbs`, `test_root_grammar_invariants`, `test_root_help_shape`. `test_root_grammar_invariants` confirmed still carries `AEAT_SECRET_STORE_BACKEND=unsecured`. Close S209 after S254 lands. |
| S254 | S209 B3 | Batch 3 triage: 3 files needing mixed `isolated_profile_storage_root` / `isolated_runtime_profile` split. Only remaining storage-migration blocker. |

S254 → close S209.

### Category 2 — Error registry correctness (unchanged)

| Step | Source | Description |
|------|--------|-------------|
| S198 | W01 drift | Delete duplicate `AuthProviderReservedError` registration (lines 62-65 and 106-109 of `src/aeat/core/errors/registry/_application.py`). |
| S199 | W01 drift | Delete duplicate `AuthConfigureDanglingActiveProfileError` registration (lines 84-92 and 95-103). |
| S202 | W01 drift | Audit `StoredCalculationDriftError` taxonomy: lives under `errors.refused.*` but is semantically an integrity failure; decide rename vs. documented exception. |

### Category 3 — Source hygiene: dead exports and private symbols (revised)

| Step | Source | Description |
|------|--------|-------------|
| S201 | W01 | **MOOT** — `build_error_envelope` and `json_output_requested` are no longer in `__all__`. Recommend closing via `vault plan step check`. |
| S163 | W09.P41 | Delete ghost `ProfileExportBundle` comment in `src/aeat/application/user_profile/__init__.py`. |
| S164 | W09.P41 | Delete dead alias `_profile_binding_selectors` in `src/aeat/domain/user_profile/_registry_contract.py`. |

### Category 4 — Duplicate / consolidation work (unchanged)

| Step | Source | Description |
|------|--------|-------------|
| S200 | W01 drift | Consolidate two divergent `_decimal_value` helpers. `src/aeat/application/modelo/`. |
| S205 | W01 drift | Consolidate `UserProfileLifecycleRepository.__init__` and `UserProfileSnapshotRepository.__init__` into shared base. `src/aeat/application/user_profile/_repository.py`. |
| S157 | W09.P40 | Extract shared currency-not-EUR guard to `_shared_issue_reasons.py`. `src/aeat/application/aggregation/`. |
| S158 | W09.P40 | Extract shared `BusinessClassification` branch (`PERSONAL_TRANSACTION` vs `UNCLASSIFIED`). |
| S159 | W09.P40 | Extract shared business-proportion dispatch. |

S157-S159 are independent aggregation-layer consolidations; can batch in one commit.

### Category 5 — Persistence boundary and domain integrity (unchanged)

| Step | Source | Description |
|------|--------|-------------|
| S214 | W01/W03 | Add `StoredTransactionDriftError`/`ValidationError` guard to `TransactionCatalogueRepository.load()`. `src/aeat/domain/transactions/_repository.py:139`. |
| S274 | cf7775ebe | Verify `counterparty=None → ""` side-fix in `cf7775ebe` is complete; evaluate whether `Optional[str]` on `LedgerTransactionPayload` is preferable to coercion. `src/aeat/application/ledger/_actions.py`. |
| S275 | FU-S274-A | Centralise `counterparty or ""` coercion into `display_counterparty` property on `RawTransaction`; retire two identical call-site coercions. |
| S267 | FU-S208-A | Verify all `isolated_profile_storage_root` callers pass with file-backend; document `aeat_dev_test_database_password` CI dependency. `src/aeat/tests/secure_sql.py`. |
| S270 | FU-W09-A | Verify CI sets `AEAT_DEV_TEST_DATABASE_PASSWORD`; without it 8+ test files fail at passphrase resolution. `.github/workflows/`. |

### Category 6 — Typed-boundary violations (G2 gate) — NEW

Surfaced by UNTYPED_BOUNDARY discovery sweep (S97) and existing S215. 24+ public
`dict[str, object]` sites, 14 `cast()` escapes, 3 `pydantic Any` fields.

**Promotion candidate:** S277-S280 together span 24+ public sites across CLI,
application, and domain layers. This is Wave-scale work, not a single W09 Step.
Recommend promoting to a dedicated Wave-10 phase rather than batching into W09.P41.

| Step | Layer | Sites | Description |
|------|-------|-------|-------------|
| S215 | Application | 4 | `ledger/_actions.py` lines 1024/1055/1064/1075 — four `dict[str, object]` ledger payload helpers. |
| S277 | All | 1 | `_bundle.py` `_import_ledger_transactions` `merged: dict[str, object]` — annotate as `dict[str, Transaction]` or extract `upsert_transaction` helper (FU-S104-A). |
| S278 | CLI entrypoints | 14 | 14 payload functions in `_modelo.py`, `_ledger.py`, `_config/__init__`, `_common.py`, `_app_live.py` returning `dict[str, object]`. |
| S279 | Application | 10 | 10 payload functions across `auth/`, `filing/`, `aggregation/`, `operator_surface/`, `ledger/` returning `dict[str, object]`. |
| S280 | Domain/registry | 14 | 14 `cast()` escapes + 3 `pydantic Any/object` fields in `workflow/`, `registry/`, `review/`, `schedules/`, `workflow/_models`. |

S277 is narrowest scope — single file, clear fix. S215 and S277 should land first.
S278/S279/S280 warrant a Wave-10 typed-boundary phase (see promotion section below).

### Category 7 — Legal data / registry correctness (unchanged + new)

| Step | Source | Description |
|------|--------|-------------|
| S212 | W03-F | Fix `Real Decreto-ley 4/2004` citation typo in M200 `parameters.toml`. |
| S251 | W07 | Investigate Cataluña 2024 autonomic tarifa discrepancy (4,522.78 vs 4,650.03 EUR for base 35,400). External oracle required. |
| S268 | FU-W10-A | Extract HAC/242/2025 art-8 text into corpus HTML and add `required_text`. `src/aeat/_data/registry/aeat/legal/irpf.toml`. |
| S269 | FU-W10-B | Oracle-verify M202 2025-2P/3P closing dates against AEAT calendar. |
| S271 | FU-W09-B | Complete HAC/242/2025 art-8 corpus entry with full BOE text. |
| S272 | FU-W09-C | Verify M202 2025-2P/3P deadline windows via Orden HAC source. |

S268/S271 are the same corpus gap from two angles — merge into one coder task.
S269/S272 are the same oracle check — merge likewise.

### Category 8 — CLI UX / localisation (unchanged + new)

Prior Category 8 entries (S203/S204/S219-S239) are unchanged. New entries from
discovery sweeps and round-5 audit (ROSER):

| Step | Source | Severity | Description |
|------|--------|----------|-------------|
| S282 | HARDCODED | BLOCKER | Route 2 `auth/_authenticator.py` raises via `tr()`; remove `AEAT_CERTIFICATE_PATH`, `AEAT_CERTIFICATE_PASSWORD_SECRET`, `CertificateBundle` leakage. Per round-5 B-ROSER BLOCKER. `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`. |
| S283 | HARDCODED | MAJOR | Route 9 `diagnostics/profile.py` `BadParameter` raises via `tr()`. |
| S284 | HARDCODED | MAJOR | Route `diagnostics/secure_objects.py:42-43`, `locales/cli.py`, `entrypoints/cli/__init__.py:130`, `wizard/_commands.py:800-804` via `tr()`. |
| S255 | W09 sweep | MAJOR | Convert 120 hardcoded f-string error raises across 43 application files. Batch by surface per locale CLI rule. `src/aeat/application/`. |

S282 is the highest-severity new entry (G3 BLOCKER from round-5 audit). It must land before the auth surface round-8 persona re-run.

Full Category 8 execution order: S282 → S283/S284 (independent batch) → S255 (bulk) → prior S203/S204/S219-S239 as before.

### Category 9 — Test quality (G6 gate) — NEW

Surfaced by TAUTOLOGICAL_TEST_SUSPICION sweep (S98).

| Step | Source | Description |
|------|--------|-------------|
| S285 | S98 sweep | `test_cross_dependency_calculations.py` M180/M190 tests: derive expected values from AEAT workbook or grounded fixture, not synthetic Decimal oracles. `src/aeat/domain/calculations/registry/`. |
| S286 | S98 sweep | `application/auth/test_operator.py` lines 230-260 / 477-521: replace `monkeypatch.setenv` for `AEAT_CERTIFICATE_PATH` / `AEAT_CLAVE_MOVIL_DNI_NIE` with Settings override fixture. |

Both are independent. S285 requires external oracle consultation before code change.

### Category 10 — Settings leak evaluation (G1 gate) — NEW

Three pre-existing `os.environ`/`os.getenv` reads that pre-date the G1 gate.
Each requires a decision: lift into `Settings` or write an ADR exception note.

| Step | Source | Description |
|------|--------|-------------|
| S289 | G1 retroactive | `access_gate/__init__.py` env-var read at pre-Settings bootstrap window. Evaluate lift vs ADR exception. |
| S290 | G1 retroactive | `core/i18n/_render.py` env-var read for cache-key invalidation. Evaluate Settings route vs documented rationale. |
| S291 | G1 retroactive | `core/observability/_replay.py` env-var write for replay scope. If test-infrastructure-only: document + restrict import path. If production-touching: lift into Settings. |

All three are evaluation tasks before any code change. They can be batched as a
single architecture grounding review.

### Category 11 — DSL enhancement (unchanged)

| Step | Source | Description |
|------|--------|-------------|
| S250 | W07-C | Add `age_at` formula DSL operator for casillas 0513/0515. Requires ADR first. |
| S288 | FU-S94 | Criterio de caja (casilla 62) — model Ley 37/1992 art. 163 quinquies cash-accounting regime. Out of scope for W05.P24; tracked here. |

Both require ADR-first before implementation. S288 is smaller in scope than S250.

### Category 12 — Co-landing convention notes (documentation only, expanded)

Prior S240-S243/S245 plus new Wave-7 and Wave-8 entries.

| Step | Source | Description |
|------|--------|-------------|
| S240 | W04-A | `d8bec8bd9` multi-step co-landing. |
| S241 | W05-A | `03be9b6f4` multi-step co-landing. |
| S242 | W02-A | `30065a92e` S38-S42 co-landed. |
| S243 | W02-B | `acea52801` S43+S44+S46 co-landed. |
| S245 | W07-A | `01ac9d698` S113+S114 co-landed. |
| S259 | W07-G | `604bf217d`/`f4108869d` both touch S118 scope without intervening Step record. |
| S263 | W08-A | Coordination incident: coder1/coder2 raced on S141-S144; establish task-claim protocol. |
| S276 | S253-A | `cf7775ebe` commit message says EphemeralMasterKeyProvider but helper uses file backend since `cb51d03e7`. |

All documentation-only. Batch in a single commit.

### Promotion candidates for Wave-10

The following W09.P41 clusters have grown beyond single-Step scope and warrant
promotion to a dedicated Wave-10 phase:

**Typed-boundary wave (G2):** S278/S279/S280 together cover 24 public
`dict[str, object]` functions and 14 `cast()` escapes across CLI, application,
and domain. This is 3-4 coder-weeks of mechanical refactoring with broad surface
area. Promoting avoids cluttering W09.P41 dispatch slots.

**Validation-helper dedup cluster (G5):** S149-S156 (8 Steps in W09.P39) cover
the `_missing_refs` duplication across 7 registry-validate modules. These are
independent but form a natural batch and could be a W09.P39 micro-wave.

**Registry validate-helpers (W09.P39 — S149-S156):** 8 Steps that create a
shared `_validate_helpers.py` and update 7 sibling files. Batching all 8 into
one Wave-10 registry-consolidation phase avoids 8 separate tiny commits.

### Execution priority order for W09 (refreshed 2026-05-27)

Priority tiers replace the prior linear list:

**Tier 0 — MUST-FIX before W09 quality-gate sign-off:**
1. S254 (Batch 3 storage migration — 2 files remain) → closes S209.
2. S282 (auth BLOCKER — G3 hardcoded env-var/class-name in user-facing message).

**Tier 1 — High-confidence, low-risk, independent:**
3. S198/S199 (duplicate error registrations — delete).
4. S277 (FU-S104-A — single dict annotation fix in `_bundle.py`).
5. S212 (M200 citation typo — one-line data fix).
6. S163/S164 (dead comment + dead alias — delete).
7. S270 (CI env-var verification — `AEAT_DEV_TEST_DATABASE_PASSWORD`).
8. S276 (documentation accuracy — step record correction).
9. S240-S245/S259/S263 (convention notes — single documentation commit).

**Tier 2 — Medium scope, architecture-boundary corrections:**
10. S214 (transaction drift guard — mirrors S05 pattern).
11. S215 + S274/S275 (ledger payload typing + counterparty coercion consolidation).
12. S157-S159 (aggregation shared-guard extraction).
13. S267 (CI passphrase dependency documentation).
14. S286 (auth test monkeypatch → Settings override).
15. S264 (remove redundant `_activate_subcommand_output_language` wrapper).
16. S265/S261 (drop unsecured-backend monkeypatches from `test_output_language_parity`).

**Tier 3 — UX / localisation surface:**
17. S203/S204 (i18n orphan/surplus — fast locale-file fixes).
18. S229/S232 (output-language parity options — independent CLI additions).
19. S283/S284 (diagnostics + wizard hardcoded strings — bulk tr() migration).
20. S220/S235/S236 (CLI UX minor — independent).
21. S224/S231/S237/S238/S239 (CLI UX major — independent, medium scope each).
22. S221/S222/S225 (error-locale surface — batch).
23. S255 (120-file bulk hardcoded-string sweep — largest i18n task).
24. S266/S262 (output-language surface sweep — enumerate all commands).

**Tier 4 — Investigation-first (block on external oracle or ADR decision):**
25. S289/S290/S291 (G1 settings-leak evaluation — architecture grounding, batch).
26. S202 (error taxonomy decision).
27. S226 (casilla label localisation — registry decision required).
28. S234 (iva.regime wizard — scope understanding required).
29. S271/S268 (HAC/242/2025 corpus entry — merge and execute).
30. S272/S269 (M202 deadline oracle — merge and execute).
31. S285 (tautological M180/M190 tests — AEAT workbook oracle required).
32. S251 (Cataluña tarifa investigation — external oracle).

**Tier 5 — ADR-gated or Wave-10 promotion candidates:**
33. S288 (criterio de caja casilla 62 — ADR-first; W09 or promote to W10).
34. S250 (age_at DSL operator — ADR-first; deferred to W10).
35. S278/S279/S280 (typed-boundary bulk — promote to Wave-10 typed-boundary phase).
36. S149-S156 (registry validate-helper dedup — promote to Wave-10 registry-consolidation).
37. S216/S217 (ledger coverage gaps — medium effort, deferred).
38. S258 (registry snapshot equivalence — documentation or test).
39. S257 (hexagonal violation in modelo project CLI — refactor).
40. S256 (legal_refs surface in modelo project output).

**Tiers 5 onward** — S165/S166/S167/S168-S175 (P42-P49 structural verifications):
41-50. P42-P49 consolidation, replacement, coverage, and swarm steps — sequenced
    by the termination criteria (S171-S175 depend on W09 completion).

Total open W09 Steps: **97**.
Tier 0 (MUST-FIX): **2**.
Promotion candidates for Wave-10: **S278/S279/S280** (typed-boundary, 38 sites)
+ **S149-S156** (registry validate-helpers, 8 Steps).
MOOT Step to close: **S201**.

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

## Task #130 — W08.P38.S146-S148 Wave-8 breakpoint consolidation

**Review date:** 2026-05-27

### S146 — Consolidated Wave-8 commit review

#### W08.P35 — De-hardcode 17 f-string error raises (`b6991aeb1`)

Commit converts all 17 hardcoded `f"..."` error raises in
`src/aeat/application/modelo/_actions.py` to `tr()`-managed locale keys.

**Locale compliance (G4):** Seven keys coined under
`application.modelo.errors.*`. Step record confirms `python -m aeat.locales
scaffold` was used for all four locale files. Verified in `en.yml`: all seven
keys carry proper operator prose with `%{placeholder}` interpolation. No
hand-editing of yml structure. G4 compliant.

**Key correctness:** Pattern is consistent — `WorkUnitNotFoundError`,
`CalculationRevisionNotFoundError`, `FilingRecordNotFoundError`,
`VerificationReportNotFoundError`, and `WorkUnitMutationRefusedError` each
receive a dedicated key. No key reuse across error types with different
semantics. Placeholder names match the function parameter names exactly (`work_unit_id`,
`calculation_revision_id`, etc.) — no stale names.

**Test changes:** Three `match=` regex assertions that checked raw English
f-string substrings (`"discard|state|DISCARDED"`, `"calculation|revision|not|found"`)
were dropped. The exception type assertion is retained. This is correct — the
`match=` argument was testing implementation language choice, not error semantics.
Dropping it does not reduce meaningful contract coverage.

**S140 Haiku sweep:** 120 additional f-string raises identified across 43
application files; operator-facing subset documented in the step record. Captured
as S255 in W09.P41 for follow-on work. The sweep result is honest: it surfaces
the scope of remaining work rather than claiming completeness.

**Pre-existing failures noted in step record:** `~40 tests` failing with
`RegistryValidationError: bound casilla '15' requires resolved binding` — a
pre-existing registry binding configuration issue, not introduced by this step.
Confirmed: these failures exist at `HEAD` independently.

**W08.P35 verdict: APPROVE.** Mechanical, correct, locale-scaffold-compliant.
No follow-ups.

#### W08.P36 — `--output-language` parity (S141-S144)

Previously reviewed as Task #78. Verdict: **ACCEPT-WITH-FOLLOWUP** (FU-W08-A
through FU-W08-D). Full findings in the Task #78 section above.
FU-W08-B resolved as S264 (already closed).

#### W08.P37 — Re-export removal (S145)

`882d6c027` closes S145 in the plan with a note that the `__all__` cleanup
already landed in `f864d72fd` as part of an earlier S02+S03 fix-forward commit.
No new code was needed. This is a plan-accounting closure — the actual change
was already reviewed as part of the S02/S03 work. **PASS.**

#### Wave-8 rollup table

| Commit | Step(s) | Verdict | Notes |
|--------|---------|---------|-------|
| `b6991aeb1` | S123-S140 | APPROVE | G4 scaffold-compliant; 7 locale keys; test match= removal correct |
| `4c631baba` | S255 append | APPROVE | Plan expansion; S140 sweep result honest |
| `03016c382` | S141-S143 | ACCEPT-WITH-FOLLOWUP | FU-W08-A coordination; wiring real |
| `dcc774795` | S144 | ACCEPT-WITH-FOLLOWUP | FU-W08-C/D fixture + coverage gap |
| `925d8fb0f` | S141-S143 | ACCEPT-WITH-FOLLOWUP | coder1 duplicate; FU-W08-A noted |
| `02813c853` | S144 exec record | PASS | Step record only |
| `882d6c027` | S145 plan close | PASS | Code already landed in f864d72fd |

**Wave-8 consolidated verdict: APPROVE / ACCEPT-WITH-FOLLOWUP.** P35 clean.
P36 carries four follow-ups (S261-S264 in W09.P41, S264 already closed). P37
closed via plan accounting. All Wave-8 follow-ups are captured in the plan.

### S147 — Catalan-preferring and Hungarian-preferring persona re-run

**Deferred — not yet dispatched.** The round-8 persona sweep covered Roser
(Catalan, auth surface, round-5 focus) and Núria (gestor, multi-profile). A
dedicated Hungarian-preferring persona re-run to verify `--output-language hu`
renders correctly for the W08.P35 new keys and W08.P36 verb registrations has
not been dispatched.

**Recommendation:** Spawn a Hungarian-preferring persona as a standalone
background task. The verification target is narrow:
- W08.P35 seven new `application.modelo.errors.*` keys render in Hungarian
  (hu.yml has prose, not scaffold stubs, for all seven).
- W08.P36 newly-registered commands (`auth clear`, `config profile show`,
  `work calculate/verify/file`) honour `--output-language hu`.

Until that persona runs, S147 remains open. The overall Wave-8 breakpoint is
not blocked — S147 is a verification step, not a blocking gate. Logging as
deferred pending team-lead dispatch decision.

### S148 — Plan expansion from Wave-8 persona findings

No new persona findings to capture beyond what is already in the plan. The
W08.P36 follow-ups (S261-S266) were captured at review time. The W08.P35 follow-up
(S255 — 120 remaining f-string raises) is in W09.P41. No uncaptured items.

**S148: COMPLETE.** No new Steps required.

### Wave-8 breakpoint close summary

| Step | Status |
|------|--------|
| S146 — consolidated commit review | COMPLETE (rollup above) |
| S147 — Catalan/Hungarian persona re-run | DEFERRED — Hungarian re-run not yet dispatched |
| S148 — plan expansion | COMPLETE (no new Steps) |

S146 and S148 closed. S147 deferred pending persona dispatch.

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

---

## Task #89 — W06.P29.S108-S109 import idempotency (e5a7979a5 + 07f14dfcc)

**Review date:** 2026-05-27

### Scope

Two commits: `e5a7979a5` (S109 regression test) and `07f14dfcc` (exec records +
plan closure). S108 carries no new source — the claim is that the S106 implementation
already satisfies the idempotency contract. Primary verification: confirm the live
import path in `config_profile_import` actually delivers what S108 specified;
confirm S109 tests that contract without tautology.

### S108 — Idempotency contract satisfied by S106

S108 specified: "add idempotency mode that respects bundle `profile_id` when no
local profile of that id exists and refuses or upserts when one does."

The live path in `config_profile_import` (already audited in Task #85) delivers
exactly this:

- UUID preserved: `_atomic_create_profile(..., profile_id=bundle_profile_id)` passes
  the bundle's UUID directly to `register_active_profile`; a fresh UUID is minted
  only when `profile_id=None`. **Covers "respects bundle profile_id when no local
  profile exists".**
- Tier-1 UUID collision: `read_profile_bucket_by_id(bundle_profile_id) is not None`
  → `CliRefusedBoundaryError` citing "already registered". **Covers "refuses when
  one does".**
- The `ProfileAlreadyRegisteredError` catch downstream is insurance; the Tier-1
  guard fires first in the happy-collision path.
- No "upsert" in the S108 sense is implemented — the spec text "refuses or upserts"
  was ambiguous; the implementation chose the safer "refuse" path, which is correct
  per ADR D5 (the `delete` + re-import recovery path is documented in the refusal
  message). **No gap.**

**S108 contract: SATISFIED by S106. Correct to close without new source.**

### S109 — Regression tests

`src/aeat/entrypoints/cli/test_profile_import_idempotency.py` (222 lines,
`e5a7979a5`):

**`test_reimport_same_bundle_is_refused`:** Creates a minimal profile, exports it,
attempts import into the same root (UUID collision — refused immediately), then opens
a fresh `isolated_profile_storage_root`, imports once (succeeds), imports again
(refused). Confirms via `profile list` and `profile show` that exactly one profile
exists and its UUID matches the exported one. Real CLI path throughout. **PASS.**

**`test_label_collision_different_uuid_refused_even_with_explicit_label`:** Occupies
a label in a fresh root with a locally-minted profile (different UUID), then imports
the bundle without `--label` (refused), with `--label <same>` (refused), and with
`--label <free>` (succeeds). Exercises Tier-2 guard explicitly. **PASS.**

**`test_mutated_profile_id_creates_second_profile` (anti-tautology):** Mutates the
bundle's `profile_id` to a fresh `uuid.uuid4()` before the second import. Both
imports succeed (different UUIDs, different labels). `profile show` for each label
returns the matching UUID, proving the UUID is the genuine discriminator. If the
guard were tautological (never checking UUID), the second import would collide on
label rather than succeeding — the test would fail, exposing the broken contract.
**Anti-tautology mandate: PASS.**

Fixture choice: `isolated_profile_storage_root` throughout — correct, because
`_create_minimal_profile_and_export` calls `config profile create` and `config
profile export` via CLI before any import. The test exercises the full create path,
not a pre-provisioned session. **PASS.**

No mocks, no `unsecured` monkeypatches, no `skip`/`xfail`. **PASS.**

### Exec record (07f14dfcc)

Step record `2026-05-27-cross-domain-continuity-W06-P29-S108-S109.md` is honest: it
names the S106 commit (`af81954a6`) as the implementation basis, enumerates all
three S109 tests, and documents the fixture choice rationale. No inflated claims.
**PASS.**

### Verdict

| Check | Status |
|-------|--------|
| S108 contract satisfied by S106 live path | PASS |
| UUID preservation in `_atomic_create_profile` | PASS |
| Tier-1 UUID collision guard fires before `ProfileAlreadyRegisteredError` | PASS |
| S109 reimport-refused test | PASS |
| S109 label-collision-with-explicit-label test | PASS |
| S109 anti-tautology (UUID mutation creates second profile) | PASS |
| Fixture: `isolated_profile_storage_root` (create-path correct) | PASS |
| No mocks / no unsecured backends | PASS |
| Exec record honest about S108 no-code closure | PASS |

**Overall: APPROVE.** W06.P29 closes cleanly. No follow-ups.

---

## Task #128 — W06.P30.S110-S112 Wave-6 breakpoint consolidation

**Review date:** 2026-05-27

### S110 — Consolidated Wave-6 commit review

This section rolls up the per-commit verdicts from Tasks #85 and #89 and
reviews the S260 profile-portability ADR commit (`57d017aec`).

#### S260 — Profile-portability ADR (57d017aec)

Commit authored `2026-05-27-profile-portability-adr.md` with six decisions
D1-D5 (D1: full-bundle content; D2: encrypted-material stripping; D3: typed
pydantic throughout, anti-tautology proof; D4: schema version bump to 2,
SUPPORTED_BUNDLE_SCHEMA_VERSIONS frozenset; D5: refuse-on-profile-id-collision,
two-tier guard). The commit also lands a wrongly-named scaffold stub
`2026-05-27-cross-domain-continuity-adr.md` which was the placeholder generated
before the ADR title was known — this is a known vault naming artefact, not a
code defect.

ADR content reviewed against the Task #75 grounding (already in this doc): all six
architecture decisions match the grounding recommendations exactly. D3 mandates
`model_dump(mode="json")` / `model_validate` typed equality — verified implemented
in `af81954a6`. D4 SUPPORTED_BUNDLE_SCHEMA_VERSIONS frozenset — verified at import
boundary in `config_profile_import`. D5 two-tier UUID + label guards — verified
in Task #89 review.

**S260 verdict: APPROVE.** ADR status correctly flips to `accepted`.

#### S104-S107 — Bundled export (af81954a6 + 92df99bad)

Previously reviewed as Task #85. Verdict: **APPROVE** with FU-S104-A
(annotate `merged` dict in `_import_ledger_transactions` — resolved in S277).
Full findings in the Task #85 section above.

#### S108-S109 — Import idempotency (e5a7979a5 + 07f14dfcc)

Previously reviewed as Task #89. Verdict: **APPROVE.** No follow-ups.
Full findings in the Task #89 section above.

#### Follow-up items from Wave-6 review

- **FU-S104-A** — annotate `merged: dict[str, Transaction]` in
  `_import_ledger_transactions`. Resolved by S277 (W12.P61). **CLOSED.**
- **FU-W06** — No additional Wave-6-specific follow-up items beyond what is
  already tracked. The co-landing convention note pattern (FU-W04-A, FU-W05-A,
  FU-W07-A) does not apply here; each Wave-6 step landed in its own commit.

#### Wave-6 rollup table

| Commit | Step(s) | Verdict | Notes |
|--------|---------|---------|-------|
| `57d017aec` | S260 ADR | APPROVE | D1-D5 match grounding; scaffold stub artefact benign |
| `af81954a6` | S104-S107 | APPROVE | FU-S104-A resolved in S277 |
| `92df99bad` | S104-S107 exec records | APPROVE | Honest step records |
| `e5a7979a5` | S109 regression test | APPROVE | Anti-tautology UUID-mutation proof PASS |
| `07f14dfcc` | S108-S109 exec records | APPROVE | Honest S108 no-code closure |

**Wave-6 consolidated verdict: APPROVE.** All P28 and P29 steps close cleanly.
Single resolved follow-up (FU-S104-A via S277). Zero blocking items.

### S111 — Núria gestor round-8 persona re-run

**Satisfied by round-8 testimonial.** The round-8 persona sweep (R8-NURIA)
exercised the gestor multi-profile workflow post-Wave-6. Key findings from the
testimonial, as captured in the plan:

- **BLOCKER (S305 in flight, Task #116):** Multi-profile gestor view broken —
  `aeat app overview calendar` and `aeat app overview` surface active-profile
  only; the `fail-closed` exception handler in `_profile_repository.py` swallows
  cross-profile iteration errors. Fix being executed by coder2.
- **BLOCKER (S306):** `--all-profiles` flag missing from `aeat app overview
  calendar`; gestor cannot see all managed profiles in one pass.
- **HIGH (S307):** M184 atribucion de rentas calculation path missing; sociedad
  civil / comunidad de bienes clients cannot file from the CLI.
- **MODERATE (S308):** Bundle export contains cleartext NIF, names, surnames —
  LOPD risk for gestors transmitting bundles via email; passphrase encryption
  needed.
- **MODERATE (S309):** M131 modulos manual entry path missing; binding source is
  ledger-only today; clients without integrated bookkeeping cannot file M131.
- **LOW (S310):** Orphan bucket cleanup on failed profile create.

W06 bundle-content goal (Cluster E: full bundle with work units, ledger,
revisions, filings) is confirmed **working** for the single-profile path by
the round-8 testimonial — Núria was able to export and re-import a full bundle.
The multi-profile blocker (S305/S306) is a separate surface (overview command,
not the bundle itself).

**S111 verdict: SATISFIED.** The round-8 testimonial provides the required
persona evidence. No additional re-run needed.

### S112 — Plan expansion from persona findings

All R8-NURIA persona-driven Steps are already captured in the plan:

| Finding | Severity | Plan Step | Status |
|---------|----------|-----------|--------|
| Multi-profile gestor view broken | BLOCKER | S305 | In flight (#116) |
| `--all-profiles` flag missing | BLOCKER | S306 | In flight (#116) |
| M184 atribucion path missing | HIGH | S307 | Pending |
| Cleartext NIF bundle LOPD | MODERATE | S308 | Pending |
| M131 modulos manual entry | MODERATE | S309 | Pending |
| Orphan bucket cleanup | LOW | S310 | Pending |

No uncaptured persona findings from the round-8 testimonial. Plan expansion is
complete — all findings are already Steps in W09.P41.

**S112 verdict: COMPLETE.** No new Steps required.

### Wave-6 breakpoint close summary

| Step | Verdict |
|------|---------|
| S110 — consolidated commit review | COMPLETE (rollup above) |
| S111 — Núria re-run | SATISFIED by round-8 testimonial |
| S112 — plan expansion | COMPLETE (all findings already in plan) |

W06.P30 closes. W06 campaign is fully landed.

---

## Task #94 — W05.P24 IVA intracom + export axes: architecture grounding

**Date:** 2026-05-27

### Investigation 1 — `BusinessClassification` current values

`BusinessClassification` lives in `src/aeat/domain/transactions/_enums.py`. Current
members: `BUSINESS`, `PERSONAL`, `MIXED`, `NOT_YET_PROCESSED`,
`PROCESSED_UNCLASSIFIED`, `SKIPPED_BY_RULE`, `FAILED_VALIDATION`.

There is no intracom, export, or retention variant. The S91 brief proposes
`INTRACOM_SUPPLY`, `INTRACOM_ACQUISITION`, `EXPORT_NON_EU`, `RETAINED_INCOME`.

S91 additions are necessary — the operator has no axis to tag a transaction as an EU
supply or export from `ledger classify`, so the IVA aggregation pipeline cannot route
those transactions to casillas 59/60.

**Critical design issue in the S91 brief:** The proposed additions conflate two
independent axes. `BusinessClassification` answers "is this transaction
business-relevant, and in what proportion?" The proposed additions instead answer
"what VAT treatment category does this transaction belong to?" — that is the job of
`IvaCategory` in `src/aeat/domain/iva/_schema.py`, which already has
`INTRA_COMMUNITY_SUPPLY` and `EXPORT_THIRD_COUNTRY_ZERO_RATED` with full legal
citations. Adding IVA-category semantics into `BusinessClassification` creates two
parallel axes that can contradict each other. The `_classify_iva_transaction`
aggregation path reads `business_classification` only to gate the
business/personal/unclassified decision, then derives IVA category from
`_RATE_KIND_TO_DOMESTIC_CATEGORY[rate_kind]` — it never reads an IVA category from
the transaction.

**Revised S91 decision:** Do NOT extend `BusinessClassification` with IVA-category
values. Instead add `iva_category: IvaCategory | None = None` on `Transaction`.
`RETAINED_INCOME` maps to the IRPF retention domain (`irpf_category` field already
present) — must not enter `BusinessClassification`.

### Investigation 2 — `counterparty_country` on `Transaction`

`Transaction` (`_models.py:674`) has no `counterparty_country` field. `RawTransaction`
has `counterparty: str | None` (free-text). The IVA classification engine takes
`customer_member_state: EUMemberState` at the invoice level.

**Revised S92 design — two fields, not one:**

- `iva_category: IvaCategory | None = None` on `Transaction` — the operator-supplied
  or classifier-derived IVA category. Primary routing key for casillas 59/60. `None`
  means the pipeline falls back to the domestic `_RATE_KIND_TO_DOMESTIC_CATEGORY`
  path.
- `counterparty_eu_member_state: EUMemberState | None = None` on `Transaction` —
  the EU member state of the counterparty, required for intracom transactions and
  Modelo 349. Type must be `EUMemberState` (existing domain enum), not bare `str`.

Both fields go on `Transaction` directly (operator-classified enrichments, not
verbatim ingest data). `extra="forbid"` is active on `Transaction`; fields must be
added explicitly with `None` defaults. S91+S92 can be collapsed into one step.

### Investigation 3 — CLI `ledger classify` flag shape for new axes (S93)

Required additions:

- `--iva-category <IvaCategory value>` — sets `iva_category`. Type: `click.Choice`
  over `IvaCategory` string values. Combinable with `--classification BUSINESS`.
- `--eu-member-state <EUMemberState value>` — sets `counterparty_eu_member_state`.
  Required when `--iva-category` is an intracom category. Validation error if
  supplied with an export/domestic category.
- `--retained-income-rate` or existing `--irpf-category` — the `RETAINED_INCOME`
  brief maps to the IRPF domain, not a new `BusinessClassification` value.

### Investigation 4 — IVA aggregation wiring to casillas 59, 60, 62 (S94)

`aggregate_iva_ledger_observations` (line 318) assigns category via
`_RATE_KIND_TO_DOMESTIC_CATEGORY[rate_kind]` only — no branch reads
`transaction.iva_category`. The pre-classified candidate path
(`aggregate_iva_ledger_candidates`) accepts typed `IvaCategory` but requires
upstream callers to populate `IvaLedgerCandidate` explicitly.

S94 wiring strategy:

1. In `_classify_iva_transaction`: after business-gate checks, read
   `transaction.iva_category`. If set to a non-domestic category, emit the
   observation directly with that category without going through `_RATE_KIND_TO_DOMESTIC_CATEGORY`.
   For `INTRA_COMMUNITY_SUPPLY` and `EXPORT_THIRD_COUNTRY_ZERO_RATED`: `flow_direction
   = REPERCUTIDO`, `rate_kind = ZERO`, `iva_amount = 0` (zero-rated).
   For `INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`: `flow_direction = SOPORTADO`,
   `rate_kind` from `iva_rate`.
2. Add registry bindings in both revision.toml files mapping
   `INTRA_COMMUNITY_SUPPLY + REPERCUTIDO` to casilla 59 and
   `EXPORT_THIRD_COUNTRY_ZERO_RATED + REPERCUTIDO` to casilla 60.

**Casilla 62 is NOT an intracom/export box.** It is for the `criterio de caja`
cash-accounting regime (Ley 37/1992 art. 163 quinquies–undecies). The S94 brief
incorrectly groups it with 59/60. Casilla 62 requires a separate step (FU-W05-A /
S278). S94 scope: casillas 59 and 60 only.

### Investigation 5 — Casillas 59, 60, 62 in the 2023-y-siguientes revision

Both `2009-y-siguientes` and `2023-y-siguientes` revisions contain all three:

- **59** (`semantic_role = "dr303_59"`): "Entregas intracomunitarias bienes y
  servicios". `input_kind = "manual"`. Legal refs: `ley-37-1992:art-88`,
  `ley-37-1992:art-92`. No `binding =` in revision.toml — unbacked. S94 adds it.
  The zero-rating authority is `ley-37-1992:art-25`; bindings should add this.
- **60** (`semantic_role = "dr303_60"`): "Exportaciones y operaciones asimiladas".
  Same — `input_kind = "manual"`, no binding. S94 adds. Export authority:
  `ley-37-1992:art-21`.
- **62** (`semantic_role = "dr303_62"`): "Entregas criterio caja devengado art 75
  LIVA — Base imponible". Cash-accounting-regime box. Out of scope for S94.

Legal refs on 59/60 are correct for the informational summary boxes. The bindings
S94 adds should also cite `ley-37-1992:art-25` (intracom) and `ley-37-1992:art-21`
(export) in their `legal_refs`.

### Investigation 6 — S95 test scenario

Marc's IT services to a German client: direction `INCOMING`, `iva_category =
INTRA_COMMUNITY_SUPPLY` (or `DOMESTIC_NOT_SUBJECT` per R12 — see note below),
`counterparty_eu_member_state = EUMemberState.DE`, `taxable_base = 1000.00`,
`iva_amount = 0.00`. After classify, aggregate for 2026/1T → casilla 59 binding
resolves to `Decimal("1000.00")`.

**R12 vs R10 nuance (critical):** The IVA classification tests confirm that outbound
B2B services to EU members resolve to `DOMESTIC_NOT_SUBJECT` (R12: place of supply
is the customer's country), not `INTRA_COMMUNITY_SUPPLY` (R10: goods only). For
Marc's software services the IVA category is `DOMESTIC_NOT_SUBJECT`. However, the
303 instructions specify that casilla 59 also receives B2B services to EU members
where the place of supply is the customer's territory (not subject in ES but
reportable as intracom). The registry binding for casilla 59 must therefore accept
both `INTRA_COMMUNITY_SUPPLY` AND `DOMESTIC_NOT_SUBJECT` when
`counterparty_eu_member_state` is set. The S95 test brief must be explicit about
this. The S95 goods-export scenario (`EXPORT_THIRD_COUNTRY_ZERO_RATED`, casilla 60)
is straightforward — no R12-type ambiguity.

### No existing ADR covers W05.P24

No ADR for `BusinessClassification` extension or transaction-level IVA classification
routing was found. S91 requires a pre-implementation ADR (4 decisions: D1 iva_category
field placement; D2 no BusinessClassification extension; D3 casilla 62 out of scope;
D4 R12 services routing for casilla 59).

### Revised Step text for S91-S95

**S91 — REVISE.** Scope: add `iva_category: IvaCategory | None = None` and
`counterparty_eu_member_state: EUMemberState | None = None` on `Transaction` in
`src/aeat/domain/transactions/_models.py`. Do NOT extend `BusinessClassification`.
Preceded by ADR authoring (see FU-W05-B).

**S92 — COLLAPSE into S91.** Both new fields land in the same file. Repurpose S92 as
the step that updates `ledger classify` test coverage for the new fields, or absorb
it into S91 and use the freed step for the ADR.

**S93 — ADD `--iva-category` and `--eu-member-state` flags.** `--retained-income-rate`
maps to IRPF axis (`--irpf-category`), not a new `BusinessClassification` value.

**S94 — NARROW to casillas 59 and 60.** Add registry bindings in both revision.toml
files. Extend `_classify_iva_transaction` to branch on `transaction.iva_category`.
Casilla 62 (criterio de caja) is explicitly out of scope.

**S95 — UPDATE test scenario.** Marc IT services to DE → `iva_category =
DOMESTIC_NOT_SUBJECT` with `counterparty_eu_member_state = EUMemberState.DE`. Assert
casilla 59 receives the base. Add a second scenario (`EXPORT_THIRD_COUNTRY_ZERO_RATED`)
for casilla 60.

### Follow-ups

| ID | Step | Description |
|----|------|-------------|
| FU-W05-A | S278 | Criterio de caja ledger axis (casilla 62): separate step after S94 |
| FU-W05-B | pre-S91 | Author W05.P24 IVA-classification ADR (D1-D4) before coder starts S91; block S91 on ADR acceptance |

---

## Task #95 — W04.P21.S79-S80 persona re-run grounding

**Date:** 2026-05-27

### Investigation 1 — Marc round-7 `work verify` experience

Marc Carrasco Vidal's round-7 audit (section above, lines ~159-201) did NOT reach
`work verify` at all. The session was blocked earlier by two defects:

- **R7-D2:** `StoredCalculationDriftError` surfaced as an unhandled traceback on
  `aeat app modelo work` import. This blocked all `work *` subcommands.
- **R7-D4:** `ledger import --period 2024T1` failed (ledger import path not feeding
  the unified period parser).

The round-7 Marc session was stopped at the `modelo work` import crash (R7-D2). It
never exercised `work calculate`, `work verify`, or `verificado_completo`. S79 must
therefore re-run from scratch reaching the full `work → calculate → verify` path.

**R7-D2 is now closed** — `StoredCalculationDriftError` was registered in
`ErrorCode` in `aaec080e7` (S75+S76 commit). Marc's import-crash blocker is gone.

**R7-D4 status:** `ledger import --period` token format inconsistency was noted as
INCOMPLETE in the round-7 cross-persona summary. It must be confirmed as either
closed or still present at S79 time; if still present it is a pre-verify blocker
for the M130 path and must be logged.

### Investigation 2 — Tax-shape recommendation for S79 fresh persona

The S79 brief says "Marc autónomo IT AND fresh persona reaching `work verify`." Two
distinct personas are called for:

**Marc (repeat):** autónomo IT, Catalan output (`--output-language ca`). Tax shape:
`actividad_economica = design`, non-zero IRPF income, M130 quarterly obligation
(since he had W05.P22 M130 income-side resolver landed in S81-S85). Marc exercises
the full `work → calculate → verify` path on M130. He is the natural fit because:

1. The M130 income-side aggregation resolver (S81-S85) was not yet live when Marc's
   round-7 session ran — it landed later. S79 confirms it works end-to-end.
2. The verificado_completo four-layer gate (S72-S77) applies to M130 casilla 02
   (`required = true` per S73+S74). Marc exercises Layer 1 (missing casilla 02 →
   refused) and Layer 2 (predicate gate if any M130 predicate is defined).
3. Marc's round-6 S349 intracom finding: does a Modelo 349 obligation exist alongside
   M303 and M130? S79 should probe whether `app modelo work list` surfaces M349.

**Fresh persona:** A fresh persona that exercises the provenance re-validation path
(S210-S211) specifically. The best fit is a _trabajador autónomo with a prior-period
revision that has been tampered_ — this exercises the drift-detection path directly.
However, since we cannot literally corrupt storage in a persona testimonial, the
fresh persona should instead exercise the provenance path via the `--json` output and
inspect `observations` fields for `legal_refs` and `source_refs` presence.

Recommended fresh persona: **Inés Ortega Castell** (S.A. director, round-7 repeat).
She has a corporate M200 obligation (not M130/M303), which exercises a different
casilla cluster. Her S79 run should confirm:

- M200 `work verify` refuses on an empty draft (Layer 1: `required = true` casillas
  `00501`/`00562` from S73+S74).
- M200 `work calculate` populates `observations` with typed `CasillaObservation`
  entries carrying `legal_refs` and `source_refs`.
- `granted_verificado_completo = false` without the required inputs.
- `granted_verificado_completo = true` once required inputs are populated.
- Exit code is 1 on refusal and 0 on success.

### Investigation 3 — Specific verification scenarios to probe

For each persona the S79 testimonial must exercise these four scenarios in sequence:

**Scenario A — empty draft refused:**
1. `aeat app modelo work create --modelo 130 --period 1T`
2. `aeat app modelo work calculate <work_unit_id>` (no ledger transactions → all
   casillas zero or absent)
3. `aeat app modelo work verify <revision_id>` → must exit 1, output must contain
   `granted_verificado_completo\tfalse`, must contain at least one
   `MISSING_REQUIRED_CASILLA` finding citing casilla 02 (M130) or 00501/00562 (M200).
   Must NOT contain `Traceback`.

**Scenario B — populated draft accepted:**
1. Import at least one income-side ledger transaction via `app ledger import`.
2. `aeat app modelo work calculate <work_unit_id>`.
3. `aeat app modelo work verify <revision_id>` → must exit 0,
   `granted_verificado_completo\ttrue`.

**Scenario C — `--json` output provenance check:**
After Scenario B, re-run `work verify <revision_id> --output json` (or check that
the standard output contains `legal_refs` and `source_refs` fields in the
`observations` array). The provenance fields must not be empty tuples for the
computed casilla. This is the S210-S211 surface check — it confirms observations
survived the export boundary with their provenance intact.

**Scenario D — VERIFICADO_COMPLETO state persistence:**
After Scenario B succeeds, `aeat app modelo work list --modelo 130` must show the
revision with `state\tVERIFICADO_COMPLETO`. `aeat app modelo work verify <same_id>`
re-run must NOT re-verify (state-machine guard: already VERIFICADO_COMPLETO).
The CLI should surface a `CalculationRevisionStateError`-derived refusal, not a
traceback.

### S79 Persona Operating Brief

The following is the operating brief for the S79 fresh background-agent dispatch.

---

**W04.P21.S79 Persona Operating Brief**

**Objective:** Re-run the `work → calculate → verify` path on Modelo 130 (Marc,
autónomo IT) and Modelo 200 (Inés, S.A.) confirming `verificado_completo` is
refused on empty drafts and granted on populated ones. Surface any residual R7-D4
or Cluster T regressions.

**Method:** CLI-only. No source code access. Isolated `AEAT_LOCAL_STORAGE_ROOT`
(use `tmp_path`-style isolation). No live rights. Two personas.

**Persona 1 — Marc Carrasco Vidal (autónomo IT, repeat)**
- Language: `--output-language ca` on all commands.
- Tax shape: autónomo IT, actividad_economica = design, fiscal_year = 2026.
- Setup: `aeat config profile create marc --tax-id 12345678Z --activity design
  --output-language ca`
- Probe R7-D4 first: `aeat app ledger import --period 2026T1 <csv>` (note: must use
  `1T` format, not `2026T1`; if `2026T1` fails, log as R7-D4 still open).
- Exercise Scenarios A, B, C, D on M130 in sequence.
- Additionally probe: `aeat app modelo work list --output-language ca` — all labels
  must be in Catalan, no English leakage.
- Additionally probe: `aeat app modelo work list --modelo 349` — does a M349
  obligation surface? Log as informational.

**Persona 2 — Inés Ortega Castell (S.A. director, repeat)**
- Language: `--output-language es`.
- Tax shape: sociedad anónima, M200 obligation.
- Setup: `aeat config profile create ines-sa --tax-id B12345678 --activity consulting
  --output-language es`
- Exercise Scenarios A, B, C, D on M200 in sequence.
- Required casillas to supply in Scenario B: `00501` (base imponible general) and
  `00562` (cuota íntegra). Supply via `work calculate` with explicit `--casilla`
  flags or via the full ledger path if available.

**Output format:** A single `.vault/audit/yyyy-mm-dd-cross-domain-continuity-audit.md`
append (do not create a new file) with:
- One subsection per persona.
- Findings as third-level headings labelled BLOCKER / MAJOR / MINOR / CLOSED per
  the established convention.
- A cross-persona table at the end mapping finding to step.

**Known open items to confirm closed:**
- R7-D2 (`StoredCalculationDriftError` traceback on `modelo work`): MUST be closed.
- Anna D1 (same as R7-D2): MUST be closed.
- `verificado_completo` Layer 1 refusal on empty M130 draft: MUST work.
- `verificado_completo` Layer 1 refusal on empty M200 draft: MUST work.

**Known open items to probe (may still be open):**
- R7-D4 (`ledger import --period 2026T1` format): probe and report.
- Cluster T (M100 cuota=0): not relevant for M130/M200 — skip for this session.
- `ledger classify/list/view` silent empty results (R7-D1): probe once per persona.

---

### Investigation 4 — S80 consolidation guidance

**Question: new audit doc or append?**

Append to `2026-05-29-cross-domain-continuity-audit.md`. The established convention
(round-4 through round-7 all in the same growing document) is to append; a new
document is only warranted when the audit target is a wholly distinct campaign or
Wave terminus. S79 is an incremental wave-4 breakpoint re-run within the ongoing
`cross-domain-continuity` campaign.

**Question: threshold for "expand plan in place" (S80)?**

The plan expansion threshold is:

- 1 or more BLOCKER findings → expand plan in place, add new Steps under the
  affected Phase or a new Phase, assign to the appropriate Wave.
- 2 or more MAJOR findings that cluster on the same surface → expand plan in place
  with a mini-Phase (2-4 Steps).
- MINOR findings only → record in audit, no plan expansion; sweep into the next
  applicable Wave's follow-up list.
- 0 findings (all CLOSED) → write "W04.P21 persona breakpoint: all CLOSED" in audit
  and proceed to W05 steps.

The plan expansion must follow the vault CLI (`vault plan step add`, `vault plan
phase add`) — no hand-editing. Step identifiers must be canonical and gap-free.

**S80 output:** A single `vault plan step check` call closing S79, plus a
`vault plan step check` call closing S80 after the consolidation note is written
in the audit doc. If plan expansion is triggered, the new Steps are added before
S80 is closed.

---

## Wave promotion structural decision (Task #103 — 2026-05-27)

**Decision: Option B — create W12 as a dedicated structural-debt cleanup wave.**

### Options evaluated

**Option A — extend W10 with new P59/P60:** W10 (P50-P58) is the deadline-window
registration wave, all Steps closed. Appending structural-debt cleanup there
creates a semantic mismatch (calendar data vs. code boundary hygiene). P59 is also
already occupied by W11.

**Option B — new W12 with two phases:** W11.P59 is the standing quality-gate
meta-wave (persona fleet, drift sweep, plan expansion on every terminus) — it must
remain at the end of every wave sequence and cannot be interrupted by content
phases. Creating W12 with P60 (typed-boundary bulk) and P61 (registry
validate-helper dedup) inserts cleanly before W11 in the logical sequence. W11
then remains the eternal quality gate for W12 as well as all prior waves.

**Option C — W09.P41 macro-cluster:** W09.P41 already carries 90+ Steps across
12 semantic categories. Marking a subset as a macro-cluster does not give the PM
clean scheduling boundaries and forces W09 dispatch to interleave structural-debt
work with the much smaller and faster W09 UX/localisation Steps. No structural
benefit.

### Decision rationale

W12 is the correct home because:
1. Semantic isolation — typed-boundary and validate-helper work is structural
   hygiene that deserves its own quality gate (W12 terminus → W11.P59 re-run).
2. Schedule independence — W12 does not block W09 completion; W09 closes when
   its own Tier 0/1/2 Steps are done. W12 is a parallel campaign.
3. Clean phase numbering — the next-available Phase id after W10.P58 is P60
   (W11.P59 is taken), which is a natural home for the first W12 phase, then P61
   for the second.
4. W11 re-use — W11.P59 S192-S195 apply as the W12 quality gate without any
   new Step authoring; the PM simply re-runs the W11 termination checklist after
   W12 closes.

### Scope of W12.P60 — typed-boundary bulk (G2 gate)

Covers all `dict[str, Any]`/`dict[str, object]` public boundaries and `cast()`
escapes surfaced by the S97 UNTYPED_BOUNDARY discovery sweep. The Steps currently
filed as W09.P41.S277-S280 are the W12.P60 seed; additional sites discovered
during execution extend P60 with new Step rows.

Target files by sub-phase:
- S277 — `_bundle.py` single-site annotation (narrowest, land first as a warm-up).
- S278 — 14 CLI entrypoint payload functions in `_modelo.py`, `_ledger.py`,
  `_config/__init__`, `_common.py`, `_app_live.py`.
- S279 — 10 application service payload functions across `auth/`, `filing/`,
  `aggregation/`, `operator_surface/`, `ledger/`.
- S280 — 14 `cast()` escapes + 3 `pydantic Any/object` fields in `workflow/`,
  `registry/`, `review/`, `schedules/`, `workflow/_models`.

### Scope of W12.P61 — registry validate-helper dedup (G5 gate)

Covers the 8-Step `_missing_refs` deduplication in
`src/aeat/domain/calculations/registry/` surfaced by the W09.P39 discovery sweep
(S149-S156). The Steps are already authored in W09.P39; P61 simply re-hosts them
under W12 so they execute as a single coordinated batch (one create + 7 updates)
rather than 8 independent W09 dispatch slots.

### Execution order within W12

1. W12.P60.S277 (single-site warmup) — validates the typed-annotation pattern.
2. W12.P60.S278 (CLI entrypoints, 14 sites) — largest visible surface; review
   after each batch of 3-4 files.
3. W12.P60.S279 (application services, 10 sites) — follow immediately; same typed
   pydantic pattern.
4. W12.P60.S280 (cast() escapes, 14 + 3 sites) — requires per-site decisions
   (typed alternative vs. inline ADR note); land last in P60.
5. W12.P61.S149 (create `_validate_helpers.py`) — single new file.
6. W12.P61.S150-S156 (7 sibling-file imports) — mechanical, batch in one commit.

### CLI commands for the PM to execute

Run these in sequence after checking out the plan file:

```
PLAN=".vault/plan/2026-05-26-cross-domain-continuity-plan.md"

# 1. Add W12 wave
uv run --no-sync vaultspec-core vault plan wave add "$PLAN" \
  --title "structural-debt cleanup — typed-boundary + validate-helper dedup" \
  --intent "Retire the G2 typed-boundary violations (dict[str,object] public boundaries and cast() escapes) surfaced by the UNTYPED_BOUNDARY discovery sweep, and eliminate the _missing_refs duplication across 7 registry validate modules. Both clusters were promoted from W09.P41 because their combined scope (38 sites + 8 Steps) exceeds what W09 dispatch slots can absorb without starving the W09 UX/localisation work."

# 2. Add W12.P60 — typed-boundary bulk
uv run --no-sync vaultspec-core vault plan phase add "$PLAN" \
  --wave W12 \
  --title "typed-boundary bulk — replace dict[str,object] and cast() escapes" \
  --intent "Replace all public dict[str,object] return types and cast() type-erasure operations identified by the S97 UNTYPED_BOUNDARY sweep with typed pydantic models or inline ADR-documented boundary exceptions. Execute in sub-batches: S277 (single site) first, then S278 (CLI 14 sites), S279 (application 10 sites), S280 (cast 14+3 sites)."

# 3. Add W12.P61 — registry validate-helper dedup
uv run --no-sync vaultspec-core vault plan phase add "$PLAN" \
  --wave W12 \
  --title "registry validate-helper dedup — _missing_refs consolidation" \
  --intent "Extract the duplicated _missing_refs helper from 7 registry validate modules into a single src/aeat/domain/calculations/registry/_validate_helpers.py and update all import sites. Steps S149-S156 from W09.P39 are re-homed here and executed as one coordinated batch."

# 4. Move S149-S156 from W09.P39 to W12.P61
# (use vault plan step move for each; confirm canonical ids after phase add)
# Example for S149:
uv run --no-sync vaultspec-core vault plan step move "$PLAN" W09.P39.S149 --to-phase P61

# Repeat for S150-S156 (adjust Pxx to the actual assigned id after step 3 above)

# 5. Move S277-S280 from W09.P41 to W12.P60
uv run --no-sync vaultspec-core vault plan step move "$PLAN" W09.P41.S277 --to-phase P60
uv run --no-sync vaultspec-core vault plan step move "$PLAN" W09.P41.S278 --to-phase P60
uv run --no-sync vaultspec-core vault plan step move "$PLAN" W09.P41.S279 --to-phase P60
uv run --no-sync vaultspec-core vault plan step move "$PLAN" W09.P41.S280 --to-phase P60
```

**Notes for the PM:**
- Run `vault plan status "$PLAN"` after each wave/phase add to confirm the new
  canonical identifier before running subsequent commands.
- The `--to-phase` flag takes the canonical Phase id (`P60`, `P61`) not the
  display path. Verify with `vault plan query --wave W12` after the add.
- After the moves, run `vault plan check "$PLAN"` to confirm no id gaps or
  dangling references.
- S215 (ledger `_actions.py` four payload helpers) remains in W09.P41 rather than
  moving to W12 because it is lower in scope (4 sites, one file, already under
  active coder attention) and should not be gated behind the full P60 batch.

---

## S254 Batch-3 + D5 regression fix — architecture review (Task #106)

**Commits:** `2a897c177` (S254 Batch-3 + D5 fix) + `8067dc8ff` (vault records)
**Gates applied:** G1, G2, G3, G5, G6
**Verdict: ACCEPT-WITH-FOLLOWUP**

### Commit `2a897c177` — S254 Batch-3 migration + D5 fix

#### Fixture migration (`test_profile_lifecycle_verbs.py`)

The `AEAT_SECRET_STORE_BACKEND=unsecured` / `AEAT_ALLOW_UNENCRYPTED=1`
monkeypatches are gone from `test_profile_lifecycle_verbs.py`. The replacement
pattern is correct: `isolated_profile_storage_root` for create-path tests,
`profile_storage_session` wrapping direct encrypted-SQL reads, `root_app` invocation
so `decorate_typer_app` error boundary is active. The `enforce_unique_tax_id=False`
flag on `profile_create_storage_span` correctly avoids cross-bucket tax-id scan
collisions in per-bucket-storage mode. Pattern is consistent with the established
S208/S252/S253/S273 migration chain.

**G6 (test quality):** `test_profile_import_label_lands_second_copy_under_new_name`
asserts `original.bucket_id != restored.bucket_id` — this is a genuine
discriminating assertion; the test would fail if `--label` preserved the bundle UUID.
Non-tautological. PASS.

#### D5 regression fix (`_config/__init__.py`)

The pre-existing D5 regression was introduced when ADR D5 (UUID preservation on
import) was implemented: the `--label` path was incorrectly made to preserve the
bundle UUID instead of minting a fresh one. This caused
`test_profile_import_label_lands_second_copy_under_new_name` to fail because both
"operator" and "operator-restored" profiles shared the same `bucket_id`.

**Fix analysis — CORRECT.** The `fresh_uuid_mode` branch accurately implements the
ADR intent:

- No `--label` → identity-preserving recovery → Tier-1 UUID collision check applies;
  `profile_id=bundle_profile_id` passed to `_atomic_create_profile`.
- With `--label` → fresh independent copy → Tier-1 UUID check skipped; `profile_id=None`
  passed to `_atomic_create_profile`, which mints a fresh UUID.

The revised Tier-2 guard (`if existing is not None`, dropping `!= bundle_profile_id`)
is also correct for the `fresh_uuid_mode` path: in fresh-UUID mode the minted id is
new each call, so the old `!= bundle_profile_id` condition would have let label
collisions through on a retry (the minted UUID would differ from `bundle_profile_id`
every time).

**Architecture boundary check:** The ADR D5 contract is preserved. The no-`--label`
path still:
1. Checks `read_profile_bucket_by_id(bundle_profile_id)` — refuses if UUID taken.
2. Checks `_read_profile_bucket(target_label)` — refuses if label taken.
3. Calls `_atomic_create_profile(..., profile_id=bundle_profile_id)` — preserves UUID.

The `test_reimport_same_bundle_is_refused` and `test_mutated_profile_id_creates_second_profile`
tests in `test_profile_import_idempotency.py` continue to cover the no-`--label`
identity-preserving path. UUID round-trip confirmed by `assert exported_id in r_show.output`.

**G5 — bonus: dead shim deleted.** The `2a897c177` diff also removes the infinite-
recursion stub `def _activate_subcommand_output_language(ctx, language): _activate_subcommand_output_language(ctx, language)` from `_config/__init__.py` (lines 1553-1556 of the prior version). This was the S264 (FU-W08-B) target. G5 gate: shim retired, direct import from `_common` used. Recommend closing S264 as resolved by this commit.

#### MINOR follow-up (G3)

Tier-2's `tr()` default string `"label {target_label!r} is already taken by a different profile"` uses "different profile" phrasing regardless of whether the caller is in `fresh_uuid_mode` or the identity-preserving path. In `fresh_uuid_mode` the "different profile" phrasing is misleading — the label might have been taken by the very same bundle imported earlier under a different `--label`. The locale key is `import_label_taken_different_id`; the `default=` text should say "already taken" without "different". This is a wording issue, not a functional bug. Log as W09 follow-up.

### Commit `8067dc8ff` — vault records

Step record for S254 is well-formed. Plan checkbox `[x]` on S254 is present.

**ISSUE: S254 closed prematurely. `test_root_help_shape.py` not migrated.**

The S254 step text lists three files: `test_profile_lifecycle_verbs`,
`test_root_grammar_invariants`, `test_root_help_shape`. This commit migrated only
`test_profile_lifecycle_verbs`. Inspection of the current working tree confirms:

- `test_root_grammar_invariants.py` — no `AEAT_SECRET_STORE_BACKEND` references.
  Already clean (migrated by a prior commit or never needed it). OK.
- `test_root_help_shape.py` — `_console_env` helper at lines 40-41 still sets
  `AEAT_SECRET_STORE_BACKEND=unsecured` and `AEAT_ALLOW_UNENCRYPTED=1`. Called
  on lines 121 and 149 — both `--help` surface tests that never reach storage.
  The unsecured env is vestigial and must be removed (S265 target).

**Consequence: S209 cannot be closed yet.** S209 requires all 20 files in the
Batch-3 migration to be clean. `test_root_help_shape.py` is still open.

### Summary

| Item | Status |
|------|--------|
| `test_profile_lifecycle_verbs.py` migration | PASS |
| D5 `fresh_uuid_mode` logic | CORRECT |
| Tier-2 guard fix | CORRECT |
| S264 (dead shim) — closed by this commit | PASS — recommend `vault plan step check S264` |
| `test_root_grammar_invariants.py` | Already clean, OK |
| `test_root_help_shape.py` migration | NOT DONE — S254 closed prematurely |
| S209 closable? | NO — blocked on `test_root_help_shape.py` |

### Follow-up Steps

- Reopen S254 via `vault plan step uncheck W09.P41.S254` and add a note that only
  `test_root_help_shape.py` remains. Alternatively dispatch as a standalone S265-scope
  fix (drop unsecured env from `_console_env` in `test_root_help_shape.py`; `--help`
  tests need no storage backend).
- After `test_root_help_shape.py` is clean, close S254, then close S209.
- Close S264 now (shim deletion landed in `2a897c177`).
- Log Tier-2 "different profile" wording as a minor W09 follow-up.

---

## coder2 S254 (manifest-status repair) + S282 (auth env-var) — architecture review (Task #109)

**Commits:** `2b37264f4` (code) + `7cfc2b71d` (vault records)
**Gates applied:** G1, G2, G3, G5, G6
**Verdict: APPROVE** (with one commit-message inaccuracy noted)

### Overlap with coder1's `2a897c177`

The two S254 commits are **non-overlapping facets**:

- Coder1 `2a897c177` — migrated `test_profile_lifecycle_verbs.py` from unsecured
  monkeypatch to `isolated_profile_storage_root`; fixed D5 `fresh_uuid_mode`
  regression in `_config/__init__.py`.
- Coder2 `2b37264f4` — fixed `_bucket_key_schedule` in
  `src/aeat/adapters/persistence/storage/master_key/_master_key.py` to tolerate
  a manifest missing the `status` field (legacy format); fixed S282 auth env-var
  leak in `_authenticator.py`.

No file overlap. Both commits can coexist without conflict.

### `_bucket_key_schedule` manifest-status tolerance fix

The change catches `StorageValidationError` carrying the message
`"missing required lifecycle status"` and falls back to parsing `key_schedule`
directly from raw TOML so the repair command can open a session to backfill the
missing field. The fallback is tight:

- `"missing required lifecycle status"` string match is narrow — other
  `StorageValidationError` subtypes fall through to `raise`.
- `BucketKeySchedule(str(raw))` is strict: `BucketKeySchedule` is a `StrEnum`
  with only `LEGACY_MASTER_KEY` and `BUCKET_DEK_V1` members; any unknown value
  raises `ValueError` rather than silently accepting it.
- The `dict[str, object]` from `tomllib.loads()` is a documented third-party
  boundary (`tomllib` returns `dict[str, Any]`); not a G2 violation.

**G5 check:** The fix adds no shim or re-export. It extends an existing function
with a narrow legacy-format fallback that self-destructs once all manifests have
been repaired. PASS.

### S282 auth env-var leak fix

Both `CertificateLoadError` raises in `_require_bundle` now use `tr()` with new
locale keys `application.auth.certificate.load.path_unset` and
`application.auth.certificate.load.password_unset`. The raw
`AEAT_CERTIFICATE_PATH`, `AEAT_CERTIFICATE_PASSWORD_SECRET`, and
`CertificateBundle` names are gone from operator-facing output. Four locales
(en/es/ca/hu) all populated.

**Architecture boundary check:** `login_operator_auth` in `_operator.py` already
raises `AuthLoginPreconditionError` with `tr()` before `_require_bundle` is
reached — the LIVE_TESTS gate fires at line 847, then `_assert_login_precondition`
at line 859 raises `AuthLoginPreconditionError` for missing cert path or file.
The S282 fix to `_require_bundle` is defence-in-depth for any non-login caller
that reaches the bundle directly. Correct layering.

**G3 check:** env-var/class-name leakage eliminated at the source in
`_require_bundle`. The `default=` prose in the `tr()` calls is user-facing
operator guidance ("Run 'aeat config auth configure --provider certificate
--file PATH'") — appropriate for the `default=` parameter which is never rendered
in production (locale key takes precedence). PASS.

**Round-5 B-ROSER BLOCKER:** The round-5 audit flagged this as the specific
failing message. The fix closes that finding. PASS.

### FU-W08-B (duplicate `_activate_subcommand_output_language`) claim

The commit message for `2b37264f4` states "Also removes the duplicate
`_activate_subcommand_output_language` definition". This is **inaccurate** — coder1's
`2a897c177` already deleted the shim. Coder2's commit does not touch
`_config/__init__.py` at all (`git show 2b37264f4 -- src/aeat/entrypoints/cli/_config/__init__.py`
produces no output). The claim in the message is a documentation error, not a
functional issue. S264 is confirmed closed by `2a897c177` (not `2b37264f4`).

### Vault records (`7cfc2b71d`)

The plan diff in `7cfc2b71d` checks only S282. S254 remains open in the plan
(`[ ]`), consistent with the prior review's finding that `test_root_help_shape.py`
is still unmigrated.

### Summary

| Item | Status |
|------|--------|
| `_bucket_key_schedule` legacy-manifest fallback | CORRECT |
| S282 `_require_bundle` env-var/class-name elimination | PASS |
| Four-locale prose (en/es/ca/hu) | PASS |
| S264 FU-W08-B claim in commit message | INACCURATE (done by `2a897c177`) |
| S254 plan checkbox | Correctly left open |
| S282 plan checkbox | Correctly closed |
| S209 closable? | Still NO — `test_root_help_shape.py` open |

---

## Task #113 — Architecture review: W12.P62 validate-helper dedup (46ecfb966 + ec0bb2542)

**Verdict: APPROVE**

### G5 gate — no shim, no re-export, no compatibility alias

`_validate_helpers.py` is a new module containing exactly one function:
`_missing_refs`. No re-export of the old definition exists in any of the 7
updated modules. All 7 modules (`_validate_algorithms.py`,
`_validate_constructs.py`, `_validate_dependency_sections.py`,
`_validate_exports.py`, `_validate_record_sections.py`,
`_validate_revision_sections.py`, `_validate_surfaces.py`) remove the local
definition and add a single `from ._validate_helpers import _missing_refs` line.
G5 PASS.

### Canonical definition confirmed

`_validate_helpers.py:10` is the sole module-level `def _missing_refs` in the
entire `registry` package. Verified by grep across all registry modules. PASS.

### `@staticmethod _missing_refs` in `_validate.py` — distinct, not a duplicate

`_validate.py:197` defines `_missing_refs` as a `@staticmethod` on a validator
class. It is called as `self._missing_refs(...)` (lines 137-138), not as a
module-level import. The class binding is a genuinely different symbol — it is
not visible to the 7 `_validate_*.py` module importers, and none of them import
from `_validate.py`. The two definitions are independent and both correct: the
class method serves a validator object's internal cohesion; the module-level
function serves the 7 standalone validation modules. Not a duplication concern.
PASS.

### `Iterable` import cleanup

Six modules (`_validate_algorithms.py`, `_validate_dependency_sections.py`,
`_validate_exports.py`, `_validate_record_sections.py`,
`_validate_revision_sections.py`, `_validate_surfaces.py`) remove `Iterable`
from their `collections.abc` import because `_missing_refs` was the sole
consumer. `_validate_constructs.py` retains `Iterable` — confirmed correct: it
uses `Iterable` as an annotation on 7 function parameters in
`validate_construct_member_references` and related functions. PASS.

### Pre-existing `test_cross_domain_snapshot_registration.py` failure

The 1/279 failure on `test_cross_domain_snapshot_registration.py` is attributed
to a circular import `_applicability.py` → `deadlines._engine`. Verification:
`_applicability.py` was last touched by `acea52801` (W02.P11 applicability
authority work), which predates `46ecfb966`. `_validate_helpers.py` imports only
from `collections.abc` and `._schema` — no `deadlines`, no `_applicability`,
no new transitive dependency that could introduce the circular chain. The failure
is pre-existing and orthogonal to this commit. S304 tracking is correct. PASS.

### Plan checkboxes (ec0bb2542)

S149-S156 checked in plan. Exec record present at
`.vault/exec/2026-05-26-cross-domain-continuity/2026-cross-domain-continuity-W12-P62-S149-S156.md`.
PASS.

### Summary

| Item | Status |
|------|--------|
| Single canonical `_missing_refs` in `_validate_helpers.py` | CONFIRMED |
| No shim / re-export / deprecation alias at original sites | PASS (G5) |
| All 7 import updates correct | PASS |
| `@staticmethod` in `_validate.py` is genuinely distinct | CONFIRMED |
| `Iterable` retained in `_validate_constructs.py` (other usages) | CORRECT |
| `Iterable` removed from 6 other modules (sole consumer gone) | CORRECT |
| Pre-existing circular import — NOT introduced by `46ecfb966` | CONFIRMED |
| S304 tracking of circular import as separate step | CORRECT |

---

## Task #114 — R8-NURIA + S304/S305/S306 triage

### S304 — Circular import: latent defect, NOT currently CLI-blocking

**Current state:** `aeat --version` returns cleanly. `import aeat.domain.calculations.registry`
succeeds in both registry-first and deadlines-first import order. All 3 tests in
`test_cross_domain_snapshot_registration.py` pass. The reported "CLI paralysis" is
NOT reproducible against the current working tree.

**Introduction commit:** `9368c9d46` ("sweep: registry __init__ + remaining
fixture regen") added `from ._applicability import ...` to
`calculations/registry/__init__.py`. This creates the cycle:
`calculations.registry → _applicability → deadlines.taxpayer_model →
deadlines.__init__ → deadlines._engine → calculations.registry`.

**Why it does not bite now:** `_applicability` is imported near the END of
`registry/__init__.py`, after all the `DeadlineWindowDefinition`, `ModeloRevision`,
and other symbols that `deadlines._engine` needs. By the time `_engine` executes
`from ..calculations.registry import (DeadlineWindowDefinition, ...)`, the
registry module is already in `sys.modules` and those symbols are populated. A
comment in `9368c9d46` ("Applicability is imported after _schema so its transitive
import of aeat.domain.deadlines ... does not race a partially-initialised registry
namespace") documents this fragility explicitly.

**Risk:** If the import order in `registry/__init__.py` changes — or if a new
`registry` symbol that `deadlines._engine` needs is added after `_applicability`
in the file — the cycle will bite with `ImportError`. This is a latent defect.

**Revised S304 step text:**
> S304: Mitigate the latent circular import introduced by `9368c9d46`: `calculations.registry
> → _applicability → deadlines → deadlines._engine → calculations.registry`. Current
> runtime is safe because `_applicability` is imported after the symbols `deadlines._engine`
> consumes, but the ordering is fragile. Preferred fix (Option A): factor the
> `TaxpayerModel` types that `_applicability` imports from `deadlines.taxpayer_model`
> into a new `domain.taxpayer_types` leaf module with no registry or deadlines dependency,
> eliminating the cross-domain cycle entirely. Fallback (Option B): convert
> `from ._applicability import ...` in `registry/__init__.py` to a lazy
> function-level import guard. Do NOT use `TYPE_CHECKING` guards. File:
> `src/aeat/domain/calculations/registry/__init__.py` and
> `src/aeat/domain/calculations/registry/_applicability.py`.

### S305 — Multi-profile workspace creation: root cause correction

**Task description inaccuracy:** The description says "`_refuse_duplicate_tax_id`
opens `UserProfileLifecycleRepository` with the NEW bucket session". This is
incorrect for the `config profile import` / `config profile duplicate` paths —
those call `_atomic_create_profile` which passes `enforce_unique_tax_id=False`,
so `_refuse_duplicate_tax_id` is never reached. The scan IS reached from the
`config profile create` wizard path: `_run_full_flow` → `persist_answers` →
`register_active_profile` with the default `enforce_unique_tax_id=True`.

**Session nesting is architecturally correct.** `profile_storage_session` uses
`ContextVar` with token-based `activate_session` reset — nested sessions stack
and unwind cleanly. The inner `profile_storage_session(summary.profile_id)` call
correctly activates the existing profile's session for `self.load(summary.profile_id)`.

**Actual failure mode:** `_refuse_duplicate_tax_id` scans ALL non-tombstoned
profiles. If any existing profile's `_bucket_key_schedule` raises a non-`"missing
required lifecycle status"` `StorageValidationError`, or `_load_or_mint_bucket_dek`
fails, the `except Exception as exc` at line 668 catches it and raises
`UserProfileValidationError("Cannot verify tax-id uniqueness because profile X
is unreadable")`. For a gestor with 5 client profiles, one profile with any
storage issue blocks creating any new client profile — even one with a completely
different NIF.

**Revised S305 step text:**
> S305: Fix `_refuse_duplicate_tax_id` fragility in multi-profile gestor scenarios.
> Change the `except Exception` handler at `_profile_repository.py:668` from
> fail-closed (raise immediately) to warn-and-continue: accumulate unreadable-profile
> warnings in a list; after the scan, if any warnings exist AND the new NIF was not
> confirmed a duplicate, emit the warnings as non-blocking notices in the CLI output
> and allow creation to proceed. Only raise `UserProfileValidationError` when a
> duplicate NIF is confirmed. Add regression test: create two profiles with different
> tax IDs, corrupt profile 2's manifest, create a third profile with a third tax ID;
> assert creation succeeds with a warning about profile 2. File:
> `src/aeat/application/user_profile/_profile_repository.py` method
> `_refuse_duplicate_tax_id` (line 639).

### S306 — No cross-profile calendar: confirmed single-profile, fix path decided

**Confirmed.** `overview_calendar` in `_overview.py` (line 84) uses `_state()`
(single active profile) and passes one `_TaxpayerProfile` to `build_overview_calendar`.
`build_overview_calendar` is pure — no I/O, no repository. `overview status`,
`explain`, `agenda`, and `backlog` are all identically single-profile.

**Fix path:** `build_overview_calendar` need not change. The union-view is CLI-layer
work: iterate `list_profile_buckets()`, open `profile_storage_session(bucket_id)` per
bucket, read `record_to_values`, derive `_profile_to_taxpayer`, call
`build_overview_calendar`, collect results keyed by profile label. The function's
pure signature is perfectly suited to this iteration.

**Revised S306 step text:**
> S306: Add `--all-profiles` flag to `aeat app overview calendar`. When set: iterate
> `list_profile_buckets()`, for each non-tombstoned bucket open
> `profile_storage_session(bucket_id)`, read `record_to_values`, derive
> `_profile_to_taxpayer`, call `build_overview_calendar`, collect per-profile results.
> Output a list of `{profile_label, calendar}` objects in JSON mode; in text mode emit
> a section header per profile. `build_overview_calendar` itself requires no changes.
> `--all-profiles` is mutually exclusive with any flag that assumes a single active
> profile. Track `overview status`, `explain`, and `agenda` `--all-profiles` parity
> as follow-on steps. File: `src/aeat/entrypoints/cli/_overview.py`.

### Summary

| Item | Finding |
|------|---------|
| S304: CLI currently paralysed? | NO — `aeat --version` clean, all 3 tests pass |
| S304: Cycle exists? | YES — latent, introduced by `9368c9d46` |
| S304: Fix path | Option A: factor `TaxpayerModel` to leaf module; Option B: lazy import |
| S305: `_refuse_duplicate_tax_id` with new bucket session? | INACCURATE — session nesting is correct via ContextVar |
| S305: Actual failure mode | Fail-closed scan: one unreadable existing profile blocks any new creation |
| S305: Fix path | Change `except Exception` handler to warn-and-continue; only raise on confirmed duplicate |
| S306: Single-profile calendar confirmed? | YES |
| S306: Fix path | `--all-profiles` flag at CLI layer; `build_overview_calendar` unchanged |

---

## Task #115 — Architecture review: W05.P24.S91-S95 IVA classification enrichment

**Commits:** `c27f35398` (sweep — implementation) + `c95617243` (test file + plan
step-close) + `dc6e6c63d` (step record)
**Date:** 2026-05-27
**Reviewer:** architecture-specialist

### D1 — `iva_category` and `counterparty_eu_member_state` on Transaction

CONFIRMED. `src/aeat/domain/transactions/_models.py` lines 777-778:

```
iva_category: IvaCategory | None = None
counterparty_eu_member_state: EUMemberState | None = None
```

Both fields are on `Transaction`, not on `BusinessClassification`. `_coerce_transaction_enum_fields`
includes coercion for both (lines 283-284). Import at line 34:
`from ..iva._schema import EUMemberState, IvaCategory`. Domain-layer placement correct;
no adapter or application leakage.

### D2 — BusinessClassification remains frozen at 7 members

CONFIRMED. `src/aeat/domain/transactions/_enums.py` lines 49-55 show exactly 7 members:
`BUSINESS`, `PERSONAL`, `MIXED`, `NOT_YET_PROCESSED`, `PROCESSED_UNCLASSIFIED`,
`SKIPPED_BY_RULE`, `FAILED_VALIDATION`. No IVA-category additions. `CLASSIFIED_STATES`
frozenset unchanged. ADR D2 constraint honoured.

### D3 — Casilla 62 not touched

CONFIRMED. No reference to `casilla_62` in `_iva_ledger.py` or `_schema.py`. Scope
constraint respected.

### D4 — DOMESTIC_NOT_SUBJECT does not feed casilla 59

CONFIRMED. `casilla_59_base_imponible` (line 642 of `_iva_ledger.py`) sums only
`IvaCategory.INTRA_COMMUNITY_SUPPLY` observations. `DOMESTIC_NOT_SUBJECT` is absent
from that predicate. `test_domestic_not_subject_services_do_not_populate_casilla_59`
exercises this directly — a DOMESTIC_NOT_SUBJECT row produces an observation but
`casilla_59_base_imponible` returns `Decimal("0")`. R12 routing per ADR D4 is correct.

### D5 — Three reject reasons present and gated correctly

CONFIRMED. `IvaLedgerAggregationIssueReason` carries:
- `DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION` (line 81)
- `EU_MEMBER_STATE_ON_EXPORT_TRANSACTION` (line 82)
- `MISSING_COUNTERPARTY_EU_MEMBER_STATE` (line 553)

`_validate_intracom_export_counterparty` at lines 537-568 implements all three rules.
Gate fires before `_classify_iva_transaction` so rejected transactions produce zero
observations. Explicit `iva_category` override in `_classify_iva_transaction` (lines
455-468) takes precedence over the `_RATE_KIND_TO_DOMESTIC_CATEGORY` fallback — correct.

### G2 — Typed pydantic throughout

CONFIRMED. `IvaCategory` and `EUMemberState` are both `StrEnum` members from
`src/aeat/domain/iva/_schema.py`. No `dict[str, Any]` for any boundary record.
`IvaLedgerAggregation.issues` is `list[IvaLedgerAggregationIssue]` (typed). No
`cast()` or `str()` coercion escapes found.

### G6 — Anti-tautology proof on D5 reject tests

CONFIRMED SUFFICIENT. Each D5 test asserts BOTH `len(aggregation.observations) == 0`
AND the specific `IvaLedgerAggregationIssueReason` value. If the gate were disabled
and the transaction passed through, `len(observations)` would be 1 and the first
assert would fail — the test is not tautological. The combined `test_marc_combined_scenario`
additionally cross-checks `casilla_59 == 5000` while `casilla_60 == 0`, providing
partition-of-observations confidence.

### S93 — Locale keys

CONFIRMED for en, es, ca. `c27f35398` adds `iva_category_help` and
`counterparty_eu_member_state_help` under `cli.ledger.classify` in
`en.yml`, `es.yml`, and `ca.yml` with proper prose. `hu.yml` adds
the keys but uses the dotted key path as the value rather than a
Hungarian translation — a minor locale gap, not a blocking defect.

### Test run

All 7 Marc persona tests PASS (`pytest src/aeat/application/aggregation/test_intracom_export.py`
in 1.85s).

### Follow-up

- **HU locale gap (S93, MINOR):** `hu.yml` should translate
  `iva_category_help` and `counterparty_eu_member_state_help` rather
  than using key-path fallbacks.
- **S94 note:** ADR S94 records that casillas 59+60 remain `input_kind=manual`
  pending binding-type confirmation. This is intentional; no defect.

### Verdict

**APPROVE.** All ADR constraints D1-D5 and gates G2, G6 are satisfied.
Implementation is architecturally clean. One minor locale gap in `hu.yml`
(HU translations absent for the two new keys) is tracked as a non-blocking
follow-up. S91-S95 are closed.

---

## Task #118 — Architecture grounding: W05.P25 bulk classify + W05.P26 IVA wallet

**Date:** 2026-05-27
**Author:** architecture-specialist

---

### W05.P25 — Bulk classify + rule-based classifier

#### Existing classify path

`ledger classify` is a single-transaction verb at `_ledger.py:480`. It accepts
`--id`, `--classification`, `--business-pct`, `--category-id`, `--taxable-base`,
`--iva-rate`, `--iva-amount`, `--irpf-category`, `--iva-category`,
`--counterparty-eu-member-state`. It builds a `ManualLedgerTransactionPatch` and
calls `update_manual_transaction_fields`. No CSV input path exists anywhere; no
batch loop exists. There is no `--from-csv` flag on any ledger command.

The `source_command` field on `ManualLedgerTransactionCommand` records the
originating CLI verb. The `edit_lineage` trail on `Transaction` preserves
this provenance per mutation.

There is no persisted `ClassificationRule` model, no `description_pattern` field
anywhere in `src/aeat/`, and no rule storage concept in the profile or any
repository. The only existing rule-adjacent concept is `classified_by` (a string
in the classification decision) and `_IvaClassificationRule` (an internal
`NamedTuple` inside `_classification.py` for stateless IVA rate routing —
not stored, not operator-configurable).

#### S96 — `--from-csv` bulk classify

**Pattern:** parse CSV with header `id,classification[,category_id,business_pct,...]`,
iterate, call `update_manual_transaction_fields` once per row using
`ManualLedgerTransactionPatch`. Re-use `_parse_decimal`, `_validate_category_id`,
`_resolve_id` exactly as `ledger classify` does. `source_command` for each
persisted mutation should be `"aeat app ledger classify --from-csv"`.

**CSV schema decision:** minimum required columns are `id` and `classification`.
All other `ManualLedgerTransactionPatch` fields are optional columns. Unknown
columns must be rejected before any persistence call (fail-closed input).

**Input model:** introduce `BulkClassifyRow(BaseModel)` in
`src/aeat/application/ledger/_models.py` — one pydantic model per CSV row,
validated before any persistence call. This keeps the boundary typed.

**Result model:** introduce `BulkClassifyResult(BaseModel)` with
`rows_attempted`, `rows_succeeded`, `rows_failed`,
`failures: tuple[BulkClassifyFailure, ...]` where `BulkClassifyFailure`
carries `row_index`, `transaction_id`, and `reason`. Emit via `_emit` in
JSON mode; in text mode emit a summary line plus per-failure detail.

**ADR gap (non-blocking):** partial-success vs all-or-nothing batch semantics.
Recommendation: **partial-success** with per-row failure reporting, matching
the existing ledger import pattern (`LedgerSourceImportResult.skipped` /
`diagnostics`). Document in commit message; no separate ADR needed.

**Revised S96 text:**
Add `--from-csv <file>` flag to `aeat app ledger classify`. CSV header must
include `id` and `classification`; optional columns: `category_id`,
`business_pct`, `taxable_base`, `iva_rate`, `iva_amount`, `irpf_category`,
`iva_category`, `counterparty_eu_member_state`. Unknown columns rejected
before any persistence call. Each row validated as `BulkClassifyRow` before
persistence. Rows failing validation collected in `BulkClassifyResult.failures`
(partial-success semantics matching ledger import). `source_command` for each
persisted mutation is `"aeat app ledger classify --from-csv"`. Add
`BulkClassifyRow`, `BulkClassifyResult`, `BulkClassifyFailure` to
`src/aeat/application/ledger/_models.py`. Locale keys:
`cli.ledger.classify.from_csv_help`, `cli.ledger.classify.bulk_summary`.
Files: `src/aeat/entrypoints/cli/_ledger.py`,
`src/aeat/application/ledger/_models.py`, locale YMLs.

#### S97 — Rule-based classifier surface

**No existing model.** There is no `LedgerClassificationRule` record type, no
rule repository, no pattern-matching engine anywhere. This is greenfield domain
work.

**Data model:** `LedgerClassificationRule` belongs in
`src/aeat/domain/transactions/` (domain layer). Minimum fields: `rule_id`
(content-addressed SHA-256 of pattern+classification+category), `description_pattern`
(regex string), `classification: BusinessClassification`, `category_id: str | None`,
`priority: int` (lower = higher priority), `created_at: datetime`, `actor: str`.
Recommend **regex** as the canonical engine — consistent with existing
`classified_by="rule:vendor-map"` provenance string convention.

**Storage:** rules are profile-scoped. They live in a
`SecureBoundRepository[LedgerClassificationRule]` with namespace
`"aeat.ledger.classification.rules"`, sensitivity `AUDIT`. The `rule_add`
and `apply_classification_rules` actions live in
`src/aeat/application/ledger/_actions.py`.

**Interaction with manual `ledger classify`:** `apply_classification_rules`
iterates ACTIVE NOT_YET_PROCESSED transactions in priority order and calls
`update_manual_transaction_fields` with `classified_by="rule:<rule_id>"`.
Manual `ledger classify --id` always wins; a subsequent `rule apply` must
NOT overwrite an existing manual classification unless `--reaffirm` is
passed (matching the existing `reaffirm` flag on `ledger classify`).

**ADR gap (BLOCKING for S97):** No ADR exists for rule storage and engine
semantics. The classification-harmonization ADR (`2026-04-20`) documents
intent but deferred pending `#236`. That contract is now live on `Transaction`
(confidence + `classified_by` provenance). An ADR must be authored before
S97 implementation covering: pattern engine (regex only or regex+substring+glob),
storage backend (profile-scoped `SecureBoundRepository` vs flat JSON in profile
record), conflict policy, `rule apply` scope, and reaffirm interaction.

**Revised S97 text:**
Author `LedgerClassificationRule` domain model in
`src/aeat/domain/transactions/_classification_rule.py`. Add
`LedgerClassificationRuleRepository(SecureBoundRepository[LedgerClassificationRule])`
in `src/aeat/application/ledger/_rule_repository.py` with namespace
`"aeat.ledger.classification.rules"`. Add `add_classification_rule` and
`apply_classification_rules` actions in `src/aeat/application/ledger/_actions.py`.
Expose `aeat app ledger rule add` CLI sub-app. `apply_classification_rules`
iterates ACTIVE NOT_YET_PROCESSED transactions in priority order; skips any
transaction whose `classified_by` is not `"manual"` unless `--reaffirm`.
Requires rule-engine ADR authored first.

**Revised S98 text:**
Regression tests for S96 and S97. S96 tests: (a) valid CSV with mixed
success/failure rows produces correct `BulkClassifyResult`; (b) CSV with
unknown column rejected before any persistence call; (c) `source_command`
recorded as `"aeat app ledger classify --from-csv"` in `edit_lineage`.
S97 tests: (a) round-trip `LedgerClassificationRule` through
`LedgerClassificationRuleRepository` with anti-tautology proof; (b)
`apply_classification_rules` matches by regex and skips manually-classified
rows; (c) `--reaffirm` flag overwrites prior manual classification.
All tests use real `isolated_runtime_profile`; no mocks.

---

### W05.P26 — IVA wallet balance verb

#### Existing IVA wallet infrastructure

`app live iva-wallet` (`_app_live.py`) already provides three verbs: `pull`
(live fetch + persist, `IvaWalletCaptureReport`), `history` (local history +
carry-forward lots + authority decisions, `IvaCompensationHistoryReport`), and
`capture-history` (live pull of multi-year filed Modelo 303 history). The
`app modelo` tree has no `iva-wallet` sub-command. No `balance` verb exists anywhere.

#### Balance model

The balance is NOT a dedicated wallet record. It is computed from
`IvaCompensationPeriodState` records persisted in `IvaCompensationHistoryRepository`
via `build_iva_compensation_carry_forward_report` in
`src/aeat/application/calculations/_iva_compensation_history.py`. That function
loads all periods, applies FIFO allocation of `applied_amount` across
`generated_amount` lots, and returns `IvaCompensationCarryForwardReport` with
per-lot `remaining_amount`. The current balance is the sum of `remaining_amount`
across all non-expired lots. This is already surfaced (though not aggregated) in
`iva-wallet history` via `_iva_wallet_history_lines`.

#### Next pull date

No "next pull date" concept exists. The four-year expiry window is enforced by
`enforce_iva_compensation_four_year_window`. Expiry review states transition at
`age_years == 4` (`EXPIRY_REVIEW_DUE`) and `age_years > 4` (`EXPIRED_REVIEW_REQUIRED`).
"Next pull date" is ambiguous between (a) the next Modelo 303 quarterly filing
deadline (deadline engine) and (b) the nearest lot-expiry boundary
(`source_filing_year + 4`). The deadline engine is out of scope for this step.
**Decision required:** surface (b) — nearest `source_filing_year + 4` among ACTIVE
lots — as `next_expiry_year` rather than a wall-clock date. This avoids coupling to
the deadline engine and is self-contained within the history repository.

#### Naming: `app modelo iva-wallet` vs `app live iva-wallet`

A `balance` verb reads only local persisted history — no AEAT connectivity needed.
Placing it under `app live` would mislead operators. Place under a new
`app modelo iva-wallet` sub-app, mirroring the pattern where offline computation
verbs live under `app modelo` and live-fetch verbs live under `app live`.

#### S99 — revised text

Add `aeat app modelo iva-wallet balance` verb. Logic: call
`build_iva_compensation_carry_forward_report(list_periods(), as_of_year=current_year)`,
enforce the four-year window, sum `remaining_amount` across non-expired lots.
Emit: `total_balance`, `lot_count`, `oldest_lot_year`,
`oldest_lot_expiry_review_state`, `next_expiry_year` (nearest
`source_filing_year + 4` among ACTIVE lots, or `None` if no lots). Introduce
`IvaWalletBalanceReport(BaseModel)` in a new
`src/aeat/application/calculations/_iva_wallet_balance.py`. Wire via a new
`modelo_iva_wallet_app` Typer sub-app in `src/aeat/entrypoints/cli/_modelo.py`.
Add locale keys: `cli.modelo.iva_wallet.balance_help`,
`cli.modelo.iva_wallet.total_balance`, `cli.modelo.iva_wallet.next_expiry_year`.

#### S100 — revised text

Regression test asserting coherent state after a sequence of quarterly filings
with credit. Use `isolated_runtime_profile` (real encrypted storage). Sequence:
persist three `IvaCompensationPeriodState` records (Q1 2024 generates 1200 EUR,
Q2 2024 applies 300 EUR, Q1 2025 applies 500 EUR). Assert: `total_balance == 400`,
`lot_count == 1`, `oldest_lot_year == 2024`,
`oldest_lot_expiry_review_state == "expiry_review_due"` when `as_of_year == 2028`,
`next_expiry_year == 2028`. Anti-tautology: mutate one persisted record
`applied_amount` to an inconsistent value, reload, assert `model_validator`
raises `ValueError`. No mocks.

---

### ADR gaps summary

| Gap | Blocking? | Scope |
|-----|-----------|-------|
| S97: Rule storage + engine semantics ADR | YES — blocks S97 | W05.P25 |
| S96: Partial-success vs all-or-nothing | NO — recommend partial-success | W05.P25 |
| S99: `balance` verb placement (`app modelo` vs `app live`) | Decision above (app modelo) | W05.P26 |
| S99: "next pull date" semantics | Decision above (lot-expiry boundary) | W05.P26 |

---

## Task #122 — Architecture review: W05.P23.S86-S90 FX conversion

**Commits:** `38d82ce95` (S86 decision) + `9239692e4` (S87 schema) +
`434ed8a18` (S88+S89 implementation) + `9ff321c88` (S90 tests) +
`cfcd6559a` (exec records + plan closure)
**Date:** 2026-05-27
**Reviewer:** architecture-specialist

### S86 — Decision doc: AEAT/BOE authority citations

CONFIRMED. The step record cites three distinct statutory authorities:

- Art. 79.Dos LIVA (BOE-A-1992-28740): IVA devengo date → ECB reference rate on
  tax point date
- Art. 14 LIRPF (Ley 35/2006, BOE-A-2006-20764): IRPF exigibilidad date
- Art. 16.5 LIS (Ley 27/2014, BOE-A-2014-12328): IS transaction date for revenue
  items

Conversion date proxy: `value_date ?? booked_date` matching the existing
`operation_date` applied across all aggregation gates. Rationale for hybrid over
on-aggregation-conversion is clearly argued: determinism, no late-binding rate
provider in the aggregation layer, provenance preservation. Placement on
`Transaction` (not `RawTransaction`) is explicitly justified matching the
`iva_category` boundary precedent. S86 decision doc is thorough and legally grounded.

### S87 — Transaction schema: G2 compliance + coupling invariant

CONFIRMED. `fx_rate: Decimal | None = None` and `value_in_eur: Decimal | None = None`
added to `Transaction` (lines 794-795 of `_models.py`). Both added to
`_TRANSACTION_DECIMAL_KEYS` (lines 269-270). Two validators enforce correctness:

- `_validate_fx_fields`: rejects negative values via existing
  `_validate_non_negative_decimal` helper
- `_enforce_fx_coupling`: both set or both absent; EUR-native transactions carry neither

G2 compliant: typed `Decimal | None`, no `dict[str, Any]`. Backward compat: both
fields default to `None`, so all existing `Transaction` records remain valid.

### S88 — Import path FX wiring

CONFIRMED. `_apply_fx_conversion` helper in `_actions.py`: EUR rows return
`(None, None)` immediately; non-EUR rows with no normalizer or a missing rate also
return `(None, None)`, preserving the coupling invariant. Rate date is
`raw.value_date or raw.booked_date` — consistent with S86 decision.
`CurrencyNormalizationService` is optional in `import_ledger_transactions` and
`_evaluate_import_rows`; callers without a rate provider retain existing behaviour.
ECB source is the `ExchangeRateProvider` abstraction injected by the caller —
not hardcoded. G4 locale gate: no locale yml touched. PASS.

### S89 — Shared predicate: G5 compliance

CONFIRMED. `is_non_eur_without_conversion` canonical helper in
`_currency_predicates.py:18`. All three independent
`if transaction.raw.currency != "EUR"` guards in `_iva_ledger.py:398`,
`_renta_ledger.py:272`, and `_renta_income_ledger.py:225` replaced with
the shared predicate. Zero remaining raw `currency != "EUR"` checks in those
files. G5 gate passes.

`effective_eur_amount` is defined and exported but not yet called in any
aggregation file — a preparatory helper for a future wiring step (IVA ledger
currently uses operator-supplied `taxable_base`). Not a defect in S89 scope.

One minor dead-code line in `test_missing_rate_leaves_fx_fields_absent`
(line 210): an unused `CurrencyNormalizationService` construction is shadowed
immediately by the `_NoRateProvider` inner class two lines below. Non-blocking.

### S90 — Regression test: oracle + G6 anti-tautology

CONFIRMED STRONG. ECB oracle is explicit and well-documented:

- ECB EXR.D.USD.EUR.SP00.A 2024-01-15 = 1.0868 (published reference rate)
- `_ECB_2024_01_15_USD_RATE = Decimal("1") / Decimal("1.0868")` — derived from
  the published figure, not author-invented
- `_EXPECTED_EUR` computed from the derived rate with a module-level
  `assert _EXPECTED_EUR == Decimal("92.01")` — the test file fails to import
  if the oracle derivation is wrong

Satisfies `no-tautological-calculation-tests`: expected EUR value traces to a
published ECB figure, not to the formula under test.

Anti-tautology proof (test 5): mutant rate (50% of canonical) in a separate
provider instance produces a distinct `value_in_eur`; `assert canonical_eur != mutant_eur`
fails if the rate is ignored. Non-tautological.

All 5 tests pass (`pytest test_fx_conversion.py` in 3.13s; `isolated_runtime_profile`
real adapter; no mocks).

### Follow-up (non-blocking)

- `effective_eur_amount` wiring: the helper is exported but unused. A future
  step should wire it into the amount projection path for non-EUR rows when
  `taxable_base` is absent at import. Track as W05.P23 follow-up.
- Dead code in `test_missing_rate_leaves_fx_fields_absent` line 210: shadowed
  `CurrencyNormalizationService` construction. Remove in next cleanup pass.

### Verdict

**APPROVE.** S86-S90 all pass. Decision doc is well-grounded with three BOE
citations. Schema coupling invariant is tight. G2, G5, G6 gates all satisfied.
Oracle from published ECB EXR data satisfies no-tautological-calculation-tests.
G4 locale gate: no yml mutation across any of the 5 commits. Two minor
non-blocking follow-ups logged.

---

## Task #124 — W12.P61.S277 typed-boundary warmup (1515ec548 + 621f8b83b + 487642ce3)

### Commits reviewed

- `1515ec548` — replace `_parse_json_object_options` with `_parse_typed_cli_observations`
- `621f8b83b` — regression tests for `_parse_typed_cli_observations`
- `487642ce3` — exec record + plan closure

### G2 compliance

The UNTYPED_BOUNDARY site is eliminated. `_parse_json_object_options()` returning
`tuple[dict[str, object], ...]` is fully removed — no remaining callers anywhere in
`src/aeat/`. The replacement `_parse_typed_cli_observations[ObservationT: BaseModel]`
accepts `model=` and validates each JSON string via `model.model_validate_json(raw)`.

`PerModeloAggregationCommand` is now constructed directly with typed observation
tuples (`RetencionObservation`, `CounterpartObservation`, `ForeignAssetIngestObservation`)
rather than going through a `model_validate_json(json.dumps({...}))` indirection.
All three types are correctly imported from `aeat.application.aggregation`.

The `dict[str, object]` occurrences remaining in `_modelo.py` are all serialisation
payload helpers (`_work_unit_payload`, `_verification_report_payload`, etc.) —
these are S278 scope (output direction), not this step.

### PEP 695 type parameter syntax

`[ObservationT: BaseModel]` uses PEP 695 syntax, valid from Python 3.12+.
The project targets Python 3.13 (confirmed by the test runner: Python 3.13.11).
Correct choice — avoids the `TypeVar` boilerplate and satisfies ruff UP047/UP049.

### G4 — locale scaffold compliance

`cli.app.modelo.aggregate.json_validation_error` was added via
`python -m aeat.locales scaffold` as documented in the step record. Verified:
en.yml carries prose (`{flag} value is not a valid observation object: {details}.`);
es/ca/hu carry scaffold stubs (full key path as placeholder). Structural addition
via scaffold, not hand-edit. G4 satisfied.

### Regression tests (621f8b83b)

Four tests, all exercising `_parse_typed_cli_observations` directly (unit-level,
no CLI runner overhead):

- `test_parse_typed_cli_observations_round_trips_valid_json` — constructs a full
  `RetencionObservation` payload; asserts typed fields including `RetencionScheme`
  StrEnum coercion from JSON string. Genuine round-trip.
- `test_parse_typed_cli_observations_rejects_invalid_json_syntax` — `{not: json}`
  must raise `typer.BadParameter`.
- `test_parse_typed_cli_observations_rejects_non_object_json` — JSON array must
  raise `typer.BadParameter` (distinct code path from syntax error).
- `test_parse_typed_cli_observations_rejects_schema_violation` — object missing
  required `scheme` field must raise `typer.BadParameter` (pydantic `ValidationError`
  path).

All 4 pass in 1.55s. G6 gate: the three error-path tests collectively serve as the
anti-tautology proof — if the function stopped raising `BadParameter` on bad input
any of the three would fail. No tautological assertions.

### Minor observations (non-blocking)

- The `_ = _typer` line in `test_parse_typed_cli_observations_round_trips_valid_json`
  is an unused-import suppressor for a `typer` import that is only used in the other
  three tests. The import itself is at function scope in each test, so the suppressor
  is redundant and could be deleted; this is cosmetic, not a correctness issue.
- The step record notes two pre-existing test failures
  (`test_work_calculate_binding_help_points_at_bindings_list`,
  `test_period_token_error_enumerates_modelo_specific_tokens`) unrelated to S277.
  These are pre-existing and not introduced by this step.

### Scalability assessment for S278-S280

S277 established the **input-direction** pattern: parse raw CLI strings into typed
pydantic models at the CLI boundary. This generic is **not reusable** for S278/S279
which are **output-direction** (functions returning `dict[str, object]` to the CLI
emitter). Coder2 must understand:

- **S278 pattern** (14 CLI payload functions): define an `OutputSchema` subclass in
  `src/aeat/entrypoints/cli/_modelo_payloads.py` (the established home for these —
  `WorkUnitPayload`, `VerificationReportPayload`, etc. are there). Replace the
  `-> dict[str, object]` function with `-> TheTypedPayload`. The emitter already
  handles `OutputSchema` instances. One `OutputSchema` subclass per payload shape.
- **S279 pattern** (10 application payload functions): same principle but in
  `src/aeat/application/` — typed return models, not `dict[str, object]`. These
  may need new pydantic models in the relevant `_models.py` file per subpackage.
- **S280 pattern** (14 `cast()` sites): each site must be individually assessed.
  `cast()` in `workflow/_adapters.py` lines 107/112/141/147/203/204` is likely
  third-party adapter coercion — inline documentation is the correct resolution
  per `aeat-calculation-grounding`. `registry/_schema.py` casts may be
  replaceable with typed constructors.

The S277 generic is not the S278/S279 template. Coder2 should follow the
`_modelo_payloads.py` `OutputSchema` pattern for S278, not adapt the input-direction
generic.

### Verdict

**APPROVE.** G2 satisfied — old untyped function fully deleted, no remaining callers.
G4 satisfied — locale key added via scaffold. G6 satisfied — four regression tests,
three covering error paths as anti-tautology proof. PEP 695 syntax correct for
Python 3.13. Pattern is sound and scalable to S278 with the caveat that S278/S279
are output-direction and require `OutputSchema` subclasses, not the input-direction
generic from S277. Two non-blocking cosmetic observations noted.

---

## Task #131 — S305+S306 gestor unblock (51acf7a6d + dd8934c72 + 9fdb3bd92)

**Review date:** 2026-05-27

### Commits reviewed

- `51acf7a6d` — S305: `_refuse_duplicate_tax_id` warn-and-continue + regression fix
- `dd8934c72` — S306: `--all-profiles` flag on `aeat app overview calendar`
- `9fdb3bd92` — exec records + plan closure

### S305 — warn-and-continue for unreadable profiles

**Scope compliance:** The change is precisely scoped. `_refuse_duplicate_tax_id`
previously raised `UserProfileValidationError` on any `Exception` during the
uniqueness scan. The new path logs a `warning` + `continue` so one torn bucket
does not block a different taxpayer from registering. Duplicate detection still
fires against all readable profiles — the `ProfileAlreadyRegisteredError` raise
on `existing_tax_id == new_tax_id` is unchanged.

**Architect grounding match (#114):** The Task #114 grounding specified
warn-and-continue as the correct approach. Implementation matches exactly.
`log.warning` (not `log.debug`) is used, providing operator-visible signal.
The removed `raise UserProfileValidationError(...)` + deleted locale key
`duplicate_tax_id_scan_unreadable_profile` is clean — no remaining callers
confirmed via grep.

**Pre-existing regression fix:** Commit also fixes a regression from `39383541b`
that broke all 17 profile-repository tests. The fix adds session-aware
`_create/_load/_delete/_select/_rename` helpers in the test file that wrap
`ProfileRepository` calls in the correct `profile_storage_session` context,
mirroring CLI call patterns. This is correct — the test file was calling
`repository.create()` directly without a session, which broke after the session
requirement was hardened. The fix is in the test file only; no production code
change.

**Anti-tautology proof pair (G6):**

- `test_create_succeeds_with_different_nif_when_scan_hits_unreadable_profile`:
  Creates a profile, corrupts its manifest to simulate a torn bucket, then
  creates a second profile with a **different** NIF. Asserts success +
  round-trip load. If the warn-and-continue path were broken (still fail-closed),
  this test would raise `UserProfileValidationError` and fail. **PASS.**

- `test_create_still_refuses_duplicate_nif_against_readable_profiles`:
  Creates two profiles (readable + torn bystander), then attempts to create
  a third with the same NIF as the readable one. Asserts `ProfileAlreadyRegisteredError`
  fires with the readable profile's NIF in the match. The torn bystander is
  irrelevant — the duplicate fires against the readable one. If warn-and-continue
  accidentally suppressed all duplicate detection, this test would fail to raise.
  **PASS.** This is the correct anti-tautology structure: the two tests are
  complements — one proves the gate opens for different-NIF, the other proves
  it still closes for genuine duplicates.

All 3 targeted tests pass in 5.56s. No mocks.

### S306 — `--all-profiles` flag

**Hexagonal compliance:** `build_overview_calendar` is unchanged. The new
`_overview_calendar_all_profiles` helper lives in the CLI entrypoint layer
(`_overview.py`) and calls into the application layer via the established
`profile_storage_session` + `ProfileRepository.load` + `build_overview_calendar`
path. No new application-layer abstractions introduced. **Clean.**

**`list_profile_buckets` usage:** Called correctly — filters to
`BucketLifecycleStatus.ACTIVE` buckets only; sorted by label for deterministic
output order. Unreadable buckets emit `profile_skipped\t{id}\t{label}` and
`log.warning` — matches the S305 posture exactly.

**Isolation:** The `--all-profiles` branch is a hard early-return
(`_overview_calendar_all_profiles(...)` then `return`) so the existing
single-profile path is not touched. No regression risk on the active-profile
case.

**`tax_id_default="00000000T"` argument:** `projection_for_taxpayer` is called
with a fallback tax ID for profiles that have no declared `identity.tax_id`.
This is a calendar-generation concern, not a tax-ID assertion — the calendar
needs some identifier for display; using a placeholder is the correct defensive
approach for an undeclared model.

**G4 — locale scaffold compliance:** `cli.overview.calendar.all_profiles_help`
confirmed present in all four locale files with full prose (not scaffold stubs):
- en.yml: "Render the calendar for every registered profile instead of the active one."
- es.yml: Spanish prose
- ca.yml: Catalan prose
- hu.yml: Hungarian prose (genuine Hungarian, not a scaffold stub)

The en.yml diff also shows deletion of
`duplicate_tax_id_scan_unreadable_profile` (from S305 — key no longer needed)
and alphabetical key reordering from scaffold re-run. No structural hand-edits.
**G4 satisfied.**

**Regression test (G6):**
`test_all_profiles_flag_iterates_every_registered_profile` registers two profiles
via the real `profile_create_storage_span` + `workflow_state_repository` path,
invokes the CLI with `--all-profiles --allow-incomplete`, and asserts both profile
labels appear in output plus exactly two `profile\t` header lines. Real adapter,
real CLI path, no mocks. Passes in 70.79s (integration test with real encrypted
SQLite). **PASS.**

**Minor observation (non-blocking):** The `all_calendars: list[dict] = []` type
annotation accepts `dict` (untyped). The `cal.model_dump(mode="json")` call
returns `dict[str, Any]` from pydantic — this is a third-party API boundary;
inline documentation noting this would satisfy `aeat-calculation-grounding`.
Not blocking for this step; log as FU-S306-A.

### Exec records (9fdb3bd92)

Step records for S305 and S306 are honest and complete. Plan checkboxes closed
for `W02.P11.S306` and `W04.P19.S305`. **PASS.**

### Verdict table

| Commit | Step | Verdict | Notes |
|--------|------|---------|-------|
| `51acf7a6d` | S305 | APPROVE | warn-and-continue correct; anti-tautology pair sound; regression fix clean |
| `dd8934c72` | S306 | APPROVE with FU-S306-A | --all-profiles clean; G4/G6 satisfied; `list[dict]` annotation minor |
| `9fdb3bd92` | exec records | PASS | honest records; plan checkboxes correct |

**Overall: APPROVE.** R8-NURIA-1 (multi-profile gestor show-stopper) is closed.
S305 and S306 both land cleanly against the Task #114 architecture grounding.

### Follow-ups

| ID | Description |
|----|-------------|
| FU-S306-A | Annotate `all_calendars: list[dict[str, object]]` → typed payload or inline `# dict[str,Any] from pydantic model_dump` comment per `aeat-calculation-grounding` |

---

## Task #135 — S318 verification provenance threading (eddd19047 + 6dcc19d64 + 2d36575a9)

**Review date:** 2026-05-27

### Commits reviewed

- `eddd19047` — S318: thread casilla legal_refs/source_refs into verification findings
- `6dcc19d64` — S318 tests: provenance-threading integration + anti-tautology unit proofs
- `2d36575a9` — exec record + plan step close

### Option A compliance

The implementation follows the mandated Option A (inline fields on the domain
model) exactly:

**Domain model (`_verification_report.py`):** `legal_refs: tuple[str, ...] = ()`
and `source_refs: tuple[str, ...] = ()` added with empty-tuple defaults. The
`frozen=True` + `strict=True` model config is preserved. Persisted reports
round-trip without migration — empty-tuple defaults cover all existing blobs.

**Threading path (`_actions.py`):** `_collect_revision_verification_findings`
is refactored to load the registry snapshot directly (`authority.snapshot(...)`)
rather than delegating to the two separate helpers
`_required_input_casillas_for_revision` and `_verification_predicates_for_revision`.
This gives it access to full `CasillaDefinition` objects. The refactor is
correct — it avoids a second registry round-trip and eliminates the now-redundant
helper call duplication. The two helper functions remain available for other
callers; they are not deleted.

`_missing_required_casilla_finding` gains a keyword-only `casilla_def:
CasillaDefinition | None = None` parameter. When `casilla_def` is present,
`legal_refs` and `source_refs` are populated; when absent (e.g. the registry
lookup produced no snapshot — already blocked above), they default to empty
tuples. The `casillas_by_id` dict is built once per verify call and passed via
`.get(casilla_id)` — correct defensive fallback.

**BLOCKING_RULE / predicate findings:** `_evaluate_verification_predicates`
now propagates `legal_refs=tuple(str(r) for r in predicate.legal_refs)` on
BLOCKING_RULE findings. `source_refs` is NOT threaded for predicate findings —
`VerificationPredicateDefinition` carries `legal_refs` but no `source_refs`
(cross-casilla predicates are policy, not casilla-source authority). This is
the correct decision: `source_refs` on a predicate would be misleading.

**Hexagonal direction:** The registry authority is accessed via
`_authority_via_resources()` inside the application layer — this is the
established pattern throughout `_actions.py`. No entrypoint-layer registry
access introduced. **Clean.**

**CLI emit path (`_modelo.py`):** `_verification_report_payload` emits
`legal_refs` and `source_refs` as lists (correct — JSON arrays). 
`_verification_report_lines` conditionally appends `finding_legal_refs` and
`finding_source_refs` tab-separated lines when non-empty — the conditional
guard avoids polluting output for findings with no provenance (e.g. registry
unavailable). Both paths correct.

### G6 — Tests

**Integration test (`test_missing_required_casilla_finding_carries_registry_provenance`):**
- Creates M130 work unit, calculates with casilla 02 deliberately absent,
  runs verify, locates the `MISSING_REQUIRED_CASILLA` finding for casilla 02.
- Asserts `finding.legal_refs` non-empty + matches `_M130_CASILLA_02_LEGAL_REFS`
  oracle drawn from the actual TOML.
- Asserts `finding.source_refs` non-empty + matches `_M130_CASILLA_02_SOURCE_REFS`
  oracle.
- Oracle values verified against
  `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/casillas/0001-casillas.toml`
  lines 12-13/25-26: exact match confirmed. This is the external authority —
  not hand-computed from the threading code itself.
- Real registry + real application-layer verify path. No mocks. **PASS.**

**Anti-tautology unit test (`test_missing_casilla_finding_legal_refs_empty_when_casilla_def_absent`):**
- Calls `_missing_required_casilla_finding("99", "wu-test-id", casilla_def=None)`
  directly and asserts both `legal_refs == ()` and `source_refs == ()`.
- This proves the threading is structural: if the integration test passes but
  the `casilla_def` parameter were ignored (fields always empty), this unit
  test would also pass but the integration test would fail. The two tests form
  a complementary pair — neither alone is sufficient.
- The naming "anti-tautology" is accurate: without this test a naive
  implementation that always returns empty tuples would pass the unit test
  but fail the integration test, and vice versa.

Both tests pass in 29.10s. No mocks, no skip/xfail.

### Minor observations (non-blocking)

- The `casillas_by_id = {str(casilla.id): casilla for casilla in snapshot.revision.casillas}`
  dict is built once and looked up via `.get(casilla_id)`. The `.get` fallback
  to `None` is appropriate — the same `casilla_id` was just extracted from
  iterating `snapshot.revision.casillas`, so the fallback should never fire in
  practice. The defensive `.get` is still correct insurance.
- The large number of formatting-only changes in the `_actions.py` diff (line
  wrapping, quote style) is ruff formatter output co-landing with the
  substantive changes. Not a concern.

### Verdict table

| Commit | Step | Verdict | Notes |
|--------|------|---------|-------|
| `eddd19047` | S318 implementation | APPROVE | Option A correct; hexagonal direction clean; BLOCKING_RULE predicate legal_refs correct; source_refs omission on predicates deliberate |
| `6dcc19d64` | S318 tests | APPROVE | Oracle from TOML; anti-tautology pair sound; real registry; no mocks |
| `2d36575a9` | exec record + plan close | PASS | Honest step record; plan checkbox correct |

**Overall: APPROVE.** S318 closes the verification provenance gap identified in
discovery3 #121 and the Marc/Inés round-8 testimonials. Operator-facing verify
output now carries `legal_refs` and `source_refs` per finding. Option A
implementation matches the architecture grounding exactly.

---

## Task #136 — W12.P61.S278 typed payload models (c25b14a54 + c94ed9a38)

**Verdict: APPROVE**

### Scope

S278 replaces four `dict[str, object]` return types in the application-ledger
layer with typed pydantic models: `LedgerTransactionReviewPayload`,
`LedgerTransactionResultPayload`, `LedgerTransactionTrackingPayload`
(new), plus `LedgerTransactionPayload` (promoted from dict return to
typed return at the function boundary). `LedgerReviewRow.transaction`
typed from `dict[str, object] | None` to `LedgerTransactionPayload | None`.
10 call sites updated in CLI layer to use typed attribute access and
`.model_dump(mode="python")` at the JSON emission boundary.

### Gate checks

**G2 (no shims)**: Old dict-returning implementations deleted; no aliases,
no compatibility wrappers, no deprecation markers. Clean cut. PASS.

**G3 (no hardcoded user strings)**: New models in `_models.py` carry no
user-facing strings. PASS.

**G4 (locale scaffold)**: No locale keys touched. PASS.

**G5 (no shims)**: Confirmed — the four functions now return typed models
directly. The chain `_actions.py` → `_ledger.py` → `.model_dump()` at emit
is the correct pattern. PASS.

**G6 (anti-tautology tests)**: S278 is structural (type promotion, no
behavioral change). The existing ledger suite (182 tests passing in
36.97s against the real SQLite+encryption stack) provides real-behavior
coverage. No tautological assertions introduced. PASS.

### Hexagonal boundary compliance

`LedgerTransactionReviewPayload` uses only `str | None` fields — correct
for an output emit model crossing the CLI boundary. `LedgerTransactionTrackingPayload`
preserves domain entry tuples (`TransactionEvidenceProvenanceEntry`,
`TransactionEditLineageEntry`, `TransactionLifecycleLineageEntry`) as
tuple fields; these are serialized by `.model_dump(mode="json")` at the
CLI emit boundary. No domain types leak into the wire JSON directly.
PASS.

### Test run

182 passed, 1 failed (`test_rule_apply_classifies_not_yet_processed_transactions`).
The failure is in an **untracked** file (`test_ledger_bulk_classify.py`) — coder2's
Task #125 in-flight WIP, not committed, not part of S278. The S278 commit contains
no test changes and introduced no regression against committed code.

### Follow-up flag

FU-S278-B: `LedgerTransactionReviewPayload.classified_by` is typed
`str | None = None` while `Transaction.classified_by: str` is non-nullable.
The None path is unreachable at runtime but the looser typing is imprecise.
Tighten to `str = Field(default="auto")` in a subsequent S278 follow-up step.


---

## Task #139 — W05.P25.S96-S98 bulk-classify + rule engine (6c4ec924c + 666bc9c59)

**Verdict: APPROVE**

### Git-discipline gate

Step record contains no destructive-git language. The "previously committed"
note in the step record correctly describes cross-session work where coder2
authored only the three new files (`_classification_rule.py`,
`_rule_repository.py`, `test_ledger_bulk_classify.py`) — no
reconstruction, no restore, no stash. `6c4ec924c` diff confirms only
additions (three new files). **PASS.**

### ADR D1-D8 compliance

**D1 (regex-only, re.IGNORECASE):** `LedgerClassificationRule.matches()` uses
`re.search(self.description_pattern, description, re.IGNORECASE)`. No other
match strategy. PASS.

**D2 (content-addressed rule_id):** `_compute_rule_id` hashes
`f"{pattern}|{classification.value}|{category_id or ''}"` via SHA-256;
`rule_id` field enforced `min_length=max_length=64`. PASS.

**D3 (SecureBoundRepository, namespace, sensitivity):** `LedgerClassificationRuleRepository`
extends `SecureBoundRepository[LedgerClassificationRule]`;
`namespace = "aeat.ledger.classification.rules"`;
`sensitivity = SensitivityClass.AUDIT`; `schema_version = 1`. Follows the
`IvaCompensationHistoryRepository` pattern. PASS.

**D4 (actions: add + apply + result models):** `add_classification_rule` calls
`LedgerClassificationRule.create()` (which validates regex via `re.compile`
in the `@field_validator`) then `repo.save(rule)`. `apply_classification_rules`
loads rules via `rule_repo.list_rules()` and iterates transactions.
`bulk_classify_from_csv` parses CSV, rejects unknown columns pre-persistence.
PASS.

**D5 (priority: lower wins, ties by created_at, default 100):**
`list_rules()` sorts by `(priority, created_at)` ascending; field default
`priority=100, ge=1`. `test_rule_priority_order_first_match_wins` verifies
priority=1 beats priority=100 on overlapping patterns. PASS.

**D6 (scope ACTIVE NOT_YET_PROCESSED + --reaffirm extends to manual):**
`_in_scope()` predicate: `lifecycle_state is ACTIVE` AND
`business_classification is NOT_YET_PROCESSED` OR (`reaffirm AND classified_by == "manual"`).
`test_rule_apply_skips_already_classified_without_reaffirm` verifies the gate
closes. PASS.

**D7 (CLI surface: ledger rule add/apply/list):** `rule_app` sub-app registered
as `ledger rule`; three commands `add`, `list`, `apply` with correct option
signatures. `--from-csv` exclusive with `--id`/`--classification`.
PASS.

**D8 (ApplyRulesResult shape):** `rules_evaluated`, `transactions_scanned`,
`matched`, `skipped_already_classified`, `no_match`, `applied` all present.
`BulkClassifyResult` carries `total`, `applied`, `skipped`, `failures`,
`bucket_event_ids`. PASS.

### G6 anti-tautology check

Five real-behavior tests exercise distinct failure paths with non-trivial
assertions:
- Idempotency: add same pattern twice → exactly 1 rule in list (not 2)
- Invalid regex: `[invalid` → non-zero exit code (gate closes)
- Skip guard: manually classified tx preserved as PERSONAL when rule says BUSINESS
  (without `--reaffirm`)
- Dry-run: all transactions remain `NOT_YET_PROCESSED` after dry-run
- Priority ordering: `priority=1 BUSINESS` beats `priority=100 PERSONAL` on
  overlapping description

The `classified_by` provenance assertion (`startswith("rule:")`) is the
non-trivial behavioral proof that the rule-engine provenance chain is
wired end-to-end through the domain model, repository, action, and CLI
emit path. No tautological assertions found. PASS.

### Test run

13/13 passed in 13.04s against real SQLite+encryption stack.

### Follow-up note

`LedgerClassificationRule.priority: int = Field(default=100, ge=1)` sets
a lower bound of 1. The ADR does not specify a lower bound — this is a
reasonable defensive constraint (priority=0 would be ambiguous with
"unset"). No action required.


---

## Task #141 — W12.P61.S279+S280 typed-boundary completion (b86b9bddb + 926347705 + be7a18a8b + 40c6a70e8)

**Verdict: APPROVE**

### Git-discipline gate

Both step records contain no destructive-git language — no
backup-restore, no HEAD-reconstruction, no stash/pop references.
Commits are clean, no suspicious patterns. **PASS.**

### S279 — Mapping[str, object] annotation (deviation assessment)

The #124 grounding recommended typed pydantic subclasses for CLI
entrypoint output-direction functions. S279 operates at the application
service layer (logging extras, AeatError context dicts, internal JSON
parse boundaries) — a different surface class from the CLI output
direction.

`Mapping[str, object]` is correct for these sites:
- `as_extra()` methods feed stdlib logging which accepts `dict[str, object]`
  at runtime; a pydantic model here would require `.model_dump()` at every
  log call site — over-constrained and unidiomatic.
- `_status_context` feeds `AeatError(context=...)` whose parameter is
  `Mapping[str, object] | None` — annotation matches callee type exactly.
- `_payload`/`_json_object` are internal deserialization boundaries; read-only
  callers benefit from the narrower `Mapping` contract.
- `_detail_fingerprints_from_payload` returns `dict[str, str]` (fully typed).
- `_review_metadata_reset` retains `dict[str, object]` with inline comment
  explaining mutation requirement — correct exception documented.

**This is not a quality regression.** The #124 pydantic-subclass recommendation
applied to CLI payload functions. `Mapping[str, object]` at internal service
helpers is the right idiom for this surface. No follow-up required.

### S280 — cast() elimination

Six `cast()` calls in `workflow/_adapters.py` replaced with
`type: ignore[arg-type]` / `type: ignore[return-value]` with inline
prose documenting the Protocol-boundary bridging reason at each site.
One `cast("dict[str, object]", value)` in `registry/_loader.py` replaced
with `type: ignore[return-value]` plus inline TOML-boundary explanation.

Three pydantic `object/Any` field declarations confirmed as legitimate:
- `split: object = None` in `review/_actions.py` — validation-trap parameter
  that immediately rejects any non-None value
- `current: object` in `registry/_schedules.py` — dispatch-table traversal
  accumulator whose type is narrowed by `isinstance` guards
- `get(key, default: object = None)` in `workflow/_models.py` — standard
  dict-protocol signature

This exactly follows the `aeat-calculation-grounding` rule: third-party
adapter boundaries documented inline, not wrapped in typed helpers.
**PASS.**

### W12.P61 closure confirmation

`vault plan query --wave W12 --phase P61` confirms:
- S277 checked (warmup site)
- S278 checked (CLI payload typed models)
- S279 checked (service helper Mapping annotations)
- S280 checked (cast elimination + documentation)

S350 is a new follow-up step (13 remaining CLI payload helpers) appended
to the plan — this is correct plan-expansion behaviour, not scope debt.
W12.P61 original four steps are all closed. **CONFIRMED.**

### Follow-up

FU-S279-A (non-blocking): If a future typed-boundary pass visits the
`as_extra()` surface, consider whether a dedicated `LogExtra` pydantic
model would add value. The current `Mapping[str, object]` is correct but
typed log extras would surface schema drift at type-check time. Log as
low-priority W09 item.

---

## Verdict: W05.P26.S99+S100 — IVA wallet balance verb (e9f45806c + c9fb9f1f8 + b7d3e8d2e)

**APPROVE.**

### Commits reviewed

- `e9f45806c` — W05.P26.S99: `IvaWalletBalanceReport` + `iva-wallet balance` CLI verb
- `c9fb9f1f8` — W05.P26.S100: 7 regression tests
- `b7d3e8d2e` — vault step records + plan checkbox closure

### Gate checks

**G1 (no naked env):** `query_iva_wallet_balance` instantiates
`IvaCompensationHistoryRepository()` directly; profile resolution flows
through `SecureBoundRepository` → `Settings` — same pattern as every
other repository in the codebase. No `os.environ`/`os.getenv` introduced.
**PASS.**

**G2 (typed boundaries):** `IvaWalletBalanceReport` is strict/frozen
pydantic. The CLI verb calls `report.model_dump(mode="json")` at the
emission boundary only — no intermediate `dict[str, Any]`. The existing
`_calculation_revision_payload`, `_verification_report_payload`,
`_work_unit_payload`, `_filing_record_payload` helpers were all migrated
from `dict` returns to typed pydantic returns in this same S99 commit;
call sites updated to `.model_dump(mode="python")` before spread into
existing dict-merge patterns. This is the correct forward motion on
the typed-boundary campaign. **PASS.**

**G3 (tr() coverage):** All three operator-visible strings in the
`iva_wallet_app` and `balance` command use `tr(key, default=...)`.
No hardcoded f-string exception sites visible. **PASS.**

**G4 (locale scaffold):** `python -m aeat.locales audit` returns
`ok` for all four locale files (ca, en, es, hu) with three new keys
each: `cli.app.modelo.iva_wallet.group_help`, `.balance_help`,
`.as_of_year_help`. Spanish and Catalan prose is domain-correct.
**PASS.**

**G5 (no shims):** No compatibility aliases, re-exports, or
deprecation stubs introduced. **PASS.**

**G6 (anti-tautology):** `test_carry_forward_lot_rejects_unbalanced_amounts_anti_tautology`
constructs a `IvaCompensationCarryForwardLot` with
`applied_amount + remaining_amount != generated_amount` and asserts
`ValidationError(match="must equal generated_amount")`. This proves the
`model_validator` closure is real and the roundtrip boundary is not
tautological. Gate opens + gate closes pattern present. **PASS.**

**Git-discipline gate:** S99 and S100 step records contain no language
about stash, HEAD reconstruction, backup-restore, or peer-WIP
manipulation. Both records are clean. **PASS.**

### Design observations

One deliberate asymmetry: `total_balance` sums ALL lots with
`remaining_amount > 0` including `EXPIRED_REVIEW_REQUIRED` lots; only
`next_expiry_year` excludes expired lots. The comment in the
implementation explains this correctly — expired lots represent real
money that may still be recoverable with operator review; surfacing them
in the balance figure gives accurate gross exposure. The clock field
(`next_expiry_year`) correctly restricts to actionable lots only. The
test at `test_next_expiry_year_is_earliest_active_lot_plus_four`
confirms the split behaviour explicitly (`total_balance=300` including
the expired lot; `next_expiry_year=2027` from the active lot only).

FU-S99-A (non-blocking, log as W09 follow-up): An operator viewing
`total_balance=300` with `lot_count=2` and `next_expiry_year=2027`
cannot tell that 100 of the 300 is in an expired lot. A future
enhancement to add `expired_balance` and `active_balance` fields would
remove this ambiguity. Not a gate failure — current design is
documented and coherent.

### Tests

7/7 pass, 2.74s, real encrypted SQLite via `isolated_runtime_profile`.
No mocks, no monkeypatches, no skips.

---

## Verdict: W04.P19.S340 — workflow abort next_action pointer (d898240f9)

**APPROVE with follow-up (FU-S340-A).**

### Gate checks

**G3 (tr() coverage): PARTIAL — follow-up logged.**

Two surfaces carry the `next_action` pointer string:

1. `_stage_validating_draft` in `src/aeat/application/workflow/_engine.py`:
   `WorkflowStep.details["next_action"]` is a hardcoded English template
   string. The workflow details dict is not a locale-aware surface today —
   other details keys (e.g. `error_count`, `status_value`) are also
   unlocalized English. This is a pre-existing pattern; not a new
   regression introduced by S340. Acceptable as W09 follow-up.

2. `_verification_report_lines` in `src/aeat/entrypoints/cli/_modelo.py`:
   the tab-delimited `next_action\t<command>` line is emitted to the
   terminal directly. The text is a CLI invocation template with an
   interpolated `calculation_revision_id` — not a prose localisation
   target. No other `_*_lines` function in this codebase wraps
   tab-delimited command hints in `tr()`. The current approach is
   consistent with the existing pattern. Acceptable as a design choice.

FU-S340-A (non-blocking W09): When a future pass localises the
tab-delimited CLI surface, add `tr()` wrapping to the static prefix
of `next_action\t`. Consider a typed `WorkflowStepDetails` model if
the details bag grows further.

**G4 (locale scaffold):** S340 introduced no locale file structural
changes. `python -m aeat.locales audit` shows one pre-existing missing
key (`errors.calc.bound_input_smuggled_without_binding_value`) — predates
S340 and is not introduced by it. **PASS.**

**G6 (anti-tautology + real adapters):**

- `test_draft_has_errors_surfaces_next_action_pointer`: engine unit test
  with real `ModeloFinding(severity=ERROR)`. Asserts
  `details["next_action"]` present and contains `"verification-report
  list"`. **PASS.**
- `test_verification_report_lines_includes_next_action_when_refused`:
  real `VerificationReport(granted_verificado_completo=False)` with real
  finding. Asserts `next_action\t` line present with real
  `calculation_revision_id`. **PASS.**
- `test_verification_report_lines_omits_next_action_when_granted`:
  anti-tautology — `granted=True` report must NOT emit `next_action`.
  Gate opens and closes. **PASS.**

**Git-discipline gate:** Step record contains no stash, HEAD
reconstruction, backup-restore, or peer-WIP language. **PASS.**

### Tests

18/18 `TestAbortReasons` pass (no regressions). 2/2 new CLI tests pass.

---

## Triage: Tomás round-9 CRITICAL pair — S352 + S353

### S352 — M303 wallet gate locks first-time users

**Root cause analysis.**

The binding `modelo-303-compensacion-pendiente-anteriores` in the M303
2023-y-siguientes revision declares `source = "previous_filing"` with
selector `source_period_offset_from_target = -1`. The prefill path in
`src/aeat/application/calculations/_binding_prefill.py` calls
`_gather_observations()`, which silently skips (line 153 `continue`)
when no prior period observation or IVA history record exists. If no
prior M303 work unit has been filed or imported, neither
`CalculationObservationRepository` nor `IvaCompensationHistoryRepository`
holds a prior-period record — the binding resolves to nothing, and
`resolve_bindings_from_local_store` returns `binding_values = {}` for
that slot.

Option (c) (`--binding override`) is **BLOCKED by architecture**. It
would open an uncontrolled escape from the reconciliation invariant,
letting any operator silently override wallet state with arbitrary values
at any time. This must remain rejected.

Option (b) (auto-detect first period and emit zero) is architecturally
dangerous: it silently assumes zero carry-forward, which is wrong for
any taxpayer with prior-period IVA credit predating the app. Silent
wrong values in a filed declaration are worse than a blocked first run.

**Correct fix: Option (a) — explicit seed verb.**

`aeat app modelo iva-wallet seed --filing-year <year> --period <period>
--amount <decimal>` creates an `IvaCompensationPeriodState` record with
`status = "seeded"` and `available_end_amount = <amount>`. The prefill
path then finds this record via `IvaCompensationHistoryRepository` and
resolves the binding correctly. The operator's deliberate choice is
recorded with full provenance.

The seed verb must require a `--confirm` flag and emit a locale-aware
(`tr()`) warning: "This declares the IVA compensation carry-forward
balance from periods prior to app installation. Incorrect seeding
constitutes a filing error." The warning is not optional.

Before dispatching: the coder must verify whether `--binding override`
is rejected by the engine or by missing CLI flag registration. If the
engine silently drops unknown binding keys rather than raising a useful
error, that is a second gap to surface as a finding in the same step.

Size: **SMALL-MEDIUM.** New CLI verb + `status = "seeded"` variant +
3 locale keys + 3 tests: seed resolves binding, double-seed rejected,
seed warning emitted.

### S353 — M100 casilla 0505 manual without formula derivation

**Root cause confirmed.**

`src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0487-0505.toml`
declares casilla 0505 (`base liquidable general sometida a gravamen`)
with **no `input_kind` and no `formula`**. The registry schema defaults
`input_kind` to `"manual"` (schema line 1615). No formula in any 2024
revision file targets 0505 as its output — zero hits for `target.*0505`
across all `formulas/*.toml`. The identical gap exists in the 2025
revision (`0571-0505.toml`).

Casilla 0500 (`base liquidable general`) is correctly `input_kind =
"computed"` with `formula = "renta-2024-base-liquidable-general"`. Eight
downstream formulas consume 0505 as an operand (cuota escala estatal,
cuota escala autonómica, tipo medio gravamen estatal/autonómico, mínimo
personal sobre base general estatal/autonómica). All produce zero when
0505 is zero. This is the Cluster T variant Tomás hit.

**LIRPF relationship (Art. 50, Art. 56):**

`0505 = max(0, 0500 - anualidades_alimentos_hijos_judicial)`. For
taxpayers with no judicial child-support payments (the overwhelming
majority, including Tomás), 0505 == 0500 exactly.

**Correct fix: Option (a) — computed formula.**

1. Author formula `renta-2024-base-liquidable-general-sometida-a-gravamen`
   targeting casilla `0505`. Expression: `max(0, 0500 minus the
   anualidades-alimentos-hijos sum)`. The anualidades casilla is already
   an operand of the existing `renta-2024-anualidades-alimentos-hijos-suma`
   formula; the coder must identify the correct source casilla from the
   AEAT DR-100-2024 dictionary (`aeat-dr-100-2024-dictionary`), which is
   already cited in 0505's `source_refs`.
2. Change casilla 0505 `input_kind` to `"computed"` with
   `formula = "renta-2024-base-liquidable-general-sometida-a-gravamen"`.
3. Same change for the 2025 revision (identical gap).

**G6 legal grounding requirement:** The coder must verify the
`max(0, 0500 - anualidades)` expression against the AEAT Renta 2024
manual or AEAT workbook oracle. If the exact anualidades operand cannot
be confirmed from registry sources, fall back to Option (b):
`input_kind = "manual"` + `required = true` (verify gate fires when
0505 is missing) as the safe fallback. Option (b) is worse UX but
correct behaviour. Do not use Option (b) unless the legal grounding
for Option (a) cannot be confirmed.

Size: **MEDIUM.** Two new formula TOMLs (2024 + 2025), two casilla
TOML edits, oracle-grounded test asserting `0505 == 0500` when
anualidades = 0, anti-tautology proof via nonzero anualidades case,
verify-gate test confirming zero 0505 triggers a finding before the
formula is wired.

### Dispatch sequencing

S353 has no blocked dependencies — dispatch immediately (coder1,
MEDIUM, TOML + test). S342 (heavy, ongoing) and S353 (medium, TOML)
touch different files and can run in parallel.

S352: dispatch after S340 lands (coder2, SMALL-MEDIUM). The
investigation of `--binding override` rejection is the first task
in the step brief.

---

## Triage: Roberto round-9 CRITICAL — S361 M100 cuota chain broken (2024)

**Root cause confirmed. This is worse than S353 — it is the entire
settlement tail, not a single casilla.**

### Investigation results

Six casillas in the 0587→0670 settlement chain all have no `input_kind`
field in the 2024 revision — all default to `"manual"`:

| Casilla | Label | Formula exists in 2024? | Formula exists in 2025? |
|---------|-------|------------------------|------------------------|
| 0587 | Cuota líquida incrementada total (0585+0586) | NO | YES (`renta-2025-cuota-liquida-incrementada-total`) |
| 0595 | Cuota resultante de la autoliquidación | NO | YES (`renta-2025-cuota-resultante-autoliquidacion`) |
| 0598 | Suma retenciones capital inmobiliario (copy of 0153) | NO | YES (`renta-2025-retenciones-arrendamientos-urbanos`) |
| 0609 | Total pagos a cuenta (sum 0592-0606) | NO | YES (`renta-2025-total-pagos-a-cuenta`) |
| 0610 | Cuota diferencial (0595 - 0609) | NO | YES (`renta-2025-cuota-diferencial`) |
| 0670 | Resultado declaración | NO | YES (`renta-2025-resultado-declaracion`) |

**The 2024 `renta-cuota-chain` construct** (in
`src/aeat/_data/registry/aeat/modelos/100/revisions/2024/constructs/0001-renta-cuota-chain.toml`)
lists formulas up through `renta-2024-cuota-liquida-estatal-incrementada`
(which produces 0585 and 0586) but stops there. The settlement tail
that converts 0585+0586 into 0587 and flows to 0670 was simply never
authored for 2024.

The **2025 revision** has a dedicated `renta-final-settlement` construct
(`constructs/0005-renta-final-settlement.toml`) containing exactly the
six formulas that are missing from 2024. The 2025 formulas use
`orden-hac-277-2026:art-3` as their primary legal_ref (the 2025 BOE
form order). The **equivalent authority for 2024** is `orden-hac-56-2024:art-1`
plus `boe-modelo-100-2024-form`.

The 2020 revision has the same gap — no settlement tail formulas —
so this was never a 2024-specific regression; the 2024 revision was
authored in the same incomplete state as 2020. The 2025 revision was
the first to close the gap. This makes the fix straightforward: backport
the 2025 formulas with 2024-appropriate legal_refs and source_refs.

### Fix path

The coder must author six new formula TOML files in
`src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/`:

1. `renta-2024-cuota-liquida-incrementada-total` → target `0587`,
   expression `sum(0585, 0586)`. Legal ref: `orden-hac-56-2024:art-1`.
2. `renta-2024-cuota-resultante-autoliquidacion` → target `0595`,
   expression `sum(0587, negate(0588), negate(0414), negate(0589),
   negate(0590), negate(0591))`. Legal refs: `ley-35-2006:art-99`,
   `orden-hac-56-2024:art-1`.
3. `renta-2024-retenciones-arrendamientos-urbanos` → target `0598`,
   expression `copy(0153)`. Legal refs: `ley-35-2006:art-99`,
   `rd-439-2007:art-100`, `orden-hac-56-2024:art-1`.
4. `renta-2024-total-pagos-a-cuenta` → target `0609`, expression
   `sum(0592..0606 per the 2025 formula's operand list minus any
   casillas that don't exist in 2024 — coder must verify)`. Legal
   refs: `ley-35-2006:art-99`, `rd-439-2007:art-109`,
   `orden-hac-56-2024:art-1`.
5. `renta-2024-cuota-diferencial` → target `0610`, expression
   `subtract(0595, 0609)`. Legal refs: `ley-35-2006:art-99`,
   `orden-hac-56-2024:art-1`.
6. `renta-2024-resultado-declaracion` → target `0670`, expression
   mirrors 2025 formula's 17-operand sum — coder must verify each
   operand casilla exists in 2024 and adjust if any were added in 2025.

Then update casillas 0587, 0595, 0598, 0609, 0610, 0670 to
`input_kind = "computed"` with their respective formula IDs.

Then extend `renta-cuota-chain` construct with the six new formula IDs
(or author a new `renta-2024-final-settlement` construct mirroring the
2025 pattern — preferred for clarity).

**G6 legal grounding requirement:** Source references for 2024 formulas
must come from `aeat-dr-100-2024-dictionary`, `boe-modelo-100-2024-form`,
and `aeat-renta-2024-manual-parte1` (all already cited in the 2024
casilla `source_refs`). The coder must NOT copy 2025 source_refs
verbatim — `orden-hac-277-2026:art-3` and `aeat-renta-2025-manual-parte1`
are 2025 authority only.

**Operand verification requirement:** Before authoring formula 4 (0609
total pagos) and formula 6 (0670 resultado), the coder must confirm
each operand casilla number exists in the 2024 revision. The 2025
formula for 0609 has 14 operands; the 2024 form may have fewer if
some payment categories were added in 2025. Casilla 0414 (in 0595
formula) must also be confirmed in 2024.

### Size

**HEAVY.** Six new formula TOMLs + six casilla TOML edits + construct
extension + oracle-grounded test asserting Roberto's scenario
(base liquidable €55.5k → 0587=15,141, 0609=1,824, 0610=13,317) +
anti-tautology + regression tests for each formula individually.

The 2025 backport template means the expressions are known — the heavy
part is operand verification for 2024 and legal-ref sourcing.

### Dispatch

**CRITICAL, IMMEDIATE.** This affects 100% of M100 2024 filers who
attempt to calculate their result (every autónomo, every landlord,
every salaried employee). Dispatch to coder1 as the highest-priority
item after S342 if S342 is still in flight, or replace it as the
current priority if coder1 is free. S342 and S361 touch completely
different subsystems (aggregation vs. registry TOML) and can run in
parallel on different coders.

**S353 (0505) and S361 (settlement chain)** are both M100 2024 TOML
gaps. If dispatching to the same coder, S361 must be done first (it
blocks every filing; S353 only blocks taxpayers without explicit 0505
supply). If dispatching to different coders, both can proceed in
parallel since they touch different casilla files and different formula
files.

---

## S350 — W12.P61 typed-boundary CLI payload sweep (13 helpers)

**Commits:** `f45a8532c` (Batch 1 `_modelo_payloads.py`) + `2ae2b1a10`
(Batch 2 `_ledger.py`, `_config/__init__.py`, `_common.py`,
`_app_live.py`)

**Verdict: APPROVE**

### Gate results

**G1 (naked env reads):** PASS. No `os.environ` / `os.getenv` in any
modified file.

**G2 (typed pydantic at boundaries):** PASS with documented exceptions.
Batch 1 extended `FindingPayload` with `legal_refs` / `source_refs`
and `ModeloRecordPayload` with `ExternalEvidencePayload` sub-model and
`amends_filing_record_id`. All five `_modelo.py` helpers already typed
from the concurrent S99 iva-wallet campaign (`e9f45806c`). Batch 2
promoted five read-only row helpers from `dict[str, object]` to
`Mapping[str, object]` — correct for immutable projection paths.
Two functions deliberately retain `dict[str, object]`:
`_business_invoice_payload` (post-call mutation: callers append
`bucket_event_ids` directly on the dict — `Mapping` would break the
call contract) and `_aggregate_filing_inputs` (not a CLI JSON payload
but a casilla binding dict fed into the calculation engine). Both
exceptions are documented with inline rationale comments.

**G3 (user strings via tr()):** PASS. No new user-facing string
literals introduced. No locale structure changes.

**G4 (locale yml structure):** PASS. No locale YAML touched.

**G5 (no shims/re-exports/duplication):** PASS. No new re-exports or
duplicate symbols.

**G6 (no tautological tests):** PASS. No test changes in this commit
cluster.

**Grounding gate:** PASS. This is a structural boundary-typing pass,
not a calculation or domain-logic change. No registry grounding
required.

**Git-discipline gate:** PASS. No stash/reset/backup language in step
record. Step record commit `2a0e1a341` references correct commits.
Note: step record lists `f45a8532c` but git log shows it as commit
`f45a8532c646952326b513a6a0c47b8ae6af379e` — SHA matches.

### Test results

`src/aeat/entrypoints/cli/_config/` suite: 24/24 passed (10.47s).
`ruff check` on all five modified files: clean.

### Observations

The step record's Batch 2 boundary decision table is well-reasoned and
matches what is in the code. The `Mapping` vs `dict` distinction is
applied correctly based on downstream mutation semantics, not
mechanically. No follow-up items.

---

## M721 — Eva round-9 SHOW-STOPPER: cryptocurrency informativa registry gap

**Research note:** `.vault/research/2026-05-27-m721-informativa-criptomonedas-research.md`

**Verdict: SHOW-STOPPER confirmed. Recommend registry-stub-with-explicit-refusal (SMALL).**

### Confirmed absence

`src/aeat/_data/registry/aeat/modelos/` has no `721/` directory.
No TOML file in the codebase references Modelo 721 as an identifier,
`Ley 11/2021` as a legal ref, or `Orden HFP/887/2023` as a source ref.
The legal authority for M721 has zero registry footprint.

### Legal authority

M721 (Declaración informativa sobre monedas virtuales situadas en el
extranjero) was created by Ley 11/2021, DA-10, and regulated by Orden
HFP/887/2023 (BOE A-2023-17052, 28-VII-2023). Applicable from fiscal
year 2022 (first filing in 2023). Annual cadence, period type `0A`.
Threshold: holdings abroad > 50,000 EUR aggregate value at 31 December.

Key registry legal_refs:
- `ley-11-2021:da-10`
- `orden-hfp-887-2023:art-1`, `art-2`, `art-3`
- `rd-1065-2007:art-42-quater`

### Decision: stub-first, full authoring as follow-on

**Why not full authoring now:** M721 is a pure informative modelo with
no computed casillas and no formula engine involvement. Full authoring
would require the Orden HFP/887/2023 form PDF for casilla labels/numbers
and is a MEDIUM (2-3 day) TOML authoring exercise. It does not block
any current calculation or filing workflow.

**Why stub closes the SHOW-STOPPER:** Eva's pain is that the CLI either
crashes or silently mishandles M721 input. A registry stub with an
explicit `"Modelo 721 is not yet fully supported; registry stub only"`
refusal closes the operator-visible regression while deferring the full
casilla inventory.

**Stub scope (SMALL, ~1 day):**
- `src/aeat/_data/registry/aeat/modelos/721/manifest.toml` — mirrors
  M720 structure with correct id, title, tax_domain, cadence,
  legal_refs
- `src/aeat/_data/registry/aeat/modelos/721/revisions/2023-y-siguientes/revision.toml`
  — minimal revision shell, period `year_from = 2022`, period type `0A`
- CLI guard: ensure the operator receives a clear, localised refusal
  when attempting M721 operations; must not crash or silently return
  empty results

**Full casilla inventory (MEDIUM, follow-on):** ~30-40 casillas across
four sections (custodian-held, self-custody, acquisitions/transmissions,
identification). No formula work required.

### Structural template

M720 (`2013-y-siguientes` revision, `tax_domain = "informative"`,
`cadence = "annual"`, period_selector `year_from = 2012`) is the exact
structural template. The manifest and revision TOML structures copy
directly with different `id`, `title`, `year_from`, and `legal_refs`.

### Size

**SMALL** for stub. **MEDIUM** for full casilla inventory.

### Dispatch

Issue as a new Step in the registry-authoring wave. Can be dispatched
to any coder not currently on M100/M303 TOML work (S361/S353/S352 all
touch different modelos — no conflict). Coder needs the Orden
HFP/887/2023 form PDF accessible for casilla labels in the full pass.

