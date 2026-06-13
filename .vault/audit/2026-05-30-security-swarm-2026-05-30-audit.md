---
tags:
  - '#audit'
  - '#security-swarm-2026-05-30'
date: '2026-05-30'
modified: '2026-05-30'
related: []
---

# `security-swarm-2026-05-30` audit: secrets-handling and configuration surfaces

## Scope

Read-only audit of axis 2 of the security swarm: secrets handling and
configuration surfaces across the AEAT codebase. Coverage includes
direct `os.environ` / `os.getenv` reads outside the pydantic-settings
boundary, `Settings` field typing (`SecretStr` vs bare `str`), repr /
log / model_dump leakage, hardcoded credentials, sensitive data in
fixtures and worktree files, CLI flags that would expose secrets on
argv, and `pyproject.toml` / `.env*` for production-value leaks. No
source modifications were performed.

Methodology: ripgrep sweeps over `src/aeat/`, paired with targeted
reads of `core/config.py`, `core/logging.py`, the master-key store,
the browser proxy adapter, and the worktree `.env` files. Findings
are cross-referenced against `aeat-quality-gates.md`,
`aeat-source-hygiene.md`, and the standing "Settings not naked env"
memory rule.

## Findings

### HIGH-1 — worktree `env/.env` carries the operator's real NIE

- Severity: HIGH
- File:line: `env/.env:1`, `env/.env:3` (also surfaced via
  `AEAT_CLAVE_MOVIL_NIE_SOPORTE`)
- Data exposure: A real NIE (`Y4113523X`) and the matching support
  number (`C05745291`) are written in cleartext inside the worktree.
  The file is gitignored and not in `git log`, so it is not in
  history; the exposure is the local working tree only. Any backup,
  ad-hoc tarball of the worktree, screen-share, or accidental
  `git add -A` (banned by rule but still feasible) would lift this
  to a public-history incident. The NIE alone is regulated personal
  data under Spanish AEAT semantics; the audit-cadence rule treats
  cleartext NIFs in config surfaces as a fail-closed condition.
- Remediation: Move the live operator identity into the encrypted
  secret store (master-key backend) or into the per-profile
  credential vault that the auth provider already supports. Keep
  `env/.env` shape-only, mirroring `env/.env.example`. Add a
  pre-commit-time canary (NIF regex) that fails when a real NIE
  pattern appears in any tracked or untracked file under `env/`.

### HIGH-2 — `aeat_proxy_password_secret` typed `str`, not `SecretStr`

- Severity: HIGH
- File:line: `src/aeat/core/config.py:633-636`
- Data exposure: Every other operator-credential field on `Settings`
  is `SecretStr` (`aeat_certificate_password_secret`,
  `aeat_llm_*_api_key`, `aeat_secret_passphrase`,
  `aeat_dev_test_database_password`). `aeat_proxy_password_secret`
  is declared as a bare `str` with `description="Password for proxy
  authentication"`. The value is read in
  `adapters/outbound/aeat/browser/session.py:142` and passed to
  Playwright. Any `repr(settings)`, `settings.model_dump()`,
  pydantic `ValidationError`, or accidental observability emit that
  walks `Settings.model_fields` will print the proxy password in
  cleartext. The field name ends in `_secret`, so the
  `logging.py` redaction regex *would* catch the key in a free-form
  log line, but it does not catch a `pydantic.BaseModel.__repr__`
  call that emits `aeat_proxy_password_secret='…'`.
- Remediation: Re-type the field as `SecretStr` (defaulting to
  `SecretStr("")`) and update the single consumer in
  `browser/session.py` to call `.get_secret_value()` at the
  Playwright boundary. Add a `Settings`-level invariant test that
  every field whose name matches `(password|secret|api_key|token|
  passphrase)` is `SecretStr` or `SecretStr | None`.

### MEDIUM-1 — `_default_passphrase_callback` documents non-popping by design

