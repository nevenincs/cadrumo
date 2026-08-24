---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:158e04089f802ac6f270fb76a2f7674c03fac7ef27440d7f30b15b19d9003c99'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-architecture-censo-operation-authority-reconciliation-research]]"
  - "[[2026-08-11-tui-architecture-W03-P06-S31]]"
---

# `tui-architecture` audit: `S31 exact reviewed apply review`

## Scope

Formal review of `W03.P06.S31` against the amended TUI architecture decision,
the censo authority reconciliation research, and the exact reviewed operand
introduced by `W03.P06.S30`. The review traced the reviewed-proposal path from
strict operand rehydration through baseline comparison, ADOPT/PRESERVE effect
derivation, schema validation, repository compare-and-swap, and authenticated
event publication. It also checked that the pre-existing direct certificate
reconciliation mode remains explicitly disjoint rather than becoming an
alternate reviewed-proposal writer.

Evidence included the production diff, all call sites, the canonical profile
repository command, and real encrypted-repository tests. Focused execution
passed 10 integration tests covering operand integrity, exact effects, stale
revision and digest refusal, tamper refusal, legacy schema judgement, and event
history. Focused Ruff and BasedPyright gates passed with zero diagnostics.

## Findings

### s31-exact-apply-review | medium | Profile-identity and mode-exclusivity refusals lack real regression proofs

Production code compares the reviewed baseline's profile identity, revision,
and content digest before deriving effects, and rejects a reviewed proposal
combined with either direct-effect argument. The real repository suite proves
revision and digest staleness plus digest tampering, but does not exercise a
foreign `profile_id` baseline or either invalid mixed/partial mode call. These
are important fail-closed branches: the current implementation is correct by
inspection, but a future regression could weaken exact-baseline identity or
reintroduce parallel-mode ambiguity without failing the focused suite.

### s31-exact-apply-review | resolved | Profile-identity and mode-exclusivity proofs added

Resolved on 2026-08-24. The real encrypted-repository suite now submits an
otherwise valid operand bound to a foreign profile identity, both reviewed-plus-
direct combinations, each incomplete direct combination, and the empty direct
call. Every case asserts that the profile record and authenticated event history
remain exactly unchanged after refusal. The focused set now passes 16 integration
tests; isolated-environment BasedPyright reports zero diagnostics and Ruff is
clean for the production and review-test surfaces.

## Recommendations

Add real encrypted-repository tests that submit an otherwise self-consistent
operand bound to a different profile identity and assert record and
authenticated-history stability. Add focused contract tests for reviewed plus
direct arguments and incomplete direct arguments, asserting refusal before
repository publication. No production redesign or additional writer is needed.

Close verdict: approved with one medium test-integrity follow-up. No critical or
high findings remain. The reviewed path has one canonical writer and one CAS
publication, verifies the operand digest by strict rehydration, compares the
complete baseline before effect derivation, derives only frozen ADOPT/PRESERVE
intents, and publishes exactly one `CENSO_APPLIED` event on success while the
tested stale and tamper paths publish none.

Final reattestation: approved and closed. The medium finding is resolved; no
critical, high, medium, or low findings remain in `W03.P06.S31`.
