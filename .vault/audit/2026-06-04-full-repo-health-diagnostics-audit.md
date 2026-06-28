---
tags:
  - '#audit'
  - '#repo-health-diagnostics'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-just-tooling-bootstrap-research]]'
  - '[[2026-06-04-just-tooling-bootstrap-adr]]'
  - '[[2026-06-04-just-tooling-bootstrap-plan]]'
---

# `repo-health-diagnostics` Audit

This audit captures the first full-repo health pass after wiring the modern `just`
diagnostic surface. Commands were run in the shared worktree on 2026-06-04. The
results are advisory findings, not a green-gate assertion.

## HEALTH-001 | HIGH | Type-control debt is broad and concentrated in active domain/application contracts

`ty check src --output-format concise` reported 1014 diagnostics. Full-tree Pyright
reported 2370 errors and 495 warnings. The scoped deprecation/type-opportunity lane
over `src/aeat/domain` and `src/aeat/application` reported 797 errors and 491
warnings.

Dominant themes:

- Typed contract drift between aggregation source kinds and counterpart source
  kinds in `src/aeat/application/aggregation`.
- Optional value access without narrowing in aggregation, filing evidence,
  transaction, and secure-storage tests.
- Secure repository subclass payload type overrides that are invariant against
  the base `BaseModel` payload type.
- Pydantic/config constructor calls passing raw `str` or `str | None` into typed
  `Path`, `SecretStr`, enum, `bool`, `int`, `Decimal`, and literal fields.
- Private API usage warnings across tests that reach into module internals.
- Strict generic annotation gaps in `src/aeat/domain/usage_ratios/_service.py`.

Representative high-signal files include
`src/aeat/application/aggregation/_counterpart.py`,
`src/aeat/application/aggregation/_models.py`,
`src/aeat/application/aggregation/_source_mesh.py`,
`src/aeat/application/auth/_apoderado.py`,
`src/aeat/domain/justificante/_repository.py`,
`src/aeat/domain/submission/_repository.py`,
`src/aeat/domain/renta/_ledger_expenses.py`, and
`src/aeat/adapters/inbound/sanitizer/_pipeline.py`.

### 2026-06-04 refresh after no-sync just typecheck repair

Status: appended.

`just typecheck` now invokes both checkers with `uv run --no-sync`, matching the
shared-worktree virtual-environment repair discipline. The gate remains red on
the current baseline. `ty check src` reported 1002 diagnostics before Pyright
could run in the chained recipe. The scoped Pyright half was then run directly as
`uv run --no-sync pyright src/aeat/domain src/aeat/application`, reporting 792
errors and 494 warnings.

Current high-signal type-control clusters:

- Declaracion parser boundary tests pass `object`-typed mappings into stricter
  parser contracts and use dynamic keyword payloads that Ty expands into multiple
  invalid call shapes.
- Auth and Cl@ve tests construct `Settings` with raw `str` or `str | None`
  values where the model expects `Path`, `SecretStr`, booleans, and typed
  timeout values.
- Aggregation model errors still show `AeatError` constructor signature drift and
  optional member access in ledger aggregation code.
- Domain filing and secure repository classes still expose invariant payload-type
  override pressure against the generic storage repository contract.
- Renta and transaction tests still surface optional `Decimal` arithmetic,
  literal narrowing gaps, and read-only model field assignment.
- Several top-level ratchet tests remain in the typecheck scan; this makes the
  count useful as a full-source debt inventory, but less useful as a production
  readiness signal without a production-only type lane.

This refresh keeps the type ratchet workstream focused on typed boundary fixes
over blanket ignores: constructor normalization at settings/config boundaries,
optional narrowing before arithmetic/member access, and repository generic
contract repair should be preferred before expanding any allowlist.

### 2026-06-04 W06.P18.S63 all-green type bucket inventory

Status: appended.

The all-green campaign now tracks the remaining type work as executable buckets in
`W06.P18.S63` through `W06.P18.S70`. Targeted checker runs on the first buckets
showed the following current baseline:

- `S64` Declaracion parser boundary tests: Ty reports five diagnostics in
  `test_parser_boundary.py`. One is an `object` membership check against an error
  detail; four are from dynamic `**{"año_override": 2026}` construction that
  makes Ty treat the integer as every keyword parameter shape accepted by
  `parse_declaracion`.
- `S65` exception-hygiene AST narrowing: Ty reports one diagnostic in
  `test_exception_hygiene.py` where an `ast.AST` value is read as if every node
  had `lineno`.
- `S66` auth Settings constructors: full `just typecheck` still reports raw
  `str` and `str | None` values passed into typed `Settings` fields such as
  `Path`, `SecretStr`, booleans, and timeout values.
- `S67` aggregation residuals: a targeted Pyright run over aggregation plus
  adjacent domain buckets reports 26 errors and 35 warnings. The aggregation
  errors cluster around `AeatError` constructor signature drift, optional access,
  object-to-`Decimal` narrowing, and tests still passing string literals where
  `CounterpartSourceKind` now expects enum-backed literals.
- `S68` filing repository residuals: `domain/filing/_repository.py` still has
  the invariant `payload_type` override pattern that earlier secure repository
  repairs removed from justificante, submission, and apoderado repositories.
- `S69` renta and transaction residuals: current findings include `Literal["EUR"]`
  assignment widening, unnecessary runtime type checks after static narrowing,
  optional `Decimal` arithmetic in gross-invariant tests, and assignment to a
  read-only `ModelProfile.model_id` field.

Port-bound RAG corroborated that the aggregation and secure-repository residuals
are follow-on work from W02 rather than new architecture: the top vault results
were W02 aggregation source-kind and secure repository payload execution records,
and code search returned the canonical `CounterpartSourceKind` and
`counterpart_source_kind` surfaces in `src/aeat/core/aggregation.py`.

## HEALTH-002 | HIGH | Structural boundaries are now diagnosable and show real layer violations

The initial structural run failed because `aeat` was not importable from the shared
`.venv`, which was a `uv` virtual-environment concurrency issue. A no-deps editable
reinstall repaired the local project install. Verification after repair:

- `uv run --no-sync python -c "import aeat"` resolves to `src/aeat/__init__.py`.
- `uv run --no-sync aeat --help` exits successfully.
- `uv run --no-sync lint-imports` now analyzes 1925 files and 7863 dependencies.

Import Linter result after repair: 3 contracts kept, 1 contract broken. The broken
contract is the AEAT layered architecture rule. The remaining findings are real
layering issues, primarily tests under `application` and `domain` importing adapter
surfaces directly or indirectly through `aeat.tests.secure_sql`.

