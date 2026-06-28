---
tags:
  - "#audit"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-summary-exec]]"
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

Audit walked the seven security domains called out in the task brief
(secrets, path-traversal, subprocess, deserialisation, network egress,
live-AEAT-write, restructure shims) plus a pass over logging filters
and TLS posture. Sources audited:

- `src/aeat/adapters/persistence/storage/_master_key.py`,
  `_secret_store.py`, `_redaction.py`, `_recovery.py`,
  `_path_safety.py`;
- `src/aeat/adapters/outbound/aeat/auth/` (entire package, including
  `_certificate_backends/_httpx_fallback.py`, `_clave_movil.py`,
  `_file_permissions.py`, `_gate.py`, `__init__.py`,
  `certificate.py`);
- `src/aeat/adapters/outbound/aeat/export/` (engine, errors,
  submitters);
- `src/aeat/adapters/outbound/llm/_providers/` (openai, gemini,
  local, base);
- `src/aeat/adapters/inbound/sanitizer/_pipeline.py`,
  `src/aeat/adapters/inbound/pdf/` (pikepdf-based);
- `src/aeat/application/setup/_env_writer.py`;
- `src/aeat/core/paths.py`, `_test_paths.py`, `logging.py`,
  `env_io.py`;
- `src/aeat/entrypoints/cli/doctor.py`,
  `entrypoints/mcp/launch_google_workspace.py`;
- shim modules `src/aeat/{errors,auth,submission,formulas}/__init__.py`
  and the canonical targets they re-export.

