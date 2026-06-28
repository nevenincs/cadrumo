---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-audit]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-08-cli-backend-boundary-adr]]"
  - "[[2026-04-25-error-code-registry-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-error-registry-exhaustiveness-invariant-adr]]"
  - "[[2026-05-13-identity-adr]]"
---


# `cross-domain-continuity` audit: `wave-1-commit-review`

## Scope

Wave-1 breakpoint review covering every commit on `chore/eliminate-shims`
that implements W01.P01–P08 (S02–S33 less the breakpoint Step itself).
Reviewed against the plan (`2026-05-26-cross-domain-continuity-plan.md`),
the four primary ADRs (CLI-backend-boundary, error-code-registry,
exhaustiveness-invariant, identity), and the source-hygiene / architecture
rules. Each commit receives a verdict: ACCEPT, ACCEPT-WITH-FOLLOWUP, or
REJECT.

---

## Commit Verdicts

### W01.P01.S02+S03 — `CliStoredDataValidationBoundaryError` class + registry (cb0c684f8 + f864d72fd)

**ACCEPT-WITH-FOLLOWUP**

The class definition in `src/aeat/entrypoints/cli/_errors.py` is correct:
typed `original_exception: ValidationError`, distinct locale key
`errors.storage.stored_data_validation_boundary`, `suggestion="aeat config repair"`.
The `__init__` signature wraps `ValidationError`, not the raw
`StoredProfileDriftError`, which is the right contract: the CLI boundary
adapter holds the pydantic detail, not the domain wrapper.

`f864d72fd` correctly moved the registry entry from `_application.py` to
`_entrypoints.py` and aligned category/code to INTEGRITY per the PM override.
The final state in `_entrypoints.py` — `code="INTEGRITY_STORED_DATA_VALIDATION_BOUNDARY"`,
`category=ErrorCategory.INTEGRITY`, `message_key="errors.storage.stored_data_validation_boundary"` — is
consistent with the exhaustiveness-invariant ADR and the error-code-registry ADR.

**Follow-up (FU-B closed):** `__all__` in the final committed state no longer
contains `build_error_envelope` or `json_output_requested`. W09.P41.S201
(logged by PM) is satisfied; no residual here.

**Minor open item (FU-C):** `_I18N_STRICT_PLACEHOLDERS` (a private name) is
exported in `src/aeat/core/i18n/_render.py`'s `__all__` via commit `b17876feb`.
Private names beginning with underscore must not appear in `__all__`; only
`UnmatchedPlaceholderError` and the existing public surface should be exported.
Low severity; test consumers that import it directly still work. Add to W09.

---

### W01.P01.S04 — Locale strings (29dca90f4 + 73bbc293e)

**ACCEPT**

Four-language locale strings (`es`, `en`, `ca`, `hu`) added correctly under
`errors.storage.stored_data_validation_boundary`. The follow-up migration
(`73bbc293e`) correctly moved the initial `errors.refused.*` keys to the
`errors.storage.*` namespace. No structural yaml drift; keys consistent with
the locale cli rule. No `%{name}` placeholders in the locale value that are
unmatched at call sites — the context dict supplies `recovery`.

---

### W01.P01.S05 — `StoredProfileDriftError` + repository wrap (8984a9186)

**ACCEPT**

Domain error class placed correctly in `src/aeat/domain/user_profile/_errors.py`
(not entrypoints, not application layer), inheriting from `UserProfileError`.
Carries `profile_id: str` and `original_exception: ValidationError`.
Both `load()` and `iter_records()` in `src/aeat/application/user_profile/_repository.py`
are wrapped. The `iter_records()` site uses `self._bucket_id` as the context
identifier when the hashed key is unavailable — comment documents the
limitation. Registry entry in `_application.py` with
`code="INTEGRITY_STORED_PROFILE_DRIFT"`, `category=ErrorCategory.INTEGRITY`
is the correct placement for domain-layer errors.

Hexagonal boundary is clean: domain error defined in domain, catch-and-wrap in
application repository, CLI boundary re-wraps in `command_error_boundary`.
No leak upward.