The relative-import checker reports 14 absolute `aeat.*` imports inside `src/aeat`.
Representative production violations include
`src/aeat/adapters/outbound/fx/_ecb_provider.py` and
`src/aeat/adapters/outbound/fx/_ecb_refresh.py`; representative test violations
include `src/aeat/application/user_profile/test_bundle_reexports.py` and
`src/aeat/application/workflow/test_declaration_key.py`.

## HEALTH-003 | HIGH | Complexity hotspots identify several monolithic refactor candidates

Radon found 284 C-or-worse cyclomatic-complexity blocks. The top cyclomatic
hotspots include:

- `src/aeat/entrypoints/cli/_modelo.py` `work_calculate`.
- `src/aeat/domain/calculations/registry/_formula_runtime.py` `_initial_values`.
- `src/aeat/entrypoints/cli/_modelo.py` `modelo_project`.
- `src/aeat/diagnostics/_identity_placement.py`
  `find_same_name_constant_multi_declarations`.
- `src/aeat/entrypoints/cli/_modelo.py` `modelo_compare`.
- `src/aeat/entrypoints/cli/_config/_google.py` `google_sync_calc_pull`.
- `src/aeat/domain/calculations/registry/_remote_state_guard.py`
  `_validate_policy`.
- `src/aeat/entrypoints/cli/_ledger.py` `ledger_list`.
- `src/aeat/application/ledger/_actions.py` `_filter_ledger_review_rows`.
- `src/aeat/application/modelo/_actions.py` `_resolve_m210_rate`.

Radon maintainability index placed several files at or near zero maintainability:
`src/aeat/application/live/__init__.py`,
`src/aeat/domain/calculations/registry/_bindings.py`,
`src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`,
`src/aeat/entrypoints/cli/_ledger.py`,
`src/aeat/entrypoints/cli/_config/__init__.py`,
`src/aeat/application/ledger/_actions.py`,
`src/aeat/diagnostics/_identity_placement.py`,
`src/aeat/entrypoints/cli/_modelo.py`,
`src/aeat/domain/calculations/registry/_schema.py`,
`src/aeat/domain/calculations/registry/_record_design.py`, and
`src/aeat/application/modelo/_actions.py`.

Complexipy analyzed 1926 files and reported total cognitive complexity of 21856.
Top cognitive hotspots include `find_same_name_constant_multi_declarations`,
`resolve_previous_filing_binding_values`, `build_wizard_commands`,
`find_private_name_cross_package_imports`, `modelo_compare`, `_initial_values`,
`work_calculate`, and `classify_live_iva_acquisition_failure`.

### 2026-06-04 refresh after S35 diagnostics removal

Status: appended.

`just audit-complexity` was rerun after the unapproved `aeat.diagnostics` source
package was removed. The command remains an advisory red gate because Complexipy
exits non-zero when functions exceed `--max-complexity-allowed 20`.

The removed diagnostics package no longer appears in the current complexity
output. Current production hotspots are now concentrated in these families:

- Modelo CLI orchestration: `src/aeat/entrypoints/cli/_modelo.py`
  `work_calculate` is still the largest cyclomatic hotspot at F (45);
  `modelo_project` is D (30), `modelo_compare` is D (29), and `work_create` is
  D (24). Complexipy also reports `modelo_compare` at cognitive complexity 37
  and `work_calculate` at 32.
- Registry formula and binding runtime: `src/aeat/domain/calculations/registry/_formula_runtime.py`
  `_initial_values` is E (35) cyclomatic and 33 cognitive; `_evaluate_m210_resolve_rate`
  is D/C-high and 30 cognitive. `src/aeat/domain/calculations/registry/_bindings.py`
  remains a high-load cluster with `_validate_invoice_fact_and_aggregation` D
  (23) and 30 cognitive, plus `resolve_previous_filing_binding_values` at 44
  cognitive.
- Registry record and validation graph: `src/aeat/domain/calculations/registry/_record_design.py`
  has `calculation_closure_identities` and `calculation_closure_numbers` as
  repeated high-complexity closure builders; Complexipy reports one closure path
  at 37 cognitive and another at 29. `_cross_revision_divergence.py`
  `_iter_cross_revision_casilla_divergences` reports 34 cognitive.
- Ledger review/list and action services: `src/aeat/entrypoints/cli/_ledger.py`
  `ledger_list` is D (27), and `src/aeat/application/ledger/_actions.py`
  `_filter_ledger_review_rows` is D (27), `summarize_manual_transactions` is D
  (22), and `_command_matches_current` is C (20).
- Modelo application actions and profile binding: `src/aeat/application/modelo/_actions.py`
  `_resolve_m210_rate` is D (26), `calculate_modelo_revision` is D (25), and
  `_apply_iva_compensation_decision_binding` is D (22). `src/aeat/application/modelo/_profile_binding.py`
  `resolve_profile_sourced_bindings` reports 25 cognitive.
- Wizard/config/live-auth surfaces: `src/aeat/application/wizard/_commands.py`
  `build_wizard_commands` reports 44 cognitive; `src/aeat/entrypoints/cli/_config/_google.py`
  `_push_secure_object_inventory` reports 37 cognitive; `src/aeat/application/live/_errors.py`
  `classify_live_iva_acquisition_failure` reports 32 cognitive.

The current execution supports the existing W03 decomposition order: continue
modelo CLI extraction, then registry formula/binding extraction, then ledger
review/list projection, with live/auth split work kept behind a dedicated audit
and ADR because those flows touch encrypted sessions and remote-provider state.
Port-bound `vaultspec-rag search --type code --prefer prod --port 8766`
corroborated the registry formula runtime and previous-filing binding cluster as
semantic neighbors, so this is not just a Radon/Complexipy artifact.

## HEALTH-010 | MEDIUM | Complexity tooling currently mixes production hotspots with ratchet/test complexity

Status: open.

The raw `just audit-complexity` output still includes package-level test ratchets
and fixture tests. Radon reports top-level `src/aeat/test_*.py` files because the
current exclude pattern covers nested `src/aeat/**/test_*.py` paths but not
top-level package tests. Complexipy also scans tests because the recipe points it
at `src/aeat` without an exclude mechanism.