| severity | file:line | finding | disposition | rationale |
|----------|-----------|---------|-------------|-----------|
| HIGH | `src/aeat/adapters/outbound/aeat/auth/__init__.py:287` | `get_oauth_credentials` writes the cached Google OAuth token (incl. long-lived refresh-token) via `token_path.write_text(creds.to_json())` -- no `os.open(..., 0o600)`, no post-write `os.chmod`, no call to the in-package `restrict_file_permissions` helper. The token directory `settings.aeat_token_dir` is created only as `mkdir(parents=True, exist_ok=True)` (default mode). On POSIX the file lands at the user's umask (usually 0644) and the directory at 0755; on multi-user hosts a long-lived refresh token is therefore world-readable. | FILE | The codebase already imports `restrict_file_permissions` in the same module (line 61) for cert / Cl@ve session-state writes; the same hardening must wrap the OAuth token write. The substrate's `SecretStore` (SECRET-class, AES-256-GCM at rest) is the strict-correct destination. Filing is preferred over a quick FIX so the migration to `SecretStore` can be designed deliberately rather than bolting on a chmod. |
| MEDIUM | `src/aeat/adapters/outbound/llm/_providers/gemini.py:67` | Gemini API key is passed as a URL query parameter (`params={"key": self._api_key}`). Google's API also accepts the `x-goog-api-key` HTTP header, which is the recommended posture: query-string keys land in third-party HTTP-debug logs (httpx `DEBUG`, mitmproxy traces, OS-level network captures). The substrate's `SecretScrubbingFilter` covers project loggers, but it does not gate transport-level loggers in the httpx stack. | FIX | One-line change: move `self._api_key` from `params` to `headers={"x-goog-api-key": self._api_key}`. Sibling adapters (`openai.py`) already use the header form. |
| MEDIUM | `src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py:106-107` | Verify-only handshake exports the operator's PKCS#12 private key as un-encrypted PEM to two tempfiles (`_write_secure_tempfile`) so httpx can `load_cert_chain` them. Files are mode 0600 on POSIX (`mkstemp` default + best-effort `os.chmod`); on Windows they inherit the ACL of `%TEMP%`. Cleanup is `finally`-block `unlink`. The window is brief, but the unencrypted key sits on disk for the duration of the HTTPS GET. | FILE | This is a known trade-off (httpx `load_cert_chain` requires file paths). Acceptable for the verify-only smoke-test surface, but worth tracking. Mitigation candidates: (a) keep the bytes in memory and use `ssl.SSLContext.load_cert_chain` against an `io.BytesIO` (not directly supported by stdlib), (b) enforce Windows ACL hardening via the existing `restrict_file_permissions` helper before the GET, or (c) restrict `HTTPX_FALLBACK` to non-Windows hosts in policy. |
| LOW | `src/aeat/adapters/persistence/storage/_master_key.py:809` | `atexit.register(_purge_caches_at_exit)` zeroises cached key buffers at process shutdown, but `atexit` does not run on `SIGKILL` / `os._exit` / segfault. The substrate already documents this as a best-effort hardening; flagging only so the limitation is captured in the audit. | STRIKE | Best-effort defensible: full memory hygiene against post-mortem core dumps would require `mlock` + secure-allocator integration (out of scope). The atexit hook + bytearray-based cache is the correct posture for Python. |
| LOW | `src/aeat/entrypoints/mcp/launch_google_workspace.py:223` | `GOOGLE_OAUTH_CLIENT_SECRET` is propagated into the spawned `workspace-mcp` child env. Desktop OAuth `client_secret` is, by Google's own threat model, low-confidentiality, but it is still a secret and is passed to a third-party process. | STRIKE | Required by the upstream MCP server's contract; the launch_spec already redacts this key in `_format_spec_for_dump` and the env allow-list explicitly excludes every other AEAT secret. Acceptable. |
| STRIKE | `src/aeat/{errors,auth,submission,formulas}/__init__.py` | The four re-export shims do `from <canonical> import *` and re-import `__all__`. Examined every canonical `__all__`: each lists only public symbols (no leading-underscore names). The `LiveSubmitForbiddenError` and the `AeatAccessGate` re-export through the shims, so a caller using the deprecated `aeat.submission` path still hits the permanent-forbid contract. | STRIKE | No symbols leaked beyond the canonical public surface; layered import boundaries cannot be bypassed by routing through the shim because the shim only re-exports what the canonical module already publishes. The DeprecationWarning is set with `stacklevel=2` so the operator sees the call-site, not the shim. |
| STRIKE | `src/aeat/adapters/outbound/aeat/auth/_gate.py:94-102` | `AeatAccessGate.require_live_write` always raises `LiveSubmitForbiddenError` (no env-var bypass). `test_settings_expose_no_live_submit_env_vars` asserts no `LIVE_SUBMIT`-named env var exists in `Settings`. `SubmissionEngine.__init__` rejects any `legacy_live_kwargs` with the same forbidden error. `aeat.adapters.outbound.aeat.export._submitters` is a stub package with no submitter classes. | STRIKE | The four-factor live-submit gate is intact and reinforced -- the restructure tightened it, did not weaken it. |
| STRIKE | path-traversal: `src/aeat/core/paths.py`, `_test_paths.py`, `adapters/persistence/storage/_path_safety.py` | `resolve_record_json_path` rejects shell metachars, traversal, dotfiles, separators, overlong tokens, and null bytes via `_SAFE_FILE_TOKEN_RE`. `resolve_relative_subpath` rejects backslash, parent traversal, absolute paths. Persistence wraps both as `PathContainmentError`. The `_test_paths.py` regression suite covers every documented bypass shape. | STRIKE | No new ingestion paths, all callers route through the typed wrappers. |
| STRIKE | subprocess invocations | Production sites: `cli/doctor.py:151` (gcloud, argv list, binary from `shutil.which`), `adapters/outbound/aeat/auth/_file_permissions.py:68` (`icacls.exe`, argv list, absolute path from `SYSTEMROOT`, every error swallowed), `domain/financial/transactions/_llm.py:430` (LLM CLI, argv list, prompt via stdin or single argv element, binary from `shutil.which`). No `shell=True`. No `os.system`. No f-string command construction. | STRIKE | Every subprocess site uses argv lists, no shell escape, no f-string command interpolation. |
| STRIKE | deserialisation | Only `yaml.safe_load` (sanitize CLI mapping). No `pickle`, no `marshal`, no `yaml.load`/`unsafe_load`. PDF parsing is via `pikepdf` (libqpdf-backed); the sanitiser strips dynamic surfaces (JS, OpenAction, AA, AcroForm, attachments) before any content-stream rewrite. Inbound declaracion parsing is regex-only. | STRIKE | No untrusted-deserialisation attack surface. |
| STRIKE | TLS verification | `ssl.create_default_context()` for the httpx-fallback mTLS handshake; httpx default `verify=True` for OpenAI / Gemini / local Ollama. No `verify=False` anywhere in the production tree. The local Ollama adapter is HTTP because the endpoint is loopback (`127.0.0.1:11434`). | STRIKE | TLS posture is correct. |
| STRIKE | secret logging | `aeat.core.logging.SecretScrubbingFilter` is attached to every project logger and to every handler at `configure_logging()` time. Patterns cover `access_token`, `api_key`, `authorization`, `bearer`, `cert_password`, `cookie`, `credential`, `nif`, `oauth_*`, `passphrase`, `pkcs12`, `refresh_token`, `secret`, `session_cookie`, `tax_id`, `token`. Bearer regex catches `Bearer XXX` strings; LLM regex catches `sk-...` prefixes. `LoadedCertificate` keeps PKCS#12 bytes and passphrase in `PrivateAttr` so `model_dump` / `repr` cannot leak them. `SecretStr` wraps the cert passphrase end-to-end. | STRIKE | Defence-in-depth: filter + structural redaction at the boundary types. |
| STRIKE | env-writer secret hygiene | `application/setup/_env_writer.py` writes ONLY the `owned_env_keys` allow-list to `env/.env`. PKCS#12 password is NEVER written; only the env-var name is recorded as a comment line. `write_profile_file` routes the operator profile through `save_encrypted_envelope` at IDENTITY class with HKDF context `aeat.application.setup.profile.v1`. | STRIKE | First-run setup writer cannot accidentally persist a secret to the plaintext `.env`. |

