---
tags:
  - '#adr'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a42e11433edda9fa9c13ec53448265ba8ca67ba870afd068b38e5cd6acd09df4'
related:
  - '[[2026-08-06-llm-package-split-measurement-basis-reference]]'
  - '[[2026-08-06-llm-package-split-ingest-cascade-reference]]'
  - '[[2026-08-07-unstructured-document-ingestion-adr]]'
  - '[[2026-08-07-unstructured-document-ingestion-provisioning-adr]]'
  - '[[2026-08-06-llm-package-split-adr]]'
  - '[[2026-08-06-invoice-canonical-structure-adr]]'
  - '[[2026-06-10-llm-evidence-classification-adr]]'
---

# `unstructured-document-ingestion` adr: `Operational surface: batch ingestion, the human review process, the consent lifecycle, and deinstallation` | (**status:** `proposed`)

## Problem Statement

The sibling pipeline record decides how one document becomes filing-grade
data, and the provisioning record decides what stands under the models. The
operator's ruling is that together they are still a fragment: the feature is
an epic whose remaining tentacles — batch ingestion, the human review gate
and process, consent withdrawal, secure-storage blob integration, ledger
integration end to end, the CLI-only boundary, conformance honesty and
deinstallation — must be designed, not deferred. Two of those were until now
explicitly out of scope somewhere in the corpus (batch in the package-split
ADR's "scale verbs", withdrawal nowhere at all), and an epic that leaves the
operational surface undesigned repeats the session's measured defect class:
capability with a ceiling above it, correct and unreachable.

This record is the seam for exactly the decisions that are *operator
workflows over the pipeline* rather than pipeline stages or provisioning
substrate: how many documents flow at once, how a human reviews and corrects
what the pipeline produced, how consent is granted, recorded and withdrawn,
how the produced records reach the ledger with their evidence, and how the
whole apparatus is removed. Each is CLI-reachable end-operator behaviour;
none changes a pipeline stage's contract or a probe's semantics — which is
why they are one record and not amendments scattered across two.

## Considerations

- **The idempotency prerequisite is decided.** Package-split D13: evidence
  `add` gains a caller-supplied idempotency key with a full-field no-op
  match; the blob layer is already content-addressed. Batch re-run safety
  builds on that, not beside it.
- **The transcription cache makes resume cheap.** Pipeline S1's encrypted
  cache means a re-run re-reads no bytes and re-transcribes nothing already
  transcribed; batch resumability is mostly already-designed substrate.
- **Admission control is per-load, but a batch is many loads.** Provisioning
  D3 refuses an unsafe load; a batch must respect that refusal without
  dying, and must pace rather than fan out — the concurrency bound (default
  one) is the pacing mechanism.
- **Consent is per-invocation and non-sticky by D8a**, which shapes
  withdrawal: there is no standing grant whose revocation stops future
  transmissions, because nothing persists to revoke. The withdrawal problem
  is therefore about the past (what already left) and about eligibility
  (whether the gate may even be offered again).
- **Transmitted bytes cannot be untransmitted.** Any withdrawal design that
  implies deletion-at-the-provider is a claim this product cannot verify and
  must not make. Honesty here is a hard constraint.
- **The review contract exists in outline.** The accepted
  evidence-classification ADR fixed suggest → review → apply/reject as the
  spine and made human review load-bearing; the pipeline record added typed
  findings and per-field provenance. What is undesigned is the *process*:
  what a reviewer must see, what cannot be confirmed blind, and what a
  correction records.
- **The blob home is settled and single.** Evidence bytes live in the
  content-addressed `AttachmentStore` over encrypted `SecureObjectRepository`
  envelopes; the transcription cache (pipeline S1) keys on the same content
  address. No decision here may create a second blob store.
- **The CLI is the only product surface.** Roots are `config` and `app`; the
  MCP server shells the CLI; notices are the sole diagnostic channel; the
  `pull`/`--file` naming standard binds new verbs; `ledger import` already
  accepts a directory and is the batch-input precedent.
- **Conformance wording is a peer-owned lane with a binding boundary.** The
  canonical-format gates assert XSD-layer validity; claims must say
  "syntactically schema-valid", never "conformant", and no Schematron ships.

## Considered options

- **Batch as a shell loop left to the operator** (status quo: one verb, one
  document). Rejected: per-item idempotency, pacing, partial-failure
  reporting and resume are exactly what a shell loop gets wrong, and the
  operator named batch as scope.
- **Batch as a daemonised queue service.** Rejected: a second entrypoint
  beside the CLI, process supervision the product refuses elsewhere, and
  nothing in the workload needs residency — a batch is a bounded run.
- **Batch as a CLI verb family over a typed in-run queue with per-item
  results (chosen).** One process, one invocation, resumable by keys and
  cache, respecting admission control by construction.
- **Consent withdrawal as provider-side deletion requests.** Rejected as the
  primary mechanism: unverifiable, provider-specific, and it would let the
  product imply a guarantee it cannot check. Recorded as an operator-manual
  pathway the consent ledger makes possible, not a product claim.
- **Consent withdrawal as ledger + eligibility + local re-derivation
  (chosen).** Everything the product can actually verify and enforce.
- **Review as free-form editing of the draft.** Rejected: it erases the
  distinction between what the document said and what the operator asserts,
  which is the provenance axis the whole pipeline exists to carry.

## Constraints

- Every decision here operates over the pipeline, provisioning and consent
  contracts of the two sibling records and changes none of them.
- Sensitive bytes: encrypted at rest, in-memory in flight, never on disk in
  the clear — batch introduces no spool files, no temp queues, no plaintext
  progress journals. Batch state that must persist (completed-item keys)
  persists through secure storage.
- Human review is mandatory before minting; batch does not change that — a
  batch produces reviewed-pending drafts, never auto-confirmed invoices.
- Regulated numbers stay registry-derived; a batch confirms nothing the
  single-document path would refuse.
- No live AEAT interaction anywhere in this record's scope.

## Implementation

### D1 — batch ingestion: a bounded run with per-item truth

A batch verb family on the evidence surface accepts a directory or an
explicit file set (`--file` repeated, per the CLI standard), and executes
the full pipeline per item inside one invocation: shape probe, transcription
(cache-first), extraction, grounding, classification suggestion. Semantics,
each load-bearing:

- **Per-item results, never batch abort.** Each item ends in a typed row —
  ingested, refused (with its typed refusal), or ambiguous-pending-review —
  and one item's failure never aborts the run. The batch result is the list
  plus a summary; exit status reflects "any item failed", not "first item
  failed".
- **Idempotent re-run by construction.** Each item derives its idempotency
  key from content address plus declared direction, riding package-split
  D13: a re-run over the same directory re-ingests nothing, re-transcribes
  nothing cached, and reports each such item as a no-op row. Resume after a
  crash is therefore re-run, with no journal format to invent; the
  completed-item record IS the store's idempotent state.
- **Ordering is deterministic** (sorted by content address) so two re-runs
  report identically; nothing depends on filesystem enumeration order.
- **Contention and rate limits are batch-wide.** Inference-bearing items
  pass the provisioning admission check; a standing contention refusal
  pauses the inference lane and completes every non-inference item rather
  than failing the batch. The cloud engine route, where consented, applies
  its provider rate limits across the run with the shared backoff policy,
  never per item in isolation.
- **Progress is notice-channel.** A per-item progress notice stream in text
  mode, a complete typed row set in JSON mode; no second progress channel.

### D2 — the human review process: nothing is confirmed blind

The review surface presents, per draft: every field with its value, its
`FieldOrigin`, its verbatim anchor, its grounding outcome and any ambiguity
candidates; every discrepancy finding; the direction suggestion with its
derivation basis; and the classification suggestions with their allow-list
provenance. Three rules make it a gate rather than a viewer:

- **Blocking findings block.** A draft carrying an unresolved closure
  discrepancy, an ambiguous identity, or an unresolved direction cannot be
  confirmed at all until the operator resolves each named finding with an
  explicit per-finding resolution (choose a candidate, supply a value,
  attest the printed total) — there is no bulk "confirm anyway" flag.
- **A correction is an assertion, not an edit.** An operator override
  re-stamps the field `OPERATOR` with the prior value and origin retained in
  the confirmation record; the document-derived value is never overwritten
  in place, so the record can always answer "what did the document say, and
  what did the operator assert instead".
- **The confirmation itself carries provenance:** who confirmed, when, which
  fields were overridden, which findings were resolved and how, and which
  evidence and transcription content addresses it was confirmed against.
  This is the record a later audit or a consent-withdrawal re-derivation
  reads.

Batch feeds this process a queue: review verbs list pending drafts, filter
by finding class, and confirm one draft per invocation — bulk confirm is
deliberately absent, because the gate's value is exactly the per-document
attention it forces.

### D3 — the consent lifecycle: grant, record, withdraw, prove

**Grant** is D8a's per-invocation token, unchanged. **Record:** the same
choke point that honours a token appends a consent-ledger entry — timestamp,
profile, evidence content address, provider and model, invocation surface —
through secure storage; the ledger is complete by construction because
recording and permitting are one code path, and a dispatch that cannot
append refuses rather than transmitting unrecorded. **Eligibility** is a
per-profile standing bar (default off, gestor-locked off): while off, the
consent gate is never even offered, so "withdraw" for the future is one
profile setting, verifiable in `aeat config check`. **Withdrawal** of the
past is handled honestly: a withdrawal verb lists every consent-ledger entry
for the profile, states plainly that transmitted bytes cannot be recalled by
this product, marks cloud-derived artefacts (drafts, classifications whose
provenance stamps name a cloud transport) as re-derivation candidates, and
offers the local re-derivation: re-run extraction from the cached
transcription on the local engine, re-stamping the artefact's provenance.
The original stamps are never rewritten — they are the honest history — but
after re-derivation no *current* artefact depends on the cloud read.
**Proof:** the choke-point gate test (no unconsented dispatch), the
ledger-completeness construction above, and a withdrawal test proving the
eligibility bar off means no gate is offered on any surface.

### D4 — ledger integration, end to end, with the waist honoured

The confirmed draft mints through the existing confirm boundary into the
canonical `Invoice` aggregate (the sibling canonical-structure ADR's writer,
including its multi-line per-rate path), linked to its evidence record and
transaction where one exists, with the typed evidence projections the ledger
contract requires bundled at revision time. The loss-forbidden guarantee
extends across the whole chain as an end-to-end gate: a bundled fixture
travels ingest → transcription → extraction → grounding → review-confirm →
`Invoice` → Modelo 303 observation, and every field the draft carried is
asserted present or accounted for at each seam — the measured defect class
(read correctly, discarded downstream) is gated at every hop, not only at
the draft-to-payload projection.

### D5 — the CLI-only boundary and conformance honesty

Every capability this epic adds is reachable only through the `aeat` CLI
under the existing `config` and `app` roots; no daemon, no HTTP surface, no
new entrypoint, and the MCP server reaches it by shelling the CLI as it does
everything else. Every new verb: `pull`/`--file` naming, typed envelope with
notices as the only diagnostic channel, JSON schema and documented-command
conformance gates from birth. Conformance wording stays honest per the
peer-owned canonical lane: XSD-layer claims say "syntactically
schema-valid", never "conformant", and no Schematron is bundled; the
benchmarking harness (pipeline D9) remains dev tooling with key-pinned
results and never ships in the product wheel.

## Rationale

The seam of this record is operator workflow versus pipeline mechanics, and
it holds under pressure: batch changes throughput, review changes who
asserts, consent changes where bytes may go, deinstallation changes what is
installed — none changes what a stage computes, which is why the pipeline
record needs no amendment beyond its scope note. Batch as a bounded
CLI run wins because every hard property it needs (idempotent re-entry,
cached transcription, admission control, backoff) was already decided as
substrate, so the design cost collapses to per-item result semantics — and
per-item truth is the property the operator's complaint history keeps
pointing at: partial success that presents as success is the enemy, so the
batch's unit of honesty is the item, never the run. The consent-withdrawal
design follows from one honest sentence — this product cannot recall
transmitted bytes — and builds everything it *can* guarantee around that:
complete recording, standing ineligibility, and local re-derivation that
removes dependence on the cloud read without falsifying history. Blind
confirmation is banned because the review gate is the one place the whole
epic's probabilistic content meets a human authority; a gate that can be
waved through in bulk is not a gate.

## Consequences

**Gains.** The epic's operator surface is decided end to end: many
documents in one honest run, a review process that cannot rubber-stamp, a
consent record that can be audited and a withdrawal that means something
true, ledger integration gated hop by hop, and a removal story that leaves
no half-working state.

**Costs and honest limits.** Bulk confirm is deliberately absent; a
thousand-document backlog therefore costs a thousand review decisions —
that is the gate working, and any future relaxation is its own ADR against
this record. Withdrawal cannot affect provider-side copies and says so to
the operator. The consent ledger adds a write to every consented dispatch;
refusing on append failure is a deliberate availability cost on a path that
is an exception by design. The end-to-end gate is the plan's most expensive
test and runs in the CI lane without any model by using an exact-parse
fixture.

**Coupling.** Consumes: pipeline D1 through D9 and D8a, provisioning D3, D5
(deinstallation mechanics live there; this record only binds their
user-facing guarantees), package-split D13, the canonical-invoice writer,
and the ledger evidence contract. Changes none of them.

**Deliberately out of scope, named.** Bulk or rules-based auto-confirmation;
provider-side deletion guarantees; a batch daemon or watch-folder mode; MCP
verbs beyond the existing CLI-shelling surface; multi-operator review
workflows (one operator per profile is the product's shape); and everything
the sibling records already scope out.

## Codification candidates

None. `single-subject-mutation-is-idempotent-guarded`,
`sensitive-financial-data-secure-storage-only`, `no-silent-under-declaration`
and the CLI contract rules govern every decision here; the durable artefacts
are the per-item batch result contract, the consent ledger, and the
end-to-end waist gate, carried as executable gates.