This does not invalidate the production hotspot list above, but it makes the raw
dashboard noisy: the highest current cognitive item is the test ratchet
`test_utc_validator_enrollment_inventory.py` `_file_has_inline_tzinfo_guard` at
50. The just tooling should grow a production-only complexity lane, while keeping
a separate test-ratchet complexity lane for test-maintenance debt.

## HEALTH-004 | MEDIUM | Dependency declaration drift is small but points at production dependency hygiene

`just audit-deps` scanned 859 production files and reported 6 dependency issues:

- `formulas`, `rich`, and `torch` are declared but not detected as used in scanned
  production source.
- `playwright_stealth` is imported from
  `src/aeat/adapters/outbound/aeat/browser/evasion.py` but is declared as a dev
  dependency.
- `prompt_toolkit` is imported from
  `src/aeat/application/wizard/_prompter.py` but is currently only transitive.

This is a focused, tractable dependency-health workstream.

## HEALTH-005 | MEDIUM | Dead-code scan reports a small production candidate set

`just audit-dead-code` reports 15 production candidates at confidence 90-100 after
test-path exclusions were corrected.

Representative candidates:

- Unused `http` and `num_retries` variables in
  `src/aeat/adapters/outbound/google/_api.py`.
- Unused `CursorResult` import in
  `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- Unused `draft_path` variable in `src/aeat/domain/submission/_protocols.py`.
- Multiple unused CLI documentation payload imports in
  `src/aeat/entrypoints/cli/_doc_reference.py`.

The candidate set is small enough for manual triage.

## HEALTH-006 | MEDIUM | Duplication is low overall but clusters around repeated domain patterns

`just audit-duplication` scanned 827 Python files, 152860 lines, and 944256 tokens.
It found 22 clone groups, 369 duplicated lines, and 3932 duplicated tokens. Overall
duplication is low: 0.24 percent by lines and 0.42 percent by tokens.

High-signal clone clusters:

- Storage manifest and master-key KDF parameter structures.
- GROi and NIF IVA check flows.
- CSV and XLSX financial providers.
- AEAT NIF IVA and GROi registry oracle logic.
- CLI registry repeated sections.
- Ledger model repeated structures.
- Locale scanner and manager repeated traversal logic.

Duplication is not the dominant repo-health risk, but several clone groups map to
protocol or registry abstractions that could reduce future drift.

## HEALTH-007 | MEDIUM | Security scan is noisy because it scans tracked data and tests, but several classes deserve triage

`just audit-security` completed with Semgrep and reported 159 blocking findings
across 17782 tracked files. It ran 338 rules. The scan includes generated or mirrored
official data and tests, so the raw count is not directly equivalent to production
exposure.

Dominant classes:

- Plaintext HTTP links in mirrored AEAT/BOE HTML data under `src/aeat/_data`.
- Dynamic `importlib.import_module` usage in registry, CLI, resource, and test
  code.
- Python 3.7 compatibility findings for `importlib.resources`.
- Credential-leak logging patterns in tests that intentionally exercise redaction.
- A small set of generic security rules over test strings and paths.

Recommended next audit refinement is to add a Semgrep include/exclude policy so
production source, mirrored legal data, generated fixtures, and redaction tests are
reported separately.

## HEALTH-008 | MEDIUM | Ruff baseline is red and includes root-level scratch/probe files

`uv run ruff check .` reported 396 errors, with 32 fixable by safe fixes and 18
additional hidden unsafe fixes. A meaningful portion of the noise comes from
root-level scratch/probe files and ad hoc scripts such as `scratch_probe*.py`,
`run_p04_s11_test.py`, `test_m714.py`, `test_attachment_fix.py`, and
`scripts/classify_m200.py`.

Production-code Ruff signals still matter: import sorting in large CLI modules,
line-length violations in CLI commands, `__all__` ordering, and an undefined
`_emit_envelope` reference in `src/aeat/entrypoints/cli/_modelo.py`.

## HEALTH-009 | INFO | Diagnostic surface itself is now viable after the venv repair

The `uv` concurrency problem left the local project unavailable to `uv run
--no-sync`, which made structural diagnostics fail with `Could not find package
'aeat' in your Python path`. A targeted editable reinstall of the local project
repaired the `aeat` import and CLI entrypoint without running a full dependency sync
or touching the locked `vaultspec-rag.exe`.

Full `uv sync` should still be run during a clean window after the other process
releases `.venv/Scripts/vaultspec-rag.exe`, but the diagnostic command surface is
usable now.

## HEALTH-010 | CLOSED | Aggregation type error bucket reduced to zero errors

`W06.P18.S67` mitigated the aggregation package type-error bucket without changing
runtime contracts:

- `Period` now raises `AggregationPeriodError` through the current positional
  translated-message constructor.
- `effective_eur_amount` returns `Decimal`, matching the documented EUR projection
  contract used by renta ledger casilla arithmetic.
- IVA non-declarable category handling now narrows `iva_category` before reading
  its enum value.
- Aggregation tests now pass enum-backed counterpart source kinds at typed
  construction sites, and validator error contexts/evidence payloads are narrowed
  before member access.

Verification:

- `uv run --no-sync ty check src/aeat/application/aggregation --output-format concise`
  passed.
- `uv run --no-sync pyright src/aeat/application/aggregation --level warning --warnings`
  reported 0 errors and 17 pre-existing warnings for private/protected test
  reach-ins.
- `uv run --no-sync pytest src/aeat/application/aggregation/test_counterpart.py src/aeat/application/aggregation/test_per_modelo_registry_provider.py src/aeat/application/aggregation/test_per_modelo_service.py src/aeat/application/aggregation/test_service.py src/aeat/application/aggregation/test_ledger_filing_evidence.py src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_renta_ledger_helpers.py src/aeat/application/aggregation/test_renta_ledger_aggregation.py -q`
  passed with 89 tests.
- `uv run --no-sync ruff check` over the touched aggregation files passed.

## HEALTH-011 | CLOSED | Filing repository generic payload override reduced to zero errors

`W06.P18.S68` closed the filing-domain secure repository generic override error.
The resident RAG server (`vaultspec-rag search --port 8766`) surfaced the
`SecureBoundRepository` guidance that explicit `payload_model()` overrides are
the intended path away from the `ClassVar[type[BaseModel]]` fallback. The filing
draft repository now follows that pattern and no longer narrows the mutable
`payload_type` class variable.

Verification:

- `uv run --no-sync ty check src/aeat/domain/filing --output-format concise`
  passed.
- `uv run --no-sync pyright src/aeat/domain/filing --level warning --warnings`
  reported 0 errors and 7 pre-existing warnings for private/protected test
  reach-ins.
- `uv run --no-sync pytest src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/domain/filing/test_amendment_roundtrip.py -q`
  passed with 11 tests.
- `uv run --no-sync ruff check src/aeat/domain/filing/_repository.py` passed.

## HEALTH-012 | CLOSED | Renta and transaction Decimal residuals reduced to zero warnings

`W06.P18.S69` closed the focused Renta/transaction Decimal residual bucket. Full
domain type gates remain red due unrelated registry, contributor, deadline, and
modelos test buckets, so this step was scoped to the files named by the S69
diagnostic class.

Changes:

- Renta expense fact and observation currency defaults now use a local
  `Literal["EUR"]` constant rather than a broader `str` constant.
- The Renta finite-Decimal guard now accepts `object`, preserving the runtime
  type check instead of making the guard statically impossible.
- The non-EUR transaction gross-invariant test now narrows `taxable_base` and
  `iva_amount` before summing them.

Verification:

- `uv run --no-sync ty check src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/transactions/test_gross_invariant.py --output-format concise`
  passed.
- `uv run --no-sync pyright src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/transactions/test_gross_invariant.py --level warning --warnings`
  reported 0 errors and 0 warnings.
- `uv run --no-sync pytest src/aeat/domain/transactions/test_gross_invariant.py src/aeat/domain/renta/test_first_slice_routing.py -q`
  passed with 13 tests.
- `uv run --no-sync ruff check src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/transactions/test_gross_invariant.py`
  passed.

## HEALTH-013 | OPEN | W06 type ratchet is Ty-green with explicit Pyright residuals

`W06.P18.S70` captured the post-S64-through-S69 type baseline.

Closed baseline:

- `uv run --no-sync ty check src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/adapters/inbound/declaracion/test_exception_hygiene.py src/aeat/adapters/outbound/aeat/auth src/aeat/application/aggregation src/aeat/domain/filing src/aeat/domain/renta/_ledger_expenses.py src/aeat/domain/transactions/test_gross_invariant.py --output-format concise`
  passed.

Explicit Pyright residual ratchets:

- Auth production profile-service drift:
  `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` reports constructor and
  method-call drift around profile service/repository access.
- Auth provider description return path:
  `src/aeat/adapters/outbound/aeat/auth/_authenticator.py` reports a missing
  return path for `AuthProviderDescription`.
- Auth test config narrowing:
  `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py` reports
  non-required `ConfigDict["frozen"]` access.
- Aggregation and filing packages report no Pyright errors but still carry
  pre-existing private/protected test reach-in warnings.

This keeps W06 honest: the primary `ty` ratchet is green for the executed bucket
set, while Pyright remains an explicit follow-up ratchet rather than an implied
all-green claim.

## HEALTH-014 | CLOSED | Production complexity lane split from test ratchets

`W06.P19.S71` split the generic `just audit-complexity` endpoint into a
production-only lane. The public recipe now delegates to
`just audit-complexity-production`, which runs Radon and a programmatic
Complexipy pass over production source only.

The previous lane mixed production hotspots with top-level package ratchet tests,
which made the refactor queue hard to prioritize. The new lane excludes
`src/aeat/test_*.py`, nested `test_*.py`/`_test_*.py`, `tests` directories, and
the generated `_data` tree for both Radon and Complexipy.

Verification:

- `just --list` exposes `audit-complexity-production`.
- `just audit-complexity-production` now analyzes 862 production files and fails
  with exit code 1 while production cognitive findings remain above the
  threshold.
- The current top production cognitive findings are:
  `resolve_previous_filing_binding_values` and `build_wizard_command` at 44,
  `modelo_compare`, `_push_secure_object_mirror_rows`, and
  `calculation_closure_identities` at 37, followed by registry formula/runtime,
  CLI, live error-classification, secure-object, and parser hotspots.

Residual:

- This does not claim complexity all-green. It makes the failing production lane
  dependable so S73-S77 can burn down source hotspots without being crowded out
  by test-ratchet maintenance debt.

## HEALTH-015 | CLOSED | Top-level ratchet-test complexity lane added

`W06.P19.S72` added `just audit-complexity-tests` for the top-level
`src/aeat/test_*.py` ratchet cohort. This keeps inventory-test cognitive debt
visible without reintroducing it into the production complexity queue.

Verification:

- `just --list` exposes `audit-complexity-tests`.
- `just audit-complexity-tests` analyzes 55 top-level package test files and
  fails with exit code 1 while ratchet-test cognitive findings remain above the
  threshold.
- The current top ratchet-test cognitive findings are:
  `_file_has_inline_tzinfo_guard` at 50, `_collect_violations` in canonical
  clock usage at 30, `_mock_imports` at 27, cast-rationale collectors at 24,
  and skip/xfail plus module-coverage collectors at 23.

Residual:

- This is a dedicated ratchet lane, not an all-green claim. Production burn-down
  continues under S73-S77, and top-level ratchet-test simplification can be
  scheduled separately.

## HEALTH-016 | CLOSED | Wizard command factory cognitive hotspot removed

`W06.P19.S73` extracted `build_wizard_command` responsibilities into focused
helpers for output-language override handling, translated error freezing,
profile-name validation, profile-id resolution, environment language seeding,
foral CCAA refusal, persistence-path dispatch, and success emission.

Verification:

- Focused Complexipy check on
  `src/aeat/application/wizard/_commands.py` now reports
  `build_wizard_command` at cognitive complexity 1. No function in the module is
  above 15.
- `just audit-complexity-production` no longer lists
  `src/aeat/application/wizard/_commands.py::build_wizard_command`; the
  production lane still fails on remaining non-wizard hotspots.
- `uv run --no-sync ruff check src/aeat/application/wizard/_commands.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_commands_helpers.py`
  passed.
- `uv run --no-sync ty check src/aeat/application/wizard/_commands.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_commands_helpers.py --output-format concise`
  passed.
- `uv run --no-sync pytest src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_commands_helpers.py src/aeat/application/wizard/test_wizard_translations_resolve.py -q`
  passed with 29 tests.

Residual:

- Scoped Pyright reports 0 errors and 14 warnings, all in the existing
  private-helper/test-reach-in class.
- A wider wizard/root verification run failed outside the S73 surface because
  the shared worktree currently has a modelo import break:
  `_require_persisted_iva_compensation_decision_matches_revision` is imported
  from `aeat.application.modelo._actions` but not present there.

## HEALTH-017 | OPEN | W05 post-remediation quality-audit baseline remains advisory red

`W05.P17.S60` reran the full `just quality-audit` surface after the W05 shim
and policy cleanup slices. The top-level recipe completed because the advisory
lanes are error-tolerant, but several underlying recipes still fail on tracked
debt. This is a baseline record, not an all-green claim.

Current lane status:

- `just quality-audit` exited 0 at the top level after running all advisory
  recipes.
- `uv run --no-sync ty check src --output-format concise` exited 1 with 800
  diagnostics. The first current cluster is BOE/export encoding and
  deserialisation typing, followed by Sede browser/session object narrowing,
  Google API protocol tests, secure storage tests, generated justificante
  fixtures, and top-level ratchet tests.
- `uv run --no-sync pyright src/aeat --level warning --warnings` exited 1 with
  2055 errors and 514 warnings.
- `uv run --no-sync pyright src/aeat/domain src/aeat/application --level warning --warnings`
  exited 1 with 811 errors and 510 warnings.
- `just audit-structure` exited 1 on the layered architecture contract. Current
  representative violations are domain submission/filing/transaction tests and
  `domain.submission._repository` importing adapter storage SQL surfaces,
  core tests importing domain portal constants, and application tests reaching
  adapters through `aeat.tests.secure_sql`.
- `just audit-deps` exited 0: Deptry reported no dependency issues across 882
  scanned files.
- `just audit-dead-code` exited 0: Vulture reported no current findings under
  the configured allowlist.
- `just audit-complexity-production` exited 1. The current production cognitive
  queue is led by `resolve_previous_filing_binding_values` at 44,
  `_push_secure_object_mirror_rows` and `calculation_closure_identities` at 37,
  `_iter_cross_revision_casilla_divergences` at 34, `initial_values` at 33,
  `classify_live_iva_acquisition_failure` at 32, and two registry/runtime
  functions at 30. This directly feeds S74-S77 follow-up work.
- `just audit-duplication` exited 0 while reporting 23 Python clone groups:
  850 files, 160265 lines, 997233 tokens, 411 duplicated lines, and 4032
  duplicated tokens.
- `just audit-security` exited 0 while Semgrep reported 11 blocking findings
  across 891 tracked targets. The current findings are the ECB dynamic urllib
  use, master-key chmod permissions, SQLAlchemy `text` construction in secure
  objects, Python 3.7 importlib compatibility findings, and dynamic import
  findings in registry snapshot/profile validation plus CLI module loading.

Execution note:

- The `typecheck-audit` recipe still stops after Ty fails, so its full-tree
  Pyright line is not reached inside `just quality-audit`. S60 therefore ran
  full-tree Pyright directly and records that result here. This should be fixed
  separately if the audit recipe is intended to collect both checker matrices
  in one pass even while Ty remains red.

## HEALTH-018 | CLOSED | Modelo CLI command callbacks reduced below C-level complexity

`W06.P19.S74` reduced the remaining modelo CLI command callback complexity
without changing Typer registration or command semantics. The slice extracted
bindings-list target resolution and row projection, work-calculate input parsing
and output advisory assembly, and work-amend option/amendment parsing into
private helpers.

Current focused complexity result:

- `bindings_list` moved from Radon C (20) to B (10).
- `work_calculate` moved from Radon C (19) to A (4).
- `work_amend` no longer appears in the high-complexity command list; its
  branch preflight now lives in `_required_amendment_inputs`.
- Complexipy reports no `_modelo.py` function above the project threshold of
  20; the top `_modelo.py` cognitive entries are `_parse_row_spec` and
  `_resolve_revision_for_cli`, not command callbacks.

Verification:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py` passed.
- Focused real CLI tests passed for bindings-list missing/year behavior,
  work-calculate borrador/help/default behavior, saved-result confirmation, and
  result-summary rendering.