**Summary**: 1 HIGH (OAuth token-cache disk hardening), 2 MEDIUM
(Gemini API-key transport, httpx-fallback PEM tempfiles), 1 LOW
(workspace-mcp client_secret propagation), plus the
`atexit` zeroise nuance (LOW). No CRITICAL findings. The
restructure neither weakened nor introduced new exposure surfaces in
any of the seven target domains. The four re-export shims and the
`LiveSubmitForbiddenError` end-to-end remain intact.

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

Five-axis sweep of src/aeat/ for production-reachable NotImplementedError sites, abstract methods without concrete implementations, dead exports, dead definitions, duplicated enum / class declarations, and reserved enum members never produced.

| severity | scope | finding | disposition | rationale |
|---|---|---|---|---|
| MEDIUM | src/aeat/adapters/outbound/aeat/auth/_providers.py:328-333 | select_provider(CLAVE_PERMANENTE) raises NotImplementedError; CLAVE_PIN falls through to the catch-all NotImplementedError. Both members are still declared in the AuthProviderKind StrEnum, described in _registry.py as configurable providers, and exposed by cli/auth/_session.py - so the user-visible CLI catalogue advertises four providers but only two actually authenticate. | FILE | The 2026-04-21 clave-portal reference doc justified excluding CLAVE_PERMANENTE (AEAT does not offer it on SelectorAccesos.html); CLAVE_PIN has no equivalent justification on file. Either remove the unimplementable enum members + registry entries or wire concrete providers. The current shape leaks four enum values into JSON contract output (provider_kind) without four working backends. |
| LOW | src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py:85-88 | HttpxFallbackBackend.preload raises NotImplementedError unconditionally; the class is registered as a _CertBackend ABC implementor. | STRIKE | The base contract documents preload is optional for verify-only backends; the test surface confirms the verify-only path is the supported usage. Disposition LOW because the contract is honest but the abstract method should be split (verify-only backends should not inherit a preload slot they cannot fill). |
| LOW | src/aeat/adapters/outbound/aeat/sede/_walker.py:204 | fetch_justificante_pdf is a public-looking helper that immediately raises NotImplementedError("...is wrapped by capture_justificante; call that instead"). | FILE | Either delete the function (its callers all use capture_justificante) or convert it to a private _fetch_justificante_pdf_impl so consumers cannot import a public symbol whose only behaviour is to raise. |
| HIGH | src/aeat/domain/financial/invoices/_stubs.py | Whole module declares two Protocol stubs (SupportsAttachmentId, SupportsTaxCategoryId) flagged as "Typing-only Protocol placeholders for sibling packages not yet on main". rg confirms zero non-test references inside src/aeat/. Only mention is in .vault/plan/2026-04-17-invoice-catalogue-plan.md as forward-looking placeholders for issues #76 / #77. | FILE | Issues #76 (attachment service) and #77 (tax-category catalogue) have landed (see src/aeat/domain/financial/attachments/ and src/aeat/domain/financial/categories/). The protocol stubs were forward-looking placeholders that survived their replacement. Delete the module. |
| HIGH | src/aeat/domain/casillas/models.py:36-41 vs src/aeat/domain/modelos/_codes.py:15-45 | Two distinct ModeloCode StrEnum classes with incompatible member values: casillas.models.ModeloCode carries "MODELO_130" / "MODELO_303" / "MODELO_390" (only three members, prefixed values) while modelos._codes.ModeloCode carries "036" / "100" / ... / "840" (twenty-one members, raw codes). Both enums share the MODELO_<n> member names. | FILE | High-risk cross-module landmine: any boundary that round-trips through string values from one enum to the other silently loses identity. The casilla corpus models KNOWN_MODELO_IDS literal at models.py:13 is also a hard-coded shadow. Pick the canonical enum (the 21-member one in domain/modelos), retire casillas.models.ModeloCode, replace KNOWN_MODELO_IDS with frozenset(c.name for c in ModeloCode). |
| MEDIUM | src/aeat/domain/schema/_enums.py:26-43 vs src/aeat/domain/casillas/models.py:24-33 | Two distinct CasillaDataType StrEnum classes with identical member sets. The schema/_enums.py docstring (lines 28-35) explicitly acknowledges the duplication and forbids isinstance comparison across them. | FILE | Acknowledged in source ("the two enums are bridged by string-value round-trip") but still a concrete duplication. A single shared definition under domain/casillas (the schema package can import it) eliminates the manual round-trip. |
| MEDIUM | src/aeat/application/filing/_schema.py:57-62 vs src/aeat/adapters/outbound/aeat/export/_protocols.py:104-109 | Two distinct FilingFindingSeverity StrEnum classes with identical member values (ERROR/WARNING/INFO). The export-side definition docstring calls out the duplicate and explains it is distinct from FilingValidationFinding. | FILE | Same risk as ModeloCode: an "is" check or non-coerced cross-boundary call silently fails. Consolidate into one canonical type and have the submission engine accept the filing-side type. |
| MEDIUM | src/aeat/domain/deadlines/_calendar.py:21-25 vs src/aeat/domain/financial/aggregation/_models.py:30-35 | Two distinct PeriodKind StrEnum classes: deadlines._calendar.PeriodKind carries QUARTERLY/ANNUAL with UPPERCASE values; financial.aggregation._models.PeriodKind carries MONTHLY/QUARTERLY/ANNUAL with lowercase values. | FILE | Two different period-kind universes co-exist with inconsistent casing on the wire. One direction (deadlines -> aggregation) silently mis-serialises if a value crosses the boundary as a JSON string. Standardise to one PeriodKind (lowercase, including MONTHLY) under domain/financial/aggregation. |
| LOW | src/aeat/domain/casillas/models.py:13 | KNOWN_MODELO_IDS = frozenset({"MODELO_130", "MODELO_303", "MODELO_390"}) - three values hard-coded as a module-level frozenset. The list now disagrees with the 21-modelo ModeloCode enum + the 21-modelo _entries/ registry. Used as a validator gate. | FILE | Replace with a derivation from the canonical ModeloCode enum (or a registered "has-casilla-corpus" predicate) so newly-onboarded modelos cannot be silently rejected by the casilla validator. The current shape is a feature-flag wearing a constants disguise. |

