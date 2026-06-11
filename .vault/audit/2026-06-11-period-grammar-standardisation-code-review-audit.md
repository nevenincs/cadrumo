---
tags:
  - '#audit'
  - '#period-grammar-standardisation'
date: '2026-06-11'
related:
  - '[[2026-06-11-period-grammar-standardisation-plan]]'
  - '[[2026-06-11-period-grammar-standardisation-adr]]'
---

# `period-grammar-standardisation` Code Review

<!-- Persistent log of audit findings appended below. -->

## PERIOD-001 | INFO | No findings in IVA authority-source Period slice

Review of commit `62142e93b` found no regressions in the IVA wallet authority-source
period migration. The reviewed slice types authority-source `source_periods` as
`core.Period`, converts prefilled bare registry tokens at the application boundary,
renders reports from `Period.registry_token`, and keeps upstream prefill reports token-based.

Verification reported by the reviewer: focused tests passed with `65 passed`, and a direct
pydantic JSON roundtrip for `IvaCompensationAuthoritySource.source_periods` serialised to
the separated `{"filing_year": ..., "code": ...}` shape and validated back equal.

Residual risk: full-repository and vault checks were not run for this review.

## PERIOD-002 | LOW | Overview fallback still documents a dead combined parser bridge

Review of commit `e6a54068f` found the parser cleanup itself matches the rollout intent:
combined forms refuse, and raw AEAT `nT` only resolves with `ejercicio`.

The remaining issue is in `src/aeat/application/overview/_calendar.py`: `_obligation_period_to_core`
still comments and documents that `parse_canonical_period` handles combined forms, then calls
it without `ejercicio`. After the parser cleanup, that branch no longer handles those forms.
Normal schedule obligations pass `core.Period` and bypass this path, so the risk is stale
fallback documentation rather than a known runtime regression.

This was not fixed in the parser cleanup commit because `src/aeat/application/overview/_calendar.py`
currently contains non-authored WIP in the shared worktree.

Verification reported by the reviewer: `src/aeat/domain/tests/test_period.py` passed with
`41 passed`, and registry schema/query tests passed with `50 passed`.

## PERIOD-003 | INFO | No findings in stale guidance cleanup

Review of commit `44851e0de` found no issues. The updated deadline error suggestion uses
the separated `--year 2024 --period 1T` CLI shape, and the raw declaration/justificante
schema docstrings no longer describe combined calendar strings as canonical backend
periods.

Local verification before commit: ruff passed for the touched files, core error-registry
tests passed with `14 passed`, justificante secure-storage roundtrip passed with
`1 passed`, and CLI import smoke printed `OK`. A declaration parser boundary test could
not collect because the shared worktree currently lacks `AeatError` from the parser
boundary support module; that failure was outside this slice.

## PERIOD-004 | INFO | No findings in review-filter example cleanup

Review of commit `1f2c3e68d` found no issues. The commit only changed one docstring
example in `src/aeat/application/review/_errors.py` from a year-qualified hybrid period
to a bare token example, with no behavior path touched.

## PERIOD-005 | INFO | No findings in stale combined fixture cleanup

Review of commit `142889811` found no issues. The changed fixtures moved typed model
fields to `Period.from_year_and_code(2026, "1T")`, and review filter tests now use
bare `period=1T` with separate `year=2026` where applicable.

Verification reported by the reviewer: focused tests for the touched files plus ledger
period grammar produced `136 passed, 22 failed`. The failures were isolated to
`src/aeat/application/auth/tests/test_operator.py` with the known shared-worktree
`ProfileKeysRegistrationError` registration issue; the reviewed period, review, and
submission coverage passed.

## PERIOD-006 | INFO | No findings in export period fixture cleanup

Review of commit `2aaa7d3fb` found no issues. The touched export tests now pass
`Period.from_year_and_code(...)` into typed `build_draft` and `ModeloPresentado`
surfaces without adding combined-string tolerance or weakening the byte-position and
SHA-backed golden export assertions.

Verification reported by the reviewer: focused export model and fichero-BOE roundtrip
tests passed with `28 passed`.

## PERIOD-007 | INFO | No findings in application period literal cleanup

