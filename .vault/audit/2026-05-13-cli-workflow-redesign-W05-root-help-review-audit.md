---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---



# `cli-workflow-redesign` Code Review


W05-ROOT-HELP-001 | HIGH | Bare root invocation does not execute the required overview workflow
`src/aeat/entrypoints/cli/__init__.py:123`-`128` handles bare `aeat` by loading workflow state and printing `render_root_landing_text(build_root_landing_report(...))`. The backend report in `src/aeat/application/operator_surface/_help.py:19`-`31` only constructs a message and a "Next:" command string. With an active profile, this never delegates to the overview service or the mounted `app overview` command path, so bare `aeat` returns a hint instead of the canonical "where do I stand?" overview result required by the root-help ADR. This also means the real overview payload, active-profile output conventions, and backend-owned readiness/count behavior are bypassed.

W05-ROOT-HELP-002 | MEDIUM | Root help and landing output bypass the shared emitters and root format state
`src/aeat/entrypoints/cli/__init__.py:120`-`127`, `src/aeat/entrypoints/cli/__init__.py:188`-`190`, and `src/aeat/entrypoints/cli/_config.py:45`-`47` render help and landing output with direct `typer.echo(...)` calls. The root callback only stores `ctx.obj["format"]` at `src/aeat/entrypoints/cli/__init__.py:129`-`130`, after the bare-invocation branch has already returned. As a result, root discovery behavior does not use `_emit` or schema emitters and bare `aeat --format json` cannot follow the project-wide output boundary. This conflicts with the W05 thin-CLI exposure row requiring root help and discovery results to render through the central emitters.

W05-ROOT-HELP-003 | MEDIUM | Verification does not prove help rows are backed by mounted commands or that bare root runs overview behavior
`src/aeat/entrypoints/cli/test_root_help_shape.py:33`-`62` checks selected substrings in rendered help, and `src/aeat/entrypoints/cli/test_root_help_shape.py:65`-`76` checks the bare-root hint strings. The backend tests in `src/aeat/application/operator_surface/test_contract.py:196`-`219` call the same help and landing builders that the CLI renders. None of these tests parse every rendered command row and prove it resolves against the actual Typer command tree, and none assert that active-profile bare `aeat` executes the real overview backend/output path. The suite can pass while the implementation violates the root-help ADR's bare-invocation behavior.

W05-ROOT-HELP-004 | LOW | Common-mistype surface extends beyond the accepted mistype list
`src/aeat/application/operator_surface/_contract.py:51`-`56` adds a retired `auth` root suggestion, and `src/aeat/application/operator_surface/_help.py:101`-`106` renders `aeat auth -> aeat config auth` in the common-mistypes footer. The accepted root-help ADR's mistype list covers `init`, `setup`, `status`, `sanitize`, `archive`, and `submit`; it does not authorize `auth` as an additional rejected spelling. This is not a registered alias, but it does widen the compatibility/deprecation vocabulary the redesign is trying to keep closed.

W05-ROOT-HELP-005 | INFO | Targeted tests inspected and run
Reviewed the W05 grounding ADRs, the W05 plan rows, the operator-surface application changes, root/config CLI callbacks, and root-help tests. Ran `uv run pytest src/aeat/entrypoints/cli/test_root_help_shape.py src/aeat/application/operator_surface/test_contract.py`; all 15 selected tests passed. A separate console-script smoke attempt with `uv run aeat --format json` failed before command execution because a current worktree `AeatError` subclass outside the W05 files is missing a registered error-code entry; that failure was not counted as a W05 finding.

W05-ROOT-HELP-006 | INFO | Re-review after root-help fixes
Re-reviewed only the W05 root-help findings against the current worktree. Ran `uv run pytest src/aeat/entrypoints/cli/test_root_help_shape.py src/aeat/application/operator_surface/test_contract.py`; all 17 selected tests passed.

W05-ROOT-HELP-001-RR | HIGH | RESOLVED - Bare active root now emits overview status
`src/aeat/entrypoints/cli/__init__.py:130`-`136` loads workflow state and, when an active profile exists, emits `build_overview_status_report(state=workflow_state)` through `_emit`. `src/aeat/entrypoints/cli/_overview.py:120`-`121` uses the same report builder and renderer for `aeat app overview status`, and `src/aeat/entrypoints/cli/test_root_help_shape.py:66`-`79` asserts bare-root output equals `app overview status` output.

