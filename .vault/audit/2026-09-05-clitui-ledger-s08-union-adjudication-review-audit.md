---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:33eddea0638bbf7e7c0f4e38b52fa21611b8831b5e8fdb670da0bfe4e3697a33'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-09-04-clitui-ledger-W01-P02-S08]]"
---

# `clitui-ledger` audit: `S08 union adjudication review`

## Scope

Mandatory independent review of `W01.P02.S08`. The review traced the seven
accepted S04-S07 observation streams through `LedgerUnionDenominatorV1`, the
semantic-home/effect/applicability adjudication, source digests, canonical
framing, tests, reference, Step Record, plan, and feature index. No production
code was changed by the review.

The serialized mechanics reproduce: 760 raw observations with stream counts
78 CLI endpoints, 50 CLI suboperations, 63 backend operations, 10 missing
product observations, 546 registry routes, six artifact observations, and seven
TUI routes; 718 emitted rows; 546 distinct registry identities; eight backend
direct-proof blockers; registry blockers partitioned 510 direct, three sidecar,
and 33 destinationless; Overview installed and six TUI routes component-only.
Independent standard-library JSON/framing reconstruction yields
`sha256:5012ceafec5bc9dae942b22f48daa34f66d93008cd48b9f81c0b0f69f4f49b06`.
G0 correctly remains OPEN.

## Findings

### fail-open-adjudication | high | New observations receive invented semantic decisions instead of reopening S08

`_planned_owner` accepts any new identity under a broad prefix and
`_semantic_home_for` invents request/result names from that identity.
`_effect_for` likewise defaults unmatched identities to mutation. An
independent mutation appended a new CLI census entry with result identity
`ledger.transaction.future`; `build_ledger_union_denominator` silently emitted
761 observations and 719 rows with owner
`cadrumo.application.ledger.operator_commands`, command
`LedgerTransactionFutureCommand`, result `LedgerTransactionFutureResult`, and
mutation effect. It did not reject an unreviewed capability.

This contradicts the reference claim that exact per-row decisions make a newly
unmatched CLI identity fail. It also lets source refresh turn an addition into
apparently adjudicated applicability, gaps, blockers, and next action without
review. S08 needs an explicit, complete non-registry adjudication table keyed by
every admitted semantic identity. Registry rows may use their validated
structural projection. Unknown, removed, duplicate, or newly split identities
must fail closed. Durable tests must add a live CLI endpoint/suboperation,
backend declaration, missing product, artifact, and TUI selection and prove
rejection until an explicit decision is authored.

### heuristic-effect-errors | high | Query, mutation, proposal, and artifact effects are materially misclassified

Effects are inferred from substrings rather than adjudicated behavior. Every
`ledger.llm.*` identity becomes a proposal before query tokens are considered.
Consequently persistent `ledger.llm.apply`, `apply_saturated`, `apply_split`,
`apply_evidence_classification`, `reject`, and `review_decision` are proposals,
and `ledger.llm.diagnostics` is also a proposal rather than a query. CLI
`ledger.classify.llm_apply`, `llm_reject`, `llm_saturate_apply`, and
`llm_saturate_reject` have the same defect.

The token spelling also misses typed queries containing underscores. At least
`ledger.counterparty.resolve`, `ledger.evidence.attachment_queue`,
`ledger.evidence.attachment_view`, `ledger.evidence.consent_survey`,
`ledger.field_change.provenance`, `ledger.fx.provenance`,
`ledger.import.aggregate_results`, `ledger.import.normalization_provenance`,
`ledger.manual_override.provenance`, `ledger.transaction.review_query`,
`ledger.workspace.affected_declarations`, and `ledger.workspace.project` are
emitted as mutations despite their declared `*Query` contracts.
`ledger.evidence.download` is emitted as a mutation with no artifact
applicability, and `ledger.export.provenance` is emitted as an artifact despite
being a provenance query.

These errors alter applicability, provenance/composition/artifact gaps, proof
requirements, and generated command suffixes. Replace substring inference with
an explicit effect decision for every non-registry semantic row, with mutation
tests for all five effect classes and exact refusal on an unclassified row.

### false-existing-homes | high | Three claimed existing immutable request contracts do not match their live owners

The existing-home test checks only that the owner and type names coexist in a
module; it never checks the owner's signature. Live
`execute_reviewed_decision` does not accept `LlmReviewRequest`; it accepts loose
`suggestion`, `origin`, `decision`, and `bucket_id` business parameters. Live
`update_manual_transaction` requires `transaction_id` outside
`ManualLedgerTransactionCommand`. Live `update_manual_transaction_fields`
requires `bucket_id`, `transaction_id`, `actor`, and `source_command` outside
`ManualLedgerTransactionPatch`. These are exactly the loose invocation shapes
the declaration comment says should remain `planned`.

Therefore the published seven-existing/711-planned split and exact request
identity claim are false. On current evidence only flat export, source import,
transaction create, and review query bind a complete named request/query as the
business invocation; the three rows above require planned complete requests or
owner refactoring. Add signature-aware tests that resolve annotations and prove
the named request and result are the effective owner boundary, not merely
symbols in the same module.

### incomplete-semantic-joins | high | Known equivalent CLI and backend behaviors remain separate rows

The remap tables join only a subset of renamed cross-stream observations.
Obvious identical authorities remain duplicated: CLI `ledger.rule.add` versus
backend `ledger.classification.rule_add`; CLI rule-apply preview/commit versus
backend `ledger.classification.rule_apply`; CLI counterparty confirm/view/
withdraw versus backend record/resolve/forget; CLI export router/formats versus
backend `ledger.export.flat`; CLI manual/LLM split effects versus backend
transaction/LLM split operations; and CLI classify LLM preview/apply/reject,
saturation, IVA, evidence-read, and auto-split effects versus their
`ledger.llm.*` backend authorities.

The same omission is visible inside the emitted homes: `ledger.export` and
`ledger.export.flat` name the same `LedgerExportCommand`/
`LedgerExportResult`, but remain separate rows. The current 42-row net reduction
is also described imprecisely. There are 763 observation-to-row selections:
one missing-product observation splits into four rows (+3), while 42 rows carry
multiple observations and remove 45 duplicate selections, for a net reduction
of 42 from 760 observations to 718 rows. Calling that net solely 42 merges
hides the split and the actual 45 joined edges.

Author an explicit observation-to-semantic-row adjudication, including
one-to-many router/backend observations where effects differ. Prove every
intended merge by owner, request, result, effect, artifact, refusal, and
reachability identity; prove every split differs on at least one of those
dimensions. Recompute the denominator only after the missing joins and split
accounting are reviewed.

## Recommendations

- Reopen S08 and remove all prefix/token fallbacks from semantic ownership and
  effect adjudication. Unknown observations must stop the build.
- Correct the existing/planned homes against live callable signatures and add
  durable signature and source-addition detectors.
- Complete the cross-stream merge/split table, publish selection-edge math, and
  refresh all counts, source digests, union digest, reference, record, plan, and
  index before re-review.
- Preserve the accurate 546 registry identities, 510/3/33 blocker partition,
  eight backend proof gaps, TUI reachability split, and OPEN G0 state.

## Verification

The focused union lane passes nine tests with 182 deselected, and the full
matrix module passes all 191 tests. Ruff format/check, scoped `ty`,
basedpyright, and the feature Vault check pass. Green tests do not cover the
fail-open source addition, effect truth, live owner signatures, or missing
semantic joins above.