- Severity: MEDIUM
- File:line: `src/aeat/adapters/persistence/storage/master_key/_master_key.py:320-354`
- Data exposure: The master-key passphrase remains in `os.environ`
  after being read so that re-entry (profile recovery, long-running
  tests) can re-resolve it. The docstring explicitly acknowledges
  this is a "cooperative-isolation property, not a confidentiality
  boundary." Any subprocess spawned from the parent (LibreOffice,
  Playwright browser, ffmpeg in adjacent tooling, helper utilities
  invoked via `subprocess.run`) inherits the passphrase via env. On
  Windows, `wmic process get commandline,environment` and similar
  surfaces can read inherited env for some process snapshots. The
  current rationale is sound, but the threat surface is not
  inventoried — there is no list of which subprocess invocations
  receive a sanitized env.
- Remediation: Add a `subprocess.run` wrapper in `core/` that strips
  `AEAT_SECRET_PASSPHRASE` from the child env by default and
  requires an explicit `pass_passphrase=True` opt-in for the rare
  callers that need it. Audit existing `subprocess.run` /
  `asyncio.create_subprocess_exec` call sites to confirm none leak
  the passphrase to LibreOffice, Playwright child processes, or
  the workbook-parity recalc subprocess.

### MEDIUM-2 — multiple test files mutate `os.environ` outside the Settings boundary

- Severity: MEDIUM
- File:line: `src/aeat/entrypoints/cli/test_windows_encoding.py:35-43`;
  `src/aeat/core/errors/test_envelope.py:20-28`;
  `src/aeat/adapters/inbound/financial/providers/test_csv.py:73-81`;
  `src/aeat/adapters/outbound/aeat/auth/test_authenticator_live.py:49,90`
  (`os.environ.setdefault` against `AEAT_*` keys)
- Data exposure: Tests write to `os.environ["AEAT_*"]` directly
  instead of using `override_settings(...)`. The
  single-surface invariant test
  (`src/aeat/core/test_settings_single_surface_invariant.py`)
  enforces this for production code via an allowlist, but the test
  files above bypass the Settings boundary entirely. This is a
  process gap rather than a leak; the risk is that the same
  pattern silently re-enters production through copy-paste, and
  that env mutations in one test can leak into a parallel pytest
  worker.
- Remediation: Migrate each call site to `override_settings(...)`
  (already used by `test_config_override.py`). Extend the
  single-surface invariant to scan test files as well, with a
  narrow allowlist for the genuinely env-only scenarios
  (`AEAT_LIVE_TESTS_ENABLED` gate, `PYTEST_CURRENT_TEST`).

### MEDIUM-3 — `DEV_TEST_DATABASE_PASSWORD` published as a module-level constant

- Severity: MEDIUM
- File:line: `src/aeat/core/config.py:61`,
  `env/.env.example:112` (`AEAT_DEV_TEST_DATABASE_PASSWORD`)
- Data exposure: The literal `"aeat-dev-test-database-password"` is
  declared as a `S105`-suppressed constant and ships as a `Settings`
  default via `aeat_dev_test_database_password: SecretStr`. The
  comment correctly states this is a "published non-production
  constant," but a developer who unknowingly copies the dev backend
  configuration into a live operator profile inherits the
  deterministic key. The fact that the value is `SecretStr` blocks
  repr leakage; the risk is misuse rather than disclosure.
- Remediation: Keep the constant for fixture use, but add a
  `Settings.model_validator(mode="after")` that refuses to start
  if `aeat_dev_test_database_password` equals the published default
  *and* the active operator profile carries a real NIF/NIE/CIF
  (mirrors the `unsecured` backend NIF-canary gate).

### MEDIUM-4 — `aeat_clave_movil_dni_nie` / `nie_soporte` are bare `str`

- Severity: MEDIUM
- File:line: `src/aeat/core/config.py` (see field declarations near
  the `_empty_optional_clave_fields_are_none` validator at
  `:1091-1099`)
- Data exposure: The DNI/NIE identity and the NIE support number
  are stored as plain `str` fields on `Settings`. The product
  documentation (`env/.env.example:263`) correctly says "not a
  secret on its own," but a NIE *is* regulated personal data under
  AEAT semantics; combined with `aeat_clave_movil_nie_soporte` it
  is sufficient to identify the operator. Any `Settings.model_dump`
  used in observability, audit-trail emit, or error-envelope
  context will surface these values.
