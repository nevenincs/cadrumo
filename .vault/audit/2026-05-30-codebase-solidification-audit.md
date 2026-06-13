---
tags:
  - '#audit'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-adr]]"
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# `codebase-solidification` audit: `Wave 2 swarm re-audit`

## Scope

Recurring eight-axis swarm dispatched after Wave 1 closed all 224
Steps at 100%. Each axis verifies the Wave 1 closures held (no
regression) and surfaces fresh drift (new sites, survivors the
inaugural audit missed). Findings classified as `regression` are the
most diagnostic signal — they prove the original drift habit can
recur even immediately after a structural close, and they shape the
Wave 2 hardening priorities.

## Wave 1 closure verification

Wave 1 landed 224 structural changes across 9 axes with paired
real-behavior tests. The Wave 2 swarm confirms zero closures
regressed on the original `file:line` sites for **5 of 8 axes** (A1
exceptions, A3 locale, A4 pydantic, A6 stubs / dead, A8 typecheck).

## Findings summary

| Axis | New | Regression | Survivor-missed | Total |
| --- | --- | --- | --- | --- |
| A1 exceptions | 0 | 0 | 25 | **25** |
| A2 logging | 3 | 1 | 2 | **6** |
| A3 locale | 0 | 0 | 18 | **18** |
| A4 pydantic boundaries | 2 | 0 | 3 | **5** |
| A5 duplication | 0 | 3 | 0 | **3** |
| A6 stubs / dead | 0 | 0 | 0 | **0** |
| A7 hardcoded / enums | 5 | 4 | 3 | **12** |
| A8 typecheck escapes | 0 | 0 | 3 | **3** |
| **Total** | **10** | **8** | **54** | **72** |

## Regressions (highest diagnostic priority)

These eight findings re-introduce drift patterns that Wave 1 closed.
They sit at the top of Wave 2's Step list because they prove the
enrollment habit is not yet automatic.

### A2 regression - `_context.py` asymmetric sink teardown

- Path: `src/aeat/core/observability/_context.py:235, 321`
- Detail: Wave 1 introduced `attach_run_sink(sink)` in
  `aeat.core.logging` so the run-sink picks up
  `SecretScrubbingFilter` on attach. The detach side still calls
  `root_logger.removeHandler(sink)` directly. The asymmetry
  silently skips any future teardown logic added to
  `attach_run_sink`.
- Remediation: expose `detach_run_sink(sink)` in
  `aeat.core.logging` and call it from `_context.py`.

### A5 regression - `_now_utc` / `_utc_now` reintroduced

- Paths: `src/aeat/application/inventory/_service.py:97`,
  `src/aeat/application/storage/calc_sheets/_records.py:471`
- Detail: the canonical `_now` lives at `aeat.core.time._clock`
  (Wave 1 Step W01.P05.S141). Two new local copies were introduced
  with renamed helpers that compute `datetime.now(tz=UTC)`
  identically.
- Remediation: delete both local copies; import the canonical
  `_now` from `aeat.core.time`.

### A5 regression - `_parse_boolean` shadows canonical `_parse_bool`

- Path: `src/aeat/domain/calculations/registry/_export_parse.py:409`
- Detail: canonical `_parse_bool` lives at
  `aeat.core.parsing._utils` (Wave 1 Step W01.P05.S147). A new
  `_parse_boolean(raw: str)` was added with hardcoded truthy /
  falsy token sets.
- Remediation: delete the local helper; import `_parse_bool` and
  wrap with the registry's domain-specific token sets.

### A7 regression - `CasillaFieldKind` bypassed at 5 sites

- Paths:
  - `src/aeat/adapters/outbound/aeat/sede/_declarations.py:1471`
  - `src/aeat/domain/user_profile/_registry_contract.py:255`
  - `src/aeat/application/filing/_export.py:472`
  - `src/aeat/domain/calculations/registry/_export.py:151, 156, 167, 186`
- Detail: Wave 1 promoted `CasillaFieldKind` to a `StrEnum` (Step
  W01.P07.S169). Bare `"draft"` / `"binding"` / `"casilla"`
  comparisons survive at 5 new sites - including a `match` arm in
  `_export.py:472`.
- Remediation: replace each bare string with
  `CasillaFieldKind.<MEMBER>`; convert `match` arms to enum-member
  case patterns.

### A7 regression - `_MANUAL_CLASSIFIED_BY` shadows `CLASSIFIED_BY_MANUAL`