---

### W01.P01.S06 — `command_error_boundary` discriminator (c940ffb67)

**ACCEPT**

The `StoredProfileDriftError` arm is inserted **before** the broad `AeatError`
arm, which is required because `StoredProfileDriftError` is itself an `AeatError`
subclass. The discriminator is by typed exception, not by `ValidationError`
field-path introspection, consistent with the architecture-specialist grounding
verdict. The `_UNDER_TEST.get()` re-raise path is maintained.

The import `from ...domain.user_profile._errors import StoredProfileDriftError`
introduces a private-path import (`_errors`) from the entrypoints layer into the
domain layer. The project convention (observed throughout `_errors.py` and the
CLI) tolerates this for typed exception discrimination at boundary adapters; no
violation.

---

### W01.P01.S07 — Boundary tests (0b2f1e4b1)

**ACCEPT**

Three real-CLI tests in `src/aeat/entrypoints/cli/test_errors_boundary.py`:
corrupt-stored-profile yields stored-data message; corrupt-stored-profile does
not fall through to unexpected-error arm; malformed CLI input yields
input-time message. No mocks; uses `isolated_runtime_profile` fixture with real
KEK/DEK and real SQLite. Anti-tautology structure is sound: the tests assert
distinct message presence/absence for the two error families. The seeding
approach (direct `UserProfileLifecycleRepository.save` + deliberate JSON
corruption) exercises the real deserialization path.

---

### W01.P03.S08–S12 — Ledger per-verb validation discriminator (aff4a4c7e)

**ACCEPT**

`ledger_update`, `ledger_allocate`, `ledger_split` each wrap their mutation
calls in `try/except ValidationError as exc: raise _ledger_validation_bad(exc)`.
`ledger_list` and `ledger_view` carry documentation notes explaining no
`ValidationError` path exists at the CLI input layer (upstream fix is S05).
This matches the re-grounded architecture verdict.

Pattern mirrors `ledger_classify` (the reference implementation). No
`ValidationError` suppression, no double-catch.

---

### W01.P03.S13 + W01.P04.S16 — Validation-path tests + reaffirmation coverage (650cb762c)

**ACCEPT**

`test_ledger_validation_paths.py`: five real-CLI tests for
`add`/`update`/`allocate`/`split`/`classify`. Each drives a validator-triggering
flag and asserts field message reaches the operator rather than the generic
boundary. No mocks.

`test_actions.py` additions: four unit tests for the no-op bypass:
`reaffirm=False` returns stored transaction without events; `reaffirm=True`
bypasses outer guard but inner guard applies; `reaffirm=True` with net-change
succeeds and emits `CLASSIFIED`; different classification bypasses the no-op
guard (anti-tautology). Tests are non-tautological: the anti-tautology case
actively verifies the guard is discriminating, not always-pass.

---

### W01.P04.S14 — Re-affirmation no-op bypass (bb6c28f17)

**ACCEPT-WITH-FOLLOWUP**

`_command_matches_current` compares all 19 named fields of
`ManualLedgerTransactionCommand` against the stored `Transaction`. The early
return in `update_manual_transaction_fields` correctly fires only when
`"business_classification" in patch.model_fields_set` AND all fields match.

**Minor concern:** `_command_matches_current` compares `command.attachment_ids`
against `current.attachment_ids`. If `attachment_ids` on `Transaction` is a
mutable container type, equality comparison depends on collection identity vs
value equality. This is low-risk if pydantic freezes the field, but worth a
comment. Not a blocking defect. Add to W09 minor list.

---

### W01.P04.S15 — `--reaffirm` flag (dc38dcc43)

**ACCEPT**

Flag added to `ledger classify` CLI verb and threaded through to
`update_manual_transaction_fields` as `reaffirm: bool`. Backend function
signature extended minimally. Flag is documented in the CLI help. No business
logic in the CLI layer.

---

### W01.P05.S17 — `_decimal_value` lowercase canonical bools (17a0c3023)

**ACCEPT**

