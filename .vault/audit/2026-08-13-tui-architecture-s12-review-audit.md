---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:bd33ddcdce7b7e4ab086b85b0ef93705bed251de360f91d3dad7e169db01c6cb'
related: []
---

# `tui-architecture` audit: `s12 review`

## Scope

Independent review of `W01.P02.S12`, limited to the public-facade conformance tests, their S06-S11 production contracts, and the recorded focused gates. Semantic discovery preceded targeted source inspection.

## Findings

### state-axis-proof | high | The test proves only one lifecycle row crossed with the effect enum

`test_lifecycle_and_effect_axes_remain_independently_representable` fixes lifecycle to `RUNNING` and varies only effect. It cannot detect coupling or exclusions affecting the other lifecycle values, terminal-condition presence, or the lifecycle/terminal/effect relationship. This is effect enumeration, not broad proof that the declared state axes remain independent.

### response-binding-proof | high | The response mutation tests digest syntax rather than exact D4 binding

The accepted response contains the D4 fields, but the sole mutation changes `baseline_digest` to a value containing `g`. Rejection follows the hexadecimal field constraint even without correlation or exact-binding behavior. No valid-but-wrong mutation is made to operation identity, interaction identity, revision, token, continuation digest, reviewed proposal digest, baseline digest, proposed-effect digest, actor, or response time, so the test is insensitive to loss of the claimed tuple binding.

### capability-matrix | medium | Only one forbidden capability combination is exercised

The capability test covers recorded durability with omitted conflict scope. It does not exercise the other independent fail-closed combinations owned by the public capability contract, including ephemeral effect/replay/conflict restrictions, resumability/replay agreement, owned-resource cancellation, cooperative deadline cancellability, enforced deadline containment/resource ownership, and request-cancel support.

### event-redaction | low | The requested unsafe diagnostic families are exercised through the public API

The NIF, bearer-token, URL/query, and exception-like cases are genuine production-boundary refusals and do not mirror the validator. This portion is adequate, although the overall step remains blocked by the higher-severity proof gaps.

## Recommendations

- Replace the single-row state test with broad cross-axis cases that fail if any lifecycle is coupled to effect, and explicitly cover terminal-condition presence rules.
- Mutate every D4 correlation member to a different, individually valid value and assert the production binding boundary refuses it; lexical validation is not correlation proof.
- Add one production-boundary refusal for each independent forbidden capability family.
- Rerun the exact focused pytest, Ruff, and basedpyright gates after remediation and record current output.

## Re-review

### state-axis-proof-remediation | high | Expanded cases still do not prove broad lifecycle independence

The remediation adds terminal `FAILED` crossed with every effect plus two invalid-correlation refusals. That usefully covers terminal/effect independence, but all nonterminal acceptance remains fixed to `RUNNING`; the other declared lifecycle values are never constructed. A coupling or accidental refusal affecting queued, waiting-for-input, waiting-for-approval, cancelling, or settling would remain invisible. The original HIGH finding remains open.

### response-binding-ownership | low | Tuple preservation is the correct type-foundation proof before S22

The plan assigns response consumption to `W02.P05.S22`, and D4 requires the consuming authority to refuse stale, duplicate, mismatched, and expired responses. No expected interaction or token state exists in the S06-S11 type foundation against which a valid-but-wrong response could be compared. The new immutable full-tuple round trip proves the S10/S12 responsibility without inventing a premature comparator; the original response-binding HIGH is closed, with behavioral correlation still obligatorily owned by S22.

### capability-matrix-remediation | medium | Several claimed validator families are masked by earlier failures

The expanded table reaches many validators, but it does not independently prove every family. The ephemeral mutations retain replay `IDEMPOTENT_SUBMIT`, so replay refusal occurs before the durable conflict-scope check; no mutation independently reaches the ephemeral conflict-scope branch. Likewise there is no independently valid ephemeral declaration mutated only to a non-`NONE` effect, and the unsupported-cancellation case simultaneously violates cooperative-deadline and request-cancel rules. The table's claim of one planted declaration per independent family is therefore not established. The original MEDIUM remains open.

### gate-evidence-remediation | low | Recorded focused gates are current but cannot close uncovered branches

The execution record reports 23 focused tests passing plus clean Ruff and basedpyright. These gates are credible for the exercised paths, but green execution does not supply the missing mutation sensitivity above.

## Final re-review

### state-axis-proof-closure | low | Full declared state matrices close the HIGH finding

Every nonterminal lifecycle is now crossed with every effect, and every terminal condition is crossed with every effect using the production snapshot and receipt models. The independent invalid-correlation cases remain. This detects lifecycle/effect coupling across the complete closed enums and closes the state-axis HIGH.

### capability-matrix-closure | low | Valid-base one-field mutations close the MEDIUM finding

Each mutation begins from a production-valid declaration and changes one field. Together the cases reach empty effects; ephemeral replay, conflict, and effect restrictions; resumability symmetry; durable conflict scope; contained-resource ownership; cooperative-deadline cancellability; enforced-deadline containment; and request-cancel support. This removes the prior masking and closes the capability MEDIUM.

### final-gates | low | Exact focused evidence is complete

The execution record reports 69 focused tests passing, Ruff clean, and basedpyright with zero errors, warnings, or notes. The tests use the public production facade and introduce no mocks, fakes, patches, mirrored validators, skips, or expected failures.

Final verdict: PASS. No CRITICAL, HIGH, or MEDIUM findings remain.