### F. Missing-feature findings

#### Matrix 1: modelo x asset coverage (extractor / ruleset / export-format)

Notation: Y = present, - = absent. Per the supported-modelo set declared in this audit brief plus the two administrative modelos (036/037) shipped under _entries/.

| modelo | declared in _entries/ | extractor 2024 | extractor 2025 | extractor 2026 | ruleset 2024 | ruleset 2025 | ruleset 2026 | export 2024 | export 2025 |
|---|---|---|---|---|---|---|---|---|---|
| 036 | Y | - | Y | - | - | - | - | - | - |
| 037 | Y | - | Y | - | - | - | - | - | - |
| 100 | Y | Y (legacy 2021/22/23) | - | - | Y (full + summary) | Y (full + summary) | Y (full) | - | - |
| 111 | Y | Y | Y | Y | Y | Y | Y | - | - |
| 115 | Y | Y | Y | Y | Y | Y | Y | - | - |
| 123 | Y | Y | Y | Y | Y | Y | Y | - | - |
| 130 | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| 131 | Y | - | Y | - | Y | Y | Y | - | - |
| 180 | Y | Y | Y | Y | Y | Y | Y | - | - |
| 190 | Y | - | Y | - | - | - | - | - | - |
| 193 | Y | - | Y | - | - | - | - | - | - |
| 200 | Y | - | Y | - | Y | Y | Y | - | - |
| 202 | Y | - | Y | - | - | Y | - | - | - |
| 232 | Y | - | Y | - | - | - | - | - | - |
| 303 | Y | Y (Orden 819) | Y | Y | Y | Y | Y | Y (+preview) | Y |
| 347 | Y | - | Y | - | - | - | - | - | - |
| 349 | Y | - | Y | - | - | - | - | - | - |
| 369 | Y | - | Y | - | - | - | - | - | - |
| 390 | Y | Y | Y | Y | Y | Y | Y | - | - |
| 720 | Y | - | Y | - | - | - | - | - | - |
| 840 | Y | - | Y | - | - | - | - | - | - |

