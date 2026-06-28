---
tags:
  - '#plan'
  - '#workflow-live-flag-excision'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-workflow-live-flag-excision-adr]]"
  - "[[2026-04-25-workflow-live-flag-excision-research]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
---

# `workflow-live-flag-excision` `excise --no-dry-run and --i-understand-this-is-real from default workflow cli` plan

This plan implements issue `#393`: excise `--no-dry-run` and
`--i-understand-this-is-real` from `aeat workflow run` and `aeat workflow
next`. It is the pre-approval blocker for the controlling Kent-first CLI
wireframe ADR (iteration 5).

## Proposed Changes

Two production files modified, five colocated regression tests added. No
engine changes. No `__init__.py` changes. No public-API surface beyond
the CLI is touched.

Production scope:

- `src/aeat/entrypoints/cli/workflow/run.py`: drop `--no-dry-run`,
  `--i-understand-this-is-real`, the matching parameters, the inline
  refuse-branch, the `Console` import (now unused), and force
  `dry_run=True` at the helper call site. Update docstrings.
- `src/aeat/entrypoints/cli/workflow/next.py`: same shape.

Test scope (all colocated, all new):

- `src/aeat/entrypoints/cli/workflow/test_run_help_ascii_safe.py`
- `src/aeat/entrypoints/cli/workflow/test_next_help_ascii_safe.py`
- `src/aeat/entrypoints/cli/workflow/test_run_refuses_live_flags.py`
- `src/aeat/entrypoints/cli/workflow/test_next_refuses_live_flags.py`
- `src/aeat/adapters/outbound/aeat/export/test_access_gate_workflow_untouched.py`

All five tests carry `pytestmark = [pytest.mark.unit,
pytest.mark.domain_submission]`.

## Tasks

- Phase 1 - production code excision
  1. Edit `src/aeat/entrypoints/cli/workflow/run.py`: remove flags, parameters,
     refuse-branch, `Console` import / `_CONSOLE` initialiser, the two
     `arguments` keys; force `dry_run=True`; update docstrings.
  2. Edit `src/aeat/entrypoints/cli/workflow/next.py`: same shape as `run.py`.
  3. Sanity-grep `rg -n "no_dry_run|i_understand_this_is_real"
     src/aeat/entrypoints/cli/workflow` and confirm zero matches.
  4. Sanity-grep `rg -n "live_transport_supported=True" src/aeat/` and
     confirm only test sites remain.

- Phase 2 - regression tests
  1. Add `src/aeat/entrypoints/cli/workflow/test_run_help_ascii_safe.py`. Use
     `typer.testing.CliRunner` against `aeat.entrypoints.cli.app`. Assert exit code
     0; assert the literal substrings `"--no-dry-run"` and
     `"--i-understand-this-is-real"` are absent from `result.output`.
  2. Add `src/aeat/entrypoints/cli/workflow/test_next_help_ascii_safe.py`. Mirror.
  3. Add `src/aeat/entrypoints/cli/workflow/test_run_refuses_live_flags.py`. Invoke
     `aeat workflow run --modelo 130 --period 2026Q1 --no-dry-run
     --i-understand-this-is-real`; assert non-zero exit; assert
     "no such option" or equivalent typer text in the output.
  4. Add `src/aeat/entrypoints/cli/workflow/test_next_refuses_live_flags.py`. Mirror.
  5. Add `src/aeat/adapters/outbound/aeat/export/test_access_gate_workflow_untouched.py`.
     Three pins:
     - default `live_transport_supported=False` via
       `inspect.signature(SubmissionEngine.__init__)`.
     - `AeatAccessGate(Settings()).require_live_write()` raises
       `AeatLiveSubmitNotEnabledError` when `AEAT_LIVE_SUBMIT_ENABLED`
       is unset.
     - `AeatAccessGate(Settings()).require_live_write()` raises
       `AeatPytestLiveWriteRefusedError` when `AEAT_LIVE_SUBMIT_ENABLED`
       is true and `PYTEST_CURRENT_TEST` is set.

- Phase 3 - gates and review
  1. Run `just lint`. Fix any root-cause issues; never `# noqa`.
  2. Run `just typecheck`. Fix any root-cause issues; never `# type:
     ignore`.
  3. Run `just test`. Coverage floor 60% must hold on `src/aeat`.
  4. Run `just hooks`. Fix any prek hook failures.
  5. Invoke the `vaultspec-code-review` skill against the diff.
  6. Confirm the four engine-level invariants from the ADR's
     "what is intentionally unchanged" section are intact via
     direct file inspection plus the new pin tests.
  7. Persist exec records under `.vault/exec/2026-04-25-workflow-live-flag-excision/`.

- Phase 4 - commit and PR
  1. `git add` the modified production files, the five new tests, and the
     vault artefacts (research, ADR, plan, exec).
  2. Commit with `fix(cli/workflow): excise --no-dry-run and
     --i-understand-this-is-real flags (#393)`. Body cites EPIC `#392`,
     parent ADR iteration 5, and the safety charter.
  3. `git push -u` and `gh pr create` with the same title and a body
     that links the vault artefacts and the parent EPIC / ADR.

## Plan review (self-review against authoritative inputs)

This section discharges the explicit-plan-review obligation in the
handover prompt. Each row records a check, the source of authority,
and the outcome.