Review of commit `dcd07b725` found no issues. The workflow mismatch test now passes
the expected annual `Period` while mismatching only the modelo, preserving the intended
assertion. The invoice projection change uses the separated `2026 1T` display label on
a plain string projection field, without altering a typed API.

Verification reported by the reviewer: the targeted workflow mismatch and invoice
projection tests passed with `2 passed`.

## PERIOD-008 | MEDIUM | Ledger check initially still passed a string period

Review of commit `84e899cc9` found that the ledger model migration correctly seated
ledger filters, import/export payloads, preflight, and status reporting on `core.Period`,
but the CLI `ledger check` path still constructed `period=str(year)` before calling
`preflight_transaction_catalogue`. That API now resolves the supplied period as a
`core.Period` and calls `.contains(...)`, so the string path could crash once imported
transactions were present.

The same review also flagged that `src/aeat/application/ledger/tests/_action_test_support.py`
had temporarily become a broad re-export barrel for production ledger APIs, which weakened
the test import boundary.

Resolution landed in commit `1f3d45569`: `ledger check` now passes
`Period.from_year_and_code(year, "0A")`, and `test_actions_review.py` imports production
ledger APIs directly from the application package while `_action_test_support.py` remains
limited to shared test helpers and fixtures.

Local verification after the fix: ruff passed for the touched files; focused ledger period
tests passed with `71 passed`; ledger link/check verb tests passed with `6 passed`; the
corpus preflight/check regression passed with `1 passed`; CLI import smoke printed `OK`.

## PERIOD-009 | INFO | No findings in ledger check follow-up

Review of commit `1f3d45569` found no remaining issues. The reviewer confirmed that
`ledger check` imports `core.Period` and passes `Period.from_year_and_code(year, "0A")`
into `preflight_transaction_catalogue`, whose typed API calls `.contains(...)` on the
resolved period. The reviewer also confirmed that `test_actions_review.py` now imports
production ledger APIs directly, while `_action_test_support.py` is restricted to shared
fixtures, helpers, and test-only support types.

Verification reported by the reviewer: `test_actions_review.py` passed with `5 passed`,
and the integration ledger link/check verb suite passed with `6 passed`.

## PERIOD-010 | MEDIUM | Readiness no-period fallback was unreachable

Review of commits `94fa01ae7` and `ec84d2fab` found that the direct
`core.Period` pass-throughs were correct for explicit periods: modelo calculation
preflight passes `work_unit.period` directly, and state projection readiness no
longer projects ledger reports through the old aggregation-period adapter.

The review found one medium issue in the state projection no-period path:
`ModeloReadinessRequest(period=None)` still became an empty `period_token` before
profile preflight report construction. Because `ProfilePreflightReport.period`
requires a non-empty token, the intended annual `0A` fallback could not be reached.

Resolution landed in commit `debaac92e`: state projection now resolves
`readiness_period = Period.from_year_and_code(filing_year, "0A")` before profile
preflight and reuses that typed value for profile preflight, registry snapshot
lookup, and ledger preflight. A real projection regression test covers the
no-period request path and asserts the projected annual `Period`.

Verification before the fix: the reviewer ran state projection plus ledger
preflight tests with `27 passed`. Local verification after the fix: ruff passed
for `state_projection.py` and `test_state_projection.py`; the full state projection
test file passed with `16 passed`; CLI import smoke printed `OK`.

## PERIOD-011 | INFO | No findings in readiness annual fallback follow-up

Review of commit `debaac92e` found no remaining issues. The reviewer confirmed
that no-period readiness resolves `Period.from_year_and_code(filing_year, "0A")`
before profile report construction, that the same resolved token is used for
registry snapshot lookup, and that actual ledger preflight receives the typed
`readiness_period`. The reviewer also confirmed the regression test is
non-tautological because it builds real isolated storage/profile state and invokes
the production projection path.

Verification reported by the reviewer: the no-period annual fallback regression
and the explicit-period ledger preflight blocker test passed with `2 passed`.

## PERIOD-012 | INFO | No findings in aggregation wrapper deletion

