---
generated: true
tags:
  - '#index'
  - '#ledger-evidence-atomicity'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:49b02911910279510d3b55cc33b7d93d48988f96d2f801d16b24137d29a9b750'
related:
  - '[[2026-07-17-ledger-evidence-atomicity-adr]]'
  - '[[2026-07-17-ledger-evidence-atomicity-audit]]'
  - '[[2026-07-17-ledger-evidence-atomicity-plan]]'
  - '[[2026-07-24-ledger-evidence-atomicity-close-honesty-review-audit]]'
---

# `ledger-evidence-atomicity` feature index

Auto-generated index of all documents tagged with `#ledger-evidence-atomicity`.

## Documents

### adr

- `2026-07-17-ledger-evidence-atomicity-adr` - `ledger-evidence-atomicity` adr: `ledger-evidence-atomicity rescope grounding` | (**status:** `accepted`)

### audit

- `2026-07-17-ledger-evidence-atomicity-audit` - `ledger-evidence-atomicity` audit: `ledger evidence durable-layer continuous-gate review`
- `2026-07-24-ledger-evidence-atomicity-close-honesty-review-audit` - `ledger-evidence-atomicity` audit: `Close honesty review`

### exec

- `2026-07-17-ledger-evidence-atomicity-P01-S01` - Make generic manual-field updates refuse all evidence fields, reserve evidence catalogue and provenance mutation for attach, and expose a single atomic invoice-only linkage writer
- `2026-07-17-ledger-evidence-atomicity-P01-S02` - Prove direct evidence patches fail, invoice linkage cannot mutate evidence, and failed attach or link leaves transaction, evidence catalogue, provenance, and event history unchanged
- `2026-07-17-ledger-evidence-atomicity-P01-S03` - Prove create-time and attach-time evidence validation enforce the same missing and cross-bucket policy
- `2026-07-17-ledger-evidence-atomicity-P02-S04` - Make evidence-driven LLM splitting persist the parent transition, every child, inherited validated evidence links, provenance, classifications, and events in one atomic application transaction without generic field patching
- `2026-07-17-ledger-evidence-atomicity-P02-S05` - Prove every LLM split child inherits the parent evidence and provenance consistently and any child validation or persistence failure leaves the parent, children, catalogue, and event history unchanged
- `2026-07-17-ledger-evidence-atomicity-P03-S06` - Remove EvidenceBundleService replay, its public export, and backend tests while preserving evidence check and unrelated observability replay facilities
- `2026-07-17-ledger-evidence-atomicity-P03-S07` - Restrict ledger link to invoice-only linkage, route it through the atomic application writer, and remove evidence-id and evidence-update result paths
- `2026-07-17-ledger-evidence-atomicity-P03-S08` - Remove modelo audit replay and every call to the backend replay method while retaining only genuine evidence audit check
- `2026-07-17-ledger-evidence-atomicity-P03-S09` - Prove attach remains the sole evidence mutation, invoice link is atomic and invoice-only, and link rejects every removed evidence grammar
- `2026-07-17-ledger-evidence-atomicity-P03-S10` - Prove modelo audit exposes check without replay, backend replay calls, replay result schemas, or synthetic replay events
- `2026-07-17-ledger-evidence-atomicity-P03-S16` - Move the one-evidence-writer guard from the wrapper to the transaction builder so the bulk-classify path cannot bypass the attach authority: the builder asserts the evidence set equals the current evidence unless the _evidence_authority marker is present, OR prove BULK_CLASSIFY_ALLOWED_COLUMNS never intersects the evidence fields, with a gate proving bulk-classify cannot mutate any evidence field outside attach
- `2026-07-17-ledger-evidence-atomicity-P03-S17` - Add an explicit id-stability assertion to split_transaction_with_classified_children that raises when a classified replacement child transaction_id diverges from the bare child it derives from, so a divergence cannot silently misattribute evidence and provenance, gated on a test proving the split raises on a mismatched replacement transaction_id rather than proceeding
- `2026-07-17-ledger-evidence-atomicity-P04-S11` - Remove replay-specific fields from every payload and schema projection
- `2026-07-17-ledger-evidence-atomicity-P04-S12` - Migrate the ledger evidence and audit family help and risk metadata to the accepted grammar
- `2026-07-17-ledger-evidence-atomicity-P04-S13` - Migrate the four locale catalogues for the ledger evidence and audit families through the locales CLI
- `2026-07-17-ledger-evidence-atomicity-P04-S14` - Regenerate the operator how-to and reference pages for ledger evidence from the frozen live surface
- `2026-07-17-ledger-evidence-atomicity-P04-S15` - Prove the removed replay and evidence-patch spellings are absent from every source and generated surface
- `2026-07-17-ledger-evidence-atomicity-P05-S18` - Route the invoice-link success path through the co-commit write authority so the invoice catalogue and the transaction catalogue diff land in one apply_batch transaction, replacing the two independently-committed saves
- `2026-07-17-ledger-evidence-atomicity-P05-S19` - Prove the composed write is one unit of work with real adapters, gated on a recorder asserting zero commits between the two catalogue writes, an anti-tautology counterpart asserting the pre-fix split shape does commit between them, and a mid-batch revision conflict leaving neither catalogue linked
- `2026-07-17-ledger-evidence-atomicity-P05-S20` - Expose the dormant link-consistency detector on the existing ledger check verb as a typed period-independent result channel with a warning notice and a false readiness verdict, gated on a CLI test reproducing a one-sided link and asserting the row, the notice contract, and ready false
- `2026-07-17-ledger-evidence-atomicity-P05-S21` - Correct the apply_evidence_split and apply_evidence_classification docstrings to describe the single classified-children writer that ships instead of the removed split-then-patch path, gated on the API stub drift check staying clean
- `2026-07-17-ledger-evidence-atomicity-P05-S22` - Emit a bucket event for invoice linkage so the sole invoice-linkage writer leaves an audit trace like every neighbouring ledger mutation, co-committed in the same unit of work as the two catalogue writes, gated on a test asserting the event is appended atomically with the link and absent when the link is refused
- `2026-07-17-ledger-evidence-atomicity-P05-S23` - Close the code-review findings on the remediation itself by promoting the one-sided link direction to a core enum consumed by the domain record and the operator payload, carrying typed rows into the notice builder instead of serialised mappings, and cross-linking the concrete repository parameters in the linking docstring, gated on the docstring core-struct module returning green

### plan

- `2026-07-17-ledger-evidence-atomicity-plan` - `ledger-evidence-atomicity` plan
