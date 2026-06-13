---
tags:
  - '#research'
  - '#workflow-live-flag-excision'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
---

# `workflow-live-flag-excision` research: `pre-approval blocker for the kent-first cli wireframe adr`

Issue `#393` is the pre-approval blocker for the controlling Kent-first CLI
wireframe ADR (iteration 5, 2026-04-24). The wireframe ADR cannot move from
`proposed` to `accepted` until the live-flag leak in `aeat workflow run` and
`aeat workflow next` is closed at the source.

This research records the on-disk truth as of branch
`bug/393-workflow-live-flag-excision` so the implementation ADR, plan, and
exec records can rely on a single shared snapshot.

## Findings

### live-flag visibility on the default cli surface

`src/aeat/entrypoints/cli/workflow/run.py` registers two live-write flags on the default
public CLI:

- `--no-dry-run` (lines 23-27, `no_dry_run: bool` parameter on `run_cmd`).
- `--i-understand-this-is-real` (lines 28-32, `i_understand_this_is_real: bool`
  parameter on `run_cmd`).

`src/aeat/entrypoints/cli/workflow/next.py` registers the same two flags:

- `--no-dry-run` (lines 28-32, `no_dry_run: bool` parameter on `next_cmd`).
- `--i-understand-this-is-real` (lines 33-37, `i_understand_this_is_real: bool`
  parameter on `next_cmd`).

Both modules contain an inline refuse-branch (`run.py` lines 54-58, `next.py`
lines 58-62) that prints `refusing: --no-dry-run requires
--i-understand-this-is-real` and exits with code 2 when only one flag is
passed. The refuse-branch is defence in depth, but the flags themselves are
first-contact discoverable because neither command nor the hosting Typer
group is marked `hidden=True` in `src/aeat/entrypoints/cli/workflow/__init__.py`.

The CLI then forwards `dry_run=not no_dry_run` into the helper functions
`run_engine_for_period` and `run_engine_next` in
`src/aeat/entrypoints/cli/workflow/_helpers.py` (lines 124, 154). The helper itself does
not re-gate; it trusts the caller, then calls
`engine.run_for_period(..., dry_run=dry_run)` and
`engine.run_next(..., dry_run=dry_run)` respectively.

### engine-level four-factor gate (must remain intact)

The four-factor gate at the engine layer is independent of the CLI flag
plumbing and must not be touched by this change:

1. `SubmissionEngine.__init__` defaults `live_transport_supported=False`
   (`src/aeat/adapters/outbound/aeat/export/_engine.py` line 69). Any caller that omits the
   keyword inherits the inert engine.
2. The inline pre-transport check in `_submit_with_transport` raises
   `AeatLiveTransportUnavailableError` when a non-dry-run submission is
   requested and `self.live_transport_supported` is False
   (`src/aeat/adapters/outbound/aeat/export/_engine.py` lines 211-214).
3. `AeatAccessGate.require_live_write()` (`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py` lines
   108-130) refuses unless `AEAT_LIVE_SUBMIT_ENABLED` is true *and* the
   process is not running under pytest (`PYTEST_CURRENT_TEST` absent).
4. `confirm_live_submission` in `src/aeat/adapters/outbound/aeat/export/_confirm.py` requires an
   interactive typed confirmation phrase before any submitter dispatch.

The handover prompt names the gate file as
`src/aeat/adapters/outbound/aeat/export/_access_gate.py`. That path does not exist on this
branch. The actual implementation lives at `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py` and is
re-exported through `aeat.adapters.outbound.aeat.auth` (`AeatAccessGate`, `AeatGateEnvSnapshot`).
The gate is consumed by `SubmissionEngine._submit_with_transport` via an
inline construction (`AeatAccessGate(self.settings)`); it is never
injected as a constructor seam (R5 of safety charter `#116`).

### live_transport_supported audit

`grep -n "live_transport_supported=True" src/aeat/` matches only test sites
on this branch:

- `src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py` line 238 (test fixture).
- `src/aeat/entrypoints/cli/submission/test_live_submit_defer_visibility.py` lines 66
  and 80 (visibility regression tests).

No production caller sets it `True`. This invariant is what the new
regression test `test_access_gate_workflow_untouched.py` will pin.

### sibling branches in flight

- `feature/239-aeat-verify` owns `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/` and extends
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py`. No collision with this issue's scope
  (`src/aeat/entrypoints/cli/workflow/` plus a single new test under
  `src/aeat/adapters/outbound/aeat/export/`).
- `chore/356-followup-vault-records` is vault-only, no code overlap.
- The CLI wireframe authoring agent's vault docs are now on `main` at commit
  `e2b787f`; the controlling ADR is read-only for this issue. The authoring
  agent owns ADR edits.

### controlling adr extracts

Iteration 5 of the controlling ADR (`.vault/adr/2026-04-24-aeat-cli-wireframe-adr.md`,
lines 1819-1969) prescribes path 3 (excise the live branch from the default
CLI entirely) as the minimum-intrusion closure for this blocker. The ADR's
"file-level excision plan" enumerates:

- remove the two flags and their parameters from `run_cmd` and `next_cmd`
- remove both refuse-branches
- force `dry_run=True` at every downstream call site
- leave `src/aeat/entrypoints/cli/workflow/__init__.py` unchanged (the
  advanced-quarantine migration is iteration 4 / a separate issue)
- ship colocated regression tests for help rendering and unknown-option
  refusal
- ship an engine-level invariant test that the four-factor gate is
  untouched

The ADR also calls out that `aeat advanced workflow run --live` is the
intended 1.0.0 reintroduction path, not a re-grow of the default tree.

### prior excision adr

`.vault/adr/2026-04-18-live-submit-cli-excision-adr.md` (D1, D2, D3) sets the
foundational mandate that informs this issue:

- D1: `aeat submission submit` is unregistered from the default CLI.
- D2: `SubmissionEngine.live_transport_supported` defaults to `False`.
- D3: live-submitter clicks (`#firmar-y-enviar`) remain in code as a
  follow-up Option-C target but are no longer reachable from any default
  CLI surface.