- Remediation: Wrap both fields as `SecretStr | None`. The redaction
  regex in `core/logging.py` already covers `nif`-shaped string
  fragments in free-form text; the typing change closes the
  `model_dump` / `repr` surface.

### LOW-1 — Cl@ve Móvil values committed-via-CLI on argv

- Severity: LOW
- File:line: `src/aeat/entrypoints/cli/_config/__init__.py:1620-1629`
  (status emit); the broader Cl@ve auth CLI surface accepts the
  DNI/NIE flag.
- Data exposure: If the CLI ever accepts the DNI/NIE on the
  command line (rather than env / interactive prompt), the value
  appears in `ps`, shell history, and Windows Task Manager command
  line. A spot-check of the CLI surface did not find an explicit
  `--dni-nie` flag, but the support exists implicitly through
  Click's option-from-env coupling. Worth pinning.
- Remediation: Add a CLI test that fails if any auth-provider
  command exposes `--dni`, `--nie`, `--password`, `--passphrase`,
  `--secret`, or `--token` as an argparse / Click option. Force
  these surfaces through env (`AEAT_*`) or interactive
  `getpass.getpass`.

### LOW-2 — `_BEARER_TOKEN_RE` does not redact in pydantic `__repr__`

- Severity: LOW
- File:line: `src/aeat/core/logging.py:71`
- Data exposure: The redaction regex catches `Bearer …` tokens and
  `sk-…` patterns in free-form log strings, but `BaseModel.__repr__`
  output (which is what surfaces in pydantic `ValidationError`
  messages) is not routed through the logging filter. A
  `ValidationError` raised inside `LLMConfig` or `OAuthToken`
  construction that carries the offending value into the error
  message will bypass the scrubber.
- Remediation: Audit every pydantic model that holds a token-shaped
  value to ensure the field is `SecretStr` (so
  `BaseModel.__repr__` renders `SecretStr('**********')`). The
  scrub regex is a defense-in-depth surface, not the primary
  control.

### LOW-3 — `file_permissions.py` reads `SYSTEMROOT` / `USERDOMAIN` without Settings

- Severity: LOW
- File:line: `src/aeat/core/file_permissions.py:63,65`
- Data exposure: Direct `os.environ.get("SYSTEMROOT", ...)` and
  `os.environ.get("USERDOMAIN")` reads. These are OS-provided
  Windows environment variables (not `AEAT_*`), so they correctly
  fall outside the Settings boundary, but the pattern is
  inconsistent with how `_stdio.py` handles `COLUMNS`. No
  confidentiality risk; this is hygiene only.
- Remediation: Either document these as explicit OS-env reads with
  an inline comment matching the allowlist convention in
  `_stdio.py`, or fold them into a small `WindowsEnv` model on
  Settings so the boundary remains uniform.

## Recommendations

Re-type `aeat_proxy_password_secret` as `SecretStr` immediately and
add the field-naming invariant test (Settings sweep against the
secret-shaped-name regex). Move the live operator NIE out of
`env/.env` into the encrypted secret store before the next swarm
cycle. Add the NIF-shaped canary regex to the pre-commit hook so a
future operator cannot stash a real NIE into a tracked file. Inventory
the subprocess call sites that inherit `AEAT_SECRET_PASSPHRASE` and
build a `sanitized_subprocess` wrapper. Extend the single-surface
invariant scanner to cover test files with a narrow allowlist.

## Summary

Total findings: 9
- HIGH: 2 (operator NIE in worktree env; proxy password typed as bare str)
- MEDIUM: 4 (passphrase env retention; test-file env mutations;
  published dev-test DB password; Cl@ve identity fields as bare str)
- LOW: 3 (CLI argv exposure pin; bearer-token repr surface;
  Windows OS-env reads in `file_permissions.py`)

Most concerning: HIGH-2 (`aeat_proxy_password_secret: str`) — the
field name claims "secret" but the type contract is not enforcing
confidentiality on repr / model_dump / ValidationError surfaces, and
the value flows through Playwright at runtime.