- `uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_modelo.py`
  passed.
- `just audit-complexity-production` still exits 1 on other production
  hotspots, but the filtered output no longer lists `_modelo.py` functions
  above the cognitive threshold.

Residual:

- `uv run --no-sync ty check src/aeat/entrypoints/cli/_modelo.py --output-format concise`
  still reports 26 diagnostics in pre-existing row-splat and revision-object
  typing areas. The S74 refactor removed the local calculate-revision variable
  shadowing diagnostic introduced during extraction, but this step is not a
  full `_modelo.py` type cleanup.
- `_modelo.py` maintainability index remains C (0.00) because the module is
  still very large. Further module decomposition remains valid future work, but
  S74 closes the command callback complexity objective.

## HEALTH-019 | OPEN | 2026-06-05 repository health and complexity baseline

The 2026-06-05 repository-health pass reran the `just` diagnostic surface under
the no-sync shared-worktree discipline. Commands were run sequentially to avoid
the known `uv` virtual-environment lock contention class.

Current lane status:

- `just quality-audit` exited 0 because it is intentionally advisory and
  error-tolerant.
- `just tooling-doctor` exited 1 even though the Python audit tools are present.
  The failure is a recipe-level probe issue: `complexipy --version` prints the
  Typer help/usage surface and exits 1, while Complexipy itself runs through the
  complexity recipes.