| Check | Authority | Outcome |
| --- | --- | --- |
| Modules live under `src/aeat/<subpackage>/` only | CLAUDE.md src-layout mandate | Pass - all new files are under `src/aeat/entrypoints/cli/workflow/` or `src/aeat/adapters/outbound/aeat/export/`. |
| Errors derive from `AeatError` | CLAUDE.md project mandates | N/A - this issue raises no new errors. The existing `typer.Exit` removal is the only error-path change. |
| Logging via `aeat.core.logging.get_logger(__name__)` | CLAUDE.md project mandates | N/A - no new log sites. |
| Pydantic v2 strict for new data records | CLAUDE.md pydantic mandate | N/A - this issue introduces no new data models. |
| Pytest markers (Axis A access, Axis B domain) at module level | CLAUDE.md marker mandate | Pass - every new test file is `[pytest.mark.unit, pytest.mark.domain_submission]`. |
| No mocks / patches / stubs / fakes | CLAUDE.md test mandate | Pass - tests use `typer.testing.CliRunner`, `monkeypatch.delenv` / `setenv`, and `inspect.signature`. No `unittest.mock`, no `pytest_mock`. |
| Public-API discipline (callers import from `aeat.<subpkg>` only) | CLAUDE.md API mandate | Pass - the access-gate pin imports `AeatAccessGate` from `aeat.adapters.outbound.aeat.auth` and the typed errors from `aeat.adapters.outbound.aeat.export`, both public namespaces. |
| Trilingual copy via `Translatable` TypedDict | CLAUDE.md i18n mandate | N/A - no new user-facing strings. The removed `refusing:` line was English-only and goes away. |
| Conventional commits | CLAUDE.md VCS mandate | Pass - planned title `fix(cli/workflow): ...`. |
| Live-test env var name `AEAT_LIVE_TESTS_ENABLED` (not `AEAT_LIVE_TESTS`) | Memory: canonical live-test env var | Pass - the access-gate pin tests use `AEAT_LIVE_SUBMIT_ENABLED` (the write gate) per the four-factor contract. The read-side env var is irrelevant to this issue. |
| Sibling branch boundaries | Handover prompt + memory: feature/239-aeat-verify | Pass - this issue does not touch `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/*` or `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py`. |
| Engine `_engine.py` not modified | Handover prompt + ADR | Pass - the new `test_access_gate_workflow_untouched.py` pins the default via constructor introspection without modifying the file. |
| `cli/workflow/__init__.py` not modified | Handover prompt + ADR iteration 5 | Pass - the visibility / `hidden=` flip belongs to `#397`. |
| Controlling CLI wireframe ADR not modified | Handover prompt | Pass - the implementation ADR is a child document with its own slug. |
| Iteration-5 file-level excision plan honoured | Controlling ADR lines 1890-1969 | Pass - five tests mirror the ADR's prescription including the symmetric `test_next_refuses_live_flags.py` (the handover prompt enumerates four; the ADR explicitly prescribes the fifth - the implementation includes it to remove asymmetric regression risk and stay faithful to the controlling document). |
| Four engine-level invariants pinned | Handover prompt acceptance | Pass - constructor-default pin, `require_live_write` env-var-miss pin, `require_live_write` pytest-refusal pin, plus a static-grep check (executed in Phase 1 step 4) that no production caller passes `live_transport_supported=True`. |
| Acceptance: `--help` does not mention either flag | Handover prompt acceptance | Pass - covered by the two `_help_ascii_safe` tests. |
| Acceptance: passing both flags exits non-zero | Handover prompt acceptance | Pass - covered by the two `_refuses_live_flags` tests. |
| Acceptance: coverage 60% floor preserved | Handover prompt acceptance | Pass - removing the refuse-branch reduces measured lines slightly; five new tests more than compensate. The phase-3 `just test` run validates this. |
| Acceptance: `just lint && just typecheck && just test && just hooks` green on Windows | Handover prompt acceptance | Validated in Phase 3 before commit. |

Plan review outcome: **approved** by primary-agent self-review against
all authoritative inputs. No human-in-the-loop pause.

## Parallelization

The two production edits (Phase 1 steps 1-2) are independent and can be
written in parallel. The five test files are mutually independent. The
gates in Phase 3 are sequential (lint -> typecheck -> test -> hooks ->
review -> exec records).

## Verification

- `aeat workflow run --help` and `aeat workflow next --help` are run via
  `typer.testing.CliRunner` and the rendered output is asserted to
  contain neither flag literal.
- A live invocation with both flags is asserted to exit non-zero with
  typer's "no such option" text.
- `rg -n "live_transport_supported=True" src/aeat/` is asserted to match
  only test sites (executed in Phase 1 step 4 and re-checked in the
  code-review skill invocation).
- The four-factor engine gate is pinned by
  `test_access_gate_workflow_untouched.py` so a future refactor that
  weakens any of the three pin points fails the test suite.
- `just lint`, `just typecheck`, `just test`, `just hooks` all green on
  Windows.
- The vault docs (research, ADR, plan, exec) are persisted under the
  `2026-04-25-workflow-live-flag-excision` slug per the framework.

Honesty caveat: the regression tests do not exercise the engine end-to-end
(no real browser session, no real submitter dispatch). The engine path
is already covered by existing tests in `src/aeat/adapters/outbound/aeat/export/`. This
issue's tests pin the CLI surface and the engine constructor / gate
contract; they do not re-validate the full submission flow because that
would expand scope beyond the controlling ADR's iteration-5 prescription.
