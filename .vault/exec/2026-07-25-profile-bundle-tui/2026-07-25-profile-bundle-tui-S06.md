---
tags:
  - '#exec'
  - '#profile-bundle-tui'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S06'
related:
  - "[[2026-07-25-profile-bundle-tui-plan]]"
---

# Refuse non-interactive under-specified invocations with typed suggestion-carrying errors rather than prompting or defaulting, verified by a headless regression that fails on timeout rather than exercising the helper in isolation

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Refuse an export missing its destination, an export missing its transport, and an import missing its path with typed boundary refusals rather than prompting or silently defaulting.
- Carry a runnable command string as the suggestion on each refusal so the operator is told the exact invocation that would have worked.
- Route every refusal through the typed error document on the shared envelope spine rather than a bespoke result field.
- Prove the refusals by driving the real verbs headlessly and asserting the envelope structurally.

## Outcome

Landed in commits `807d163bbb` and `a092c1378b`. This pass verified the step rather than re-implementing it.

Both refusal proofs drive the real CLI verb end to end rather than exercising a helper in isolation: each invokes the actual command through the CLI runner, whose stdin is not a TTY, so the capability probe classifies the host non-interactive, no flow launches, and the command refuses. Assertions are structural throughout — exit code 2, envelope status, command identifier, error category, error code, and the literal suggestion command string — and never the localized message prose.

The runs are genuine verifications, not the empty-selection trap: `uv run --no-sync pytest src/cadrumo/entrypoints/cli/_config/tests/test_profile_bundle_flow.py -m integration -p no:randomly -n0` collected and passed 13 tests, a confirmed non-zero count under the correct marker.

The timeout requirement is satisfied structurally: the suite carries a 300-second per-test timeout, so a regression in which an under-specified non-interactive invocation launched a flow and blocked waiting for input fails the test rather than hanging the run. The companion console-less passphrase regression recorded under `S05` carries its own explicit 90-second wait and fails the test on expiry.

## Notes

The wider CLI conformance gate showed one unrelated failure, an uncommitted peer-owned modelo-390 documentation sequence file, attributed and left untouched as live peer work rather than absorbed or edited. The repository-wide locale translation-honesty ratchet is separately red on peer-owned manager-flow keys committed before this pass began; this feature's keys carry a real translation in all four catalogues and appear nowhere in that failure.
