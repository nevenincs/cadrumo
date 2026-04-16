---
tags:
  - '#research'
  - '#live-submit-safety-sweep'
date: '2026-04-16'
related:
  - '[[2026-04-16-live-write-static-audit-reference]]'
  - '[[2026-04-16-live-write-static-audit]]'
  - '[[2026-04-12-submission-engine-adr]]'
  - '[[2026-04-12-workflow-engine-adr]]'
  - '[[2026-04-13-filing-complementaria-adr]]'
  - '[[2026-04-13-cohesive-project-roadmap]]'
  - '[[2026-04-16-live-write-test-audit-research]]'
  - '[[2026-04-16-live-write-test-audit-adr]]'
---

# `live-submit-safety-sweep` research: `issue-117-contract-migration`

This research grounds the live-submit safety sweep as the implementation pass for
issue `#117`, using the already-landed static audit evidence to close the
production gaps filed as `#142` through `#146` without reopening the scope of
issue `#118`.

## Findings

- Charter rules `R2` through `R6` define a stricter live-write boundary than the
  current code implements. The target contract is explicit live intent via
  required `dry_run`, a distinct `AEAT_LIVE_SUBMIT_ENABLED` gate, a blocking
  human confirmation phrase, a hard pytest refusal, and an append-only audit log.
- Issue `#117` further tightens `R2` by requiring `dry_run` to be a required
  keyword-only control. This turns omission into a call-time failure instead of a
  permissive default.
- The current submission boundary still encodes the superseded
  `override_confirmation` plus `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION`
  contract in `aeat.submission`, `aeat.workflow`, and the complementaria CLI.
- The existing static audit already establishes that the missing pieces are not
  isolated defects. The gap spans engine, config, CLI, and workflow forwarding
  surfaces, so the sweep should be treated as one contract migration rather than
  five unrelated edits.
- The required confirmation phrase is `CONFIRMO FILING {modelo} {period}`. The
  confirmation path also needs draft checksum output and must be structurally
  unreachable from pytest-time import or patch surfaces.
- Production must refuse live writes whenever `PYTEST_CURRENT_TEST` is present,
  even if env vars leak into the process. This is a belt-and-braces control on
  top of the env gate, not a substitute for it.
- The append-only log at `.aeat/live-submit-audit.log` is mandatory for live
  writes. Issue `#117` also raises whether dry-run attempts should enter the same
  log; that should be recorded as an ADR decision rather than left implicit.
- The old submission and workflow ADRs are still valuable context, but their
  approved live-write contract is now stale. The new ADR will need to record that
  it supersedes the old `override_confirmation` and
  `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION` boundary.
- The current worktree’s `aeat submission submit` live path is synthetic because
  it runs through `_NullSession`. That means issue `#146` is not only a gating
  problem; it is also an operator-trust problem because the CLI currently reports
  authoritative live success without a real AEAT transport.
- Existing tests under `aeat.submission`, `aeat.workflow`, and `aeat.cli.submission`
  lock in the superseded contract. The sweep therefore needs contract-migration
  tests for the new refusal paths, but broader test-quality debt from `#150` and
  `#151` remains a separate track.

## Scope boundaries

- In scope: aligning submission, workflow, configuration, and CLI entry points
  with the live-submit safety contract required by `#117`.
- In scope: resolving the audited production gaps tracked as `#142` through
  `#146`.
- In scope: making the new ADR explicitly supersede the legacy
  `override_confirmation` plus `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION`
  boundary.
- Out of scope: re-running the one-shot static audit from `#118`.
- Out of scope: broader submission-boundary test cleanup tracked as `#150` and
  `#151`.
- Out of scope: unrelated feature work outside the AEAT live-write boundary.

## Implementation constraints

- The submission-engine contract appears to be the dependency root. Workflow
  protocol, adapter, and engine surfaces should inherit that contract rather than
  redefine it independently.
- Configuration and `env/.env.example` changes must land atomically with
  `tests/test_config.py` because that test enforces an exact declared env
  contract.
- CLI entrypoints should be updated together after the core contract is stable
  because the current live gating is duplicated across submission, filing, and
  workflow commands.
- A lower-risk sequencing is to resolve the `_NullSession` live-submit hazard
  before adding richer confirmation UX to the CLI, otherwise the operator-facing
  path still advertises a fake live submission.
- The confirmation module must be structurally unreachable from pytest, not
  merely documented as private.

## Synthesis

The sweep is a contract-correction effort rather than a greenfield design. The
repository already has an audited diagnosis: live-submit safety is fragmented
across config, engine, workflow, and CLI layers, and each layer still reflects
the older override-based confirmation model. The implementation target is a
single hardened live-write boundary centered on explicit live intent, a distinct
live-submit env gate, non-bypassable human confirmation, hard pytest refusal,
and append-only audit logging.
