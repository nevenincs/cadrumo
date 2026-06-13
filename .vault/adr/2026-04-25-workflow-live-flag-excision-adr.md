---
tags:
  - '#adr'
  - '#workflow-live-flag-excision'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-workflow-live-flag-excision-research]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
---

# `workflow-live-flag-excision` adr: `excise --no-dry-run and --i-understand-this-is-real from default workflow cli` | (**status:** `accepted`)

## Problem Statement

`aeat workflow run --help` and `aeat workflow next --help` currently advertise
`--no-dry-run` and `--i-understand-this-is-real` on the default public CLI
surface. These flags are first-contact discoverable for any operator who runs
`--help`, which violates the live-AEAT-write safety charter (`#116`) and
partially undermines the default-live-submit excision ADR
(2026-04-18). The controlling Kent-first CLI wireframe ADR (2026-04-24,
iteration 5) marks this leak as a pre-approval blocker: that ADR cannot
flip from `proposed` to `accepted` until the leak is closed at the source.

This implementation ADR is a child of the controlling wireframe ADR and
records the local decisions consumed by the plan and exec records for
issue `#393`.

## Considerations

- The controlling wireframe ADR's iteration 5 (lines 1819-1969) selects
  closure path 3 - excise the live branch from the default CLI entirely
  rather than gating it behind a `hidden=True` flip on the typer group.
  This implementation ADR adopts that selection verbatim.
- Engine-level safety must not be weakened. The four-factor gate
  (engine default `live_transport_supported=False`, inline
  `AeatLiveTransportUnavailableError` raise, env-var gate via
  `AeatAccessGate.require_live_write`, interactive
  `confirm_live_submission` typed phrase) lives at the engine layer and
  is independent of the CLI plumbing being removed here.
- The `_helpers.run_engine_for_period` and `_helpers.run_engine_next`
  functions accept `dry_run: bool` as a keyword. Forcing `dry_run=True`
  at the CLI call site preserves the helper's signature and the
  workflow engine's `run_for_period(..., dry_run=...)` /
  `run_next(..., dry_run=...)` contract; no helper changes are needed.
- The advanced-quarantine migration that hides these commands behind
  `aeat advanced workflow ...` is the iteration-4 work in `#397`. It
  deliberately runs on its own track to keep this issue minimum-intrusion.
- Sibling branches in flight (`feature/239-aeat-verify`,
  `chore/356-followup-vault-records`) do not collide with this scope.

## Constraints

- Branch `bug/393-workflow-live-flag-excision`, base `origin/main` at
  commit `19a1054`.
- Modify only `src/aeat/entrypoints/cli/workflow/run.py` and
  `src/aeat/entrypoints/cli/workflow/next.py` in production code.
- Do not modify `src/aeat/entrypoints/cli/workflow/__init__.py` (visibility / `hidden=`
  flips are out of scope per the controlling ADR).
- Do not modify `src/aeat/adapters/outbound/aeat/export/_engine.py`. The engine's
  `live_transport_supported=False` default must remain; this issue
  pins it via a regression test rather than touching it.
- Do not modify the controlling CLI wireframe ADR. The authoring agent
  owns that document.
- Tests are pytest-only, no `unittest.mock` / `pytest_mock` /
  `pytest_httpx` / `time_machine` / `freezegun` / `vcr`.
- Module-level marker convention: `pytestmark = [pytest.mark.unit,
  pytest.mark.domain_submission]` for every new test file in this issue.
- Help-rendering assertions stay ASCII-safe to avoid the Windows cp1252
  precedent documented in `#389`.
- Coverage floor 60% on `src/aeat` is preserved.

## Implementation

### file changes (production)

`src/aeat/entrypoints/cli/workflow/run.py`:

- Drop the `--no-dry-run` typer option and the `no_dry_run: bool` parameter.
- Drop the `--i-understand-this-is-real` typer option and the
  `i_understand_this_is_real: bool` parameter.
