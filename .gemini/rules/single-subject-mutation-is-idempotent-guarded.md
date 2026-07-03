---
name: single-subject-mutation-is-idempotent-guarded
trigger: always_on
---

# Single-subject creating mutations are idempotent-guarded

## Rule

Every CLI verb (and the application service behind it) that CREATES one
addressable record MUST be `idempotent_guarded`: a retry carrying the same
caller-supplied idempotency key — or the same deterministic, clock-free derived
id — returns the EXISTING record as a no-op (no second lifecycle event, no
`created_at`/`modified_at` re-stamp, no re-run of side effects) surfaced through
the surface's uniform result shape (e.g. the ledger mutation quintet with empty
`bucket_event_ids`) plus an info `Notice`; a same-key call whose content DIFFERS
refuses with an instructive, localised conflict naming the divergent fields. A
verb that is deliberately additive (two genuinely-distinct records may share
identical content) is `non_idempotent_append` and MUST document that choice. The
record's identity MUST be clock-free — the timestamp is a non-identity last-seen
body field, never folded into the derived id — so a retry at a different instant
resolves to the same record.

## Why

The `aeat` CLI's target operator is an autonomous LLM agent that retries
uncertain or failed calls, so a creating mutation that is not retry-safe silently
double-writes: a duplicate ledger transaction inflates every downstream modelo
aggregation, and a time-stamped verify report or filing record accumulates one
copy per retry. The `2026-06-30-ledger-add-idempotency-adr` closed this across the
three single-subject surfaces — manual `ledger add`, `modelo verify`, `modelo
file` — by keying idempotency on a clock-free id, returning the existing record as
a guarded no-op, and refusing same-key/different-content. The independent close
review (`2026-07-01-ledger-add-idempotency-audit`) confirmed the pattern and
caught the recurring failure mode it guards: an idempotency/no-op match that omits
a field (recargo, source jurisdiction) silently drops the new value — a silent
under-declaration. Making the guard the standing rule keeps every future creating
verb retry-safe by construction, and keeps identities clock-free (advancing the
replayability the determinism work depends on). This is the creating-mutation
companion to `ledger-mutation-returns-uniform-quintet` (the result shape the no-op
rides on), `cli-notices-are-the-only-diagnostic-channel` (the no-op Notice),
`no-silent-under-declaration` (the match must be complete), and
`carried-observations-stamp-their-revision` (identity is content, not clock).

## How

- **Good:** `create_manual_transaction` keys on the clock-free provider id
  `manual:{bucket}:{key}`; a same-key retry with matching content returns the
  existing-row quintet with empty `bucket_event_ids` + an info `Notice`, emitting
  no second `LEDGER_TRANSACTION_CREATED` event and leaving `created_at` unchanged;
  a same-key add whose content differs raises `TransactionValidationError`. The
  idempotency match compares EVERY persisted field (including `recargo_amount` and
  `source_jurisdiction`).
- **Good:** `derive_verification_report_id` / `derive_filing_record_id` fold the
  OUTCOME (revision + status/findings + actor) and drop the timestamp from
  identity; a non-granting verify retry and a re-file of an already-`PRESENTADO`
  revision collapse to the existing record with an info `Notice`; the timestamp
  survives as a non-identity last-seen field.
- **Good:** the keyless `ledger add` path stays `non_idempotent_append` (two
  genuine identical same-day cash movements both persist) and the agent-harness
  contract requires the agent to always pass a stable idempotency key.
- **Bad:** a creating verb whose id folds `now()`/`occurred_at`/`filed_at`, so a
  retry mints a new id and double-writes — the pre-ADR manual-add and
  time-stamped-report defect.
- **Bad:** a guarded no-op whose match omits a persisted field, so a same-key
  retry that changes only that field no-ops and silently drops the new value
  (`no-silent-under-declaration`).
- **Bad:** modelling a deliberately-additive verb as guarded (collapsing genuine
  distinct records) or an idempotent verb as append (double-writing on retry)
  without documenting the choice.

## Source

ADR `2026-06-30-ledger-add-idempotency-adr` (codification candidate), research
`2026-06-30-ledger-add-idempotency-research`, plan
`2026-06-30-ledger-add-idempotency-plan`, close honesty-review audit
`2026-07-01-ledger-add-idempotency-audit`. Promoted per the `vaultspec-codify`
discipline after the pattern held across all three single-subject surfaces
(`ledger add`, `modelo verify`, `modelo file`) plus an independent PASS/GO review
in one full execution cycle. Companion rules:
`ledger-mutation-returns-uniform-quintet`, `cli-single-subject-id-is-positional`,
`cli-notices-are-the-only-diagnostic-channel`, `no-silent-under-declaration`.
