---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
tags:
  - '#audit'
  - '#workflow-live-flag-excision'
date: '2026-04-25'
related:
  - "[[2026-04-25-workflow-live-flag-excision-research]]"
  - "[[2026-04-25-workflow-live-flag-excision-adr]]"
  - "[[2026-04-25-workflow-live-flag-excision-plan]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
---

# `workflow-live-flag-excision` audit: `mandatory code review for issue #393`

## Scope

Review of the working-tree diff for issue `#393` on branch
`bug/393-workflow-live-flag-excision`. The diff excises
`--no-dry-run` and `--i-understand-this-is-real` from the default
`aeat workflow run` and `aeat workflow next` CLI surfaces and adds
five colocated regression tests pinning the closure.

Files under review:

- modified: `src/aeat/cli/workflow/run.py`,
  `src/aeat/cli/workflow/next.py`,
  `src/aeat/cli/workflow/__init__.py` (docstring only),
  `src/aeat/cli/workflow/test_cli.py` (two stale tests removed)
- new: `src/aeat/cli/workflow/test_run_help_ascii_safe.py`,
  `src/aeat/cli/workflow/test_next_help_ascii_safe.py`,
  `src/aeat/cli/workflow/test_run_refuses_live_flags.py`,
  `src/aeat/cli/workflow/test_next_refuses_live_flags.py`,
  `src/aeat/submission/test_access_gate_workflow_untouched.py`

## Findings

INVARIANT-001 | LOW | engine constructor default `live_transport_supported=False` confirmed
The constructor default at `src/aeat/submission/_engine.py` line 69 is
unchanged. Verified via `inspect.signature` in the new pin test.

INVARIANT-002 | LOW | `AeatLiveTransportUnavailableError` raise intact
The inline guard at `src/aeat/submission/_engine.py` lines 211-214 is
unchanged. The engine still raises when `dry_run=False` is requested
on an inert engine.

INVARIANT-003 | LOW | `AeatAccessGate.require_live_write` posture intact
Both refusal branches (`AEAT_LIVE_SUBMIT_ENABLED` unset,
`PYTEST_CURRENT_TEST` set) are unchanged at `src/aeat/auth/_gate.py`
lines 108-130. Both branches are pinned by
`src/aeat/submission/test_access_gate_workflow_untouched.py`.

INVARIANT-004 | LOW | help output omits both flag literals
`aeat workflow run --help` and `aeat workflow next --help` exit 0
with neither `--no-dry-run` nor `--i-understand-this-is-real` in the
output. Pinned by the two `_help_ascii_safe` test modules.

INVARIANT-005 | LOW | `live_transport_supported=True` matches only test sites
`rg -n "live_transport_supported=True" src/aeat/` matches only test
fixtures and one prose docstring; no production caller re-introduces
True.

INTENT-001 | LOW | production scope honoured
Only `src/aeat/cli/workflow/run.py` and `src/aeat/cli/workflow/next.py`
are modified in production code; the docstring change in
`src/aeat/cli/workflow/__init__.py` is a non-code metadata fix that
removes a now-false claim.

INTENT-002 | LOW | helper signatures preserved
`run_engine_for_period` and `run_engine_next` retain their
`dry_run: bool` keyword; the CLI now passes `dry_run=True`
unconditionally.

INTENT-003 | LOW | refuse-branch and `Console` import removed cleanly
The inline `typer.Exit(code=2)` branch and the unused `rich.Console`
import / `_CONSOLE` initialiser are removed from both files.

INTENT-004 | LOW | stale tests in `test_cli.py` removed
`test_next_live_without_flag_exits_2` and
`test_run_live_without_flag_exits_2` asserted the old refuse-branch
wording. They are superseded by the new
`test_*_refuses_live_flags.py` modules and have been deleted to
prevent a false-failure on the now-correct typer "no such option"
path.

INTENT-005 | LOW | marker convention followed
Every new test module opens with
`pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]` per
the handover prompt's authoritative axis assignment for this issue.

