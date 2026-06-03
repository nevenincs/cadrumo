---
tags:
  - '#adr'
  - '#settings-di'
date: '2026-05-14'
related:
  - "[[2026-05-14-settings-di-research]]"
---

# `settings-di` adr: `contextvar-backed-settings-override` | (**status:** `accepted`)

## Problem Statement

The production codebase reads `os.environ` at 27 call sites across 14
files; the test suite manipulates env vars at 223 sites via
`monkeypatch.setenv`. This couples runtime configuration to the
process environment, fights type-checking, and forces tests to
manipulate global state. The live-AEAT-write security perimeter
forbids any change that would weaken fail-closed behaviour on
certificate-password lookup, master-key resolution, or the live-tests
opt-in gate, so the chosen DI strategy must preserve every existing
invariant on these paths.

## Considerations

The research document categorises every site into five buckets:
already-on-Settings (Category A), missing-from-Settings (Category B),
cross-library env channels that must remain raw (Category C),
system env vars (Category D), and CLI flag→env writes (Category E).
Categories A+B+E are migration candidates; C+D stay as-is.

Three DI strategies were compared: thread-through-parameters (high
churn, ~200 file impact), module-cached singleton (Strategy 2, low
churn but poor test ergonomics), and ContextVar-backed override on
top of the cached singleton (Strategy 3 — low churn and good test
ergonomics).

## Constraints

- Live-write fail-closed contracts on cert-password and master-key
  resolution MUST survive verbatim — any field whose unset state
  refuses operation today must continue to refuse on `None`.
- Pydantic v2 strict + frozen + extra="forbid" — no loosening.
- No backwards-compat shims. The migration lands as direct call-site
  replacement; old code paths are deleted, not deprecated.
- Subprocess boundaries (replay, browser-driver bootstrap, OpenSSL
  PKCS#12 passphrase channel) must continue to use raw env vars.
  Process-local overrides MUST NOT silently propagate into a child
  process running under a different security posture.
- Pre-existing `prek`/`ty` failures in other-agent WIP files may
  force `--no-verify` on focused commits; document each occurrence.

## Implementation

### Public surface added to `aeat.core.config`

A new `ContextVar[Settings | None]` named `_settings_override` is
declared at module load. The cached `get_settings()` factory is
extended: it first reads the ContextVar; if set, it returns that
instance directly; otherwise it returns the cached env-derived
instance exactly as today.

A new context manager `override_settings(**overrides)` resolves the
current effective `Settings`, calls `model_copy(update=overrides)` to
produce a new frozen instance validated against the Pydantic model,
sets the ContextVar to that instance for the duration of the `with`
block, and restores the prior ContextVar value on exit. Pydantic
v2's `model_copy(update=)` preserves `frozen=True` and runs
validators on the merged dict.

### Three new `Settings` fields

- `aeat_log_dir: Path | None = None` — used by the logging-config
  helper; default `None` preserves the "no override means compute a
  default at the call site" semantics.
- `aeat_libreoffice_executable: Path | None = None` — used by the
  workbook-parity scanner; default `None` preserves the "resolve from
  PATH" fallback.
- `aeat_master_key_passphrase: SecretStr | None = None` — used by the
  master-key loader; default `None` preserves the typed
  `MasterKeyError` raise on unset.

### Call-site migrations

Category A sites swap `os.environ.get("AEAT_...")` for
`get_settings().aeat_...`. Category B sites do the same against the
new fields. Category E (CLI flag write) wraps the command-invocation
body in `with override_settings(aeat_output_language=language)` and
deletes the `os.environ[...] = language` write.

Categories C and D are untouched.

## Rationale

Strategy 3 was chosen because:

1. It preserves the live-write fail-closed contract by construction:
   every new field defaults to `None`, the existing typed errors
   continue to raise on `None`, and the override helper runs
   Pydantic validators so a malformed override fails at entry rather
   than at the consumer.
2. It keeps the call-chain churn minimal (no parameter threading).
3. It provides excellent test ergonomics: `with
   override_settings(field=value):` is type-checked, strict-validated,
   and does not pollute the process env.
4. It is process-local via `ContextVar`, so subprocess channels
   (Category C — replay, OpenSSL) are unaffected.

Strategy 1 (parameter threading) was rejected: the real change
footprint is ~200 files because the 27 sites sit deep in i18n
rendering, logging, file permissions, workbook conversion, and
access-gate evaluation — every caller would also grow the parameter.

Strategy 2 (bare singleton) was rejected for test ergonomics:
overriding requires either env-var manipulation before cache clear,
or fighting `lru_cache` to inject a hand-constructed Settings.

## Consequences

### Drop-dead invariants (preserved)

1. `aeat_certificate_password_secret` remains `SecretStr | None`,
   default `None`. Authenticator still raises
   `CertificatePasswordError` on `None`. The transient
   `os.environ` write in the authenticator's PKCS#12 path stays as
   the OpenSSL-binding channel — out of scope.
2. `aeat_master_key_passphrase` defaults to `None`. Loader still
   raises typed `MasterKeyError` on `None`/empty.
3. `aeat_live_tests_enabled` default stays `False`. The override
   helper does NOT special-case this field; the authoritative gate
   remains the `@pytest.mark.live_read` conftest check.
4. `model_copy(update=)` preserves `frozen=True` — overrides yield
   fresh validated instances, never mutate the singleton.
5. `ContextVar` is process-local — overrides do not cross subprocess
   boundaries.

### Out of scope (deferred to follow-up sprints)

- Mechanical migration of the 223 test-side `monkeypatch.setenv`
  calls to `override_settings(...)`. The helper enables that work;
  the rewrites themselves are a per-package sprint.
- `CertificateBundle.password_env_var` indirection (task #103).
- The OpenSSL passphrase env channel in the authenticator
  (Category C).
- The replay-active subprocess env channel (Category C).
- System env reads in `file_permissions.py` (Category D).

### Acceptance gates (handed to the Plan)

1. `pytest src/aeat/core/ -q` is green after the helper and three new
   fields land.
2. Each migrated call site has a focused test that verifies the
   `override_settings(field=value)` value is observed without any
   env-var manipulation.
3. Each Category-B field's fail-closed branch is verified by an
   explicit test asserting `override_settings(field=None)` raises the
   same typed error as the current `os.environ` unset path.
4. `prek run --all-files` is green per commit, modulo pre-existing
   other-agent WIP failures documented inline.
5. The live-tests opt-in gate continues to refuse `live_read` runs
   when `Settings.aeat_live_tests_enabled=False`, regardless of
   whether the value came from env or override.