W05-ROOT-HELP-002-RR | MEDIUM | RESOLVED - Root/config/app help and landing now use shared emitters
`src/aeat/entrypoints/cli/__init__.py:114`-`136` stores the root format before early exits and routes root help, no-profile landing, and active overview through `_emit`. `src/aeat/entrypoints/cli/_config.py:45`-`47` and `src/aeat/entrypoints/cli/__init__.py:195`-`197` route config/app help through `_emit` as well. `src/aeat/entrypoints/cli/test_root_help_shape.py:82`-`96` covers root help and active bare-root JSON output.

W05-ROOT-HELP-003-RR | MEDIUM | PARTIAL - Overview equivalence is covered, mounted-command proof is still shallow
The active bare-root equivalence portion is resolved by `src/aeat/entrypoints/cli/test_root_help_shape.py:66`-`79`. The mounted-command backing test at `src/aeat/application/operator_surface/test_contract.py:213`-`225` only checks each help entry's root/child pair against the backend `command_families` contract; it does not resolve every rendered command row against the actual Typer command tree or verify leaf tokens such as `status`, `list`, `import`, or nested command groups. The original verification gap is reduced but not fully closed.

W05-ROOT-HELP-004-RR | LOW | PARTIAL - Visible `aeat auth` mistype removed, backend retired-surface suggestion remains
`src/aeat/application/operator_surface/_help.py:100`-`106` no longer renders `aeat auth -> aeat config auth` in the root common-mistypes section. However, `src/aeat/application/operator_surface/_contract.py:51`-`56` still records `auth` as a retired operator surface with suggestion `aeat config auth`, and `src/aeat/application/operator_surface/test_contract.py:80`-`92` asserts that contract. If the accepted mistype vocabulary is intended to be closed outside visible help as well, this LOW finding remains.

W05-ROOT-HELP-003-FINAL | MEDIUM | RESOLVED - Help command rows now resolve through real Typer help
`src/aeat/entrypoints/cli/test_root_help_shape.py:75`-`85` iterates every curated root/config/app help row, filters only explicit mistype/rejected rows, invokes the corresponding real Typer command path with `--help`, and fails on either non-zero exit or `No such command`. The backend contract check at `src/aeat/application/operator_surface/test_contract.py:210`-`223` remains as a contract-level mounted-family guard, while the CLI test now covers the actual Typer tree.

W05-ROOT-HELP-004-FINAL | LOW | RESOLVED - `auth` retired surface is removed from visible help and backend retired contract
`src/aeat/application/operator_surface/_help.py:96`-`106` has no `aeat auth -> aeat config auth` common-mistype row. `src/aeat/application/operator_surface/_contract.py:44`-`128` defines the retired surfaces without an `auth` entry, while `src/aeat/application/operator_surface/test_contract.py:80`-`92` explicitly asserts `retired_surface_suggestion("auth") is None`. `auth` remains only as the active `aeat config auth` child in `src/aeat/application/operator_surface/_contract.py:30`-`33`, `src/aeat/application/operator_surface/_contract.py:167`-`170`, and `src/aeat/entrypoints/cli/_config.py:29`.

W05-ROOT-HELP-001-FINAL | HIGH | RESOLVED - Active bare root delegates to overview backend through `_emit`
`src/aeat/entrypoints/cli/__init__.py:115` stores the root format before early exits. Active bare `aeat` loads workflow state at `src/aeat/entrypoints/cli/__init__.py:129`, builds `build_overview_status_report(state=workflow_state)` at `src/aeat/entrypoints/cli/__init__.py:135`, and emits `render_overview_status_lines(report)` through `_emit` at `src/aeat/entrypoints/cli/__init__.py:136`. The mounted `aeat app overview status` path uses the same backend report and renderer at `src/aeat/entrypoints/cli/_overview.py:120`-`121`, backed by `src/aeat/application/overview/__init__.py:433`-`469`.

W05-ROOT-HELP-007 | INFO | Final re-check completed with no remaining W05 root-help findings
Re-read the requested audit and source/test surface: `src/aeat/application/operator_surface/_contract.py`, `src/aeat/application/operator_surface/_help.py`, `src/aeat/application/operator_surface/test_contract.py`, `src/aeat/entrypoints/cli/test_root_help_shape.py`, `src/aeat/entrypoints/cli/__init__.py`, `src/aeat/entrypoints/cli/_config.py`, `src/aeat/entrypoints/cli/_overview.py`, and `src/aeat/application/overview/__init__.py`. Ran `uv run pytest src/aeat/entrypoints/cli/test_root_help_shape.py src/aeat/application/operator_surface/test_contract.py`; all 18 selected tests passed.
