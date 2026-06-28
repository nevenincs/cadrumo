---
tags:
  - "#exec"
  - "#setup-wizard"
date: 2026-04-12
modified: '2026-04-12'
title: First-run setup wizard — exec summary
related:
  - "[[2026-04-12-setup-wizard-research]]"
  - "[[2026-04-12-setup-wizard-adr]]"
  - "[[2026-04-12-setup-wizard-plan]]"
issue: wgergely/aeat#61
status: done
---

# exec record — first-run setup wizard (#61)

Branch: `feature/61-setup-wizard`.
Vault refs: research `[[2026-04-12-setup-wizard-research]]`, ADR
`[[2026-04-12-setup-wizard-adr]]`, plan `[[2026-04-12-setup-wizard-plan]]`.

## summary

Shipped `aeat.application.setup` end-to-end: pydantic v2 strict records, typed
`SetupWizard` orchestrator, pure verifier, env-file writer,
`QueuedPrompter` + `TyperPrompter`, and four Typer subcommands
(`aeat setup`, `aeat setup verify`, `aeat setup show`, and the
non-interactive path via `--non-interactive --from <path>`).

## deliverables

- `src/aeat/application/setup/__init__.py` — public API surface
- `src/aeat/application/setup/_models.py` — `SetupStep`, `SetupOutcome`,
  `VerifySeverity`, `SetupAnswers`, `SetupResult`, `VerifyFinding`,
  all strict, frozen, `extra="forbid"`
- `src/aeat/application/setup/_errors.py` — `SetupError`, `SetupAbortedError`,
  `SetupVerifyError`, `SetupAnswersError`, all inheriting from
  `aeat.core.errors.AeatError`
- `src/aeat/application/setup/_protocols.py` — `Prompter`, `FirstRunRunner`
- `src/aeat/application/setup/_prompter.py` — `QueuedPrompter`, `TyperPrompter`
- `src/aeat/application/setup/_env_writer.py` — `write_env_file`,
  `write_profile_file`, `owned_env_keys`
- `src/aeat/application/setup/_verifier.py` — `Verifier`, `load_answers_from_file`
- `src/aeat/application/setup/_wizard.py` — `SetupWizard`
- `src/aeat/entrypoints/cli/setup.py` — Typer sub-app
- `src/aeat/entrypoints/cli/__init__.py` — registered sub-app via
  `setup_wizard_module` alias (avoids a pytest `setup_module` hook
  collision inside the `aeat.entrypoints.cli` package namespace)
- `pyproject.toml` — per-file S105/S106 ignores for the setup tests
  (false positives on the `*_var_name` / prefix-comment pattern)

## tests

41 new unit tests, all `@pytest.mark.unit`, colocated under
`src/aeat/application/setup/`:

- `test_models.py` — round-trip, frozen, extra-fields rejected,
  never-carries-password-field, enum catalogues closed
- `test_env_writer.py` — persists every owned key, never writes
  password value even when `os.environ` holds the passphrase,
  byte-equal idempotent rerun, unrelated keys preserved, rewrite in
  place on rerun, profile JSON emission, owned-keys stability
- `test_verifier.py` — happy path, missing cert (ERROR), missing
  password env var (WARNING), output-dir mkdir, invalid profile
  (ERROR), missing profile (WARNING), answers self-consistency,
  loader happy path + missing + invalid
- `test_wizard.py` — non-interactive happy path, requires defaults,
  requires prompter, every `SetupStep` reachable, first-run skipped
  cleanly when runner is None, verify failure → `ABORTED_VERIFY_FAILED`,
  interactive `QueuedPrompter` drive-through, env file path is the
  absolute target the caller supplied
- `test_cli.py` — `setup --help`, `setup verify --help`,
  `setup show --from`, `setup --non-interactive --from`, missing
  `--from` rejected, `setup verify --from` end-to-end

Local gates: `uv run ruff check .`, `uv run ty check src tests`,
`uv run pytest`, `just hooks` — all green on Windows. 604 passed, 1
skipped, 18 deselected (live, not opted in). No Actions CI touched.

## invariants enforced

- **never-write-secrets.** `SetupAnswers` has no field for the
  passphrase value, only `certificate_password_secret_var_name`.
  `write_env_file` never reads `os.environ`. A dedicated test sets
  a distinctive sentinel in `os.environ`, runs the writer, and
  asserts the sentinel is absent from the written file.
- **idempotent-rerun.** Delegated to `aeat.core.env_io.write_env_vars`,
  verified by a byte-equal comparison after two consecutive runs.
- **unrelated-keys-preserved.** Pre-seeded env file with comments
  and unrelated keys; post-run assertion that every unrelated key
  survived.
- **pydantic v2 strict.** Every boundary record is
  `strict=True, frozen=True, extra="forbid"`, including
  `VerifyFinding` and `SetupResult`.
- **public API discipline.** Callers import only from `aeat.application.setup`.
- **errors inherit from `AeatError`.** Verified by the type
  hierarchy.
- **logging via `aeat.core.logging.get_logger(__name__)`** throughout.

## notes

- `AEAT_FALLBACK_LANGUAGES` already defaults to `en,es` in config.py
  so the wizard's `Translatable` findings render cleanly for any
  active `aeat_output_language`.
- The `FIRST_RUN` step is Protocol-stubbed per the ADR. When #59
  lands, the wizard takes a `FirstRunRunner` instance and the step
  transitions from `skipped` to `completed` with no wizard code
  change.
- `AEAT_CERTIFICATE_PASSWORD_SECRET` is the suggested default env
  var name for the PKCS#12 passphrase, matching the pattern used by
  `aeat.adapters.outbound.aeat.auth.CertificateBundle.password_env_var`. The wizard never
  reads or writes the value itself.