This issue extends D1 to cover the workflow CLI, which was missed by the
original 2026-04-18 sweep. The decision is consistent: every default CLI
surface must be incapable of triggering an AEAT submission.

### existing test patterns

Existing workflow CLI tests (`src/aeat/entrypoints/cli/workflow/test_cli.py`,
`test_cli_runtime.py`) drive the typer surface via
`typer.testing.CliRunner` and import the root app from `aeat.entrypoints.cli`. They use
the module-level marker pattern `pytestmark = [pytest.mark.unit,
pytest.mark.<domain>]`. The new colocated regression tests must follow the
same shape so the test discovery and marker selection stay coherent.

The `_helpers.set_test_hooks` and `clear_test_hooks` seam is available for
isolating the engine factory in tests, but the new tests in this issue do
not need to construct an engine at all - they exercise help rendering and
unknown-option refusal, which run before any engine wiring.

### actions ci status

`.github/workflows/ci.yml` runs on every PR across Ubuntu and Windows
(Python 3.13). No new workflow file is required; the local gates
(`just lint`, `just typecheck`, `just test`, `just hooks`) are re-run by
CI on PR open.

### windows console encoding precedent

PR `#389` documented a Windows cp1252 crash on certain CLI surfaces. Help
output is rendered through Rich, which can include non-ASCII glyphs. The
new help-rendering tests therefore restrict their assertions to ASCII-safe
substrings (`"--no-dry-run"` and `"--i-understand-this-is-real"`) rather
than full-output normalisation - that is the spirit behind the
`test_*_help_ascii_safe.py` filename convention.

## scope decisions consumed by the implementation adr

- The implementation hits exactly two production files:
  `src/aeat/entrypoints/cli/workflow/run.py` and `src/aeat/entrypoints/cli/workflow/next.py`.
- `src/aeat/entrypoints/cli/workflow/__init__.py` is not modified; the
  advanced-quarantine migration (iteration 4 / `#397`) is out of scope.
- Five new test files, all colocated:
  - `src/aeat/entrypoints/cli/workflow/test_run_help_ascii_safe.py`
  - `src/aeat/entrypoints/cli/workflow/test_next_help_ascii_safe.py`
  - `src/aeat/entrypoints/cli/workflow/test_run_refuses_live_flags.py`
  - `src/aeat/entrypoints/cli/workflow/test_next_refuses_live_flags.py` (symmetry
    completion mandated by iteration 5; the handover prompt enumerates
    four tests but the controlling ADR explicitly prescribes the
    `next` mirror to avoid an asymmetric regression surface)
  - `src/aeat/adapters/outbound/aeat/export/test_access_gate_workflow_untouched.py`
- All five tests carry `pytestmark = [pytest.mark.unit,
  pytest.mark.domain_submission]` per the handover prompt's authoritative
  marker assignment for this issue.

## risks and mitigations

- **Risk:** removing the refuse-branch could mask a regression that
  re-introduces the flags via merge conflict.
  - **Mitigation:** the help-rendering tests assert flag absence on
    every PR; the unknown-option tests assert that a script in the wild
    still passing the flags fails loudly with a typer "no such option"
    exit rather than silently succeeding.
- **Risk:** programmatic callers that import the `run_cmd` or `next_cmd`
  function directly may fail with a `TypeError` if they pass keyword
  arguments matching the removed parameters.
  - **Mitigation:** there are no production callers of `run_cmd` /
    `next_cmd` outside the typer registration; the only callers are
    `app.command(...)(run_cmd)` and `app.command(...)(next_cmd)` in
    `src/aeat/entrypoints/cli/workflow/__init__.py`, which take the function by
    reference. A grep across `src/aeat/` confirms no imports of these
    symbols.
- **Risk:** the engine-level four-factor gate is silently weakened in a
  later refactor.
  - **Mitigation:** the new
    `src/aeat/adapters/outbound/aeat/export/test_access_gate_workflow_untouched.py` pins
    the four invariants (default `live_transport_supported=False`,
    inline `AeatLiveTransportUnavailableError` raise, gate refusal
    without env var, gate refusal under pytest).

## open questions

None blocking. Iteration 4 (`#397`) will hide the workflow commands behind
`aeat advanced workflow ...` after this issue lands; that work is on its
own track and does not gate this PR.