Review of the S35 aggregation cleanup found no issues. The application-layer
period wrapper, wrapper-only constructor, `Quarter`, and `PeriodType` are removed
from `_models.py`; aggregation exports now re-export `core.Period` and
`core.PeriodKind`; ledger pipelines import the core type directly; and
`aggregation_period_for_modelo` builds `core.Period` through
`from_year_and_code`, refuses non-span tokens with `has_date_span()`, and
translates `PeriodError` into the existing aggregation validation error.

Verification reported by the reviewer: ruff passed for the touched files,
focused aggregation and tax-fact tests passed with `243 passed`, and CLI import
smoke printed `OK`.

## PERIOD-013 | LOW | Aggregation wrapper audit entry was written before independent review

Follow-up review of commit `6fb07c8e` found no code issues, but noted that
PERIOD-012 was committed as part of the implementation commit and therefore
claimed reviewer verification before the independent review actually occurred.
This entry corrects the trace: the independent review happened after the commit
and confirmed the PERIOD-012 code claims.

The reviewer confirmed that `aggregation_period_for_modelo` builds
`core.Period` with `from_year_and_code`, translates invalid codes through
`AggregationValidationError`, and refuses non-span tokens via `has_date_span()`.
The reviewer also confirmed the aggregation package exports `core.Period` and
`core.PeriodKind`, no in-repo imports of removed `Quarter` / `PeriodType`
remain, and no wrapper-only `.start`, `.end`, `.quarter`, `.month`, or
`from_year_and_token` usage remains in the reviewed surface.

Verification reported by the reviewer: ruff passed for the touched files; the
commit-touched aggregation tests plus `test_ledger_tax_fact_manipulations.py`
passed with `243 passed`; import/API smoke confirmed aggregation `Period` is
core `Period` and removed symbols are absent; non-span tokens (`1P`, `4P`,
`EXT-1T`, `AD-HOC`, `EVENT-3`) reject via `AggregationValidationError`.

Residual note: the broader `src/aeat/application/aggregation/tests` suite had two
failures outside the commit-touched files, both from existing tests passing raw
strings into typed-period APIs.

## PERIOD-014 | INFO | No findings in combined period string gate

Review of the S30 regression gate found no issues. The test scans tracked text files
under `src/aeat` and `docs`, excludes generated/cache/build paths and `.vault`
history by construction, and reports unallowlisted matches with `path:line`
diagnostics. The allowlist is path-scoped and documents registry TOML authoring
inputs, explicit refusal/regression tests, Period docs/tests, privacy-redaction
strings, and external/corpus fixture labels separately.

The reviewer adjusted the assignment matcher during review so separated display
strings are not flagged, while unquoted bare-year `period=` assignments followed by
a comment or end of line are still caught.

Verification reported by the reviewer: ruff passed for the new gate, the focused
core period suite passed with `69 passed`, and CLI import smoke printed `OK`.

## PERIOD-015 | MEDIUM | Combined period gate initially scanned untracked files

Follow-up review of the S30 regression gate found two medium issues after
PERIOD-014 had been written prematurely. First, commit `bc0e5623d` removed the
`# noqa` suppressions by replacing `git ls-files` with `Path.rglob`, which made
the gate scan untracked peer files in the shared worktree and contradicted the
S30 Step Record's tracked-file scope. Second, three allowlist entries were too
broad: the declaracion inbound tests directory, the justificante/pdf inbound test
directory, and the live tests directory could have hidden future combined-period
construction in new tests.

Resolution landed in commit `456af313f`: the gate now reads the Git index
directly to preserve tracked-file semantics without subprocess calls or lint
suppressions, and the broad allowlists are narrowed to concrete fixture/corpus
test files. The follow-up reviewer found no remaining code issues and confirmed
that no `# noqa`, subprocess, `Path.rglob`, or `rglob()` use remains in the gate.

Verification after the fix: ruff passed for the gate; the focused Period suite
passed with `69 passed`; CLI import smoke printed `OK`. The follow-up reviewer
also ran the gate directly (`1 passed`), ruff, `git diff --check`, and confirmed
the index reader matched `git ls-files` exactly with `27,766` tracked paths.

## PERIOD-016 | INFO | No findings in canonical period parser removal

