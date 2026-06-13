---
tags:
  - "#adr"
  - "#setup-wizard"
date: 2026-04-12
modified: '2026-04-12'
title: First-run setup wizard — ADR
related:
  - "[[2026-04-12-setup-wizard-research]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-12-deadline-engine-adr]]"
issue: wgergely/aeat#61
---

# adr: first-run interactive setup wizard (#61)

## context

`aeat setup` is the first command a fresh autónomo runs after
`just bootstrap`. Without it, the only path to a working environment
is to read `src/aeat/config.py` and hand-edit `env/.env`. Every
primitive the user needs (profile, certificate, language, directories,
live-test opt-in) has already shipped as a typed subpackage. What is
missing is the typed, interactive, idempotent UX that turns those
primitives into a configured environment.

## decision

Ship `aeat.application.setup` as a new subpackage with strict pydantic v2 models,
a typed `SetupWizard` orchestrator, a pure verifier, and a dedicated
env-file writer. Wire four Typer subcommands (`setup`, `setup verify`,
`setup show`, `setup --non-interactive --from <path>`) through the
existing CLI. No new Settings fields. No live tests in this slice.

### public surface (exported from `aeat.application.setup`)

- Enums (`StrEnum`):
  `SetupStep`, `SetupOutcome`, `VerifySeverity`.
- Records (strict frozen `BaseModel`):
  `SetupAnswers`, `SetupResult`, `VerifyFinding`.
- Protocols:
  `Prompter`, `FirstRunRunner`.
- Functions / classes:
  `SetupWizard`, `Verifier`, `write_env_file`,
  `load_answers_from_file`.
- Errors (inherit from `AeatError`):
  `SetupError`, `SetupAbortedError`, `SetupVerifyError`,
  `SetupAnswersError`.

Callers outside the subpackage import only from the subpackage root,
matching the project's public-API-discipline rule.

### the ten steps (from issue #61)

`WELCOME → PROFILE → CERTIFICATE → LANGUAGE → OUTPUT_DIRS →
LIVE_TESTS_OPT_IN → FIXTURE_PROVISIONING → VERIFY → FIRST_RUN → DONE`.

Every step is independently skippable in non-interactive mode via a
`steps_to_skip: frozenset[SetupStep]` field on `SetupAnswers`. The
wizard records the completed vs skipped set in `SetupResult`.

### invariants

1. **never-write-secrets.** The wizard captures
   `certificate_password_secret_var_name` (the env var *name*). The
   env writer exposes no field for the password value. A dedicated
   unit test iterates every reachable code path and asserts the
   password value never reaches the filesystem.
2. **idempotent-rerun.** Running the wizard twice on the same env
   file with the same answers produces a byte-equal result. Delegated
   to `aeat.core.env_io.write_env_vars`, re-verified by a unit test.
3. **unrelated-keys-preserved.** The wizard only rewrites keys in its
   owned set (enumerated in the research doc). A unit test seeds the
   env file with extra keys and asserts they round-trip untouched.
4. **typed prompter.** No direct `typer.prompt` calls from the wizard
   body. A `Prompter` Protocol sits between the state machine and
   the I/O layer; the Typer-backed implementation lives in
   `aeat/entrypoints/cli/setup.py`, and tests use a tiny in-process prompter that
   yields canned answers from a queue.
5. **verifier is pure.** Each check is a small function returning a
   `VerifyFinding`. Checks: certificate path exists and is readable;
   password env var is set in `os.environ`; `AEAT_DRAFTS_DIR` /
   `AEAT_SUBMISSIONS_DIR` / `AEAT_MANUALS_ROOT` exist or can be
   created; `AutonomoProfile` JSON round-trips through pydantic;
   `Settings()` validates clean. None of these mutate state.

### data model sketch

