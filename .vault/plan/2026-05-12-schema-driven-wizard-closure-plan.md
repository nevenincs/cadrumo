---
tags:
  - '#plan'
  - '#schema-driven-wizard-closure'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-adr]]"
  - "[[2026-05-12-schema-driven-wizard-plan]]"
  - "[[2026-05-12-schema-driven-wizard-revision-plan]]"
  - "[[2026-05-12-schema-driven-wizard-research]]"
  - "[[2026-04-12-setup-wizard-research]]"
---

# schema-driven wizard closure plan

Closure plan landing the final five findings from the second-loop code
review of the schema-driven wizard work. The original ADR is unchanged;
the revision plan closed fourteen of fifteen original findings cleanly;
this plan closes the five surviving issues the second-loop reviewer
identified.

## Proposed Changes

The second-loop reviewer accepted the wizard slice on the headline ADR
contract (descriptor-driven Typer flag derivation, `setup/` deletion,
`setup_status` consolidation, legacy autonomo-helper removal, locale
parity for `wizard.*`) but flagged five surviving items:

- N1 — Module docstrings still describe the deleted `aeat archive` /
  `aeat topic` / `aeat help` invocation forms after R14's wiring move
- N2 — `cli.archive.*` and `cli.topic.*` translation keys leak as raw
  literal text at runtime because the R9 audit broadening stopped at
  the `cli.config.*` namespace
- N3 — R12 and R13 reintroduced transient-meta phrasing the R2 Step
  was tasked to excise (`historically`, `with the wizard rewrite`,
  `UX-015 closure.`)
- N4 — Top-level `version` command at the CLI root violates the
  standing config-plus-app-only rule (pre-existing but unaddressed)
- N5 — `test_workflow_surface.py` (30 failures) and
  `application/test_config_parity.py` (3 failures) test the deleted
  `aeat setup` / `aeat init` surfaces. The revision executor's R15
  record classified these as "pre-existing" — verified wrong by the
  reviewer (the file was authored on this branch by a WIP commit
  *after* session baseline, so the wizard work is the cause)

## Tasks

The C-prefixed step numbers belong to this plan and commit messages
only; they never appear in source code.

- C1 — Sweep stale invocation-form docstrings from the archive and topic CLI surface
  - Files owned: `src/aeat/entrypoints/cli/_archive.py`,
    `src/aeat/entrypoints/cli/_topic.py`,
    `src/aeat/application/topics/__init__.py`
  - Rewrite each module docstring so it describes the surface under
    its current invocation path (`aeat app archive`, `aeat app topic`).
    Remove every reference to the deleted `aeat archive`, `aeat topic`,
    `aeat help <slug>` forms in docstrings, module-level comments, and
    in-source examples
  - Acceptance gates:
    - `grep -rn 'aeat archive\b\|aeat topic\b\|aeat help <\?slug' src/aeat/entrypoints/cli/_archive.py src/aeat/entrypoints/cli/_topic.py src/aeat/application/topics/` returns nothing
    - prek + ruff + ty green
  - Does NOT: rename the underlying typer commands

- C2 — Land the `cli.archive.*` and `cli.topic.*` locale catalogues and broaden the audit
  - Files owned: `src/aeat/locales/{ca,en,es,hu}.yml`,
    `src/aeat/application/wizard/_translations.py`
  - Replace the placeholder `<key>: cli.archive.<key>` (literal key
    text as value) pattern in every locale file with a real
    translated value for the full `cli.archive.*` and `cli.topic.*`
    namespaces. Reference inventory: every key the entrypoint files
    (`_archive.py`, `_topic.py`) reference at `tr(...)` call sites
  - Broaden `audit_cli_config_translations` (rename to
    `audit_cli_translations` if its scope is no longer config-specific)
    to walk every `cli.<group>.*` namespace referenced by entrypoint
    modules. The audit produces a structured failure when any key is
    absent or any locale carries the literal-key fallback value
  - Acceptance gates:
    - `aeat app archive --help` and `aeat app topic --help` render
      translated text in every locale (no raw `cli.archive.*` or
      `cli.topic.*` strings visible)
    - `audit_cli_translations()` returns `()`
    - `pytest src/aeat/entrypoints/cli/test_workflow_surface.py::test_user_help_surfaces_do_not_leak_translation_keys` green
  - Does NOT: touch wizard or config locale keys (already complete)

- C3 — Excise the three transient-meta phrases R12 and R13 reintroduced
  - Files owned: `src/aeat/application/profile/_storage_namespaces.py`,
    `src/aeat/domain/deadlines/_profiles.py`,
    `src/aeat/entrypoints/cli/_topic.py`
  - Rewrite the docstring at `_storage_namespaces.py:10` to describe
    the constants' purpose structurally (their role as HKDF context
    binding) without referencing the wizard rewrite
  - Rewrite the inline comment at `_profiles.py:36-38` to describe
    the normalisation invariant structurally without the
    `deadline-engine callers historically supplied mixed case`
    framing
  - Remove the `UX-015 closure.` line from `_topic.py:3`
  - Acceptance gates:
    - `grep -rn 'historically\|legacy\|previously\|formerly\|replaces\|UX-[0-9]' src/aeat/application/profile/_storage_namespaces.py src/aeat/domain/deadlines/_profiles.py src/aeat/entrypoints/cli/_topic.py` returns nothing
    - prek + ruff + ty green
  - Does NOT: change behavior

