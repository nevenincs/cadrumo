---
tags:
  - '#research'
  - '#settings-di'
date: '2026-05-14'
related: []
---

# `settings-di` research: production env-read inventory and DI strategy

Inventories every production `os.environ` read in the aeat codebase,
categorizes each by whether it can move behind `Settings`, and compares
DI strategies for the migration. Output drives the companion ADR.

## Findings

### Production env-read inventory (27 sites, 14 files)

The grep `os\.environ\.get\|os\.environ\[` across `src/aeat/` excluding
tests and conftest returns 27 hits. Five categories emerge.

#### Category A — already on `Settings`, call-site can migrate cleanly

These read environment variables that are already declared as `Settings`
fields. Migration is a one-liner: replace `os.environ.get("FOO")` with
`get_settings().foo`.

- `aeat.core.i18n._render:59` reads `AEAT_OUTPUT_LANGUAGE` →
  `Settings.aeat_output_language`.
- `aeat.core.access_gate:103` reads the live-tests opt-in flag →
  `Settings.aeat_live_tests_enabled`.
- `aeat.core.access_gate:128` re-reads the same flag for the typed
  diagnostic snapshot → same field.

#### Category B — missing from `Settings`, must add field then migrate

These read env vars the `Settings` model does not currently model.
Phase 1 of the DI migration is to add the field; Phase 2 migrates the
call site.

- `aeat.core.logging:240` reads `AEAT_LOG_DIR`. Default lives in the
  function; should become `Settings.aeat_log_dir: Path | None`.
- `aeat.domain.calculations.registry._workbook_parity:397` and `:736`
  read `_LIBREOFFICE_EXECUTABLE_ENV` (the module-private name for
  `AEAT_LIBREOFFICE_EXECUTABLE` or similar). Should become
  `Settings.aeat_libreoffice_executable: Path | None`.
- `aeat.adapters.persistence.storage.master_key._master_key:249` reads
  `PASSPHRASE_ENV_VAR`. Should become
  `Settings.aeat_master_key_passphrase: SecretStr | None`. This is part
  of the live-write security perimeter — see Risks below.

#### Category C — legitimate boundary env channels, must remain `os.environ`

These cannot move behind `Settings` because the environment variable
IS the inter-process or inter-library channel the surrounding code
intentionally drives.

- `aeat.adapters.outbound.aeat.auth._authenticator:770-831` writes
  the cert passphrase into a transient `os.environ` slot so the
  Playwright / httpx PKCS#12 backend can consume it. The env var is
  the cross-library channel; Settings cannot replace it. The
  authenticator already reads the source secret from
  `Settings.aeat_certificate_password_secret` (good). The env write is
  scoped + restored in a `try`/`finally`. Retain as-is; #103 (Cert
  Bundle SecretStr refactor) is the path to fully eliminating the
  bundle's env-var indirection, not this DI sprint.
- `aeat.core.observability._replay:159-171` reads/writes
  `REPLAY_ACTIVE_ENV_VAR`. The variable threads "this subprocess is
  replaying run X" across `subprocess.run` calls; Settings cannot
  cross the subprocess boundary. Retain.
- `aeat.core.observability._context:276` reads the same replay-active
  flag for in-process observability tagging. Retain (paired with the
  write above).
- `aeat.adapters.outbound.aeat.auth.certificate:315` reads the
  passphrase env var named by `CertificateBundle.password_env_var`.
  The bundle's env-var indirection is the design under review by
  task #103. Out of scope for this DI sprint.

#### Category D — system env vars (Windows / POSIX), must remain `os.environ`

These read non-aeat operating-system variables that are not under our
configuration control.

- `aeat.core.file_permissions:63` reads `SYSTEMROOT` to locate
  `icacls.exe`. Pure Windows-system path; retain.
- `aeat.core.file_permissions:65` reads `USERDOMAIN`. Pure
  Windows-system identity; retain.

#### Category E — write sites at the CLI flag boundary

These write `os.environ` so the env-var-driven downstream reader picks
the value up. Once the downstream reader migrates to `Settings`, the
write can also migrate to a `Settings` override.

- `aeat.entrypoints.cli.__init__:126` writes `AEAT_OUTPUT_LANGUAGE`
  from the `--language` flag. Once Category A migration lands for
  `aeat.core.i18n._render:59`, this write should become a Settings
  override on the request-scoped Settings instance (or the
  `override_settings()` context manager described below).

#### Bystanders (comments / docstrings only — not real sites)

