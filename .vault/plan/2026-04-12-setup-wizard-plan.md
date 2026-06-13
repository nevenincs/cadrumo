---
tags:
  - "#plan"
  - "#setup-wizard"
date: 2026-04-12
modified: '2026-04-12'
title: First-run setup wizard — plan
related:
  - "[[2026-04-12-setup-wizard-research]]"
  - "[[2026-04-12-setup-wizard-adr]]"
issue: wgergely/aeat#61
status: approved
---

# plan — first-run setup wizard (#61)

## goal

Ship `aeat.application.setup` end-to-end per the ADR: pydantic v2 strict records,
typed wizard, pure verifier, env-file writer, four CLI subcommands,
colocated unit tests, lint/type/test/hooks green on Windows.

## pre-conditions

- `uv sync` green.
- `uv run vaultspec-core install` already completed for this
  worktree (it is).
- Sibling branches respected (no touching `[tool.pytest]`,
  `conftest.py`, `src/aeat/application/workflow/`, release-please surface).

## workstreams

### W1 — subpackage scaffold

1. Create `src/aeat/application/setup/__init__.py` with the public exports from
   the ADR. All callers outside `aeat.application.setup` import from this root.
2. `_errors.py` with the error hierarchy (`SetupError`,
   `SetupAbortedError`, `SetupVerifyError`, `SetupAnswersError`),
   all subclasses of `aeat.core.errors.AeatError`.
3. `_models.py` with `SetupStep`, `SetupOutcome`, `VerifySeverity`,
   `SetupAnswers`, `SetupResult`, `VerifyFinding`. Every record is
   `strict=True, frozen=True, extra="forbid"`.
4. `_protocols.py` with `Prompter` and `FirstRunRunner` Protocols.
5. `_prompter.py` with `QueuedPrompter` (a tiny test-friendly
   in-process prompter backed by a FIFO queue of typed answers).

### W2 — env-file writer

1. `_env_writer.py` exposing `write_env_file(answers, target) -> None`
   and `owned_env_keys() -> tuple[str, ...]`.
2. The writer delegates to `aeat.core.env_io.write_env_vars` so idempotency
   and unrelated-key preservation are inherited for free.
3. A second side effect: `write_profile_file(answers, target)` emits
   the `AutonomoProfile` JSON alongside the env file.
4. Unit tests (`test_env_writer.py`): round-trip via `Settings()`;
   never-write-secrets; byte-equal idempotent rerun; unrelated-keys
   preserved.

### W3 — verifier

1. `_verifier.py` exposing `Verifier.run(answers) -> tuple[VerifyFinding, ...]`.
2. Checks: certificate path exists; password env var is set (WARNING
   if missing, because the user may set it later); output dirs are
   creatable; `AutonomoProfile` JSON round-trips; `Settings()` builds
   from the written env file.
3. Unit tests (`test_verifier.py`): happy path; missing cert;
   missing password env var; unwritable output dir; invalid profile.

### W4 — wizard orchestrator

1. `_wizard.py` exposing `SetupWizard` with
   `async run(*, env_file: Path | None = None,
               non_interactive: bool = False,
               defaults: SetupAnswers | None = None,
               prompter: Prompter | None = None,
               first_run_runner: FirstRunRunner | None = None,
               now: Callable[[], datetime] | None = None) -> SetupResult`.
2. State-machine walks through every `SetupStep`. In non-interactive
   mode, every step short-circuits to `defaults`.
3. Skipped steps land in `SetupResult.steps_skipped`; completed steps
   land in `SetupResult.steps_completed`.
4. Verifier runs unconditionally. If any finding has severity
   `ERROR`, outcome becomes `ABORTED_VERIFY_FAILED`.
5. First-run is gated on `first_run_runner is not None`; absent
   runner → step is skipped cleanly.
6. `load_answers_from_file(path)` loads + validates a JSON file
   through `SetupAnswers.model_validate_json`.
7. Unit tests (`test_wizard.py`): every step reachable; happy-path
   non-interactive run produces `COMPLETED`; verify-failure produces
   `ABORTED_VERIFY_FAILED`; explicit user abort produces
   `ABORTED_BY_USER`; first-run skipped cleanly when runner is None.

### W5 — CLI wiring

1. `src/aeat/entrypoints/cli/setup.py` exposes a Typer sub-app with:
   - `setup` (default) — interactive.
   - `verify` — run verifier only.
   - `show` — print config without writing.
2. `setup` accepts `--non-interactive / --from <path> / --env-file <path>`.
3. Register in `src/aeat/entrypoints/cli/__init__.py` via `app.add_typer(
   setup_module.app, name="setup", ...)`.
4. Smoke test via `typer.testing.CliRunner` for `setup --help`,
   `setup verify --help`, `setup show --help`.

### W6 — hygiene

1. `just lint` green (ruff).
2. `just typecheck` green (ty).
3. `just test` green (pytest, all unit tests).
4. `just hooks` green (prek).
5. Commit with a focused message referencing `#61`.

## plan review

**Reviewer:** executing team (self-review per handover instructions —
"no human in the loop").
**Date:** 2026-04-12.
**Outcome:** **approved**.
**Notes:**

- Scope matches issue #61's acceptance criteria line-for-line.
- No new Settings fields; no `.env.example` drift; no sibling-branch
  territory touched.
- Pydantic-v2-strict mandate honoured across every boundary record.
- Never-write-secrets, idempotent-rerun, unrelated-keys-preserved
  invariants are each landed as dedicated unit tests.
- Protocol stub for `FirstRunRunner` keeps us decoupled from #59.
- Ready for execution phase.
