---
tags:
  - '#research'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - '[[2026-06-10-ledger-interface-contract-adr]]'
  - '[[2026-06-10-ledger-amount-direction-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-06-30-agent-harness-adr]]'
  - '[[2026-04-24-aeat-cli-wireframe-reference]]'
---

# `ledger-add-idempotency` research: `manual ledger add idempotency and verify-report retry shape`

The `aeat` CLI's target operator is an autonomous LLM agent (`2026-06-30-agent-harness-adr`)
that retries uncertain or failed calls. Two single-subject mutating verbs are not
retry-safe: a retried `ledger add` double-writes a duplicate transaction, and a repeated
non-granting `modelo verify` accumulates time-stamped reports. The first silently corrupts
every downstream modelo calculation that aggregates the ledger. This research grounds both
gaps at HEAD, contrasts them against the import path (already retry-safe) and `create_work_unit`
(already idempotent-guarded), and frames the design decision the ADR must resolve: make a
retry a no-op while preserving two genuinely-identical same-day movements.

All findings confirmed at HEAD (`git log -1` clean on the three touched files; no peer WIP).

## Findings

### F1 - Manual add identity folds the wall clock; the default keyless retry double-writes (CRITICAL)

`create_manual_transaction` (`src/aeat/application/ledger/_actions_manual.py:106-148`) performs
**no existence/dedup check**. It builds a `LEDGER_TRANSACTION_CREATED` event, then
unconditionally `_upsert_transaction` (`src/aeat/application/ledger/_actions_common.py:571-574`,
keyed on `transaction.transaction_id`).

When no `idempotency_key` is supplied (the default - `idempotency_key: str | None = None`,
`src/aeat/application/ledger/_models.py:102`), the id is wall-clock-derived:

- `_provider_transaction_id` (`_actions_manual.py:1053-1056`) returns
  `manual:{bucket_id}:{occurred_at.isoformat()}:{_source_sha256(...)}`.
- `_source_sha256` (`_actions_manual.py:1059-1062`) also folds `occurred_at` into the hash.
- `occurred_at` defaults to `now()` via `_normalise_timestamp(None)`
  (`_actions_common.py:566-568`).

So two identical retries at different wall-clock instants resolve to **different ids** and
**both persist**. Manual rows are also stamped `import_fingerprint=None`
(`_transaction_from_command`, `_actions_manual.py:995`), so no downstream content dedup catches
them either. This is the ledger-correctness hazard: a duplicate row inflates the ledger and
silently corrupts every modelo aggregation that sums it.

### F2 - The `idempotency_key` substrate is half-built: deterministic id, but no guarded no-op

A caller-supplied `idempotency_key` already exists end-to-end at HEAD - CLI option
`--idempotency-key` (`src/aeat/entrypoints/cli/_ledger.py:244-248`, threaded at `:318`), command
field (`_models.py:102`), and a deterministic id branch
(`_provider_transaction_id`, `_actions_manual.py:1054-1055`):
`manual:{bucket_id}:{idempotency_key}` (clock-free). It is also folded into `_source_sha256`'s
input set (`_raw_fields`, `_actions_manual.py:1086-1087`) and the update path
(`_actions_manual.py:516`, `:560`).

But the hook is incomplete. With a stable key the transaction_id is deterministic, yet
`create_manual_transaction` still:

- emits a **fresh** `LEDGER_TRANSACTION_CREATED` event each retry - `derive_bucket_event_id`
  (`src/aeat/domain/buckets/_event.py:213-233`) folds `occurred_at`, so the event_id differs
  per retry and a new event appends (content-addressed natural idempotency, `_event.py:240-243`,
  holds only for byte-identical bodies; the differing `occurred_at` defeats it);
- **re-stamps** `created_at`/`modified_at` to the new `now` (`_transaction_from_command`,
  `_actions_manual.py:1004-1005`), because `create_manual_transaction` passes neither;
- re-runs evidence verification (`_verify_evidence_references`, `_actions_manual.py:125-130`);
- returns via `_result` (`_actions_common.py:772-781`) as if freshly created - no signal that
  the row already existed.

Net: the keyed path is `idempotent_last_wins` with creation-event side effects, **not** the
clean `idempotent_guarded` no-op an agent retry needs. The missing pieces are an existence
guard, a same-key/different-content conflict refusal, and a typed no-op notice.

### F3 - The import path is the retry-safe template: content-only fingerprint, intra-batch keep

`derive_import_fingerprint` (`src/aeat/domain/transactions/_models.py:118-151`) is **content-only**:
amount magnitude, currency, direction, normalised narrative, effective date - **no timestamp**.
`_evaluate_import_rows` (`src/aeat/application/ledger/_actions_import.py:153-234`) sends an
already-present fingerprint to `skipped_refs` (`:201-203`), so re-importing the same statement is
idempotent. Crucially, an **intra-batch** fingerprint collision is deliberately **kept** (two
genuine same-day identical movements) and distinguished by a row-index-bearing transaction_id
(`:184-226`, comment `:188-200`); only a true content-id collision is skipped. The day-key
heuristic (`derive_movement_day_key`, `_models.py:154-164`) drives a non-blocking
`likely_duplicate` advisory, not a block. This is the exact retry-vs-genuine-duplicate split the
manual path lacks.

### F4 - `create_work_unit` already implements the recommended guarded-no-op shape