- `aeat.core.access_gate._errors:69` and `aeat.core.access_gate.__init__:9,97`
  contain `os.environ[...]` in docstrings illustrating the old per-site
  pattern. These are documentation, not code reads. No migration needed.

#### Test-side scope (out of band)

`grep -rn "monkeypatch.setenv\|monkeypatch.delenv" src/aeat/` returns
223 hits across the test suite. These are not in scope for the
production-DI sprint, but the new `override_settings()` helper will
let test files migrate from "set env var, hope Settings re-reads it"
to "construct Settings directly with the field set". Test migration
should land as a follow-up sprint per package.

### Current `Settings` shape (`aeat.core.config`)

The `Settings` class derives from `pydantic_settings.BaseSettings` and
already covers ~50 fields:

- Token / database / secret-store / blob-store directories.
- Output language, fallback chain, authoritative-language anchors.
- AEAT base URL, sede paths, rate-limit timing.
- Certificate path, password (`SecretStr | None`), backend, verify URL,
  warn/critical thresholds.
- Cl@ve Móvil identity, DNI/NIE artefacts, timeouts.
- Browser channel, headless flag, proxy URL/username/password, bypass.
- Storage provider kind (`local_filesystem` / `google_drive` /
  `in_memory`) and provider-specific roots.
- `aeat_live_tests_enabled: bool` and `aeat_allow_unencrypted: bool`.

The model declares `model_config = SettingsConfigDict(env_file=...,
env_ignore_empty=True)`. Field names map verbatim to upper-case env
vars (`aeat_database_url` → `AEAT_DATABASE_URL`).

The model does NOT currently expose:

- `aeat_log_dir: Path | None` (Category B above)
- `aeat_libreoffice_executable: Path | None` (Category B)
- `aeat_master_key_passphrase: SecretStr | None` (Category B,
  live-write perimeter)

The construction site is `aeat.core.config.get_settings()` (cached) —
that singleton is the natural injection seam.

### DI strategy comparison

Three strategies considered.

#### Strategy 1 — thread `Settings` through every call site

Every function that today calls `os.environ.get(...)` grows a
`settings: Settings` parameter. Callers pass it down.

Pros: explicit, type-checked, no implicit global state, no test-time
override required (tests construct a `Settings(field=value)` and pass
it in directly).

Cons: forces parameter churn through entire call chain. The 27 sites
sit deep inside i18n rendering, logging setup, file-permission probes,
workbook conversion, and access-gate evaluation — most of these are
called from dozens of other call sites that would also need the
parameter. Real change footprint is closer to 200+ files.

#### Strategy 2 — module-cached singleton via `get_settings()`

A single cached `get_settings()` returns the process-wide `Settings`
instance. Call sites read `get_settings().field_name`. Tests override
via a `clear_settings_cache()` helper plus env-var manipulation.

Pros: minimal call-chain churn. Compatible with the existing
`BaseSettings` construction model.

Cons: tests still rely on env-var manipulation to drive Settings
construction. The "swap field X in this test" ergonomics are bad: you
either monkeypatch the env var BEFORE the cache clear, or you
hand-construct a Settings and somehow attach it to the cache, which
fights `lru_cache`.

#### Strategy 3 — `ContextVar`-backed override with explicit context manager

Adopt strategy 2 but back the cache with a `contextvars.ContextVar`
that an `override_settings(**overrides)` context manager mutates. The
context manager:

- Reads the current cached instance (or constructs one).
- Calls `current.model_copy(update=overrides)` to produce a new frozen
  Settings with the overrides applied.
- Sets the `ContextVar` to the new instance for the duration of the
  `with` block.
- Restores the prior value on exit.

Tests call `with override_settings(aeat_log_dir=tmp_path): ...` —
no env-var manipulation, no cache invalidation, full type-checking on
the override kwargs (because Pydantic validates `model_copy(update=)`).