Findings:

| severity | scope | finding | disposition | rationale |
|---|---|---|---|---|
| HIGH | modelo 100, extractor coverage | Modelo 100 ships legacy parsers for v2021/v2022/v2023 only (under _parsers/modelo_100/), but no v2024 / v2025 / v2026 declaracion extractor. Rulesets exist for 2024/2025/2026 (full and summary) and an _entries/ declaration is shipped. | FILE | Renta is the headline autonomo deliverable. Without a current-revision extractor, calc-verify against an AEAT-supplied declaracion PDF cannot run for the year that matters. |
| HIGH | modelo 131, extractor coverage | Modelo 131 ships ruleset 2024 + 2025 + 2026 but the declaracion extractor lives only in modelo_131_v2025.py with a single class Modelo131V2025Extractor. | FILE | Extraction parity with the ruleset trio (2024/2025/2026) lets calc-verify run against historic Modelo 131 declarations the same way Modelo 130 already supports. |
| HIGH | modelo 202, ruleset coverage | Modelo 202 (pago fraccionado IS) ships only modelo_202_2025.py - no 2024 or 2026 ruleset. | FILE | Modelo 200 (annual IS) ships 2024/2025/2026 in lockstep; the quarterly companion (202) needs the same year span if Kent is to compute Q1 2024 / Q1 2026 obligations. |
| HIGH | modelos 130 / 303 only - fichero-BOE export coverage | Of nineteen periodic-return modelos, only modelo 130 and modelo 303 ship a fichero-BOE export format. | FILE | The fichero-BOE export-first roadmap explicitly waves "76+" formats; this audit confirms the gap and tags it HIGH because Kent currently has no path to upload casilla-classified data as a fichero-BOE for any modelo other than 130 / 303. |
| MEDIUM | modelos 190 / 193 / 232 / 347 / 349 / 369 / 720 / 840 - ruleset coverage | Eight extractor-shipped modelos have no ruleset at all (any year). _rulesets/__init__.py does not register them, the registry will raise MissingRulesetError, and no formula chain exists for computing their casillas. | FILE | These modelos are extractor-only (read-side), which is the documented v1 posture for low-volume / informational modelos. Document that posture in _rulesets/__init__.py (the existing docstring covers 130 / 303 / 100 / 115 / 123 / 390 explicitly but is silent on these eight). |
| MEDIUM | modelos 100 / 111 / 115 / 123 / 131 / 180 / 200 / 390 - fichero-BOE export coverage | Eight modelos ship full extractor + ruleset triplets but no fichero-BOE export format. | FILE | Track the per-modelo export-format work explicitly. Without a format module, the calc-verify chain cannot round-trip a draft into AEAT importar-datos surface; Kent has to fall back to manual data entry. |
| MEDIUM | modelos 036 / 037 - administrative-form coverage | Modelos 036 / 037 are declared in _entries/ and have v2025 extractors but no rulesets and no export formats. | STRIKE | These are census / declaracion censal forms - they carry no per-casilla calc chain in the first place; the _entries/ declaration carries the legal-citation envelope. The shape is correct for administrative modelos. |
| LOW | modelos 130 / 303 - extractor 2026 | Modelos 130 and 303 are the only modelos with a 2026 extractor revision registered. All other modelos with multi-year ruleset coverage (111/115/123/180/200/390) share a single extractor class for all three years. | STRIKE | Per the extractor-architecture ADR, an extractor revision is only re-cut when the AEAT template diff requires it. The shared-class pattern is correct when the template is unchanged. |