- Drop the inline refuse-branch (current lines 54-58) that raises
  `typer.Exit(code=2)`. The flags it gates no longer exist.
- Drop the unused `from rich.console import Console` import and the
  module-level `_CONSOLE = Console()` initialiser (the refuse-branch was
  the only caller).
- Drop the `"no-dry-run"` and `"i-understand-this-is-real"` keys from
  the `arguments` mapping passed into `cli_run_context`.
- Force `dry_run=True` at the `run_engine_for_period` call site.
- Adjust the docstring: remove the `no_dry_run` and
  `i_understand_this_is_real` argument descriptions, and add a single
  sentence stating that the command is dry-run-only and the 1.0.0
  reintroduction path is `aeat advanced workflow run --live`.
- Adjust the module-level docstring to reflect the dry-run-only
  contract.

`src/aeat/entrypoints/cli/workflow/next.py`:

- Drop the `--no-dry-run` typer option and the `no_dry_run: bool` parameter.
- Drop the `--i-understand-this-is-real` typer option and the
  `i_understand_this_is_real: bool` parameter.
- Drop the inline refuse-branch (current lines 58-62).
- Drop the unused `from rich.console import Console` import and the
  module-level `_CONSOLE = Console()` initialiser.
- Drop the `"no-dry-run"` and `"i-understand-this-is-real"` keys from
  the `arguments` mapping.
- Force `dry_run=True` at the `run_engine_next` call site.
- Adjust the docstring identically to `run.py`.
- Adjust the module-level docstring; the prior wording about
  "double-gate contract" is moved to describe the engine-level gate
  rather than CLI-level flags.

`src/aeat/entrypoints/cli/workflow/__init__.py`:

- No change. The advanced-quarantine migration is iteration 4 (`#397`).

### file changes (regression tests, all colocated, all new)

All five tests open with:

```python
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]
```

`src/aeat/entrypoints/cli/workflow/test_run_help_ascii_safe.py`:

- Use `typer.testing.CliRunner` to invoke
  `runner.invoke(root_app, ["workflow", "run", "--help"])`.
- Assert exit code `0`.
- Assert the literal substrings `"--no-dry-run"` and
  `"--i-understand-this-is-real"` do not appear in `result.output`.
- Document the ASCII-safe approach in the test docstring with a pointer
  to `#389`.

`src/aeat/entrypoints/cli/workflow/test_next_help_ascii_safe.py`:

- Mirror of the above for `["workflow", "next", "--help"]`.

`src/aeat/entrypoints/cli/workflow/test_run_refuses_live_flags.py`:

- Invoke `runner.invoke(root_app, ["workflow", "run", "--modelo", "130",
  "--period", "2026Q1", "--no-dry-run",
  "--i-understand-this-is-real"])`.
