---
tags:
  - '#audit'
  - '#repo-health-diagnostics'
date: '2026-06-04'
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
5. Dependency hygiene: resolve the six Deptry findings and decide whether `torch`
   and `formulas` are runtime, optional, or stale dependencies.
6. Semgrep policy: split production source scans from mirrored official data and
   intentional redaction/security tests before treating security counts as a gate.
