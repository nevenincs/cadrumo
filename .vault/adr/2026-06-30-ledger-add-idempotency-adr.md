---
tags:
  - '#adr'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
related:
  - "[[2026-06-30-ledger-add-idempotency-research]]"
  - "[[2026-06-10-ledger-interface-contract-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
---

# `ledger-add-idempotency` adr: `manual ledger add idempotency and verify-report retry shape` | (**status:** `accepted`)

## Problem Statement

The `aeat` CLI's target operator is an autonomous LLM agent that retries uncertain or
failed calls. Two single-subject mutating verbs are not retry-safe (research
`2026-06-30-ledger-add-idempotency-research`, F1/F5):

- A retried `aeat app ledger add` with no `--idempotency-key` **double-writes** a duplicate
  transaction: the transaction id folds `occurred_at = now()`, so two identical retries at
  different wall-clock instants get distinct ids and both persist (F1). A duplicate ledger row
  silently corrupts every downstream modelo aggregation that sums the ledger - a
  ledger-correctness hazard, not a cosmetic one.
- A repeated non-granting `aeat app modelo verify` **accumulates** time-stamped reports: the
  report id folds `run_at = now()`, and the report is persisted "regardless of outcome", so each
  retry of a still-failing verify inserts a new report (F5). A granting verify is already safe
  (it flips the revision out of `BORRADOR`, so a re-verify refuses).

A caller-supplied `idempotency_key` already exists end-to-end (CLI option, command field, a
clock-free deterministic id branch), but the hook is half-built: with a key the id is
deterministic, yet `create_manual_transaction` performs no existence check, so it still emits a
fresh creation event, re-stamps `created_at`/`modified_at`, re-runs evidence verification, and
returns as if freshly created - `idempotent_last_wins` with side effects, not the clean
`idempotent_guarded` no-op an agent retry needs (F2). The decision is non-trivial because manual
add must keep recording **two genuinely-identical same-day movements** (the manual-ledger-storage
ADR mandates this; the import path deliberately preserves the equivalent intra-batch case, F3)
while making an agent **retry** of one logical add a safe no-op.

## Considerations

- **The substrate is half-built, not absent (F2).** `--idempotency-key`, the
  `ManualLedgerTransactionCommand.idempotency_key` field, and the clock-free
  `manual:{bucket_id}:{idempotency_key}` id branch already ship. The remaining work is an
  existence guard, a same-key/different-content refusal, and a no-op notice - not a new parameter.
- **There is a proven in-project template (F4).** `create_work_unit` is `idempotent_guarded`:
  derive a deterministic id, and "if the derived work-unit id already exists, the existing record
  is returned without emitting another creation event." Manual add should mirror it exactly,
  honouring `composition-service-no-parallel-write-path`.
- **The import path is the retry-vs-duplicate reference (F3).** A content-only fingerprint
  (no timestamp) makes re-import idempotent, while two same-signature rows in one batch are kept as
  two genuine movements. Manual add needs the same split: retry = no-op, genuine duplicate = kept.
- **The project already has an idempotency vocabulary (F6).** The CLI-wireframe reference defines
  `idempotent_guarded` / `idempotent_last_wins` / `non_idempotent_append`. This ADR classifies the
  two verbs against it rather than inventing terms.
- **A no-op outcome must fit the existing contracts.** `ledger-mutation-returns-uniform-quintet`
  fixes the mutation response shape; `cli-notices-are-the-only-diagnostic-channel` owns
  operator-facing diagnostics. The no-op rides both: the existing row's quintet plus an info
  `Notice`, never a bespoke result field.
- **Clock-isolation is a cross-cutting concern (F8).** `occurred_at` and `clock` are injectable.
  A caller-supplied-key guard decides by a pure catalogue lookup (no clock read); a content-pinned
  verify id drops `run_at` from identity entirely. Both increase clock-isolation, which the
  separate determinism/golden-replay brief depends on.

## Considered options

**Add-idempotency mechanism**

- **(a) Content-fingerprint dedup with an explicit override.** Derive the import-style content-only
  fingerprint for a manual row and treat a content-identical add as a no-op unless an
  `--allow-duplicate` flag is set. *Rejected as the primary mechanism:* it cannot distinguish a
  retry from a genuine second identical same-day movement without either a recency window (a clock
  read, fighting clock-isolation, F8) or an override flag that inverts the manual-ledger-storage
  default (every genuine same-day duplicate would then need the flag). *Kept as a complementary,
  advisory-only layer* (see Implementation): stamp the content fingerprint on manual rows so they
  join the existing import dedup/`likely_duplicate` advisory, which is non-blocking and never
  suppresses a genuine duplicate.
