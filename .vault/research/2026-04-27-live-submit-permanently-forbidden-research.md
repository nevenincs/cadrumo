---
tags:
  - '#research'
  - '#live-submit-permanently-forbidden'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-security-storage-audit-audit]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
  - "[[2026-04-25-workflow-live-flag-excision-adr]]"
---

# `live-submit-permanently-forbidden` research: `issue-432-live-aeat-submission-permanently-forbidden`

Researched issue `#432` against the current branch state, the security audit,
the historical live-submit ADR set, the CLI/doc surfaces, and the remaining
submission/auth/runtime code to determine the correct enforcement strategy for
permanently forbidding live AEAT writes.

The requested source `.vaultspec/rules/rules/aeat-project-mandates.md` was not
present in this worktree at audit time. The implementation therefore needs to
create that source before regenerating provider copies.

## Findings

### Direct answer

- The product direction is `produce -> verify -> export`. Kent uploads the
  exported fichero himself in the AEAT portal. Live AEAT submission is not a
  deferred milestone and not a hidden opt-in capability.
- The safest issue-`#432` strategy is:
  1. excise every reachable live transport branch from `SubmissionEngine`,
  1. convert the historical write gate into a permanent-deny stub,
  1. remove live-submit env vars from `Settings` and `env/.env.example`,
  1. rewrite docs and charter surfaces so no future-facing live-submit story
     remains.
- A permanent-deny error at the engine boundary is still required even after
  transport excision. That preserves a typed refusal for any legacy caller that
  attempts `dry_run=False` or passes the removed live-transport opt-in keyword.
- The four-factor live gate should not survive as the current policy model. It
  is superseded history. The current policy is simpler and stricter: live AEAT
  submission is permanently forbidden.

### Current branch-state code facts

- `SubmissionEngine` is now dry-run-only. `dry_run=False` raises
  `LiveSubmitForbiddenError` before any submitter dispatch.
- The constructor no longer exposes a supported live transport toggle. Legacy
  callers that pass the removed live-transport enablement keyword receive
  `LiveSubmitForbiddenError`.
- `Modelo130Submitter.submit()` now raises `LiveSubmitForbiddenError` before any
  browser action.
- `AeatAccessGate.require_live_write()` is now a compatibility shim that always
  raises `LiveSubmitForbiddenError`.
- `Settings` no longer exposes `AEAT_LIVE_SUBMIT_ENABLED` or
  `AEAT_ALLOW_LIVE_SUBMIT_OPT_IN`.
- `aeat filing complementaria submit` no longer accepts `--live`; amendment
  submission is dry-run-only.
- `src/aeat/adapters/outbound/aeat/export/test_live_submit_permanently_forbidden.py` now pins the
  permanent prohibition through constructor, gate, settings, CLI, and source
  introspection assertions.

### Remaining historical or legacy surfaces

- `src/aeat/adapters/outbound/aeat/export/_confirm.py` still contains the old typed-confirmation
  helper. It is no longer on an executable product path.
- `src/aeat/adapters/outbound/aeat/export/_audit.py` still contains historical live-submit audit
  helpers targeting `.aeat/live-submit-audit.log`. They are no longer on an
  executable product path.
- `src/aeat/core/errors/_registry.py` and `docs/error-codes.md` still contain older
  live-submit-only registry entries alongside the new permanent-forbid code.
  They now describe legacy history rather than reachable product behavior.
- Historical workflow-refusal tests that assert the removed flags are still
  rejected remain valid because they defend the permanent prohibition.

### Security-audit findings consumed

- The security audit identified `.aeat/live-submit-audit.log` as an
  uncontrolled persistence surface outside governed storage roots. Issue `#432`
  addresses that by removing every reachable path that would append to it.
- The audit identified contradictory operator guidance around
  `AEAT_LIVE_SUBMIT_ENABLED`. Issue `#432` resolves that by removing the setting
  and its documentation entirely.
- The audit documented broader sensitive-data retention risks around browser
  traces and persisted artifacts. Keeping live-submit execution reachable would
  compound that risk; issue `#432` removes the executable write path instead.

### Why permanent prohibition is the correct architecture

- AEAT has no sandbox. A successful write is a real legal filing.
- The user's repeated product mandate is stronger than the older ADR lineage.
  Kent does not want the tool to file on his behalf.
- A future hidden-command or env-gated reintroduction path would keep the
  repository semantically drifting toward a product the user has explicitly
  rejected.
- The codebase already has mature dry-run, preflight, export, and verification
  surfaces. Those are the legitimate product features. Live submit is not
  required to close Kent's current workflow.

## Implementation recommendation

- Keep `LiveSubmitForbiddenError` as the single canonical write-side refusal.
- Remove all live-submit env-var fields from product configuration.
- Keep live-read gating separate: `AEAT_LIVE_TESTS_ENABLED` remains read-only.
- Rewrite roadmap, coverage, charter, and ADR surfaces into present-tense
  permanent-forbid language.
- Create the missing mandate source file under `.vaultspec/rules/rules/` and
  regenerate provider copies with `uv run vaultspec-core install --force`.
- Preserve historical ADRs and helper files only when they are clearly labeled
  as historical or legacy rather than current policy.
