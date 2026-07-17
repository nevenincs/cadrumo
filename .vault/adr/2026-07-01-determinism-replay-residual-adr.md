---
tags:
  - '#adr'
  - '#determinism-replay-residual'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-07-01-determinism-replay-residual-research]]"
  - "[[2026-06-30-deterministic-output-replay-substrate-adr]]"
  - "[[2026-06-30-deterministic-output-replay-substrate-research]]"
  - "[[2026-06-30-ledger-add-idempotency-adr]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
---

# `determinism-replay-residual` adr: `residual determinism fixes: surrogate-id levers, seam-coverage gate, output-ordering discipline, golden-replay coverage axis` | (**status:** `accepted`)

## Problem Statement

The `deterministic-output-replay-substrate` ADR (`proposed`) designed and landed (commit
`ab537f926`) the determinism substrate this work stands on: the `core.time` clock seam
(`now()`/`frozen_clock()`), the identity levers (inject `profile_id`, mask `snapshot_id`/`run_id`),
verbatim `SchemaEnvelope` golden capture, and the shared canonicalise/mask/compare primitive with
its anti-tautology proof. That ADR is the PARENT of this one; its decisions are settled and this
ADR re-opens none of them.

The grounding research (`2026-07-01-determinism-replay-residual-research`) verifies three residual
gaps still open at HEAD, each of which lets non-determinism re-enter operator output after the
substrate is itself correct. First, two `uuid4().hex[:16]` surrogate keys - `evidence_id`
(`application/ledger/_evidence.py:384`) and `invoice_id`
(`application/ledger/_business_operation_invoice.py:421`) - surface in ledger and renta
`--format json` output and are neither in `GOLDEN_MASK_FIELDS` nor content-addressed; crucially
they are LOAD-BEARING `typer.Argument` values re-consumed by downstream verbs, so the fix is not a
plain mask. Second, the clock seam has no enforcement: a bare `datetime.now()` bypasses it silently,
and one such bypass ships (`core/corpus_manifest/__init__.py:269`). Third, a couple of unsorted
directory scans could feed ordered output with no discipline keeping output-feeding scans sorted.
This ADR decides the lever for each residual and stops at plan approval. A fourth decision
establishes the opt-in golden-replay coverage axis that consumes these fixes and enrols the
ledger-add retried-no-op as its first case. It introduces the decided shape, not code.

## Considerations

The parent substrate is a stable, landed dependency; every decision here is additive and
path-scoped under `core/`, `application/ledger/`, and the test surface. Three facts from the
research shape the decisions. The surrogate ids are re-consumed as command arguments
(`ledger evidence show/remove/link <evidence_id>`, `link --invoice-id`), and the harness Q5 gate
asserts the tool trajectory INCLUDING passed arguments - so masking a load-bearing id erases the
referential linkage a multi-command golden must assert, whereas the project already makes analogous
ids deterministic by content-addressing (`derive_transaction_id`, `derive_work_unit_id`,
`derive_import_fingerprint`). The clock seam is default-off and reached only by code that calls
`core.time.now()`, so enforcing universal routing is a conformance concern the project already
solves elsewhere with static AST gates (`test_modelo_string_usage.py`, the locale-parity gates).
The live-AEAT auth/certificate adapters legitimately read real wall-clock to measure external
latency and already expose an injectable parameter; they are seam-compatible by injection and must
be a documented carve-out, never forced through the frozen seam. `sensitive-financial-data-secure-storage-only`
binds any committed golden fixture to synthetic data only, `aeat-safety-legal-gates` forbids a live
AEAT call in the replay path, and `cli-notices-are-the-only-diagnostic-channel` fixes full-envelope
(spine plus notices plus result) comparison granularity.

## Considered options

**Decision 1 - `evidence_id` / `invoice_id` determinism lever.**
- *Mask both in `GOLDEN_MASK_FIELDS`.* Rejected as the primary lever - these ids are load-bearing
  `typer.Argument` values (evidence show/remove/link, invoice link); masking erases the referential
  linkage a multi-command golden trajectory asserts, and the harness Q5 gate asserts passed
  arguments, so a masked-then-referenced id is not trajectory-assertable. Acceptable ONLY as a
  fallback for a single-command golden that captures the mint envelope and never re-consumes the id.
- *Inject a seedable uuid override at each mint site (a `uuid=` parameter used by tests).* Rejected
  - adds test-only API surface to two mint sites for values that should simply be stable, and
  leaves them random in production, so a production replay still flaps.
- **Chosen - make both ids DETERMINISTIC by content-addressing, mirroring `derive_transaction_id`.**
  Replace the `uuid4().hex[:16]` surrogate with a content digest over the evidence/invoice's
  identifying fields (and, where a genuine collision of identical same-instant records must stay
  distinct, an explicit disambiguator - the same retry-vs-duplicate split the idempotency ADR
  established for the ledger). The id is then stable across replay AND referenceable in a
  trajectory, needing no mask; the anti-tautology gate confirms it no longer flaps. `GOLDEN_MASK_FIELDS`
  gains an entry only if a residual single-command-golden opaque leaf remains after content-addressing.