- **(b) Caller-supplied idempotency key, raised to `idempotent_guarded` (CHOSEN).** The agent
  passes a stable key per logical add; a second add with the same key returns the existing row as a
  no-op. The substrate is half-built (F2), the decision is in the agent's hands, it is fully
  clock-isolatable (pure catalogue lookup), and it mirrors `create_work_unit` (F4). Genuine
  duplicates remain expressible (two distinct keys, or the keyless append path).
- **(c) Deterministic content-only id (drop `occurred_at` from the id).** *Rejected:* it makes the
  id itself collapse two legitimate identical same-day movements into one row - the exact case the
  import path preserves intra-batch (F3) and the manual-ledger-storage ADR mandates supporting. It
  would convert a genuine second cash payment into a silent overwrite.

**Verify non-granting-report shape**

- **(1) Content-pin `report_id` to the verification outcome (CHOSEN).** Derive the id from
  `calculation_revision_id` + `completeness_status` + `findings` + `verified_by`, dropping `run_at`
  from identity. The existing `upsert_verification_report` then collapses identical-outcome retries
  to one report, while a re-verify whose findings change (operator fixed an input) produces a new
  distinct report. The report catalogue holds one report per distinct outcome - the
  audit-meaningful granularity - and the id becomes clock-free (F8).
- **(2) Keep only the latest non-granting report.** *Rejected:* loses the history of distinct
  outcomes (e.g. that an earlier run had a different finding set), degrading the audit trail.
- **(3) Accept accumulation as an audit feature.** *Rejected:* this is the current behaviour and is
  the bug - identical retries pile up timestamped duplicates that bloat the catalogue and bury the
  audit signal in noise on exactly the non-granting retry loop an agent drives.

## Constraints

- **`Transaction` and `VerificationReport` are roundtrip-bound persisted records.** Any field
  semantics change (the verify `run_at` becoming a non-identity body field; the manual content
  fingerprint stamp) requires a strict save->load->equality roundtrip with the changed fields
  populated non-default, plus an anti-tautology proof, per `aeat-roundtrip-discipline`.
- **`VerificationReport` enforces its id by model validator.** `derive_verification_report_id` is
  re-checked on construction (`_verification_report.py:157-161`), so the identity-input change must
  update the derivation and its validator together, or no report can be built.
- **The mutation quintet is pinned by a gate.** `ledger-mutation-returns-uniform-quintet` and the
  schema-conformance gate fix the `add` response shape; the no-op must reuse the existing quintet
  (existing row, empty `bucket_event_ids`), adding no bespoke field.
- **No back-migration (`no-legacy-compatibility`).** Pre-beta, no released data: stamp the new
  identity/fingerprint on write only. Existing-session un-fingerprinted manual rows and previously
  accumulated time-stamped verify reports are left as-is; no migration pass, no read-tolerance
  branch. Existing accumulated reports simply stop growing once the content-pinned id lands.
- **Preserve `ledger-amount-is-absolute-direction-is-authority` and
  `cli-single-subject-id-is-positional`.** The fix touches identity/idempotency only - not the
  amount/direction encoding, not the id-input convention.
- **Real-gate testing (`aeat-quality-gates`).** Idempotency is a structural/provenance contract
  with no numeric oracle; tests assert no-op behaviour, genuine-duplicate preservation, conflict
  refusal, and report-collapse against real repositories - no mocks, skips, or tautologies.

## Implementation

**Manual add (decision b).** Complete the half-built `idempotency_key` hook so a keyed add is
`idempotent_guarded`, mirroring `create_work_unit`:

- In `create_manual_transaction`, after deriving the deterministic transaction id but before
  building any event, look up the id in the loaded catalogue. If a row already exists:
  - **Same key, content matches** (the retry case): return the existing row's quintet as a no-op -
    no second `LEDGER_TRANSACTION_CREATED` event, no `created_at`/`modified_at` re-stamp, no
    evidence re-verification. The no-op is surfaced as an info `Notice`
    (`cli-notices-are-the-only-diagnostic-channel`) and signalled structurally by empty
    `bucket_event_ids` in the otherwise-unchanged quintet.
  - **Same key, content differs** (the key was reused for a different movement): refuse with a
    clear, localised conflict error naming the conflicting field set - the "otherwise refuses with
    a clear reason" arm of `idempotent_guarded`. This prevents a silent last-wins overwrite under a
    recycled key.