- Assert exit code is non-zero (typer's "no such option" path).
- Assert the rendered output / stderr describes the flag as unknown
  (substring `"No such option"` or equivalent typer-emitted phrase).
- Document the intent: "if a script in the wild still passes these
  flags, the CLI must fail loudly rather than silently strip them."

`src/aeat/entrypoints/cli/workflow/test_next_refuses_live_flags.py`:

- Mirror of the above for `["workflow", "next"]`.

`src/aeat/adapters/outbound/aeat/export/test_access_gate_workflow_untouched.py`:

- Engine-level invariant pin. Imports `SubmissionEngine` from
  `aeat.adapters.outbound.aeat.export` and `AeatAccessGate` /
  `AeatLiveSubmitNotEnabledError` /
  `AeatPytestLiveWriteRefusedError` from `aeat.adapters.outbound.aeat.auth` /
  `aeat.adapters.outbound.aeat.export`.
- Pin 1: assert that `SubmissionEngine` exposes a constructor parameter
  `live_transport_supported` whose default value is `False`. The check
  uses `inspect.signature(SubmissionEngine.__init__)` so it does not
  need to construct an engine.
- Pin 2: assert that calling
  `AeatAccessGate(Settings()).require_live_write()` raises
  `AeatLiveSubmitNotEnabledError` when `AEAT_LIVE_SUBMIT_ENABLED` is
  unset (use `monkeypatch.delenv` for both `AEAT_LIVE_SUBMIT_ENABLED`
  and ensure `PYTEST_CURRENT_TEST` is set as it always is under
  pytest - the env-var miss must be reported, not the pytest refusal).
  Strategy: delete the submit env var, call `require_live_write`, catch
  the typed error.
- Pin 3: assert that
  `AeatAccessGate(Settings()).require_live_write()` raises
  `AeatPytestLiveWriteRefusedError` when `AEAT_LIVE_SUBMIT_ENABLED=true`
  but `PYTEST_CURRENT_TEST` is set (which it always is under pytest).
- The test does not import or exercise `SubmissionEngine._submit_with_transport`
  directly because that path needs a fully-wired engine; the gate-level
  pin and the constructor-default pin together cover the four-factor
  contract from the CLI's perspective.

### what is intentionally unchanged

- `src/aeat/adapters/outbound/aeat/export/_engine.py` line 69 (`live_transport_supported:
  bool = False` default).
- `src/aeat/adapters/outbound/aeat/export/_engine.py` lines 211-214 (`AeatLiveTransportUnavailableError`
  raise).
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py` (the entire access-gate module).
- `src/aeat/adapters/outbound/aeat/export/_confirm.py` (typed-phrase confirmation).
- `src/aeat/entrypoints/cli/workflow/__init__.py` (typer group registration).
- `src/aeat/entrypoints/cli/workflow/_helpers.py` (helper signatures and bodies).

## Rationale

Path 3 (excise from the default CLI) is the minimum-intrusion fix that
fully closes the Kent-facing leak without forcing the iteration-4
advanced-quarantine migration to land first. The alternative path -
flip `hidden=True` on the typer group - leaves the flags discoverable
via `aeat workflow run --help` once the user is on the command, which
does not satisfy the "no reachable mechanism" posture the safety
charter mandates.

The engine-level four-factor gate stays in place exactly because it is
the layer that protects programmatic callers (CI, scripts, future
internal automation). The CLI is the surface Kent and operators see;
the engine is the layer that enforces the actual safety contract. The
two layers are intentionally independent so a future CLI redesign
cannot weaken the engine and a future engine refactor cannot
re-expose CLI flags.

The new `test_access_gate_workflow_untouched.py` pins the engine
contract via constructor introspection rather than a full integration
build because the integration build requires browser sessions, portal
catalogues, and submitter wiring that are out of scope for a CLI flag
removal. Constructor-default + gate refusal cover the full surface
that this issue's change interacts with.

## Consequences

- Programmatic callers that import `run_cmd` or `next_cmd` directly and
  pass `no_dry_run=` / `i_understand_this_is_real=` keyword arguments
  will fail with `TypeError`. A grep across `src/aeat/` confirms no
  such callers exist; the only callers are the typer registration in
  `src/aeat/entrypoints/cli/workflow/__init__.py`, which takes the function by
  reference.
- Scripts in the wild that pass `--no-dry-run --i-understand-this-is-real`
  on the command line will exit non-zero with typer's "no such option"
  error. This is the intended behaviour per the controlling ADR's
  iteration 5: a loud failure is preferable to a silently-stripped
  flag that lets the caller think they triggered a live submission.
- The pre-approval blocker on the controlling Kent-first CLI wireframe
  ADR is closed. Iteration 6 of that ADR can flip the status from
  `proposed` to `accepted`. That iteration is owned by the authoring
  agent, not by this issue.
- The 1.0.0 reintroduction path (`aeat advanced workflow run --live`)
  remains open. Its design and implementation belong to a future ADR
  and a future issue, not this one.
- Coverage on `src/aeat/entrypoints/cli/workflow` decreases marginally because
  the refuse-branch (lines 54-58 / 58-62) is no longer measured. The
  five new tests more than compensate; the 60% floor is preserved.
