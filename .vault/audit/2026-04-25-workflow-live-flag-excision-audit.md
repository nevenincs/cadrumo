---
tags:
  - '#audit'
  - '#workflow-live-flag-excision'
date: '2026-04-25'
modified: '2026-04-25'
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

- modified: `src/aeat/entrypoints/cli/workflow/run.py`,
  `src/aeat/entrypoints/cli/workflow/next.py`,
  `src/aeat/entrypoints/cli/workflow/__init__.py` (docstring only),
  `src/aeat/entrypoints/cli/workflow/test_cli.py` (two stale tests removed)
- new: `src/aeat/entrypoints/cli/workflow/test_run_help_ascii_safe.py`,
  `src/aeat/entrypoints/cli/workflow/test_next_help_ascii_safe.py`,
  `src/aeat/entrypoints/cli/workflow/test_run_refuses_live_flags.py`,
  `src/aeat/entrypoints/cli/workflow/test_next_refuses_live_flags.py`,
  `src/aeat/adapters/outbound/aeat/export/test_access_gate_workflow_untouched.py`

## Findings

INVARIANT-001 | LOW | engine constructor default `live_transport_supported=False` confirmed
The constructor default at `src/aeat/adapters/outbound/aeat/export/_engine.py` line 69 is
unchanged. Verified via `inspect.signature` in the new pin test.

INVARIANT-002 | LOW | `AeatLiveTransportUnavailableError` raise intact
The inline guard at `src/aeat/adapters/outbound/aeat/export/_engine.py` lines 211-214 is
unchanged. The engine still raises when `dry_run=False` is requested
on an inert engine.

INVARIANT-003 | LOW | `AeatAccessGate.require_live_write` posture intact
Both refusal branches (`AEAT_LIVE_SUBMIT_ENABLED` unset,
`PYTEST_CURRENT_TEST` set) are unchanged at `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py`
lines 108-130. Both branches are pinned by
`src/aeat/adapters/outbound/aeat/export/test_access_gate_workflow_untouched.py`.

INVARIANT-004 | LOW | help output omits both flag literals
`aeat workflow run --help` and `aeat workflow next --help` exit 0
with neither `--no-dry-run` nor `--i-understand-this-is-real` in the
output. Pinned by the two `_help_ascii_safe` test modules.

INVARIANT-005 | LOW | `live_transport_supported=True` matches only test sites
`rg -n "live_transport_supported=True" src/aeat/` matches only test
fixtures and one prose docstring; no production caller re-introduces
True.

INTENT-001 | LOW | production scope honoured
Only `src/aeat/entrypoints/cli/workflow/run.py` and `src/aeat/entrypoints/cli/workflow/next.py`
are modified in production code; the docstring change in
`src/aeat/entrypoints/cli/workflow/__init__.py` is a non-code metadata fix that
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
from `aeat.adapters.outbound.aeat.auth`, the typed errors from `aeat.adapters.outbound.aeat.export`, and
`Settings` from `aeat.core.config` - all public namespaces. No
underscored-module imports are introduced.

INTENT-007 | LOW | sibling-branch boundaries respected
No file under `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/` or `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py` is
touched; `feature/239-aeat-verify` territory is untouched.

QUALITY-001 | LOW | no new pydantic / error / log surface
This issue introduces no new data records, no new error classes, no
new log sites; the pydantic v2 mandate, `AeatError` inheritance
mandate, and `aeat.core.logging.get_logger(__name__)` mandate are all
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
`uv run pytest src/aeat/entrypoints/cli/workflow/ src/aeat/adapters/outbound/aeat/export/test_access_gate_workflow_untouched.py`
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
`src/aeat/adapters/outbound/aeat/export/`. This caveat is recorded in the plan's
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

The change touches `src/aeat/entrypoints/cli/workflow/test_run_refuses_live_flags.py`
and `src/aeat/entrypoints/cli/workflow/test_next_refuses_live_flags.py` only;
six lines total. The six tests still pass after the tightening.