- `just typecheck-audit` exited 1 with 801 Ty diagnostics. The dominant Ty
  classes are `invalid-argument-type` (555), `unresolved-attribute` (94),
  `invalid-assignment` (30), `not-subscriptable` (22), `unsupported-operator`
  (20), and `possibly-unresolved-reference` (19).
- `just audit-deprecation` exited 1 with 813 Pyright errors and 514 warnings
  across `src/aeat/domain` and `src/aeat/application`. The dominant report
  classes are `reportPrivateUsage` (386), `reportMissingParameterType` (306),
  `reportArgumentType` (300), `reportAttributeAccessIssue` (77),
  `reportUnusedFunction` (70), and `reportUnnecessaryIsInstance` (44).
- `just audit-structure` exited 1: Import Linter analyzed 1969 files and 8292
  dependencies, with 2 contracts kept and 2 broken. Current failures are the
  core test imports of domain portal constants, the production
  `domain.submission._repository` import of adapter SQL storage, and
  application/domain tests reaching adapter storage through `aeat.tests.secure_sql`.
- `just audit-deps` exited 0.
- `just audit-dead-code` exited 0.
- `just audit-security` exited 0 while Semgrep still reports 11 blocking
  findings under the advisory policy: dynamic urllib in ECB refresh, master-key
  chmod permission policy, SQLAlchemy `text` construction in secure objects,
  Python 3.7 importlib compatibility findings, and dynamic import findings in
  registry/profile validation plus CLI loading.