**Decision 2 - Clock-seam coverage enforcement.**
- *Leave coverage incidental (status quo).* Rejected - a new bare `datetime.now()` silently
  re-introduces a flapping field, caught only later by a mask failure on a captured scenario.
- *Runtime global freeze / monkeypatch under replay.* Rejected - the process-global freeze
  anti-pattern the live-test import ban forbids; hides the bypass rather than removing it.
- **Chosen - a static AST conformance gate that bans bare `datetime.now()`/`datetime.utcnow()` in
  production and requires routing through `core.time.now()`, with a named, reasoned allowlist for
  the injectable live-AEAT auth/certificate/browser adapters.** Scoped to wall-clock first (the
  concrete verified-open case); the gate is structured so it can later extend to output-feeding
  uuid/random and unsorted-fs arms (decisions 1 and 3) as one ambient-input surface. The one
  shipping bypass (`corpus_manifest generated_at`) is routed through the seam in the same change.

**Decision 3 - Output-ordering discipline.**
- *Do nothing (rely on existing ad-hoc `sorted()` calls).* Rejected - no gate keeps output-feeding
  scans sorted as new code lands, so the invariant silently rots.
- *Sort every `iterdir()`/`rglob()` unconditionally.* Rejected - over-broad; sorting a membership
  test or an order-independent aggregation is noise that misleads a reader into thinking order is
  load-bearing where it is not.
- **Chosen - codify a sort-at-output-boundary rule and fix only the scans that can feed ordered
  output.** Verify the two ambiguous sites (`user_profile/_profile_repository.py:633`,
  `entrypoints/cli/_ledger_import_cli.py:159`); sort those that reach an output listing or affect
  created-row order, leave the confirmed membership/aggregation uses
  (`provisioning.py:183`, `wizard/_translations.py:116`) alone. The rule targets output-feeding
  scans specifically.

**Decision 4 - Determinism-conformance / golden-replay coverage axis.**
- *Keep replay per-scenario (the harness eval authors what it needs).* Rejected - a command is
  deterministic only if someone happens to write a scenario for it, so determinism is unmeasured
  across the registered surface and a regression on an un-scenarioed command is invisible.
- *Auto-enrol every registered command.* Rejected - forces a golden fixture for commands that are
  not yet determinism-ready (e.g. before decisions 1-3 land for their surface), reddening the axis
  on known-open work rather than on regressions.
- **Chosen - an opt-in determinism-conformance axis over the `register_schema` `--format json`
  surface, with the ledger-add retried-no-op as the first enrolled case.** For each command a
  campaign enrols as replayable, the axis captures its envelope twice under `frozen_clock` with
  injected identity against real repositories, canonicalises and masks via the shared substrate
  primitive, and asserts byte-identical full-envelope equality; an un-enrolled registered command
  is reported as a visible coverage gap, not a silent pass, so the axis grows deliberately. The
  ledger-add retried-no-op is the first enrolled state-transition case, asserted via the substrate
  optional `db_sha256` post-state tier against a hermetic synthetic `var/` root - the concrete proof
  that the idempotency clock-free identity is a true no-op, closing the join to the idempotency
  campaign. The harness operator golden gate remains the owner of AEAT-oracle expected-value and
  trajectory assertions layered on top; this axis owns only payload-and-post-state determinism.

## Constraints

This ADR depends on the accepted-shape, landed `deterministic-output-replay-substrate` as a stable
parent and re-decides none of it. Decision 1 touches the ledger `evidence_id`/`invoice_id` identity,
which are persisted, roundtrip-bound records: content-addressing them requires a strict
save-load-equality roundtrip plus an anti-tautology proof per `aeat-roundtrip-discipline`, and must
preserve the genuine-duplicate case the ledger already supports (two distinct records must not
collapse to one id) exactly as the idempotency ADR handled for transactions. No back-migration
(`no-legacy-compatibility`): the id shape changes on write only; no existing-record coercion. The
AST gate (decision 2) reuses the in-tree `ast` pattern (no new dependency) and its live-AEAT
allowlist must be reasoned per entry, never a mute button; the live-test carve-out is load-bearing
because the seam refuses under the live opt-in. All conformance and roundtrip tests run against real
adapters (no mocks/skips/tautologies, `aeat-quality-gates`); any committed golden fixture holds
synthetic data only (`sensitive-financial-data-secure-storage-only`); no live AEAT call enters the
replay path (`aeat-safety-legal-gates`). The `db_sha256` post-state tier that proves the ledger-add
clock-free no-op (parent research F8) runs against a hermetic synthetic `var/` root.