COVERAGE-001 | LOW | scoped coverage at 100% across the workflow cli package
After the user accepted scope creep ("well-rounded terminated code
that is healthy rather than leaving feature fragments"), pre-existing
gaps in `_helpers.py`, `list_cmd.py`, and `show.py` were closed in
this same PR via `src/aeat/entrypoints/cli/workflow/test_cli_coverage_completion.py`
(eight new tests targeting the exact uncovered lines: the
`_build_profile` `WorkflowError` wrap, the `WorkflowError` catch in
both `run_engine_*` helpers, the rich-render branch in `_emit`, the
invalid-since exit-2 branch in `list_cmd`, the rich-table branch in
`list_cmd`, the missing-run exit-1 branch in `show`, and the
rich-render branch in `show`).

Final coverage on `src/aeat/entrypoints/cli/workflow/`: `__init__.py` 100%,
`_helpers.py` 100%, `list_cmd.py` 100%, `next.py` 100%, `run.py`
100%, `show.py` 100%; total 100.00%.

DEDUP-001 | LOW | shared test stand-ins extracted to `_test_doubles.py`
The first cut of `test_cli_coverage_completion.py` duplicated the
`Draft`, `DeadlineEngine`, `DraftBuilder`, `SubmissionEngine`,
`InputsProvider`, `profile()`, and `engine()` stand-ins already
defined in `test_cli.py`. Per project mandate against duplication,
fakes, and shadow code, those stubs were extracted to
`src/aeat/entrypoints/cli/workflow/_test_doubles.py` and both test modules now
import from the shared source. The new module is a real
deterministic-stand-in module - no mocks, no patches, no fakes -
matching the existing test-double pattern in the repo.

The shared module exposes: `Draft`, `DeadlineEngine`, `DraftBuilder`,
`SubmissionEngine`, `InputsProvider`, `make_profile`, `make_engine`,
`make_failing_engine`. Both test files reference these by import; no
class or factory is defined twice.

SMOKE-001 | LOW | manual cli smoke confirms dry-run-only contract end-to-end
- `uv run aeat workflow run --help` lists no live-write flag
  literals; only the new descriptive sentence "(dry-run by default)"
  and the unrelated `--sync/--no-sync` pair appear.
- `uv run aeat workflow next --help` mirrors.
- `uv run aeat workflow run --modelo 130 --period 2026Q1 --no-dry-run
  --i-understand-this-is-real` exits with typer's `No such option:
  --no-dry-run Did you mean --no-sync?` error.
- `uv run aeat workflow next --no-dry-run --i-understand-this-is-real`
  mirrors.

GEMINI-002 | LOW | docstring ADR refs allegedly leak into --help; premise verified false
Gemini's second pass added two medium-priority comments
(`run.py:41` and `next.py:42`) suggesting the function docstrings'
references to the controlling CLI wireframe ADR and to the planned
1.0.0 reintroduction path might confuse end users via `--help`
output. Verified false: `aeat workflow run --help` and
`aeat workflow next --help` render the `help="..."` strings declared
on the `app.command(...)` registrations in `__init__.py` (currently
"Run the workflow for a specific (modelo, period) target." and
"Run the workflow for the next pending obligation (dry-run by
default)." respectively). Function docstrings are not surfaced.

The docstring ADR pointer is the highest-value piece of context for
a future contributor: per CLAUDE.md, code comments should explain
*why* something is done, and the dry-run-only contract exists
specifically because of the controlling ADR. Stripping the pointer
would lose the "why" without making any user-visible difference.

Decision: decline the change. The docstrings stay; the
user-facing help is unchanged and clean.

CODEX-001 | LOW | independent codex pass found no issues
The chatgpt-codex-connector bot ran an independent review on the
post-fix state and confirmed the GEMINI-001 hardening (exit code 2
+ `.lower()`) landed correctly across all six pin sites. Verdict:
"Didn't find any major issues. Breezy!" No follow-up needed.

REVIEW-CHANNELS-001 | LOW | exhausted external review pool
- Gemini bot review: received and addressed (`GEMINI-001`).
- Codex bot review: requested via `@codex review` mention on PR #427.
- Claude bot review: requested via `@claude review` mention on PR #427.
- Fresh Gemini pass on the post-fix commit: requested via
  `@gemini review` mention on PR #427.
- `/ultrareview` is user-triggered + billed; not invoked by the
  executing agent.
