---
tags:
  - "#audit"
  - "#aeat-restructure"
date: 2026-05-01
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-summary]]"
---

# Post-restructure code audit (open-ended, continuously appending)

## Status

`in_progress` — autonomous open-ended audit launched 2026-05-01 after
the 15-step restructure pipeline closed. The audit appends findings as
parallel sub-agents and reviewers surface them; no edits to source
code happen inside this doc — every finding either lands as a separate
fix PR or is queued as an issue.

## Scope

The audit treats the post-restructure tree (`src/aeat/` under the new
hexagonal layered layout) as the unit of inspection. In scope:

- **Code security** — secret leakage, command injection, deserialisation
  trust, path-traversal, network egress, OS-keychain mishandling,
  certificate / private-key handling.
- **Tautological tests** — assertions that re-state the implementation
  (`x == x` after rebuild), tests that mock the very surface they
  claim to verify, tests that pass on any implementation by design.
- **Stubs / fakes / patches / mocks / shadows** — production code paths
  that wire fakes; `monkeypatch.setattr` calls that shadow real
  surfaces; private-symbol re-exports that paper over a bypass.
- **Implementation gaps** — production-reachable
  `raise NotImplementedError`, hollow Protocol stubs, empty function
  bodies with callers, placeholder enum values rejected by validators.
- **Missing features** — modelo / casilla / year coverage gaps,
  documented capabilities that have no entry-point binding, CLI
  commands that print but don't act.
- **Uniformity gaps** — modelos with rulesets for some years but not
  others; modelos with one extractor + one mapping + no formula;
  documents missing for features that have code but no plan / ADR.
