---
tags:
  - "#research"
  - "#setup-wizard"
date: 2026-04-12
modified: '2026-04-12'
title: First-run setup wizard — research
related:
  - "[[2026-04-12-deadline-engine-research]]"
  - "[[2026-04-12-cert-auth-research]]"
  - "[[2026-04-12-trilingual-i18n-research]]"
issue: wgergely/aeat#61
---

# research: first-run interactive setup wizard (#61)

## problem statement

A fresh autónomo who just cloned the repo has no obvious path to a
working `env/.env`. The project has already shipped every primitive
the user needs — `AutonomoProfile` (#38), `CertificateBundle` (#8),
`Language` (#20), the storage layer (#10), the draft engine (#39), the
submission engine (#42), the status reader (#43), the filing-deadline
engine (#38) — but no *on-ramp* that hands those primitives a
configured environment.

Issue #61 asks for exactly one command: `aeat setup`. Running it on
an empty repo should produce a valid `env/.env`, verify that every
configured surface is reachable, and (optionally) run a dry-run of the
workflow engine (#59, Protocol-stubbed until it lands).

## constraints

1. **Never write secrets to disk.** The PKCS#12 password lives in an
   operator-controlled secret store. The wizard captures the env var
   **name** the operator wants to use; the operator sets the value
   themselves. `CertificateBundle.password_env_var` already models
   this — we only need to mirror the contract.
2. **Idempotent.** Re-running the wizard on a populated env file must
   read existing values, present them as defaults, and produce a
   byte-equal result when no answers change.
3. **Preserve unrelated keys.** The wizard owns a fixed subset of the
   env file. Any key it does not own (from `aeat bootstrap`, from
   hand-edits, from future features) must round-trip untouched.
4. **Pydantic v2 strict everywhere.** Every boundary-crossing record
   is a `BaseModel` with `strict=True, frozen=True, extra="forbid"`.
   Closed enumerations are `StrEnum`.
5. **No mocks/patches/fakes/stubs in tests.** Use real `tmp_path` env
   files, real `SetupAnswers` instances, real pydantic round-trips.
6. **Typer surface.** The CLI is already Typer-based (`src/aeat/cli`).
   New subcommands wire through `aeat setup` / `aeat setup verify` /
   `aeat setup show` / `aeat setup --non-interactive --from <path>`.
7. **No new Settings fields.** The wizard reads existing Settings and
   writes the existing env var names — its job is UX, not surface.
8. **No hard import from `aeat.application.workflow`.** #59 is in flight. A
   Protocol stub (`FirstRunRunner`) keeps the wizard honest about the
   dependency without pinning the implementation.

## inventory of existing primitives

| Surface                | Subpackage            | Relevant type / env var                         |
|------------------------|-----------------------|--------------------------------------------------|
| Profile                | `aeat.domain.deadlines`      | `AutonomoProfile`, `IVARegime`                   |
| Certificate            | `aeat.adapters.outbound.aeat.auth`           | `CertificateBundle`, `CertificateBackend`        |
| Language               | `aeat.core.i18n`           | `Language` (`es`/`en`/`hu`)                      |
| Output dirs            | `aeat.core.config`         | `aeat_drafts_dir`, `aeat_submissions_dir`, etc.  |
| Manuals corpus         | `aeat.domain.manuals`        | `aeat_manuals_root`                              |
| Live tests opt-in      | `aeat.core.config`         | `aeat_live_tests_enabled`                        |
| Env-file rewrite       | `aeat.core.env_io`         | `read_env_file`, `write_env_vars`                |
| Workflow (stub)        | `aeat.application.workflow` (#59) | `FirstRunRunner` Protocol — to be wired later    |

The env-file writer in `aeat.core.env_io.write_env_vars` already
(a) preserves comments and blank lines, (b) rewrites existing keys in
place, and (c) appends new keys in insertion order. That gives us
idempotency and unrelated-key preservation for free — we just need to
discipline the wizard to only touch keys it owns, and to write keys
in a stable order.

## env vars owned by the wizard

Captured from issue #61 and cross-checked against `src/aeat/config.py`:

- `AEAT_CERTIFICATE_PATH`
- `AEAT_CERTIFICATE_FRIENDLY_NAME`
- `AEAT_CERTIFICATE_BACKEND`
- `AEAT_CERTIFICATE_VERIFY_URL`
- `AEAT_OUTPUT_LANGUAGE`
- `AEAT_DEFAULT_PROFILE_PATH`
- `AEAT_DRAFTS_DIR`
- `AEAT_SUBMISSIONS_DIR`
- `AEAT_MANUALS_ROOT`
- `AEAT_LIVE_TESTS_ENABLED`
- `AEAT_LIVE_TESTS_GOOGLE`

Plus a **comment-only** marker line that records the env var *name*
the user chose to hold the PKCS#12 password (e.g. `# PKCS#12 password
sourced from env var: AEAT_CERT_PASSWORD`). This is informational
only — the value is never written.

The `AutonomoProfile` fields are NOT stored in the env file. They are
written to a small JSON file at `AEAT_DEFAULT_PROFILE_PATH` (default
`env/profile.json`). The wizard owns that file too; writing it is a
second side effect of `SetupWizard.run()`.

## key design choices to record in the ADR

1. **Interactive vs non-interactive split.** Both modes run the same
   `SetupWizard.run()`. In non-interactive mode we short-circuit the
   prompt layer and consume a fully-populated `SetupAnswers`.
2. **Typed prompter Protocol.** A `Prompter` Protocol decouples
   Typer's `typer.prompt`/`typer.confirm` from the wizard's state
   machine, so unit tests can drive the wizard with a real in-process
   prompter (no mocks, no patches).
3. **Verifier is pure.** Each verifier check is a small function that
   returns a `VerifyFinding`. The verifier never mutates state — it
   is safe to run on production-looking env files.
4. **First-run is Protocol-stubbed.** We declare a `FirstRunRunner`
   Protocol and accept `None` as the default. When a real runner is
   wired in later, no wizard code changes.
5. **Never write the password.** Enforced by construction: the wizard
   never captures the password, only the env var *name*; the env
   writer never accepts a password field. A dedicated unit test
   asserts the invariant for every reachable code path.

## open questions

- **Fixture provisioning step.** Issue #61 lists
  `FIXTURE_PROVISIONING` as a step. We defer the actual call-out to
  `scripts/provision_google_fixtures.py` — the step only captures the
  boolean opt-in and prints the command the user should run.
- **First-run dry-run.** Issue #61 lists `FIRST_RUN`. We expose the
  `FirstRunRunner` Protocol and skip the step cleanly if no runner is
  provided. This keeps the wizard shippable today without waiting for
  #59.

## decisions surfaced for the plan

- Subpackage layout mirrors `aeat.status` / `aeat.domain.deadlines`:
  `_models.py`, `_errors.py`, `_env_writer.py`, `_verifier.py`,
  `_wizard.py`, `_protocols.py`, `_prompter.py`, `__init__.py`.
- CLI lives at `src/aeat/entrypoints/cli/setup.py` and is registered in
  `src/aeat/entrypoints/cli/__init__.py` via `app.add_typer(setup_module.app, ...)`.
- Unit tests are colocated: `test_models.py`, `test_env_writer.py`,
  `test_verifier.py`, `test_wizard.py`.
- No live tests. No new Settings. No `.env.example` edits.
