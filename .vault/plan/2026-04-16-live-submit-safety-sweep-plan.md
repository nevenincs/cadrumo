---
tags:
  - '#plan'
  - '#live-submit-safety-sweep'
date: '2026-04-16'
related:
  - '[[2026-04-16-live-submit-safety-sweep-research]]'
  - '[[2026-04-16-live-submit-safety-sweep-reference]]'
  - '[[2026-04-16-live-submit-safety-sweep-adr]]'
  - '[[2026-04-16-live-submit-safety-sweep-adr-review]]'
---

# `live-submit-safety-sweep` `phase-1` plan

Implement the approved live-submit safety sweep by replacing the stale
override-based live-write contract with explicit live intent, ordered refusal
gates, internal confirmation, append-only audit logging, and CLI behavior that
refuses unsupported live execution instead of simulating it.

## Proposed Changes

- Replace the legacy live-submit configuration contract with a single
  `AEAT_LIVE_SUBMIT_ENABLED` gate and standardized typed refusal errors.
- Add internal `_confirm.py` and `_audit.py` modules and wire them into the
  submission engine as the ordered live gate path before any live dispatch.
- Update submission and workflow protocol boundaries so live-capable APIs require
  explicit keyword-only `dry_run` and no longer infer execution mode.
- Tighten CLI submission and filing entry points to require explicit mode
  selection, reject `_NullSession`-backed `--live`, and expose `aeat submission
  audit-log`.
- Refresh configuration coverage and focused unit tests so the new refusal,
  confirmation, audit, and mode-selection contract is verified end to end.
- Capture execution artifacts and final review evidence for the sweep without
  pulling broader cleanup from `#150` or `#151` into scope.

## Tasks

- `Phase 1: replace the live-submit contract`
  1. Remove the old live-submit config/env assumptions from the engine and
     callers.
  2. Standardize on `AEAT_LIVE_SUBMIT_ENABLED` and new typed refusal errors.
- `Phase 2: add engine-side safety gates`
  1. Introduce `_confirm.py` for exact-phrase live confirmation.
  2. Introduce `_audit.py` for append-only attempt logging.
  3. Wire pytest refusal, env gating, confirmation, audit, and dispatch into one
     ordered engine path.
- `Phase 3: make execution mode explicit`
  1. Update submission and workflow APIs so `dry_run` is required and explicit.
  2. Rewrite protocol, adapter, engine, and CLI call sites to propagate
     `dry_run=` deliberately.
- `Phase 4: tighten CLI behavior`
  1. Require explicit `--dry-run` or `--live` on live-sensitive submission
     surfaces.
  2. Refuse `--live` when the runtime is backed by `_NullSession`.
  3. Add `aeat submission audit-log` for audit inspection.
- `Phase 5: verify and publish`
  1. Refresh config and unit-test coverage for refusal paths, ordered gates,
     audit logging, and CLI behavior.
  2. Record execution artifacts, complete local review, and prepare the PR.

## Parallelization

- The config and typed-error migration can proceed in parallel with the initial
  CLI surface rewrite as long as both converge on the same explicit live-mode
  contract.
- `_confirm.py` and `_audit.py` can be implemented in parallel before engine
  integration.
- Workflow protocol changes can proceed in parallel with engine call-site
  rewrites once the required `dry_run` contract is fixed.
- Test updates should begin after the public contract stabilizes so assertions
  target the final refusal and audit behavior rather than temporary
  intermediate states.

## Verification

- Live submission is refused unless `AEAT_LIVE_SUBMIT_ENABLED` is explicitly set
  and every ordered engine gate passes.
- Pytest-time live-write attempts fail closed with the typed refusal error even
  if other env vars are present.
- Submission and workflow live-capable APIs require explicit keyword-only
  `dry_run` and no longer preserve implicit defaults or override-confirmation
  shims.
- CLI submit surfaces require explicit mode selection, refuse `_NullSession`
  `--live`, and expose a functioning `aeat submission audit-log` command.
- Configuration and focused unit tests align with the new environment and
  refusal contract.
- Final execution artifacts show compliance with the approved ADR without
  expanding scope into `#150` or `#151`.

## Explicit Plan Review

- **Scope check:** limited to `aeat.submission`, `aeat.workflow`, affected CLI
  entry points, configuration/env alignment, focused unit tests, and `.vault/`
  execution artifacts for `#142` through `#146`.
- **Regression check:** the plan removes stale compatibility paths rather than
  layering new write surfaces on top of them, which reduces live-write drift and
  keeps unsupported CLI live execution fail-closed.
- **Approval check:** the user explicitly instructed autonomous execution
  without a human approval pause, so this plan is approved for immediate
  execution.