`create_work_unit` (`src/aeat/application/modelo/_work_lifecycle.py:51-124`) derives a deterministic
id (`derive_work_unit_id`, content-addressed over the four-axis key,
`src/aeat/domain/modelos/_work_unit.py`), and **"if the derived work-unit id already exists, the
existing record is returned without emitting another creation event"** (`:73-75`, `:122-124`). This
is the in-project `idempotent_guarded` template the manual-add fix should mirror - no parallel
write path, no second lifecycle event. `work classify` operates on an existing transaction by
positional id (`cli-single-subject-id-is-positional`), so a retry is `idempotent_last_wins` by
construction (re-applies the same classification to the same row; no new row) - confirmed
retry-safe, no change needed.

### F5 - Verify persists one report per wall-clock attempt; non-granting retries accumulate

`verify_modelo_revision` (`src/aeat/application/modelo/_verification_actions.py:823-966`) computes
`report_id = derive_verification_report_id(calculation_revision_id, run_at=now, verified_by)`
(`:927-932`). `derive_verification_report_id`
(`src/aeat/domain/modelos/_verification_report.py:117-129`) folds `run_at` into the content hash,
and the report is persisted **"regardless of outcome"** via `upsert_verification_report`
(`:964-966`; `src/aeat/domain/modelos/_verification_repository.py:186-197`, keyed on
`verification_report_id`). A first verify that **grants** flips the revision out of `BORRADOR`, so a
re-verify refuses before persisting - already safe. But a **non-granting** verify (blocking
findings, revision stays `BORRADOR`) derives a fresh time-stamped id on every retry, so each retry
inserts a **new** report. The `clock` is already an injectable parameter (`:841`, `:927`), so the
identity's only non-determinism is the deliberate `run_at` fold.

### F6 - A canonical idempotency taxonomy already exists in the project

`2026-04-24-aeat-cli-wireframe-reference` ("Idempotency contract") defines the rule vocabulary the
ADR should adopt verbatim: `idempotent_guarded` ("re-running is a no-op if state already matches;
otherwise refuses with a clear reason"), `idempotent_last_wins`, and `non_idempotent_append`
("re-running creates a new record ... safe but additive"). It assigns `data import statement` =
`idempotent_guarded` (duplicate detected by SHA-256) and `transactions edit/classify` =
`idempotent_last_wins`. `ledger add` is currently unclassified/`non_idempotent_append` and is the
gap.

### F7 - Constraint inventory (rules that bind the fix)

- `ledger-mutation-returns-uniform-quintet`: a single-transaction mutation returns
  `{bucket_id, transaction_id, bucket_event_ids, review_status, transaction}`
  (`2026-06-10-ledger-interface-contract-adr` D1). A no-op result MUST still fit this shape -
  return the existing row's quintet (with empty `bucket_event_ids` to signal no new event).
- `cli-notices-are-the-only-diagnostic-channel`: a "duplicate, no-op" outcome is a typed info
  `Notice` on the envelope, never a bespoke `result` field.
- `cli-single-subject-id-is-positional`, `ledger-amount-is-absolute-direction-is-authority`:
  preserve both; the fix touches identity/idempotency only.
- `no-legacy-compatibility`: pre-beta, no released data - stamp on write, **no back-migration** of
  existing un-fingerprinted manual rows or accumulated time-stamped verify reports.
- `composition-service-no-parallel-write-path` / one-canonical-mechanism: reuse the single
  `create_manual_transaction` write path with an existence guard; do not add a parallel dedup writer.
- `aeat-roundtrip-discipline` / `aeat-quality-gates`: real-repository idempotency + roundtrip tests,
  no mocks/skips/tautologies.

### F8 - Determinism cross-reference (for the eval/golden-replay brief, not solved here)

`occurred_at` (manual add) and `clock` (verify) are injectable at both call sites
(`_actions_manual.py:114`, `_verification_actions.py:841`). Any recommended fix MUST NOT make the
result **less** clock-isolatable. A caller-supplied-key guard (pure catalogue lookup, no clock read
for the decision) and a content-pinned verify report id (drops `run_at` from identity entirely) both
**increase** clock-isolation. A time-window/recency heuristic for keyless dedup would read the clock
to decide and is therefore disfavoured.

## Decision space (resolved in the sibling ADR)

**Add idempotency.** Three options were evaluated:

- **(a) Content-fingerprint dedup + explicit override.** Mirrors import's skipped/kept split.
  Cannot, by itself, distinguish a retry from a genuine duplicate without either a time-window (a
  clock dependency, fights F8) or an override flag that inverts the manual-ledger-storage default
  (genuine same-day duplicates would need a flag). Kept only as a complementary advisory.
- **(b) Caller-supplied idempotency key (recommended).** The agent passes a stable key per logical
  add; same key = guarded no-op. Substrate is half-built (F2); the decision is in the agent's hands,
  fully clock-isolatable, and mirrors `create_work_unit` (F4). Preserves genuine duplicates (two
  keys, or keyless append).
- **(c) Deterministic content-only id (rejected).** Collapses two legitimate identical same-day
  movements into one - the exact case import deliberately preserves (F3) and the
  manual-ledger-storage ADR mandates supporting.

**Verify-report shape.** Recommended: **content-pin `report_id`** to the verification *outcome*
(`calculation_revision_id` + `completeness_status` + `findings` + `verified_by`), drop `run_at` from
identity (keep it as a last-seen body field). `upsert_verification_report` then collapses
identical-outcome retries to one report, while a changed-finding re-verify produces a new distinct
report - the audit-meaningful granularity. Rejected: "keep only latest" (loses distinct-outcome
history) and "accept accumulation" (the current bug; piles up timestamped noise on the non-granting
retry loop).
