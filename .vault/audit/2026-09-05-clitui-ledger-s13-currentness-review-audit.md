---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_hash: 'sha256:aaa828eb701319213b623d579075e8faf33fd38d128935a8add02ba8836f57b9'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-09-04-clitui-ledger-W01-P04-S13]]"
---

# `clitui-ledger` audit: `S13 fail-closed currentness`

## Scope

Reviewed `LedgerUnionReviewSnapshotV1`, all matrix/attestation/receipt/anchor
bindings that consume it, `reopened_gates_for_currentness`, direct and ordered
gate evaluation, S13's tests, execution record, reference and plan state, and
commits `4fa7649ae4`, `d7c135db90`, and `087c6ac735`. Vaultspec-RAG was used
first, but the local code index again reported zero indexed code sections;
whole-file reads, exact searches, independent remint scripts, and focused/full
execution therefore supplied the code evidence.

## Findings

**Ruling: NOT ACCEPTED.** Two HIGH quality-gate findings remain.

The production contract is directionally sound. A gate boundary requires a
fresh `LedgerUnionDenominatorV1`; missing live union state explicitly enters
the common reopening blockers. `LedgerUnionReviewSnapshotV1.from_union`
revalidates serialized union data and projects the outer union digest,
aggregate row-review digest, row-review-attestation digest, reviewed count,
review revision, review identity, and review time. Accepted/current matrix
bases, the acceptance attestation, every receipt basis, and the external
acceptance anchor all bind that projection. Consequently the existing schema-v4
union validators carry semantic home, effect, all applicability/proof fields,
primary/secondary gaps, blockers/action, TUI route/hold, artifact and registry
disposition, observation membership, seven-stream source digests, review
coverage, and all dependent digests into currentness evaluation.

An independent fully self-consistent exercise created a different but valid
union by advancing the row-review time and recomputing its attestation and
outer digest. Both accepted and current matrix snapshots, the matrix
attestation, and the full G0--G3 receipt chain were then reminted to that valid
union. With the prior external anchor all five gates reopened; with a matching
new external anchor currentness was clean. Supplying no live union reopened all
five gates. This confirms the implementation can enforce the intended
noncircular lifecycle, but its committed acceptance suite does not yet prove
that boundary and is not green.

### full-matrix-regression | high | The required complete module has ten failures

The executor recorded only the seven new focused cases. Those seven pass, but
the mandatory full module finishes **10 failed, 274 passed**. The failures are:

- `test_erasing_initial_cli_ownership_reopens_g0_even_when_current_rows_look_clean`;
- `test_g0_rejects_a_model_copy_with_an_empty_reviewer_deterministically`;
- `test_generic_review_coordinate_cannot_substitute_for_a_missing_or_invalid_attestation[missing]`;
- `test_g4_requires_an_external_acceptance_record_for_an_accepted_g3_receipt`;
- `test_g4_refuses_a_fully_recomputed_attestation_time_remint_against_the_external_anchor`;
- all four cases of
  `test_g4_refuses_missing_stale_or_rebound_external_acceptance_authority`;
- `test_ordered_evaluation_never_allows_a_later_gate_to_close`.

Several direct G4 and ordered-evaluation tests omit the newly mandatory live
union and now receive `live reviewed union observation is missing` in addition
to, or before, the behavior they were written to isolate. The ordered evaluator
now supplies common currentness blockers to every gate, contradicting older
assertions that later gates receive only the earlier-gate blocker. Separately,
the `_evaluate` test helper eagerly constructs an acceptance anchor before the
production boundary can revalidate the matrix; malformed or missing
attestations therefore raise `ValidationError`/`AttributeError` in fixture code
instead of producing deterministic fail-closed gate blockers. These are real
acceptance-suite regressions, not an unrelated environment failure.

Update direct calls to supply the live union when union currentness is not the
subject, decide and consistently test whether ordered later gates retain common
currentness detail or only the earlier-gate blocker, and make invalid-matrix
tests reach the production canonicalization boundary without attempting to
construct an anchor from invalid state. The complete module must pass before
S13 can close.

### currentness-detector-teeth-are-incomplete | high | Core absence and remint paths are not isolated durably

No test supplies `observed_union=None` and asserts that both
`reopened_gates_for_currentness` and gate evaluation relock G0 through G4. The
`_evaluate` helper uses `None` to mean "substitute the live fixture", so it
cannot express the missing-union case. Removing the explicit missing-union
blocker would leave all seven new focused tests green.

The test named
`test_a_fully_reminted_union_and_receipt_chain_cannot_replace_the_external_anchor`
also changes only `current_union_review`; `accepted_union_review` remains the
old snapshot and the supplied live union is the old union. It therefore passes
through accepted/current union drift and live/current drift before external
anchor binding is necessary. It does not demonstrate that the anchor rejects a
self-consistent new union acceptance.

Add a distinct sentinel/default in the helper and durable missing-live-union
cases for reopening plus direct/ordered evaluation. Add the valid-union remint
used in this review: recompute a complete union review and digest, set both
accepted and current snapshots to it, remint the matrix attestation and all
receipts, supply that same valid union live, and prove the unchanged external
anchor alone relocks every gate. Then prove a matching independently observed
new anchor restores the valid lifecycle. This supplies both normal-path and
representative-defect teeth at the owning boundary.

## Verification and state

- New S13 focused lane: 7 passed, 277 deselected.
- Complete matrix module: 10 failed, 274 passed in 447.26 seconds.
- Ruff format/check: passed.
- Scoped `ty`: passed.
- Scoped `basedpyright`: zero errors, warnings, or notes.
- Plan check and complete `clitui-ledger` Vault feature check: passed.

S13's plan checkbox is correctly **unchecked** while this mandatory review is
not accepted; S14 remains next only after remediation and acceptance. G0
remains OPEN. The reviewed S13 commits change development quality contracts,
tests, reachability classification, and Vault records only; they do not modify
Ledger product or production TUI code.