INTENT-006 | LOW | public-API discipline preserved
`test_access_gate_workflow_untouched.py` imports `AeatAccessGate`
from `aeat.auth`, the typed errors from `aeat.submission`, and
`Settings` from `aeat.config` - all public namespaces. No
underscored-module imports are introduced.

INTENT-007 | LOW | sibling-branch boundaries respected
No file under `src/aeat/sede/` or `src/aeat/auth/_clave_movil.py` is
touched; `feature/239-aeat-verify` territory is untouched.

QUALITY-001 | LOW | no new pydantic / error / log surface
This issue introduces no new data records, no new error classes, no
new log sites; the pydantic v2 mandate, `AeatError` inheritance
mandate, and `aeat.logging.get_logger(__name__)` mandate are all
N/A.

QUALITY-002 | LOW | typed signatures and Google-style docstrings
Both `run_cmd` and `next_cmd` retain full type hints on every
parameter; their Google-style docstrings are updated to drop the
removed `no_dry_run` / `i_understand_this_is_real` argument
descriptions and to add a single sentence explaining the dry-run-only
contract.

QUALITY-003 | LOW | no forbidden test libraries
None of the new test modules import `unittest.mock`, `pytest_mock`,
`pytest_httpx`, `time_machine`, `freezegun`, or `vcr`. They use only
`pytest`, `typer.testing.CliRunner`, `monkeypatch`, and
`inspect.signature`.

QUALITY-004 | LOW | targeted test run green
`uv run pytest src/aeat/cli/workflow/ src/aeat/submission/test_access_gate_workflow_untouched.py`
reports 19 passed; the broader gate
(`just lint && just typecheck && just test && just hooks`) is run
before commit per the plan.

DRIFT-001 | LOW | `.gitignore` hunk unrelated to issue
The bootstrap step (`uv run vaultspec-core install --upgrade`)
removed the line `/.pre-commit-config.yaml.lock` from `.gitignore`.
This is incidental drift from the framework upgrade, not part of
issue `#393`. Recommendation: drop the hunk before commit so the
`#393` PR is focused.

HONESTY-001 | LOW | engine end-to-end intentionally not re-validated
The new pin test exercises the constructor signature and the gate
helper rather than building a full engine with browser sessions and
submitters. The full engine path is covered by existing tests in
`src/aeat/submission/`. This caveat is recorded in the plan's
"Verification" section.

## Recommendations

- Drop the `.gitignore` hunk from the commit (DRIFT-001) so the PR
  diff is exactly the production code excision, the docstring fix,
  the stale-test removal, the five new tests, and the four vault
  artefacts.
- Proceed to commit and PR per the plan.

## Verdict

**PASS** - all five mandatory invariants hold, 19/19 affected tests
pass, no Critical or High findings. The one Low (DRIFT-001) is an
incidental bootstrap artefact and is excluded from the commit.

## Triage of external review (2026-04-25, post-merge of PR #427)

GEMINI-001 | MEDIUM | tighten refuse-tests to typer's standard exit code 2 and case-insensitive substring
The Gemini code-assist bot left six identical comments on PR #427
suggesting (a) `result.exit_code == 2` instead of `!= 0` and
(b) `"no such option" in result.output.lower()` instead of the
case-sensitive `"No such option" in result.output`. Both improvements
are applied in a follow-up commit:

- exit code 2 is typer/click's canonical `UsageError` code; pinning
  it catches a regression where the CLI silently strips the flag and
  returns 0 (or any other non-zero), where the looser `!= 0` would
  pass.
- `.lower()` removes the typer/click-version coupling; the rendered
  text is `"No such option"` today but a future minor version could
  change the casing without breaking the contract.

The change touches `src/aeat/cli/workflow/test_run_refuses_live_flags.py`
and `src/aeat/cli/workflow/test_next_refuses_live_flags.py` only;
six lines total. The six tests still pass after the tightening.