- **Stale code-review findings** — gemini-code-assist comments left
  un-addressed across the 20 restructure-era PRs (#478 → #501).

Out of scope:

- Editorial / cosmetic preferences (whitespace, comment phrasing) that
  don't carry an architectural or correctness signal.
- Pre-restructure design decisions that the ADR explicitly upheld.

## Disposition matrix

Every finding is dispositioned (matching the restructure plan's matrix):

- **FIX** — small, mechanical correction; lands in a follow-up PR
  bundled by area.
- **FILE** — non-trivial work; opens a GitHub issue with full context.
- **STRIKE** — false positive after deeper inspection; record the
  reason so a future reviewer doesn't rediscover the false alarm.

## Findings ledger

Each finding gets one row. New findings are **appended** at the bottom
of the appropriate section; existing rows are not edited except to
update disposition status (e.g. `FILE pending → FILE filed #NNN →
FILE landed #PR`).

### A. Stale gemini-code-assist findings on restructure PRs

Walked 20 restructure-era PRs (#478 → #501). Findings:

#### A1. Critical gap: gemini quota exhausted on the four largest PRs

The four post-keystone PRs went **un-reviewed by gemini**:

- **#495** (Step 11 markers — 405+ test files, axis-B realignment) — quota exhausted
- **#496** (Step 11 sanitization — 197 source files, dev-metadata strip) — quota exhausted
- **#497** (Step 12 Tier-3 vault — 589 vault docs) — quota exhausted
- **#501** (Step 13/14/15 closure docs + ADR outcomes) — quota exhausted

**Disposition**: FILE — these PRs had only the relative-imports check + ruff + ty + the Windows/Ubuntu test gates but no semantic review. The post-restructure audit (this document) compensates by deeply auditing the affected surfaces.

#### A2. HIGH-priority gemini findings (verified)

| PR | path:line | finding | disposition | rationale |
|----|-----------|---------|-------------|-----------|
| #486 | `src/aeat/domain/financial/transactions/__init__.py` | Promoting `TransactionCatalogueRepository` to public `__init__.py` breaks lazy-loading | **STRIKE** | Verified: lazy-loading IS preserved via `__getattr__` (line 54-62) + `TYPE_CHECKING` import (line 50-51). Gemini missed the implementation pattern. |
| #490 | `scripts/rebase_imports.py:19` | Relative imports not re-anchored as documented | **STRIKE** | Verified: relative-import re-anchoring is handled by `scripts/fix_relative_imports.py` (separate script ran in same Step-7 keystone). The rebase script's docstring claim was about absolute imports. |
| #490 | `scripts/rebase_imports.py:121` | `rewrite_text` multi-pass efficiency | **STRIKE** | Post-merge tooling; rebase is a one-shot operation that already ran. Future re-runs are rare; performance is non-critical. |
| #491 | `justfile:94` | `lint-imports` recipe needs `import-linter` package | **STRIKE** | Verified: `import-linter>=2.0` is at `pyproject.toml:135` in dev deps. Gemini was wrong. |
| #493 | `scripts/run_layout_move.py:312` | Shim generation assumes target has `__all__` | **FILE** | Real concern: the 4 shim modules currently do `from <target> import __all__`. If a future PR removes `__all__` from any target (errors/auth/export/formulas), shim import will crash. Hardening: switch to `getattr(module, '__all__', ())` with importlib. The keystone shim writer already used this pattern but the actual shim files in main use the direct import. → File hardening issue. |

#### A3. MEDIUM-priority gemini findings (verified)

| PR | path:line | finding | disposition |
|----|-----------|---------|-------------|
| #478 | exec docs | "all 4 destination layers" vs "ALL 6" count inconsistency | **STRIKE** (exec record retrospective; behaviour unaffected) |
| #481 | exec docs | `_FakeAdapter` import claim contradicts code; `grep` missing `-E` | **STRIKE** (exec record only) |
| #482 | `src/aeat/domain/schema/_boe_extractor.py:1-15` | docstring uses generic Extractor ref | **STRIKE** — current docstring (post-rewrite) doesn't reference `Extractor` at all; gemini comment stale |
| #483 | `src/aeat/adapters/inbound/identity/_tax_id.py:30` | docstring missing K, L, M from CIF letter list | **FIX** — confirmed: `_CIF_LEADERS = "ABCDEFGHJKLMNPQRSUVW"` includes K/L/M but docstring at line 30 says `"ABCDEFGHJNPQRSUVW"`. Real drift. |
| #483 | `src/aeat/adapters/inbound/identity/_tax_id.py:30+` | lost ABEH explanatory comment | **STRIKE** — current docstring at line 33 still says "leading letters in ABEH require a digit control"; comment is preserved. |
| #483 | `src/aeat/adapters/inbound/identity/_tax_id.py:118` | PEP 8: `__all__` should be after imports, before constants | **FILE** — confirmed: `__all__` is at line 118 (last); should be near top. Style nit but real. |
| #483 | `src/aeat/domain/financial/invoices/_validators.py:5` | typo "sanitiser" should be "sanitizer" | **FIX** — confirmed: comment at line 5 says "sanitiser, CLI submission gates"; should match the package name `aeat.adapters.inbound.sanitizer`. |
| #484 | `src/aeat/domain/formulas/__init__.py:56` | `__all__` not alphabetically sorted | **FILE** — verified: `MODELO_100_SUMMARY_2025` (line 56) sorts after `AddFormula` (line 57) by case-insensitive sort but ASCII puts `M` after `A`. Convention is constants-first, then alpha names. Gemini's strict-alpha read is debatable. Lower priority. |
| #485 | exec docs | 24 tests not collected | **STRIKE** — `(24 deselected)` per pytest output; deselected ≠ uncollected. |
| #487 | `src/aeat/core/_test_paths.py` | `monkeypatch.chdir` / `monkeypatch.setenv` preferred | **FILE** — modernisation; not a correctness issue. |
| #488 | `.importlinter:21+59` | "core is leaf" contract redundant; naming ambiguity | **FILE** — review the contract names + redundancy after the dust settles. |
| #488 | `pyproject.toml:134` | comment dependency-flow direction | **FILE** — comment vs import-linter direction may diverge after carve-out evolution. |
| #489 | `scripts/verify_shims.py:154+164` | command-construction + broad except | **STRIKE** — script is one-shot tooling; verify_shims is invoked manually with controlled args. |
| #491 | `justfile:88` | `--no-sync` inconsistency | **STRIKE** — verified consistent: every recipe that runs `uv run` uses `--no-sync` (lines 88, 90, 94). |
| #493 | `scripts/fix_relative_imports.py:235` | `main` duplicates rewrite logic | **STRIKE** — post-merge tooling; one-shot scripts do not need DRY. |
| #493 | `scripts/restructure_rewrite_map.json:51` | mojibake `â†'` in arrow | **FIX** — re-encode the file as UTF-8 with proper U+2192 arrow. |

### B. Code-security findings

(populated by the security-review sub-agent)

### C. Tautological-test findings

Sub-agent scanned 1086 .py files (344 test files). Aggregate: **no `unittest.mock` imports**, **no `@patch` decorators**, **no empty test bodies**, and **no `pytest_mock`**. AST scan found zero non-Protocol stub functions in production. The 56 `Protocol` classes with `...` bodies are STRUCK collectively.

| severity | file:line | finding | disposition | rationale |
|----------|-----------|---------|-------------|-----------|
| MEDIUM | `src/aeat/entrypoints/cli/_test_bootstrap.py:69-80` | `TestScratchConstants` class has 4 methods that each `assert IMPORTED_CONST == "<literal>"` against the only definition site | **FILE** | Test passes on every implementation by definition; replace with a contract test that round-trips through the Drive API surface |
| MEDIUM | `src/aeat/adapters/outbound/aeat/export/_formats/test_modelo_130_2024.py:24,27` | `test_total_record_length` asserts `RECORD_LENGTH == 878`; `test_encoding` asserts `ENCODING == "cp1252"` | **FILE** | Pin-the-constant tests; the contiguity test directly above + the byte-exact golden fixture are the real guards |
| MEDIUM | `src/aeat/adapters/outbound/aeat/export/_formats/test_modelo_303_2024.py:26` | `test_encoding_is_iso_8859_1` re-states an imported literal | **FILE** | Same pattern as above |
| MEDIUM | `src/aeat/domain/rental/_test_expense_rollup.py:171-172` | `TestCarryForwardConstantInBounds.test_max_years_constant_is_4` asserts `CARRY_FORWARD_MAX_YEARS == 4` | **FILE** | Tautology with no behavioural envelope; cannot detect drift |
| MEDIUM | `src/aeat/domain/financial/vat/test_categories.py:52-53` | `test_eu_member_state_has_27_members` ends with `EUMemberState.ES.value == "es"` and `EUMemberState.DE.value == "de"` (StrEnum self-value) | **FIX** | Earlier `len(list(EUMemberState)) == 27` is real; drop the trailing identity asserts |
| MEDIUM | `src/aeat/entrypoints/cli/_test_cloud_live.py:48,60,72` | Three tests end with `assert isinstance(result, list)` after `result = list(...)` | **FIX** | Replace with shape assertions on element type |
| LOW | `src/aeat/domain/justificante/test_verify_live.py:39` | `assert isinstance(result, bool)` after function annotated `-> bool`; `pytest.skip` swallows the failure path | **FILE** | Test silently passes via skip on real failure; assertion is tautological per the type annotation |
| LOW | 9 files (multiple `test_smoke.py`) | `assert <package>.__doc__ is not None` + `assert issubclass(errors.AeatError, Exception)` | **FILE / partial STRIKE** | The `__doc__` checks are weak; the `issubclass(AeatError, Exception)` IS strictly tautological — `AeatError` is `class AeatError(Exception):` |
| LOW | `src/aeat/entrypoints/cli/test_live_casillas.py:20-23` | `test_real_llm_workflow_is_blocked_until_issue21_lands` always calls `pytest.skip(...)` at the end | **FILE** | Tautological-by-skip: 3 parametrize variants → 3 guaranteed skips. Convert to `xfail(strict=True)` so issue #21 landing flips it green |
| STRIKE | `src/aeat/domain/casillas/test_smoke.py:17` (+ peers) | `assert logging.get_logger(__name__).name == __name__` | STRIKE | Acts as a thin-wrapper guard for `logging.get_logger`; legitimate even if borderline |

### D. Stubs / fakes / patches / mocks / shadows

| severity | file:line | finding | disposition | rationale |
|----------|-----------|---------|-------------|-----------|
| **HIGH** | `src/aeat/adapters/outbound/llm/_providers/fake.py:10` + `_providers/__init__.py:5,17` | `_FakeAdapter` is a fully implemented adapter living in production source, re-exported in `__all__`. Only test files import it. | **FILE** | Project mandate forbids fakes; the artefact ships in the wheel. Either move under a test-only path or strike if "deterministic real adapter" is the team-acknowledged escape hatch. |
| **HIGH** | `src/aeat/adapters/outbound/llm/_client.py:53` | `LLMClient.__init__` accepts `_adapter: _ProviderAdapter \| None = None` — a private kwarg whose only callers are tests | **FILE** | Test seam baked into a public class; downstream callers can pass `_adapter=` to bypass provider selection. Either remove + use a factory, or rename to a clearly-public `adapter_override` |
| MEDIUM | `src/aeat/adapters/persistence/storage/_master_key.py:454-460,787-794` | `_reset_for_tests(cls)` is invoked by production CLI (`security.py:645,690`) | **FIX** | Misnamed — this is a real production cache-reset primitive. Rename to `_clear_cache` |
| MEDIUM | `src/aeat/adapters/persistence/storage/_test_lock.py:88-91` + `test_substrate_smoke.py:159-162` | `@pytest.mark.skipif(... reason="Windows mp.spawn flaky in CI; opt-in via AEAT_RUN_LOCK_CONTENTION=1")` | **FILE** | **Direct violation of project mandate** "never add skips ... and instead tackle the core issue". Two cross-process lock tests silently skipped on every Windows CI run |
| MEDIUM | `src/aeat/entrypoints/cli/test_json_pipe_safety.py:145-152` | `@pytest.mark.skip(reason="Flaky on Linux post-restructure: master-key passphrase derivation diverges...")` | **FILE** | Same mandate violation; skip reason names a real bug (master-key passphrase divergence under new `aeat.adapters.persistence.storage` path) |
| MEDIUM | `src/aeat/entrypoints/cli/test_live_casillas.py:20-23` | Always-skip test gated on future issue #21 | **FILE** | "Always skip" is both a tautology and a stub; convert to `xfail(strict=True)` |
| LOW | `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py:775` | Delegating spy via `monkeypatch.setattr` on `certificate_health` | **STRIKE** (acceptable) | Wrapper still calls real implementation; one short edit from becoming a real mock — flag if pattern hardens |
| LOW | `src/aeat/entrypoints/cli/_test_doctor.py:62-77` | Runtime `if sys.platform != "win32": pytest.skip(...)` instead of `@pytest.mark.skipif` decorator | **FIX** | Cosmetic; convert to decorator for visibility |
| LOW | `src/aeat/core/_test_paths.py:111-118` | Manual `os.chdir`/`finally` instead of `monkeypatch.chdir` | **FIX** | (Same finding as gemini #487 under new path) |
| LOW | `src/aeat/entrypoints/cli/submission/test_schema_registry_shape.py:50,66` | `if entry.kind != "record": pytest.skip(...)` is dispatch logic inside parametrized fixture | **FIX** | Convert to `pytest.param(..., marks=...)` |

#### D. Strikes (legitimate patterns inspected)

- The 4 public-surface re-export shims (`errors`, `auth`, `submission`, `formulas`) — clean star-import + DeprecationWarning; no test-bypass.
- `src/aeat/adapters/outbound/aeat/_gate.py` `PYTEST_CURRENT_TEST` reference — audit-record only, production never branches on it.
- `src/aeat/entrypoints/cli/workflow/_test_doubles.py` — shared test-helpers, no production import.
- `src/aeat/adapters/outbound/aeat/browser/test_session.py` `DummyEvasion`/`StubContext`/`StubBrowser`/`StubChromium`/`StubPlaywright` — deterministic real-class Playwright protocol implementations, no production import.
- 56 `Protocol` classes with `...` bodies — legitimate Python protocol stubs.
- `keyring.get_password` `monkeypatch` patterns — patching a 3rd-party boundary, legitimate.
- `PROJECT_ROOT` `monkeypatch` patterns — env-base-path overrides.
- `EXPECTED_COUNTS` `monkeypatch` in `test_mutator_tautology_regression.py` — literal regression-defense for prior tautology bug.

### E. Implementation-gap findings

(populated by the gap-audit sub-agent)

### F. Missing-feature findings

(populated by the coverage-matrix sub-agent)

### G. Uniformity-gap findings

(populated by the coverage-matrix sub-agent)