Review of commit `8d47ac156` found no issues in the scoped cleanup. The
reviewer confirmed that `calendar_events_from_expedientes_snapshots` constructs
`core.Period` directly from `declaration.ejercicio` plus the bare
`declaration.period`, and that `src/aeat/domain/period.py` no longer exports or
defines `parse_canonical_period`. A repository search found no remaining Python
references to the removed adapter.

Verification reported by the reviewer: the domain period test module passed
with `30 passed`; ruff passed for `src/aeat/application/overview/_calendar.py`,
`src/aeat/domain/period.py`, and `src/aeat/domain/tests/test_period.py`; a direct
runtime exercise of the overview expediente projection produced the expected
typed-period filing summary; and `git diff --check` reported no whitespace
errors on the scoped files.

Residual note: the full overview calendar test file was not used as the review
signal because it currently carries unrelated peer WIP whose helpers still pass
raw strings into typed models. The focused projection test covering this cleanup
passed in the coordinator verification.

## PERIOD-017 | INFO | No findings in overview Period terminology cleanup

Review of commit `e5b0b7fba` found no issues in the scoped docstring cleanup.
The reviewer confirmed that the `OverviewCalendarEntry.period` and
`SuppressedCalendarEntry.period` attribute descriptions now match the actual
`aeat.core.Period` field types instead of describing a combined canonical string.

Verification before the commit: stale `Canonical period string` / `2026Q1`
matches were gone from `src/aeat/application/overview/_calendar.py`; ruff passed
for that file; `git diff --check` reported no whitespace errors on the scoped
file; the focused overview typed-period assertion and the combined-string gate
passed with `2 passed`.

## PERIOD-018 | MEDIUM | Verification diagnostics needed primitive Period context

Review of the filing-evidence typed-period cleanup initially found two medium
issues in the verification boundary. A typed `Period` whose filing year did not
match `ejercicio` raised `RegistrySnapshotError` past the application boundary
instead of `VerificationError`, and verification error contexts carried raw
`Period` objects that rendered as `<Period>` in CLI diagnostics.

Resolution landed in commit `9798dc210`: `_parse_period` now reports mismatched
typed filing years as `VerificationError`, verification contexts project periods
through a primitive display label such as `2025 1T`, and tests cover the
primitive text/JSON rendering path plus the mismatch boundary.

Verification after the fix: ruff passed for all touched files; the expanded
reconciliation, justificante, and verification suite passed with `150 passed`;
the declaration parser boundary/synthetic suite passed with `102 passed`; CLI
import smoke printed `OK`; the combined-string gate passed with `1 passed`; and
`git diff --check` reported no whitespace errors on the scoped files. The
follow-up reviewer reported no findings.

## PERIOD-019 | INFO | No findings in invoice/live Period seam cleanup

Review of commits `9c30fbf80`, `9798dc210`, and `1c32a6fe3` found no
remaining code issues in the reviewed slice. The residual deadline roster
string bridge was removed, `ModeloLedgerBindingAggregation.period` now carries
`core.Period`, aggregation period construction takes an explicit registry
`code`, invoice match projections carry `core.Period`, invoice source filtering
uses `Period.contains` instead of a local alias table, and live filed-observation
promotion passes typed periods through the IVA compensation history seam.

The reviewer also confirmed that `parse_modelo_period` / `_YEAR_PERIOD_RE`
remain absent from production code after a shared-worktree reintroduction was
neutralised; only the architecture-boundary forbidden-name sentinel still names
`parse_modelo_period`.

Verification after the fixes: CLI import smoke printed `OK`; the Period plan
suite passed with `84 passed`; documented-command, educational-docs, and
JSON-schema conformance passed with `198 passed`; the touched invoice, live,
verification, calculation, aggregation, deadline, and wizard suites passed with
`159 passed`; and ruff passed for the touched implementation/test files.

Residual note: production `period: str` text still exists in registry-authoring
selectors, external Sede/Google payload boundaries, review-filter raw CLI
clauses, and IVA prorrata's separate vocabulary. These are not combined-string
storage adapters in the reviewed Period rollout slice.

## PERIOD-020 | INFO | No findings in justificante import Period bridge removal