- The keyless path stays `non_idempotent_append`: it is the human/"record a genuine movement" path
  that supports two identical same-day cash payments by construction. The agent harness contract
  (persona/skill surface, governed by `operator-harness-cites-live-cli-surface`) REQUIRES the agent
  to pass a stable `--idempotency-key` per logical add, so the agent never relies on the keyless
  path for retry-safety. The CLI help and the agent harness doc state this explicitly.
- **Complementary advisory (decision a, non-blocking):** stamp the content-only import fingerprint
  (`derive_import_fingerprint`) on manual rows (today `import_fingerprint=None`) so a manual row
  participates in the existing import dedup/`likely_duplicate` advisory. This is defence-in-depth -
  it warns on a probable duplicate, never blocks a genuine one, and never substitutes for the
  key-based guard.

**Verify report (decision 1).** Change `derive_verification_report_id` to fold the verification
*outcome* (`calculation_revision_id`, `completeness_status`, the `findings` tuple, `verified_by`)
instead of `run_at`. Update the `VerificationReport` model validator to match. `run_at` is retained
on the report body as a non-identity "last-seen" timestamp. `upsert_verification_report` is
unchanged - it already keys on `verification_report_id`, so a content-identical retry collapses in
place and a changed-finding re-verify inserts a distinct report. The granting path is untouched
(already self-limiting). `clock` stays injectable; the identity is now clock-free.

**Tests (real behaviour, no mocks).** A retried keyed `ledger add` against a real bucket repository
yields one row, one creation event, identical `created_at`, and a no-op notice; a keyless add of
two content-identical same-day movements yields two rows; a same-key/different-content add raises
the conflict error; two non-granting verify runs with identical findings collapse to one report
while a changed-finding re-verify produces a second; plus the mandated roundtrip + anti-tautology
proofs on both persisted records.

## Rationale

Decision (b) is chosen because it is the only option that makes an agent retry a clean no-op
*without* sacrificing the genuine-duplicate case the manual-ledger-storage ADR mandates and the
import path proves is intended (research F3). It reuses a substrate that already ships (F2),
mirrors the `create_work_unit` template the project already trusts (F4), keeps the single write
path (`composition-service-no-parallel-write-path`), and is the most clock-isolatable design (the
guard is a pure catalogue lookup, F8) - which the determinism/golden-replay brief depends on.
Option (c) was rejected on the knockout criterion that it silently collapses a genuine second
same-day movement; option (a) cannot decide retry-vs-duplicate on its own without a clock-reading
window or a default-inverting flag, so it is demoted to a non-blocking advisory. For verify,
content-pinning the report id (decision 1) is chosen because the audit-meaningful unit is a
*distinct verification outcome*, not a wall-clock attempt; it both removes the accumulation noise
and removes `run_at` from the identity, strictly improving clock-isolation.

## Consequences

- **Gain:** a retried `ledger add` is a safe, observable no-op (existing row + info notice); a
  retried non-granting `modelo verify` collapses to one report; both verbs become honestly
  classifiable as `idempotent_guarded`. The ledger-correctness hazard (duplicate-row aggregation
  corruption) is closed for the agent path, and the verify catalogue stops accumulating noise.
- **Gain:** both identities become clock-free, advancing the separate determinism/golden-replay
  work without that brief having to revisit these two call sites.
- **Difficulty:** the verify report-id change touches a roundtrip-bound record with a
  validator-enforced id; the derivation, validator, and roundtrip fixture move together in one
  atomic change. The same-key/different-content refusal needs a precise, localised conflict message
  (the accepted-field-set, not a bare "invalid").
- **Pitfall:** the agent must actually pass a stable `--idempotency-key`; the keyless path remains
  append-only by design, so the harness contract (the persona/skill instruction) is load-bearing -
  a documentation gap there reopens the double-write for the keyless agent call. The content
  fingerprint advisory mitigates but does not replace this.
- **Pathway opened:** the `idempotent_guarded` no-op-notice + quintet pattern generalises to the
  other single-subject mutating verbs, and a future `aeat app` response-shape/idempotency
  conformance gate can assert it across domains. The clock-free identities feed the golden-replay
  substrate directly.

## Codification candidates

- **Rule slug:** `single-subject-mutation-is-idempotent-guarded`. **Rule:** every CLI verb that
  creates one addressable record must be `idempotent_guarded` - a retry with the same caller-supplied
  idempotency key (or deterministic key) returns the existing record as a no-op (no second lifecycle
  event, no re-stamp) via the uniform quintet plus an info `Notice`, and a same-key/different-content
  call refuses with a clear reason; only deliberately additive verbs are `non_idempotent_append` and
  must document it. (Promote only after the pattern holds across at least one full execution cycle,
  per `vaultspec-codify`.)