- Paths: `src/aeat/domain/transactions/_service.py:24, 196`;
  canonical at `src/aeat/application/ledger/_models.py:724`
- Detail: Wave 1 introduced `CLASSIFIED_BY_MANUAL` in the
  application layer. The domain layer cannot import upward from
  `application/`, so a local `_MANUAL_CLASSIFIED_BY = "manual"`
  was reintroduced. Same hexagonal-boundary bug pattern as the
  deferred `AggregationSourceKind` domain-layer gap.
- Remediation: relocate `CLASSIFIED_BY_MANUAL` from
  `application/ledger/_models.py` to
  `aeat.core.external_constants` (domain can import from core).
  Delete the domain-layer shadow.

### A7 regression - `REPLAY_ACTIVE_ENV_VAR` duplicated as private literal

- Paths: canonical
  `src/aeat/core/observability/_replay.py:26`; duplicate
  `src/aeat/core/observability/_context.py:51`
- Detail: `_context.py` declared a private
  `_REPLAY_ACTIVE_ENV_VAR = "AEAT_REPLAY_ACTIVE"` instead of
  importing the canonical `REPLAY_ACTIVE_ENV_VAR` from its sibling
  module.
- Remediation: `from ._replay import REPLAY_ACTIVE_ENV_VAR`;
  delete the local literal.

## New drift findings (post-2026-05-27)

Ten fresh drift findings that appeared after the inaugural audit.

### A2 - `print()` and raw logger in DOM-explore live-test

- Path:
  `src/aeat/adapters/outbound/aeat/sede/test_renta_web_open_explore_dom.py:57, 175, 208`
- Detail: live integration test exercises adapter production
  paths but uses `logging.getLogger(__name__)` + two `print(...)`
  calls for exception traces. NIF / session-cookie strings can
  land on stdout unscrubbed.
- Remediation: swap to `get_logger(__name__)`; replace `print`
  with `_log.debug(..., exc_info=True)`.

### A4 - JSON-decode boundary at encrypted columns

- Path:
  `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py:185`
- Detail: `json.loads(plaintext.decode("utf-8"))` returns
  unvalidated payload to the persistence boundary.
- Remediation: wrap with `EncryptedPayload(BaseModel)` or
  `model_validate(...)`.

### A4 - JSON-decode boundary at master-key envelope

- Path:
  `src/aeat/adapters/persistence/storage/master_key/_master_key.py:1117`
- Detail: `document = json.loads(envelope_payload.decode("utf-8"))`
  followed by `document.get("payload")` with no model validation.
- Remediation: define `EnvelopeDocument(BaseModel)` and use
  `model_validate_json`.

### A7 - Playwright wait-state literals (15+ sites)

- Paths: `_declarations.py:449, 831, 1636`;
  `_iva_compensation_wallet.py:271, 294, 305, 355, 427, 429`;
  `_groi_check.py:298, 427`; `_nif_iva_check.py:315, 324, 422`;
  `_censo_live.py:128`; `_walker.py:301`
- Detail: `"domcontentloaded"` and `"networkidle"` are repeated
  bare strings across 15+ adapter call-sites.
- Remediation: introduce
  `PLAYWRIGHT_WAIT_DOMCONTENTLOADED` and
  `PLAYWRIGHT_WAIT_NETWORKIDLE` in a sede-layer
  `_browser_constants.py` module (adapter-layer, not
  `external_constants` - these are third-party API tokens).

### A7 - Browser timeout magic numbers

- Paths:
  `src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py:273, 341`,
  `_walker.py:301`
- Detail: `timeout=2_000` and `timeout=10_000` literals
  scattered. `_declarations.py` already canonicalises
  `_FORM_INTERACTION_TIMEOUT_MS` and `_NAVIGATION_TIMEOUT_MS`; the
  newer files do not reuse them.
- Remediation: introduce module-level constants (or import the
  existing `_declarations.py` constants if semantics match).

### A7 - `application/json` and `text/csv` MIME literals

- Paths:
  `src/aeat/adapters/outbound/aeat/sede/_declarations.py:1223`,
  `src/aeat/application/export/_tabular.py:69`
- Detail: Wave 1 introduced `BINARY_MIME_TYPE` in
  `external_constants`; the two other MIME literals were not
  enrolled (no canonical constant exists yet).
- Remediation: add `JSON_MIME_TYPE` and `CSV_MIME_TYPE` to
  `external_constants.py`; enroll both sites.