### G. Uniformity-gap findings

#### Matrix 2: vault-doc completeness for major code domains

For the top-level code feature directories under src/aeat/, checked against .vault/research/, .vault/adr/, .vault/plan/, and .vault/exec/. Y = at least one matching doc exists; - = absent.

| code domain | research | ADR | plan | exec record |
|---|---|---|---|---|
| domain/casillas | Y (casilla-db, casilla-schema) | Y | Y | Y |
| domain/deadlines | Y | Y | Y | Y |
| domain/financial/aggregation | Y (t6-aggregation) | Y | Y | Y |
| domain/financial/attachments | Y (attachment-service) | Y | Y | - |
| domain/financial/categories | Y (p2e-tax-category-catalogue) | Y | Y | Y |
| domain/financial/invoices | Y (invoice-catalogue) | Y | Y | - |
| domain/financial/providers | Y (p2a-financial-provider, n26-data-source) | Y | Y | Y |
| domain/financial/transactions | Y | Y | Y | Y |
| domain/financial/vat | Y (r1-vat-enumeration) | Y | Y | Y |
| domain/formulas | Y (modelo-formulas, ruleset-architecture, calc-verification) | Y | Y | Y |
| domain/justificante | Y | Y | Y | - |
| domain/manuals | Y (manual-practico) | Y | Y | Y |
| domain/modelos | Y (modelo-inventory) | Y | Y | Y |
| domain/normatives | Y (normatives) | Y | Y | Y |
| domain/portals | Y (portal-catalogue) | Y | Y | - |
| domain/profile | Y | Y | Y | Y |
| domain/profile/inventory | Y (inventory-management) | Y | Y | Y |
| domain/rental | Y (rental-income-hardening, usage-ratios) | Y | Y | Y |
| domain/schema | Y (schema-extraction) | Y | Y | - |
| domain/testing | Y (synthetic-filing-fixtures, real-pdf-fixture-corpus) | Y | Y | Y |
| application/filing | Y (filing-draft-engine, filing-complementaria) | Y | Y | Y |
| application/review | Y (unified-review-queue, rename-corpus-review) | Y | Y | Y |
| application/setup | Y (setup-wizard) | Y | Y | - |
| application/sync | Y (self-healing-sync, live-sync-backend) | Y | Y | Y |
| application/verification | Y (calc-verification) | Y (aeat-verify-adr x 2) | Y | Y |
| application/workflow | Y (workflow-engine, kent-workflows-expansion) | Y | Y | Y |
| adapters/inbound/borrador | - | - | - | - |
| adapters/inbound/declaracion | Y (declaracion-extractor) | Y | Y | - |
| adapters/inbound/identity | - | - | - | - |
| adapters/inbound/pdf | Y (pdf-import, pdf-taxonomy, real-pdf-import-umbrella) | Y | Y | Y |
| adapters/inbound/sanitizer | Y (pdf-sanitizer) | Y | Y | - |
| adapters/outbound/aeat/auth | Y (cert-auth, live-cert-auth, auth-protocol, auth-cli) | Y | Y | Y |
| adapters/outbound/aeat/browser | Y (playwright-anti-bot, browser-leak, chromium-leak) | Y | Y | Y |
| adapters/outbound/aeat/export | Y (aeat-fichero-boe-export, export-first) | Y | Y | - |
| adapters/outbound/aeat/sede | Y (aeat-history-fetch, aeat-filing-detail-fetch, status-reader) | Y | Y | Y |
| adapters/outbound/llm | Y (llm-client) | Y | Y | Y |
| adapters/persistence/storage | Y (data-storage, secure-persistence-foundation) | Y | Y | Y |
| entrypoints/cli | Y (aeat-cli-wireframe, json-output-contract) | Y | Y | Y |
| entrypoints/mcp | Y (google-workspace-mcp-auth, gsuite-bootstrap) | Y | Y | Y |