```python
class SetupStep(StrEnum):
    WELCOME = "WELCOME"
    PROFILE = "PROFILE"
    CERTIFICATE = "CERTIFICATE"
    LANGUAGE = "LANGUAGE"
    OUTPUT_DIRS = "OUTPUT_DIRS"
    LIVE_TESTS_OPT_IN = "LIVE_TESTS_OPT_IN"
    FIXTURE_PROVISIONING = "FIXTURE_PROVISIONING"
    VERIFY = "VERIFY"
    FIRST_RUN = "FIRST_RUN"
    DONE = "DONE"


class SetupOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    ABORTED_BY_USER = "ABORTED_BY_USER"
    ABORTED_VERIFY_FAILED = "ABORTED_VERIFY_FAILED"


class VerifySeverity(StrEnum):
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


class SetupAnswers(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    # profile
    tax_id: str
    iva_regime: IVARegime
    has_employees: bool
    pays_rent_with_retencion: bool
    does_intracomunitario: bool
    bienes_extranjero_above_threshold: bool

    # certificate (password captured by env var NAME, never value)
    certificate_path: Path
    certificate_password_secret_var_name: str
    certificate_friendly_name: str | None = None
    certificate_backend: CertificateBackend = CertificateBackend.PLAYWRIGHT_CONTEXT

    # language
    default_language: Language
    output_language: Language

    # output dirs
    aeat_drafts_dir: Path
    aeat_submissions_dir: Path
    aeat_manuals_root: Path

    # default profile file target
    default_profile_path: Path

    # opt-ins
    aeat_live_tests_enabled: bool = False
    aeat_live_tests_google: bool = False
    provision_google_fixtures: bool = False

    # runner hooks
    steps_to_skip: frozenset[SetupStep] = frozenset()
    notes: str = ""


class VerifyFinding(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str
    severity: VerifySeverity
    message: Translatable
    remediation: Translatable | None = None


class SetupResult(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    outcome: SetupOutcome
    started_at: datetime
    ended_at: datetime
    steps_completed: tuple[SetupStep, ...]
    steps_skipped: tuple[SetupStep, ...]
    env_file_path: Path
    profile_file_path: Path
    verify_findings: tuple[VerifyFinding, ...]
    notes: str = ""
```

### non-interactive path

`SetupWizard.run(non_interactive=True, defaults=<SetupAnswers>)`
skips every prompt and feeds `defaults` directly into the state
machine. The CLI wrapper accepts a JSON path:
`aeat setup --non-interactive --from path/to/answers.json`. The JSON
is parsed with `SetupAnswers.model_validate_json`, so validation is
byte-identical to the interactive path.

### CLI surface

- `aeat setup` — interactive.
- `aeat setup --non-interactive --from <path>` — scripted.
- `aeat setup verify [--env-file <path>]` — run verifier only.
- `aeat setup show [--env-file <path>]` — pretty-print the current
  configuration (reads env file and the profile JSON; never writes).

### out of scope

- Storing the certificate password on disk. Ever.
- A web UI.
- Multi-profile management (single profile per env file for v1).
- Cl@ve auth setup.
- Hard imports from `aeat.application.workflow` (#59); `FirstRunRunner` Protocol
  stub only.
- Persisting setup runs to the storage layer.
- Modifying any in-flight sibling branch's territory (pytest
  migration #15, workflow engine #59, release-please #60).
- New env vars — the wizard is UX over existing Settings surface.

## consequences

- **Positive.** A brand-new clone reaches "valid env file +
  passing verifier" in one command. Every config decision is typed
  and re-runnable. The never-write-secrets rule is enforced by
  construction, not by convention.
- **Negative.** A new subpackage is another surface to maintain, and
  the Prompter Protocol adds a small indirection over `typer.prompt`.
  Both are worth it for the testability payoff.
- **Neutral.** The wizard is a client of existing subpackages — it
  never extends them. Future additions to `aeat.domain.deadlines`,
  `aeat.adapters.outbound.aeat.auth`, etc. are additive; the wizard picks them up on its
  next revision.