## Implementation

Four additive slices on the landed substrate; each pairs a fix with a real-behaviour gate.

**Surrogate-id determinism (decision 1).** Replace the `uuid4().hex[:16]` mint at
`application/ledger/_evidence.py:384` and `application/ledger/_business_operation_invoice.py:421`
with a content-addressed derivation over the record's identifying fields, following the shape of
`derive_transaction_id`, and carrying the same genuine-duplicate disambiguation the idempotency ADR
established so two legitimately distinct records keep distinct ids. Add the roundtrip plus
anti-tautology proofs for the changed identity. Add a ledger-evidence golden scenario that captures
the `--format json` payload under `frozen_clock` with an injected `profile_id`; if any residual
single-command-golden opaque leaf remains, add it to `GOLDEN_MASK_FIELDS` and re-run the parent
anti-tautology proof so the set stays exactly residual.

**Seam-coverage gate (decision 2).** Add a static AST conformance test under the core test surface
that walks `src/cadrumo` production modules and fails on a bare `datetime.now(...)` /
`datetime.utcnow(...)` call, directing the author to `core.time.now()`. It carries a named
allowlist recording, per entry with a reason, the injectable live-AEAT sites (auth acquisition
lock, certificate evaluators, authenticator types, browser site-health parser). Structure the gate
so its visitor can later grow output-feeding uuid/random and unsorted-fs arms. In the same change,
route `core/corpus_manifest/__init__.py` `generated_at` through `core.time.now()`.

**Ordering discipline (decision 3).** Confirm whether `user_profile/_profile_repository.py:633` and
`entrypoints/cli/_ledger_import_cli.py:159` feed ordered output or affect created-row order; wrap
those that do in `sorted(...)` at the boundary and leave the confirmed membership/aggregation scans
alone. Codify the sort-at-output-boundary discipline as the durable rule (a codification candidate,
promoted only after it holds through a cycle).

**Coverage axis (decision 4).** Introduce a determinism-conformance test axis: for each command
enrolled as replayable, capture its `--format json` envelope twice under `frozen_clock` with
injected identity against real repositories, canonicalise and mask via the shared primitive, and
assert byte-identical equality; an un-enrolled registered command is reported as an uncovered gap.
Enrol the ledger-add retried-no-op as the first state-transition case, asserting the substrate
optional `db_sha256` tier is identical after the second (idempotent) add against a hermetic
synthetic `var/` root. The axis owns only payload-and-post-state determinism; the harness operator
golden gate layers AEAT-oracle expected-value and trajectory assertions on top.

## Rationale

Each decision is the faithful, enforcement-completing fix for a verified-open residual. Content-
addressing the surrogate ids (decision 1) is chosen over masking because the ids are load-bearing
arguments in a trajectory: masking would break the referential assertion the harness Q5 gate makes,
whereas a content digest makes the id both stable under replay and referenceable - and it aligns
the two odd-one-out ids with the content-addressed identity pattern the rest of the ledger already
uses, so it removes an inconsistency rather than adding a test-only lever. The AST gate (decision 2)
turns the seam from a capability into an enforced invariant using the project's existing static-gate
idiom, catching a bypass at authoring time instead of as a late golden diff; scoping it to
wall-clock first keeps it grounded in the one verified-open case while leaving the ambient-input
extension open. The targeted ordering rule (decision 3) fixes only what can leak into output,
avoiding the misleading noise of sorting order-independent scans.

## Consequences

Gain: the ledger `--format json` surface becomes golden-replayable AND trajectory-referenceable
without masking away load-bearing ids; the clock seam becomes an enforced invariant; output-feeding
directory order stops being an unguarded invariant. Together these close the residual surface the
substrate left, so a golden scenario over the ledger-evidence flow (and the ledger-add no-op via the
`db_sha256` tier) can be authored without tripping on undeclared non-determinism.

Honest difficulties. Content-addressing a persisted id is an identity change on a roundtrip-bound
record: the derivation, its validator, the roundtrip fixture, and the genuine-duplicate
disambiguator move together in one atomic change, and getting the duplicate split wrong either
collapses two real records or re-introduces a flapping tail. The AST gate must distinguish the
injectable live-AEAT carve-outs precisely - too broad reopens the bypass, too narrow reds the gate
on legitimate external-latency reads. The ordering fix depends on first confirming whether the two
ambiguous scans reach output; a wrong call either leaves a leak or adds misleading sorts.

Pathways opened. The AST gate is the seed of a single whole-application ambient-input conformance
surface (wall-clock now, uuid/random and unsorted-fs arms later). Content-addressed ledger ids let
the ledger-evidence and ledger-add-no-op scenarios enrol in the decision-4 determinism-coverage axis.
The sort-at-output-boundary rule, once codified, binds future output-feeding scans without re-review.