Findings:

| severity | scope | finding | disposition | rationale |
|---|---|---|---|---|
| LOW | src/aeat/adapters/inbound/borrador/ | No vault doc trail anchored on the borrador-import pipeline despite _schema.py carrying an ArtefactKind StrEnum and concrete pydantic records. | FILE | The borrador adapter probably traces back to filing-draft-engine, but the lineage is not explicitly documented. Add a small .vault/reference/ doc or amend the closest plan to claim borrador as in-scope. |
| LOW | src/aeat/adapters/inbound/identity/ | No vault doc trail for identity-document inbound parsing despite an IdentityDocument StrEnum and pydantic record set. | FILE | Same shape as the borrador finding. The closest documented doc is 2026-04-21-pdf-taxonomy-adr.md but it does not name identity documents explicitly. |
| LOW | src/aeat/adapters/inbound/declaracion/ | Has research / ADR / plan but no exec-summary under .vault/exec/. | STRIKE | The extractor work was rolled into modelo-by-modelo calc-verify exec records; the exec trail exists, just not under the declaracion-extractor feature tag. |
| LOW | src/aeat/adapters/inbound/sanitizer/ | Has plan / ADR / research but no exec record under that tag. | STRIKE | Sanitiser work landed via the 2026-04-22-real-pdf-import-wave-* exec series. |
| LOW | src/aeat/domain/financial/attachments/ | Has research / ADR / plan but no exec record. | STRIKE | Attachment-service implementation rolled into 2026-04-17-attachment-service-audit.md (audit-only artefact). |
| LOW | src/aeat/domain/financial/invoices/ | Has research / ADR / plan but no exec record under the invoice-catalogue tag. | STRIKE | Invoice work rolled into 2026-04-21-real-pdf-import-execution-wave-* series. |
| LOW | src/aeat/domain/justificante/ | Has research / ADR / plan but no exec record. | STRIKE | Justificante reframing exec landed under the 2026-04-12-justificante-parser directory which was scaffolded but not finalised; the work was eventually folded into the live-write audit. |
| LOW | src/aeat/domain/portals/ | Has research / ADR / plan but no exec record. | STRIKE | Portals work landed before the exec-record convention crystallised. |
| LOW | src/aeat/domain/schema/ | Has research / ADR / plan but no exec record. | STRIKE | Schema-extraction was a one-shot; the implementation trail lives in PR review audits. |
| LOW | src/aeat/application/setup/ | Has research / ADR / plan but no exec record. | FILE | The setup wizard work is re-active for the secure-persistence onboarding sweep; future exec records under 2026-04-30-secure-persistence-foundation should explicitly cite the setup feature tag. |
| LOW | src/aeat/adapters/outbound/aeat/export/ | Has research / ADR / plan but no exec record under the export-first tag. | FILE | Export-first roadmap is partial (only 130/303); the missing exec trail tracks a real outstanding deliverable. |
| MEDIUM | aeat-history-fetch | ADR + research + plan exist; no exec record under that tag. The code under src/aeat/adapters/outbound/aeat/sede/_declarations.py was clearly executed (1000+ lines of parsing). | FILE | Add a back-fill exec summary linking the ADR + plan to the merged code, so the history-fetch feature has a closed audit trail before the milestone-0.1.5 archive. |
| LOW | aeat-verify (calc-verification) | Two same-named ADRs exist: 2026-04-24-aeat-verify-adr.md and 2026-04-25-aeat-verify-adr.md. | FILE | Either supersede or merge; the duplicate filename is a curate-pass smell. |
| LOW | secure-persistence-foundation | Multiple wave-numbered ADRs make the ADR set hard to follow. | STRIKE | The no-wave rule applies to source code, not vault docs. The wave naming records the actual delivery cadence and is correct per the delivery-cadence-as-vault-metadata principle. |

