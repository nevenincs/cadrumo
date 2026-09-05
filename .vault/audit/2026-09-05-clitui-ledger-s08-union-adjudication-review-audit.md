---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:2c478608fd1c48b00bdef919662bf959d49f18ab1fcd387f4cf9a74de313bdf8'
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

## Remediation review

**Ruling: NOT ACCEPTED.** The remediation closes the original effect-table,
typed-home-signature, and named merge/split defects, and it refuses a wholly
unknown semantic identity. Two HIGH defects remain in the adjudication
boundary.

The current projection was independently rebuilt as 760 observations and 769
selection edges, including four one-to-many observations and nine extra edges.
Fifty-nine final rows contain multiple observations, accounting for 76
duplicate selection edges and 693 final rows: 147 non-registry plus 546
registry routes. Stream counts are 78 CLI endpoints, 50 CLI suboperations, 63
backend operations, 10 missing-product declarations, 546 registry routes, six
artifacts, and seven TUI surfaces. The independent canonical serialization
reproduces
`sha256:77f310d3de86c3a097b5c976a8cdc4b1941b24e3e15d0eb47971985b38764dff`.
Semantic homes now report exactly four existing and 689 planned rows. Direct
signature mutations for a wrong request type, wrong result type, and an extra
required loose parameter are rejected.

The explicit effects correctly distinguish LLM proposals from apply, reject,
review, and saturation mutations; diagnostics and provenance reads are
queries; and evidence download is an artifact query. The reviewed joins now
coalesce rule add/apply/preview, counterparty record/resolve/forget, flat and
format exports, transaction and LLM split operations, and classify/LLM
suggest/apply/reject/saturation/evidence operations without crossing effect
classes.

### observation-adjudication-remains-fail-open | high | A new observation can silently join an existing semantic identity

`_selected_capabilities` still falls back to the observed identity when no
source-selection decision exists, while
`_validate_non_registry_decision_coverage` compares only the resulting set of
distinct semantic capability IDs. An independent mutation appended a unique
CLI endpoint observation whose result-schema identity was the already-known
`ledger.transaction.create`. The build accepted 761 observations and 770
selection edges while retaining 693 rows; only duplicate-selection edges rose
from 76 to 77. This is an unreviewed merge, not a newly adjudicated
observation. The pinned aggregate digest would drift, but refreshing that
digest could preserve the false merge, so source drift alone does not provide
detector teeth.

Replace the identity fallback with an exhaustive, stable observation-identity
to capability-tuple decision for every non-registry observation. Added,
removed, duplicated, or changed observation identities must fail closed until
their selection is explicitly authored. Add a durable mutation that appends a
new CLI endpoint with an existing result identity and requires refusal, with
equivalent coverage for the other non-registry streams whose observations can
be added independently.

### provenance-applicability-contradicts-the-adjudicated-rows | high | Provenance queries and artifact queries are marked not applicable

`_axis_decisions` derives provenance applicability from effect alone and omits
both `QUERY` and `ARTIFACT_QUERY`. Consequently
`ledger.export.provenance`, `ledger.field_change.provenance`,
`ledger.fx.provenance`, `ledger.import.normalization_provenance`, and
`ledger.manual_override.provenance` are correctly classified as queries and
carry a provenance gap, yet serialize the provenance axis as
`not_applicable`. `ledger.evidence.download` is correctly an artifact query
but is likewise provenance-not-applicable despite the contract that artifact
operations require provenance. The serialized validators reproduce this
derived contradiction rather than detecting it.

Author applicability per semantic row, or at minimum an explicit reviewed set
of provenance-bearing query identities. Mark the five provenance reads and
the evidence-download artifact query provenance-applicable, add exact semantic
assertions for them, and add a mutation proving that an incorrect applicability
decision is rejected independently of a refreshed aggregate digest.

The eight backend proof gaps, 510 canonical registry-bound plus three sidecar
plus 33 unresolved registry partition, installed Overview/six component-only
TUI posture, OPEN G0 gate, and implementation hold remain intact. Review of the
remediation commit scope found no production backend, CLI, or TUI edits.

## Remediation verification

- `uv run --no-sync pytest -q -n 0 dev/quality/tests/test_clitui_ledger_capability_matrix.py`: 201 passed.
- `uv run --no-sync ruff format --check ...` and scoped `ruff check`: passed.
- `uv run --no-sync ty check dev/quality/clitui_ledger_capability_matrix.py`: passed.
- `uv run --no-sync vaultspec-core vault check all --feature clitui-ledger`: passed before this audit append.