- `just audit-duplication` exited 0 while reporting 25 Python clone groups
  across 853 analyzed files: 451 duplicated lines (0.28%) and 4413 duplicated
  tokens (0.44%).
- `just audit-complexity-production` exited 1. Complexipy analyzed 885
  production files and found 27 functions above the cognitive threshold of 20.
- `just audit-complexity-tests` exited 1. The top-level package test ratchet
  remains unchanged at 8 functions above the threshold.

Top production cognitive-complexity hotspots:

- 44: `src/aeat/domain/calculations/registry/_bindings_previous_filing.py::resolve_previous_filing_binding_values`.
- 37: `src/aeat/entrypoints/cli/_config_google.py::_push_secure_object_mirror_rows`.
- 37: `src/aeat/domain/calculations/registry/_record_design.py::calculation_closure_identities`.
- 34: `src/aeat/domain/calculations/registry/_cross_revision_divergence.py::_iter_cross_revision_casilla_divergences`.
- 33: `src/aeat/domain/calculations/registry/_formula_initial_values.py::initial_values`.
- 32: `src/aeat/application/live/_errors.py::classify_live_iva_acquisition_failure`.
- 30: `src/aeat/domain/calculations/registry/_formula_runtime.py::_evaluate_m210_resolve_rate`.
- 30: `src/aeat/domain/calculations/registry/_bindings.py::_validate_invoice_fact_and_aggregation`.
- 29: `src/aeat/domain/calculations/registry/_record_design.py::calculation_closure_numbers`.
- 27: `src/aeat/domain/calculations/registry/_validate_semantic_role_typos.py::_semantic_role_looks_like_typo`.

Top monolithic module pressure:

- `src/aeat/entrypoints/cli/_ledger.py`: 3808 non-comment LOC, 95 functions,
  max function length 194 lines at `ledger_classify`; also contains
  `rule_apply` above the cognitive threshold.
- `src/aeat/application/ledger/_actions.py`: 3432 non-comment LOC, 102
  functions, max function length 221 lines at `merge_transactions`.
- `src/aeat/application/modelo/_actions.py`: 3256 non-comment LOC, 74
  functions, 21 classes, max function length 273 lines at
  `amend_modelo_revision`.
- `src/aeat/entrypoints/cli/_modelo.py`: 2790 non-comment LOC, 53 functions,
  max function length 330 lines at `work_calculate`. S74 reduced the command
  callback cognitive findings, but module-size pressure remains.
- `src/aeat/entrypoints/cli/_config/__init__.py`: 2554 non-comment LOC, 58
  functions, max function length 151 lines at `config_status`.
- `src/aeat/domain/calculations/registry/_schema.py`: 2153 non-comment LOC, 78
  functions, 50 classes. This is a schema-density hotspot more than a single
  long-function hotspot.
- `src/aeat/domain/calculations/registry/_bindings.py`: 2152 non-comment LOC,
  90 functions, 31 classes, with `_validate_invoice_fact_and_aggregation` still
  above the cognitive threshold.
- `src/aeat/application/live/__init__.py`: 2151 non-comment LOC, 73 functions,
  23 classes, max function length 117 lines.

Mitigation queue implied by this pass:

- Continue W06.P19 with registry runtime and binding simplification before
  claiming production complexity green.
- Treat ledger as both a function-complexity and module-monolith problem; small
  helper extraction alone will not address the CLI module size.
- Keep typechecker burn-down focused by diagnostic class. The largest immediate
  Ty payoff is invalid argument typing; the largest scoped Pyright payoff is
  private test reach-ins plus missing parameter annotations.
- Repair `tooling-doctor` separately so it probes Complexipy through an actual
  import or tiny file analysis instead of `complexipy --version`.
- Keep dependency and Vulture lanes green; do not spend W06 capacity there
  unless new findings appear.

Execution notes:

- RAG was useful for locating the ledger `rule_apply`/application-action
  surface. Two deeper hotspot searches against the resident server timed out and
  were not treated as blockers because direct gate evidence was available.
- The raw diagnostic logs were written to the operator temp directory for this
  run and were summarized here rather than committed as bulky artifacts.

## Suggested Workstreams

1. Repair packaging environment deterministically: schedule a clean `uv sync` window
   after the `vaultspec-rag.exe` lock clears, then document the no-deps editable
   reinstall as the emergency repair path for shared worktrees.
2. Split diagnostics from tests in architecture contracts: decide whether test files
   should be excluded from layer contracts or moved behind sanctioned test helper
   boundaries.
3. Type ratchet: fix the aggregation source-kind model, secure repository payload
   override pattern, and optional-member hotspots before attempting full-tree type
   ratchets.
4. Complexity refactor queue: start with CLI `_modelo.py`, registry formula
   runtime, registry bindings/schema, CLI `_ledger.py`, and modelo/ledger action
   services.
5. Dependency hygiene: keep Deptry green and guard against dependency drift in
   the final W06 gates.
6. Semgrep policy: split production source scans from mirrored official data and
   intentional redaction/security tests before treating security counts as a gate.

## HEALTH-019-S75 | CLOSED | 2026-06-05 registry formula complexity reduction

W06.P19.S75 reduced the planned registry formula initial-value hotspot and the
adjacent M210 rate resolver hotspot without changing registry schema semantics.

Complexity deltas:

- `src/aeat/domain/calculations/registry/_formula_initial_values.py::initial_values`
  moved from Radon E (35) and Complexipy 33 to Radon A (4) and Complexipy 0.
- `src/aeat/domain/calculations/registry/_formula_runtime.py::_evaluate_m210_resolve_rate`
  moved from Radon D (27) and Complexipy 30 to Radon B (6) and Complexipy 6.
- `src/aeat/domain/calculations/registry/_formula_initial_values.py` now has no
  function above Radon B or Complexipy 8.
- `src/aeat/domain/calculations/registry/_formula_runtime.py` still has
  `calculate_registry_snapshot` at Radon D (22) and Complexipy 17. That is a
  remaining runtime orchestration hotspot, not part of the S75 initial-value/M210
  resolver scope.