Two-line change: `"true"` and `"false"` comparison already case-insensitive via
`.lower()`. This Step confirms the normalisation covers the lowercase canonical
form. Minimal, correct.

---

### W01.P05.S18 — `_coerce_profile_fact_value` bool promotion (ba5af08c5)

**ACCEPT**

`_coerce_profile_fact_value` in `src/aeat/domain/user_profile/_values.py` now
promotes lowercase `"true"`/`"false"` strings to Python `bool` before the union
resolver runs. This is the correct point of coercion: at ingestion before the
typed `ProfileFactValue` is stored, not at consumption. Downstream consumers
receive a typed `bool`, not a string.

---

### W01.P05.S19+S20 — Typed-value preservation + bool channel guard (805008c5c)

**ACCEPT**

`_profile_fact_index` return type changed from `dict[str, str]` to
`dict[str, ProfileFactValue]`. `str(fact.value)` removed; typed value stored
directly. `_decimal_value` now accepts `object` and branches via
`isinstance(value, bool)` (before `isinstance(value, int)`, correct given
`bool` is a subclass of `int`). Legacy string-encoded path retained for
backward compatibility.

Bool channel guard at enum routing site: `isinstance(value, bool)` raises
`ProfileBindingResolutionError` with a clear message before the bool could
reach `enum_values`. `_resolve_one` return type updated to `ProfileFactValue | None`;
blank-string guard updated to `isinstance(value, str) and not value.strip()`.

Architecture-specialist constraint satisfied: `ProfileSourcedBindingResult`
fields unchanged.

The test file `test_profile_binding.py` covers the full wizard-to-persistence-
to-binding-to-decimal path. Tests are real-behavior with no mocks.

---

### W01.P05.S21 — Verify-only step (f5d382727)

**ACCEPT**

Closed as verify-only with the rationale that `_render_fact_value` already emits
lowercase canonical booleans. This is consistent with the S18 change: ingestion
coerces, rendering emits lowercase, no second site needed.

---

### W01.P06.S22–S24 — CIF documentation + pinning test (c55954263)

**ACCEPT**

Module-level cross-reference comment in `src/aeat/core/identity/_tax_id.py`
correctly documents `_CIF_LEADERS` as a 20-char historical-tolerance superset.
Paired comment in `src/aeat/core/identity/_documents.py` correctly explains the
17-char `_CIF_KIND_LETTERS` as the current-spec closed catalogue.

Pinning test in `src/aeat/core/identity/test_documents.py` asserts K/L/M are
not in `_CIF_KIND_LETTERS` while `validate_spanish_tax_id` still accepts a
K-led valid CIF. Test is non-tautological: it would fail if someone merged
the two sets.

---

### W01.P07.S25–S29 — Period unification (357f0fd79 + e9250127d)

**ACCEPT**

`parse_canonical_period` in `src/aeat/domain/period.py` gains `1P`/`2P`/`3P`
arms. `workflow_period_for_work_unit` in `src/aeat/application/modelo/_actions.py`
and `_registry_period_token` in `src/aeat/application/workflow/_engine.py`
both delegate to the shared parser. Property test (`test_period_property.py`)
verifies all three sibling functions agree on every supported token. Regression
test (`test_modelo_period_consistency.py`) verifies the `1P` create-calculate-verify
workflow succeeds end-to-end.

Architecture boundary clean: period parsing is domain logic, both application
callers delegate correctly.

---

### W01.P08.S30+S31 — `filing_date → as_of` rename + strict-placeholder machinery (b17876feb)

**ACCEPT-WITH-FOLLOWUP**

S30: `filing_date` context key renamed to `as_of` at the `bracket_no_window`
raise site in `src/aeat/domain/calculations/registry/_formula_runtime.py`.
Factory signature updated. Pinning test updated. Correct.

S31: `_I18N_STRICT_PLACEHOLDERS` ContextVar and `UnmatchedPlaceholderError`
added to `src/aeat/core/i18n/_render.py`. Test-scope conftest activates the
flag for all `core.i18n` tests.