Pros: minimal call-chain churn (Strategy 2's win). Test ergonomics
are excellent (test passes the override exactly as a Settings field,
strict-validated). Thread-safe and async-safe via `ContextVar`.
Compatible with the existing live-write fail-closed contract because
the override builds on top of the validated Settings, not under it.

Cons: tests must import the helper and use `with` blocks (slightly
heavier than `monkeypatch.setenv`). Pydantic v2's `model_copy(update=)`
preserves `frozen=True`, so the override yields a new frozen instance,
not a mutation — that's the right semantics.

### Recommended strategy

**Strategy 3.** Live-write perimeter integrity is preserved because:

1. The default Settings instance is still constructed from env vars +
   `.env`, exactly as today. Live-submit gates that read
   `Settings.aeat_live_tests_enabled` and (eventually) a four-factor
   approval flag continue to see the validated singleton when no
   override is active.
2. The `override_settings()` helper does NOT bypass validation —
   `model_copy(update=)` runs Pydantic's validators against the
   merged dict. Tests cannot accidentally weaken a constraint by
   monkeypatching a string env var into a non-conforming shape.
3. The `ContextVar` is process-local; subprocess boundaries (replay,
   browser-driver bootstrap) continue to use the real env channel
   (Category C), so the override does not silently propagate into
   another process under a different security posture.

### Risks (live-write perimeter)

- `aeat_master_key_passphrase: SecretStr | None`. Adding this field
  to Settings makes the passphrase available via the validated
  singleton. The master-key loader at
  `aeat.adapters.persistence.storage.master_key._master_key:249`
  currently raises a typed `MasterKeyError` when the env var is unset
  or empty. The migration MUST preserve that fail-closed contract:
  the field default is `None`, and the loader checks for `None` (not
  for empty string) and raises identically. A truthy default would
  be a security regression; this is the only field whose default
  must remain `None`.
- `aeat_certificate_password_secret: SecretStr | None` is already on
  Settings and already nullable-and-fail-closed; no change needed
  here, but the test-side migration (#85) should not introduce a
  default value when overriding.
- The `override_settings()` helper SHALL NOT accept overrides that
  toggle `aeat_live_tests_enabled=True` outside an explicit test
  marker context. The helper should validate that the caller is
  inside a `@pytest.mark.live_read`-marked test before allowing that
  field to flip. (This is a recommendation; can be enforced via a
  validator on the override path.)

### Site-by-site categorisation summary

| File:line                                                                     | Category | Field needed                                      |
| :---------------------------------------------------------------------------- | :------- | :------------------------------------------------ |
| `core/i18n/_render.py:59`                                                     | A        | `aeat_output_language` (exists)                   |
| `core/access_gate/__init__.py:103,128`                                        | A        | `aeat_live_tests_enabled` (exists)                |
| `core/logging.py:240`                                                         | B        | `aeat_log_dir: Path \| None` (add)                |
| `domain/calculations/registry/_workbook_parity.py:397,736`                    | B        | `aeat_libreoffice_executable: Path \| None` (add) |
| `adapters/persistence/storage/master_key/_master_key.py:249`                  | B        | `aeat_master_key_passphrase: SecretStr \| None` (add, fail-closed) |
| `adapters/outbound/aeat/auth/_authenticator.py:770-831`                       | C        | retain — cross-library env channel                |
| `core/observability/_replay.py:159-171`, `_context.py:276`                    | C        | retain — subprocess env channel                   |
| `adapters/outbound/aeat/auth/certificate.py:315`                              | C        | retain — bundle indirection (task #103)           |
| `core/file_permissions.py:63,65`                                              | D        | retain — system env vars                          |
| `entrypoints/cli/__init__.py:126`                                             | E        | migrate to `override_settings` after Category A   |
| `core/access_gate/_errors.py:69` / `core/access_gate/__init__.py:9,97`        | bystander | docstring text only — no change                  |

### Migration phasing (input to the Plan)

1. Extend `Settings` with the three Category-B fields (no callers move
   yet).
2. Introduce `override_settings()` context manager + supporting
   `ContextVar` in `aeat.core.config`. Document the `pytest.mark`
   guard for live-tests.
3. Migrate Category A call sites (3 sites) one commit per site or
   one commit for all three.
4. Migrate Category B call sites (4 sites) one commit per file.
5. Migrate the Category E CLI flag write to use `override_settings()`
   for the duration of the command invocation.
6. Land a follow-up sprint for the 223 test-side
   `monkeypatch.setenv` calls — out of scope for this sprint, but
   the helper enables it.

### Test-side migration sketch (out-of-scope confirmation)

For each test that currently does:

```python
monkeypatch.setenv("AEAT_LOG_DIR", str(tmp_path))
```

The migrated form is:

```python
with override_settings(aeat_log_dir=tmp_path):
    ...
```

This is a 223-site mechanical rewrite; not part of this sprint, but
the next sprint should sequence it per package (start with the
simplest: `core/i18n`, `core/access_gate`; finish with the largest:
`adapters/persistence`).