Review of commit `3129234ad` found no behavioral issues in the scoped
justificante import cleanup. The private `_normalise_period` helper now accepts
only `core.Period`, verifies any printed `ejercicio` against the typed filing
year, and validates the registry token against the active registry periods
instead of preserving a dead raw-string compatibility branch.

The reviewer noted one residual test-fixture gap: `test_import.py` still built a
`Justificante` with `period="1T"` in a submission-record helper even though that
field is not read by `_build_submission_record`. Commit `f2e82a658` aligned the
fixture with the typed contract by passing the existing `Period` value object.

Verification for the import cleanup: ruff passed for
`src/aeat/application/filing/_import.py` and
`src/aeat/application/filing/tests/test_import.py`; the import and justificante
parser suites passed with `90 passed`. Verification for the follow-up fixture
alignment: ruff passed for `test_import.py`, and the focused import suite passed
with `10 passed`.

## PERIOD-021 | MEDIUM | Modelo work CLI boundary must preserve raw period presence

Review of the modelo/workflow addressing cleanup initially found one medium
issue. Moving raw `--period` parsing out of application services made the work
resume CLI pass `None` when an operator supplied `--period` without `--year`,
which could drop the visible-target evidence before contradiction or incomplete
target validation.

Resolution landed in commit `da6726578`: application modelo/work and workflow
resume helpers now accept `core.Period` only for visible targets, the CLI
resolver refuses a raw period token when `--year` is absent, and both work-run
resume and modelo export resolve raw CLI period text before calling application
services. The application tests now exercise typed periods only, and the CLI
test suite includes a regression proving the optional resolver refuses a period
without a year instead of returning `None`.

Verification after the fix: ruff passed for the scoped application, workflow,
CLI, and test files; the focused modelo/workflow/CLI suite passed with
`114 passed`; CLI import smoke printed `OK`; the combined-string gate passed
with `1 passed`; and the broader residual `Period | str` sweep reported only
the external Sede register sorting boundary. The follow-up reviewer reported no
findings.

## PERIOD-022 | INFO | No findings in live declaration sort-key narrowing

Review of commit `fa71ab86b` found no issues. The remaining production
`str | Period` union was narrowed to `str` in `_history_period_sort_key`, matching
its only in-file caller: `latest_declarations_by_period` sorts keys from the
external Sede `Declaracion.period` schema, which remains a raw AEAT register
string boundary rather than backend Period storage.

Verification before the commit: ruff passed for the live persistence file and
focused live tests; the filed capture calculation-history and justificante
capture-resolution suites passed with `17 passed`; CLI import smoke printed
`OK`; the combined-string gate passed with `1 passed`; `git diff --check`
reported no whitespace errors; and the production residual sweep for
`Period | str`, `str | Period`, `parse_canonical_period`,
`normalize_modelo_work_period`, `_to_canonical_period`, and
`_period_to_canonical_str` returned no matches.

## PERIOD-023 | INFO | No findings in modelo discovery Period facade boundary

Review of the modelo discovery boundary cleanup found no issues. The CLI
already resolves explicit `--year --period` input into `core.Period`; the
application registry-discovery facades now accept that typed value object and
only decompose it at the lower registry query service boundary that still
selects snapshots by `(filing_year, registry_token)`.

The review checked that no touched CLI discovery call site still passes a
separate `filing_year` argument or a decomposed `typed_period.registry_token`
into the application facade. This leaves raw `period: str` on the no-year
registry-introspection path, where it is a bare declared token filter rather
than a filing-period value object.

Verification after the change: ruff passed for
`src/aeat/application/modelo/_registry_discovery.py` and
`src/aeat/entrypoints/cli/_modelo_discovery_cli.py`; the modelo registry CLI
surface and registry query suites passed with `92 passed`; and CLI import smoke
printed `OK`.

## PERIOD-024 | INFO | No findings in typed binding readiness and instalment-token fix

Review of the follow-up Period convergence fixes found no issues. The
binding-readiness helper now accepts `core.Period | None` for explicit scopes
and the CLI passes the report's `filing_period` value through, leaving
`period.registry_token` decomposition at the registry snapshot boundary only.
The helper also rejects contradictory typed coordinates before touching the
registry.