- C4 — Remove the top-level `version` command at the CLI root
  - Files owned: `src/aeat/entrypoints/cli/__init__.py`, and the
    tests that exercise it (`test_cli_surface.py` or equivalent)
  - Delete the registered `version` Typer command at
    `src/aeat/entrypoints/cli/__init__.py:96-105`. The existing
    `--version` / `-V` flag on the root callback already serves the
    same surface
  - Update or delete any test that asserts `aeat version` produces a
    specific output; rewrite to assert `aeat --version` instead
  - Acceptance gates:
    - `aeat --help` lists exactly two subgroups: `config` and `app`
    - `aeat --version` still prints the version string
    - `aeat version` (no flag) exits non-zero with a "no such command"
      error
    - `pytest src/aeat/entrypoints/cli/test_cli_surface.py` green
  - Does NOT: change the version-string format

- C5 — Adjudicate and fix the wizard-caused test regressions
  - Files owned: `src/aeat/entrypoints/cli/test_workflow_surface.py`,
    `src/aeat/application/test_config_parity.py`, and any fixture
    helpers they import
  - For every failing test in `test_workflow_surface.py` (30 failures)
    and `test_config_parity.py` (3 failures):
    - If the test only verifies a deleted command's existence or its
      help text (e.g., `test_setup_init_help_carries_examples_*`,
      `test_setup_auth_*`): delete the test. The deleted command is
      gone; the test has no surface to assert against
    - If the test verifies error-boundary text that references the
      deleted command (e.g., `aeat setup auth login` in an error
      suggestion): rewrite the assertion against the new
      `aeat config auth` suggestion, OR update the error registry's
      suggestion string and the test together
    - If the test verifies a declaration / ledger / invoice surface
      with fixture seeding that touched removed plumbing (e.g.,
      `aeat init`-style env_writer fixtures): update the fixture to
      seed `WorkflowState` directly, matching the pattern R12 used
      to fix the deadlines / filing CLI tests
  - Acceptance gates:
    - `pytest src/aeat/entrypoints/cli/test_workflow_surface.py` zero failures
    - `pytest src/aeat/application/test_config_parity.py` zero failures
    - Tests targeting deleted surfaces are gone; tests targeting
      surviving surfaces verify the new invocation paths
  - Does NOT: delete tests that catch genuine product bugs (e.g.,
    `test_user_help_surfaces_do_not_leak_translation_keys` is correctly
    catching the N2 leak; closing C2 will make it pass without test
    modification)

- C6 — Final verification sweep
  - Files owned: none (verification only — write a step record under
    `.vault/exec/2026-05-12-schema-driven-wizard-closure/` documenting
    gate results)
  - Run every gate the second-loop reviewer cited:
    - `aeat --help` shows exactly two subgroups: `config` and `app`
    - `aeat app archive --help` and `aeat app topic --help` render
      translated text in every locale
    - `audit_cli_translations()` returns `()`
    - `pytest src/aeat/application/wizard/ src/aeat/application/ src/aeat/entrypoints/cli/ -q` green for every wizard- and
      revision-owned surface; pre-existing failures unrelated to
      this work are flagged but not fixed
    - `grep -rn 'aeat archive\b\|aeat topic\b\|aeat help <\?slug' src/aeat/` returns nothing
    - `grep -rn 'historically\|legacy\|previously\|formerly\|replaces\|UX-[0-9]' src/aeat/application/ src/aeat/domain/ src/aeat/entrypoints/` returns nothing meaningful (skip-list for legitimate "legal references" if any)
    - `vault check all` shows zero new findings attributed to this
      closure
  - Acceptance gate: every check above passes
  - Does NOT: introduce new code

## Off-limits worktree state

Concurrent agents are working on the renta-pipeline and CLI-workflow-
redesign streams. Files staged by those agents (per `git status --short`)
must not be touched. Re-run `git status --short` at the start of each
Step to refresh the exclusion list.

The executor must stage every file by explicit path, never recursively
or by glob.

## Commit discipline

- One C-step → one commit (no bundled multi-step commits)
- Commit subject style: imperative, no dates, no C-markers in the
  subject line, no phase language. The C<n> identifier may appear in
  the commit body for traceability but never in any `.py` file
- Never bypass pre-commit hooks. If prek auto-fixes a file the Step
  owns, re-stage and re-commit
- Branch is `chore/eliminate-shims`. Do not switch. Do not push

## Parallelization

No intra-closure parallelism — C2 unblocks C6 verification, C5 has
the largest scope and benefits from C4 landing first (so the
`aeat --help` assertions are stable). C-step ordering is the hard
sequence.

## Verification

Mission success when every gate in C6 passes plus every finding the
second-loop reviewer flagged is closed. The reviewer's findings list
is the authoritative checklist; this plan is the work order.

Final outcome: the wizard slice and its revision both pass a third-loop
review with verdict ACCEPT. The deleted-command-surface test
regressions are resolved at their source (test files updated or
removed) rather than deferred with an inaccurate "pre-existing" label.