**Open item (FU-C):** `_I18N_STRICT_PLACEHOLDERS` is a private name (leading
underscore) and appears in `__all__`. Only public symbols belong in `__all__`.
Test consumers that need to set the flag can import it via its fully qualified
path (`from aeat.core.i18n._render import _I18N_STRICT_PLACEHOLDERS`) without
it being in `__all__`. Remove from `__all__`. Add to W09.

---

### W01.P08.S32 — Project-wide i18n placeholder parity validator (a7d0123de)

**ACCEPT-WITH-FOLLOWUP**

AST-scan validator in `src/aeat/core/i18n/test_placeholder_parity.py` covers
ORPHAN / SURPLUS / SHADOW axes. Correctly uses AST walking rather than regex
grep (handles string literals, keyword arguments). The 5 ORPHAN + 27 SURPLUS
findings on first landing are explicitly catalogued in the commit message and
are not masked by the test (the test does not suppress them; they become
actionable follow-up Steps).

**Open item (FU-D):** The 5 ORPHAN and 27 SURPLUS findings surfaced by S32 must
be resolved as W09 Steps, not left open indefinitely. These represent live
operator-facing render failures (ORPHAN produces half-rendered text; SURPLUS
silently drops context). Each finding becomes one or more W09 Steps.

---

## Summary Table

| SHA(s) | Steps | Verdict |
|---|---|---|
| cb0c684f8, f864d72fd | S02, S03 | ACCEPT-WITH-FOLLOWUP |
| 29dca90f4, 73bbc293e | S04 | ACCEPT |
| 8984a9186 | S05 | ACCEPT |
| c940ffb67 | S06 | ACCEPT |
| 0b2f1e4b1 | S07 | ACCEPT |
| aff4a4c7e | S08–S12 | ACCEPT |
| 650cb762c | S13, S16 | ACCEPT |
| bb6c28f17 | S14 | ACCEPT-WITH-FOLLOWUP |
| dc38dcc43 | S15 | ACCEPT |
| 17a0c3023 | S17 | ACCEPT |
| ba5af08c5 | S18 | ACCEPT |
| 805008c5c | S19, S20 | ACCEPT |
| f5d382727 | S21 | ACCEPT |
| c55954263 | S22–S24 | ACCEPT |
| 357f0fd79, e9250127d | S25–S29 | ACCEPT |
| b17876feb | S30, S31 | ACCEPT-WITH-FOLLOWUP |
| a7d0123de | S32 | ACCEPT-WITH-FOLLOWUP |

No commits receive REJECT.

---

## Follow-up Steps to Add to W09

**FU-C** — Remove `_I18N_STRICT_PLACEHOLDERS` from `__all__` in
`src/aeat/core/i18n/_render.py`. Private names must not be exported. Test
consumers import via full module path.

**FU-D (×32)** — Resolve the 5 ORPHAN and 27 SURPLUS placeholder findings
surfaced by `test_placeholder_parity.py` on first landing. Each
`cli.app.ledger.*`, `cli.app.modelo.*`, `cli.diagnostics.*`,
`cli.common.errors.*` finding is a live render failure. Triage and fix each:
either add the missing kwarg at the call site (SURPLUS) or add the missing
placeholder to the locale value (ORPHAN). Each distinct key-group becomes one
W09 Step.

**FU-E** — `_command_matches_current` in `src/aeat/application/ledger/_actions.py`:
add inline comment confirming `attachment_ids` equality is value-equal (pydantic
frozen collection), not identity-equal, so the comparison is safe. One-line
documentation fix, no code change needed if confirmed by type inspection.

## Recommendations

Wave-1 is structurally sound. No ADR violations, no hexagonal-boundary leaks,
no shim introductions, no type-erasure regressions. The three ACCEPT-WITH-FOLLOWUP
items (FU-C private `__all__` export, FU-D 32 placeholder findings, FU-E
comment clarification) are all non-blocking for Wave-2 execution. Add FU-C,
FU-D, FU-E as Steps in W09.P41 to maintain the continuous-hardening posture.