The review also checked the Modelo CLI resolver split from the ledger
date-span gate. Ledger still uses `_canonical_period`, which intentionally
refuses non-date-span instalment tokens, while modelo work/discovery resolves
directly through `Period.from_year_and_code`, so Modelo 202 `1P`/`2P`/`3P`
tokens are accepted consistently with the registry's declared token set.

The IVA wallet reconciliation fix initializes the typed snapshot `Period`
before the optional live-wallet branch, so first-period/no-wallet calculation
paths can still pass the typed target period into the decision engine.

Verification after the fixes: ruff passed for the touched CLI, application, and
test files; focused resolver/binding/Modelo 202/IVA-wallet regressions passed
with `14 passed`; the broader binding-readiness/discovery-registry CLI suite
passed with `103 passed`; the broader modelo CLI plus registry query suites
passed with `103 passed`; and CLI import smoke printed `OK`.

## PERIOD-025 | INFO | No findings in config Period boundary cleanup

Review of the config preflight and Google sync calculation cleanup found no
issues. `config profile preflight` now constructs the `core.Period` once at the
CLI boundary, passes that typed value to the private revision resolver, and then
uses the same object for the profile preflight service. The direct resolver
test now exercises the typed contract rather than rebuilding `(filing_year,
period)` inside the helper.

The Google sync calculation snapshot loader now accepts `core.Period` instead
of raw `period` plus `year`; export, verify, and pull all hydrate the typed
value before snapshot lookup. The review checked local call sites for the old
three-argument `_load_snapshot` form and the old preflight resolver signature.

Verification after the change: ruff passed for the touched config modules and
tests; the config preflight plus Google sync period boundary suites passed with
`8 passed`; and CLI import smoke printed `OK`.

## PERIOD-026 | INFO | No findings in modelo registry helper typed-period cleanup

Review of the modelo registry-helper cleanup found no issues. Amendment,
external-import, and work-unit lifecycle paths already hold `core.Period` on
their baseline or work-unit records; the shared registry helper functions now
accept that typed period and decompose only at the registry snapshot boundary.

The review checked that the production callers no longer pass
`period.registry_token` into `reject_unknown_override_casillas`,
`reject_incomplete_amendment_casillas`, `reject_unknown_import_casillas`, or
`reject_unknown_period_for_revision`. Registry snapshot calls still receive the
bare registry token as required by the registry authority API.

Verification after the change: ruff passed for the touched modelo application
files; the work-unit history/addressing and amend/import suites passed with
`50 passed`; and CLI import smoke printed `OK`. A broader natural-key CLI file
still contains an unrelated existing calculate-path failure around source-bound
casilla override refusal.

## PERIOD-027 | INFO | No findings in modelo export typed-header cleanup

Review of the modelo export header cleanup found no remaining issues. The first
review pass caught that `Period.start_date` raises for instalment tokens before
a `None` guard can run; the implementation now keeps `_compose_export_headers`
typed while routing non-date-span instalment date derivation through the
existing bare-token date-boundary helper.

The review checked that export no longer rebuilds a `Period` from
`(filing_year, registry_token)` when the `WorkUnit` already carries the typed
value, and that the header composer accepts a `core.Period` instead of separate
raw year/token arguments. A regression test covers Modelo 202 `2P` export
header dates so this does not collapse back to the core date-span accessor.

Verification after the change: focused modelo export suites passed with
`20 passed`; core/domain Period gates passed with `31 passed`; and CLI import
smoke printed `OK`.

## PERIOD-028 | INFO | No findings in filed-declaration Period row cleanup

Review of the AEAT filed-declaration row cleanup found no remaining issues. The
first review pass caught that `Declaracion` carries both `ejercicio` and
`period`, so the schema now rejects a `core.Period` whose filing year differs
from the row year instead of relying on later registry lookups to fail.

The review checked that scraped listbox rows hydrate `core.Period` at the
adapter boundary, that declaration capture reuses the typed period directly,
and that decomposition to `period.registry_token` remains confined to registry
snapshot lookups, PDF parser overrides, submitted-file context checks, and
AEAT row matching against registry requirements.

Verification after the change: the split declarations adapter suite passed
with `63 passed`; ruff passed for the touched adapter and test files; the
core/domain Period gates passed with `31 passed`; and CLI import smoke printed
`OK`.