### A7 - direct `os.environ` writes in observability and CLI

- Paths: `src/aeat/core/observability/_replay.py:172, 179`,
  `src/aeat/entrypoints/cli/_stdio.py:89`
- Detail: intentional scoped env-mutation in `_replay.py`
  (context-manager) and CLI display side-effect in `_stdio.py`.
  Document explicitly per project memory `settings_not_naked_env`.
- Remediation: add `# env-write: intentional scoped mutation`
  comments OR wrap `_stdio.py`'s write in a context-manager.

## Survivor-missed findings (Wave 1 audit gaps)

54 findings the inaugural audit did not reach. The largest
clusters:

- **A1 (25 findings)**: `master_key/` package has no `_errors.py`
  (9 sites raising bare `ValueError` / `TypeError` /
  `RuntimeError`). `bucket/` storage layer has `BucketError` but
  validators inside the same package use bare `ValueError` (4
  sites). Six application-layer sites bypass enrolled errors
  (`NamespaceRegistryError` survivor in
  `_namespace_registry.py:119`; `WorkflowInputMismatchError`
  survivor in `_engine.py:282`; `ConfigBoundaryError` survivor in
  `core/config.py:1249, 1252`; `DiagnosticModelError` survivor in
  `application/diagnostics.py:416`).
- **A3 (18 findings)**: entire `AeatLoginAssertionError` hierarchy
  in `_authenticator.py` (5 sites) and `_clave_movil.py` (4 sites)
  has no `translated_message=`. Nine `SedeNavigationError` raises
  in `_declarations.py` navigation flow were not threaded.
  `PortalNotFoundError` in `application/portals/_service.py:97`
  is bare English.
- **A4 (3 findings)**: Google Drive `_find_file` return retains
  rationale comment but no `GoogleDriveFileEntry` wrapper model;
  Playwright `_build_context_kwargs` similarly lacks a
  `PlaywrightContextKwargs(BaseModel)`. `RevisionValidationContext`
  carries 17 `dict[str, Any]` fields at the registry lookup
  boundary - architectural-intent flagged for design review.
- **A7 (3 findings)**: `"EUR"` literals at `_pdf_n26.py:287-288`
  (2 sites missed in Wave 1's currency sweep);
  `_actions.py:2413` bare `ValueError(f"Unknown applicability
  filter")` should be `ModeloApplicabilityFilterError`.
- **A8 (3 findings)**: three `cast()` calls in
  `_streams.py:152`, `_actions.py:3503, 3547`, `_commands.py:928`
  lack `CAST-RATIONALE-*` markers.

## Recommendations

1. **Wave 2 P01 - regression fixes (8 Steps).** Close every
   regression first; these are the most diagnostic signal that the
   enrollment habit is leaking. Process in order: A2 detach
   helper, A5 helper re-imports, A7 enum / constant re-enrollment,
   A7 `CLASSIFIED_BY_MANUAL` relocation.
2. **Wave 2 P02 - A1 survivor sweep (25 Steps).** Establish
   `aeat.adapters.persistence.storage.master_key._errors` and
   migrate the 9 `master_key/` raises. Enroll `bucket/`
   validators into `BucketError`. Close the 6 application-layer
   survivors.
3. **Wave 2 P03 - A3 survivor sweep (18 Steps).** Highest
   operator-impact gap: thread `translated_message=` on every
   `AeatLoginAssertionError` raise across `_authenticator.py` and
   `_clave_movil.py`. Close the 9 `SedeNavigationError`
   navigation-flow raises.
4. **Wave 2 P04..P09** for the remaining axes.
5. **Pattern-level Wave 3 architectural item:** the
   `CLASSIFIED_BY_MANUAL` regression and the deferred
   `AggregationSourceKind` domain-layer gap share the same root
   cause: Wave 1 placed canonical constants in `application/`
   where `domain/` cannot import them. The structural fix is to
   relocate every cross-layer constant to
   `aeat.core.external_constants` (or a sibling `aeat.core`
   module) so the canonical home is reachable from every layer.

The Wave 2 swarm yielded 72 findings vs Wave 1's ~115; the
recurrence rate is **0% on the original `file:line` sites** (no
Wave 1 closure regressed) but **5 fresh regressions on Wave 1
canonical-home concepts**. The pattern suggests the hardening
discipline holds for closed sites but does not yet prevent fresh
drift in new code - which is exactly what the recurring-epic
shape is designed to surface and correct.
