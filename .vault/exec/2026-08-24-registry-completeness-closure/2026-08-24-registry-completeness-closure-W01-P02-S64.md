---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0008bbe6c92259ffee0c0cd605f2f8728c0a39fccf3ec4a1297a1b44dd522d83'
step_id: 'S64'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Remove fabricated strict proof authorities and digests from closure CLI tests, exercise the actual CLI with canonical live loaders and real evidence only, prove live-versus-offline refusal distinctions, keep eligibility unreachable until durable filing proof exists, prevent injected claims from bypassing the gate, and add a mutation bite rejecting canned proof

## Scope

- `dev/registry/conformance/`
- `dev/source_connectivity/`
- `dev/registry/`
- `src/cadrumo/application/registry/`

## Description

- Remove the CLI context injection branch that accepted structurally valid but
  unverified proof authorities.
- Delete fabricated strict authorities, repeated-character digests, and the
  pre-authorized success emitter test.
- Exercise the actual command through canonical live and explicit offline
  loaders, retaining distinct refusal details.
- Prove a precomposed eligible context claim cannot bypass canonical
  composition, and bite that gate with a temporary production mutation.

## Outcome

The shipped command can no longer be made eligible through Typer context
injection. Live execution uses the bundled validated registry, canonical live
source authority, and canonical live filing authority; because the latter has
no durable filing proof entries, the release predicate remains honestly false.
Offline execution remains a separately identifiable no-authority refusal.

## Notes

Scoped evidence: `ruff check` passed for both owned Python files; sequential
`pytest` passed 7 tests in 33.57 seconds; `git diff --check` passed. The mutation
run failed exactly at `test_actual_cli_ignores_a_precomposed_eligible_context_claim`,
showing exit 0 and a satisfied canned row, then the restored run passed with
exit 1. No fake authority, digest, success evidence, or production mutation
remains in the tree. No broad suite was run because the shared worktree carries
unrelated concurrent changes.
