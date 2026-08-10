---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:98546d9b859749acbfb3b4fe81a850d5702670b92b4162e7493c70113ae9e79c'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S21 typed workflow persistence and locale neutrality`

## Scope

Independent fresh-current review of `W04.P06.S21`: the closed workflow detail
union, abstract locale-key identity, canonical application-owned precondition
verdicts, encrypted workflow-run persistence, exact v2 refusal, and the direct
model and persistence tests. Engine emission and CLI/locales are excluded: they
belong to S22 and S23 respectively. The S21 change set does not modify either
surface; separately owned uncommitted engine work was present in the shared
worktree and was not attributed to S21.

## Findings

### terminal-verdict | critical | Remediated missing outcome on operational aborts

An intermediate model revision allowed an aborted result to end with a failed
step that had no `PreconditionVerdict`. That violated the action-or-explicit-
no-recovery terminal invariant. The final model rejects that shape, while the
operational-failure roundtrip now carries `NoRecoveryOutcome.TERMINAL` with a
stable error code and factual evidence.

### prose-evidence | high | Remediated compact exception prose in persisted evidence

The initial workflow-specific evidence guard rejected only strings containing
whitespace, so `failure_reason=RuntimeError:boom` remained persistable. The
final boundary rejects prose-shaped evidence keys, rendered strings, and
class-name-colon exception text while retaining stable locale-neutral facts.

No findings remain open. Direct no-write probes confirmed both remediations.

The direct model and encrypted-persistence suite passed 35 tests. Ruff lint and
format checks passed for all six S21 files, and BasedPyright reported zero
errors and warnings for the five workflow implementation and test files. The
namespace registry has a pre-existing private-import type diagnostic outside
this step's version-only change, so it was not attributed to S21.

## Recommendations

The S21 contract is review-clean. Keep the direct encrypted roundtrip,
current-version load-and-list refusal, structural locale digest, and terminal
no-recovery roundtrip tests as the durable boundary proof. Keep the integrated
plan row open while S22 migrates every engine producer to the closed records and
verdicts and S23 consumes those records without restoring string-equality
rendering or compatibility maps.