#### Per-modelo asymmetry findings (recap from Matrix 1)

| severity | modelo | asymmetry | disposition |
|---|---|---|---|
| HIGH | 100 | full ruleset triplet (2024/25/26) but only legacy v2021/22/23 extractors; no current-year extractor. | FILE |
| HIGH | 131 | ruleset triplet (2024/25/26) but extractor only 2025. | FILE |
| HIGH | 202 | ruleset only 2025; sibling 200 has full triplet. | FILE |
| MEDIUM | 130 | only modelo with 2024 export format; 2025 ships, 2026 does not. | FILE |
| MEDIUM | 303 | export format ships 2024 + 2025 + a 2024_preview skeleton; no 2026 export despite 2026 ruleset + extractor. | FILE |
| MEDIUM | 111 / 115 / 123 / 180 / 200 / 390 | extractor + ruleset triplets but no export-format module of any year. | FILE |
| MEDIUM | 190 / 193 / 232 / 347 / 349 / 369 / 720 / 840 | extractor-only (no ruleset, no export). The _rulesets/__init__.py docstring does not document this intentional omission. | FILE (docstring fix) |

#### Cross-cutting uniformity asymmetries

| severity | scope | finding | disposition |
|---|---|---|---|
| MEDIUM | _rulesets/__init__.py docstring | Documents the deliberate year-coverage policy for only six modelos (130, 303, 100 full + summary, 115, 123, 390) - silent on 111 / 131 / 180 / 200 / 202. | FILE |
| LOW | modelo_303_2024_preview.py | Production module under _formats/ carrying a DRAFT / PREVIEW warning, explicitly not wired into the CLI registry. | STRIKE |
| MEDIUM | duplicate enum families | Three confirmed duplicates (ModeloCode, CasillaDataType, FilingFindingSeverity) and one inconsistent-casing duplicate (PeriodKind). Recap of section E. | FILE |