Focused verification:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_formula_initial_values.py`
  passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_formula_initial_values.py --output-format concise`
  passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_modelo_130_registry.py src/aeat/domain/calculations/registry/test_modelo_210_registry.py src/aeat/application/modelo/test_modelo_210_phase1.py -q`
  passed with 53 tests.
- `uv run --no-sync radon cc src/aeat/domain/calculations/registry/_formula_initial_values.py src/aeat/domain/calculations/registry/_formula_runtime.py -s`
  captured the reduced Radon grades.
- `uv run --no-sync complexipy src/aeat/domain/calculations/registry/_formula_initial_values.py src/aeat/domain/calculations/registry/_formula_runtime.py --max-complexity-allowed 20`
  passed for the touched files.

Residual carried forward:

- A broader M200 registry test probe still fails before reaching the requested
  assertion surface because previous-filing bound casilla `01494` requires the
  unresolved binding
  `modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores`.
  This was left visible and not bypassed by the complexity refactor.

## HEALTH-019-S76 | CLOSED | 2026-06-05 ledger projection complexity reduction

W06.P19.S76 reduced the active ledger CLI projection hotspots in
`src/aeat/entrypoints/cli/_ledger.py`. The plan row named list/review
projection complexity; current discovery showed `ledger list` was already low,
`ledger review` was moderate by Radon but below the Complexipy threshold, and
`rule_apply` was the remaining ledger function above the Complexipy threshold.

Complexity deltas:

- `ledger_review` moved from Radon C (15) and Complexipy 6 to Radon A (1) and
  Complexipy 0.
- `rule_apply` moved from Radon C (14) and Complexipy 22 to Radon A (4) and
  Complexipy 2.
- `ledger_list` remains Radon A (2) and Complexipy 1.
- The touched module now passes `complexipy ... --max-complexity-allowed 20`;
  `ledger_classify` remains the highest ledger command by Radon at C (20) and
  Complexipy 17.

Focused verification:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger.py` passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_ledger.py --output-format concise`
  passed after local typed-boundary cleanup.
- `uv run --no-sync radon cc src/aeat/entrypoints/cli/_ledger.py -s`
  captured the reduced Radon grades.
- `uv run --no-sync complexipy src/aeat/entrypoints/cli/_ledger.py --max-complexity-allowed 20`
  passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_ledger_bulk_classify.py src/aeat/entrypoints/cli/test_ledger_list_filter.py -q`
  passed with 23 tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_surface.py::test_app_ledger_import_reimport_review_round_trips_state src/aeat/entrypoints/cli/test_backend_boundary.py::test_manual_ledger_import_and_review_boundaries_stay_backend_owned -q`
  passed when run as part of the three-test backend probe.

Residuals carried forward:

- `test_ledger_ux_defect_cluster.py::test_review_by_short_id_prefix_resolves_the_transaction`
  and `test_review_by_full_id_still_resolves_the_transaction` still fail before
  the review command is reached because import setup exits with
  `Storage runtime is not ready for profile-bound storage: The database route
  does not match the active bucket session`.
- `test_backend_boundary.py::test_manual_ledger_review_help_exposes_backend_filter_vocabulary`
  still fails because rendered `ledger review --help` does not include the
  expected `classification` filter token.

## HEALTH-019-S77 | CLOSED | 2026-06-05 complexity residual ratchet

W06.P19.S77 persisted the post-refactor complexity baseline after the modelo CLI,
registry formula, and ledger projection reductions. The complexity lanes remain
advisory-red, but the active W06.P19 reductions removed the targeted command and
registry hotspots from the Complexipy over-threshold list.

Current complexity lane status:

- `just audit-complexity-production` exits 1.
- Complexipy production scan analyzed 880 files.
- Production functions above the project threshold of 20: 24.
- `just audit-complexity-tests` exits 1.
- Top-level package test functions above the threshold of 20: 8.

Current production over-threshold ratchet:

- 44: `src\aeat\domain\calculations\registry\_bindings_previous_filing.py::resolve_previous_filing_binding_values`
- 37: `src\aeat\entrypoints\cli\_config\_google.py::_push_secure_object_mirror_rows`
- 37: `src\aeat\domain\calculations\registry\_record_design.py::calculation_closure_identities`
- 34: `src\aeat\domain\calculations\registry\_cross_revision_divergence.py::_iter_cross_revision_casilla_divergences`
- 32: `src\aeat\application\live\_errors.py::classify_live_iva_acquisition_failure`
- 30: `src\aeat\domain\calculations\registry\_bindings.py::_validate_invoice_fact_and_aggregation`
- 29: `src\aeat\domain\calculations\registry\_record_design.py::calculation_closure_numbers`
- 27: `src\aeat\domain\calculations\registry\_validate_semantic_role_typos.py::_semantic_role_looks_like_typo`
- 27: `src\aeat\domain\calculations\registry\_remote_state_guard.py::RemoteStateGuardPolicy::_validate_policy`
- 27: `src\aeat\application\storage\calc_sheets\_workbook_export.py::_apply_styling`
- 26: `src\aeat\adapters\persistence\storage\sql\secure_objects.py::SecureObjectRepository::_ensure_deterministic_object_keys`
- 26: `src\aeat\adapters\outbound\aeat\sede\_declarations.py::_capture_filed_declaration_observation_from_row`
- 25: `src\aeat\domain\iva_compensation\_reconciliation.py::reconcile_iva_compensation_wallet`
- 25: `src\aeat\domain\calculations\registry\_bindings.py::_validated_counterpart_selector`
- 25: `src\aeat\application\modelo\_profile_binding.py::resolve_profile_sourced_bindings`
- 25: `src\aeat\application\modelo\_actions.py::_resolve_m210_rate`
- 25: `src\aeat\adapters\outbound\aeat\auth\_authenticator.py::AeatAuthenticator::_resume_from_storage_state_locked`
- 25: `src\aeat\adapters\inbound\declaracion\_parser.py::_extract_profile_values`
- 24: `src\aeat\entrypoints\cli\_errors.py::command_error_boundary`
- 24: `src\aeat\domain\calculations\registry\_applicability.py::ModeloApplicabilityRule::evaluate`
- 24: `src\aeat\application\modelo\_result_summary.py::calculation_result_summary`
- 24: `src\aeat\application\calculations\_binding_prefill.py::_gather_observations`
- 23: `src\aeat\application\workflow\_resume.py::resolve_modelo_workflow_resume_target`
- 21: `src\aeat\domain\contribuyente\_descendant_facts.py::descendant_list_from_facts`

Current top-level test over-threshold ratchet:

- 50: `src\aeat\test_utc_validator_enrollment_inventory.py::_file_has_inline_tzinfo_guard`
- 30: `src\aeat\test_canonical_clock_usage.py::_collect_violations`
- 27: `src\aeat\test_mock_inventory.py::_mock_imports`
- 24: `src\aeat\test_core_time_deletion_and_cast_rationale.py::_collect_cast_violations`
- 24: `src\aeat\test_cast_rationale_inventory.py::_collect_violations`
- 23: `src\aeat\test_no_skip_xfail.py::_forbidden_marker_sites`
- 23: `src\aeat\test_every_module_has_test_coverage.py::_aeat_imports_in`
- 21: `src\aeat\test_w17_p49_closure.py::test_s634_no_bare_eur_default_in_ledger_expenses`

Next complexity targets should start with the remaining registry binding and
record-design hotspots, followed by config Google sync, live error
classification, and the top-level inventory-test collectors.

## HEALTH-020-S78 | CLOSED | 2026-06-05 Ruff scratch/probe scope verification

W06.P20.S78 verified the Ruff scope for root scratch and probe artifacts in the
current shifted worktree. The configuration change itself was already present in
`HEAD`: `tool.ruff.extend-exclude` excludes `run_p04_s11_test.py`,
`scratch_probe*.py`, `test_attachment_fix.py`, `test_m714.py`, and
`scripts/classify_m200.py`.

Verification:

- `git show HEAD:pyproject.toml` confirms the Ruff `extend-exclude` block is
  already committed.
- `uv run --no-sync ruff check . --output-format concise` no longer reports the
  named scratch/probe paths.
- `uv run --no-sync ruff check . --statistics` still exits 1 with 475 findings.
  The remaining findings are outside the S78 scratch/probe scope and are now
  dominated by docs tooling, contributor scripts, and the concurrent
  test-topology relocation.

Residual carried forward:

- The full Ruff lane remains red. Representative classes are E501 line length,
  D104 package docstrings in relocated `tests` packages, E701 one-line
  statements in contributor scripts, S105/S106 synthetic secret literals, S603
  subprocess probes, and import-order findings.
- `pyproject.toml` has unrelated dirty WIP from the concurrent test-topology
  refactor. S78 did not stage or modify that file.

## HEALTH-021-S79 | CLOSED | 2026-06-05 Dependency declaration drift verification

W06.P20.S79 reran the production dependency declaration drift lane against the
current shifted worktree. No `pyproject.toml` edit was needed.

Verification:

- `just audit-deps` exits 0.
- Deptry scanned 884 files under `src/aeat`.
- The configured command uses `--known-first-party aeat` and excludes test
  paths from the production dependency audit.
- Deptry reported: no dependency issues found.

Residual carried forward:

- None for dependency declaration drift in the current production scope.

## HEALTH-022-S80 | CLOSED | 2026-06-05 Vulture dead-code verification

W06.P20.S80 reran the configured Vulture lane against the current shifted
worktree. No source deletion or suppression edit was needed.

Verification:

- `just audit-dead-code` exits 0.
- The configured command is `uv run --no-sync vulture --config pyproject.toml`.
- Vulture reported no current findings.

Residual carried forward:

- None for the Vulture dead-code lane in the current configured scope.

## HEALTH-023-S81 | CLOSED | 2026-06-05 Semgrep security lane zero finding state

W06.P20.S81 reran the Semgrep production-security lane, resolved the 11 current
blocking findings, and clarified `.semgrepignore` policy so production-source
findings are fixed or justified at the audited line rather than hidden through
production exclusions.

Verification:

- `just audit-security` exits 0.
- Semgrep reports 0 findings and 0 blocking findings.
- The scan covers 988 tracked targets and runs 323 rules.
- `.semgrepignore` continues to exclude mirrored registry/corpus data, tests,
  and explicit test-support files, and now states that production-source
  exclusions must not be added to force a green scan.
- Scoped Ruff and Ty checks passed for every touched production file.
- Focused pytest passed for ECB refresh behavior and the registry extraction
  parser validation regression.

Residual carried forward:

- The broader repository still has unrelated dirty preflight/export-test WIP in
  the shared worktree; S81 did not absorb it.

## HEALTH-024-S82 | CLOSED | 2026-06-05 Duplication residual ratchet

W06.P20.S82 reran the configured jscpd duplication lane and preserved the
current clone set as an explicit ratchet instead of hiding or scattering
cross-domain refactors through the hygiene row.

Verification:

- `just audit-duplication` completed.
- jscpd analyzed 853 Python files and 163,121 lines.
- jscpd reported 36 clone groups.
- Current duplicated lines: 650, or 0.4%.
- Current duplicated tokens: 6,487, or 0.63%.

Current clone-family ratchet:

- AEAT Sede NIF/GROI checker shapes.
- Registry previous-filing binding and relation validation helpers.
- Registry NIF-IVA/GROI oracle helpers.
- Modelo work CLI rendering/addressing blocks.
- Registry CLI command-output blocks.
- Ledger business-invoice CLI blocks from current shared worktree state.
- Ledger model paired record blocks.
- Live borrador/censo acquisition blocks.
- Declaracion/justificante error hierarchy blocks.

Residual carried forward:

- The duplication lane remains advisory-red with 36 clone groups.
- The next safe duplication slices should start with one cohesive subsystem at a
  time: Sede checker shared helpers, registry relation/binding helpers, modelo
  work CLI output helpers, then registry CLI output helpers.

## HEALTH-025-S83 | OPEN | 2026-06-05 Hard gate attempt blocked by topology and environment

W06.P21.S83 attempted the hard-gate suite and found the current shifted
worktree is not green.

Gate matrix:

- `just verify-shims`: pass.
- `just tooling-doctor`: fail, because `uv pip check` reports broken or
  incomplete `torch` metadata in `.venv`.
- `just audit-structure`: fail, because import-linter contracts still address
  many tests at their pre-relocation module names and now see relocated
  `tests/` packages as contract violations.
- `just lint`: fail before Ruff, because `uv run` tries to reinstall
  `torch==2.12.0` and cannot rename `torch\lib\c10.dll` on Windows.
- `just typecheck`: fail, dominated by unresolved relative imports from the
  active relocated-test topology.
- `just test`: fail before pytest, blocked by the same `torch\lib\c10.dll`
  install/rename failure as `just lint`.

Residual carried forward:

- S83 remains open; no green hard-gate claim is made.
- Repair the relocated-test import surface, update structural policy to the new
  `tests/` module names without weakening production contracts, and clear the
  local venv torch lock through a non-destructive environment repair before
  rerunning the hard gate suite.
