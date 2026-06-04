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
4. Complexity refactor queue: start with CLI `_modelo.py`, CLI `_ledger.py`,
   registry formula runtime, registry bindings/schema, identity diagnostics, and
   modelo/ledger action services.
5. Dependency hygiene: resolve the six Deptry findings and decide whether `torch`
   and `formulas` are runtime, optional, or stale dependencies.
6. Semgrep policy: split production source scans from mirrored official data and
   intentional redaction/security tests before treating security counts as a gate.
