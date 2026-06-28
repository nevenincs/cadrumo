---
tags:
  - "#adr"
  - "#unclassified-state"
date: "2026-04-18"
modified: '2026-04-18'
related:
  - "[[2026-04-18-unclassified-state-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
---

# `unclassified-state` adr: `split-unclassified-and-track-classification-history` | (**status:** `accepted`)

## Problem Statement

Issue `#237` requires every `Transaction` to answer two questions Kent cannot currently answer:

1. *Did the pipeline look at this transaction, and if so, what did it decide?*
2. *What did the pipeline previously decide, and who overrode it?*

Today `BusinessClassification.UNCLASSIFIED` collapses four distinct pipeline states — "never seen", "looked at but undecided", "explicitly skipped", "rejected by validation" — into one value, and every re-classification destroys the prior decision. Kent's review workflow cannot distinguish work-to-do from work-already-done, and cannot audit overrides.

## Considerations

- The catalogue on-disk format currently stores classification as the string literal `"UNCLASSIFIED"`. Kent's existing transactions must load after the split without any manual conversion step.
- Sibling issue `#236` adds `confidence` and `DecisionProvenance` to every decision record. The state split must not preempt that work, and must leave room for future `ClassificationHistory` entries to carry a richer provenance record.
- `TransactionCatalogue` is immutable by contract (`model_config = ConfigDict(strict=True, frozen=True, extra="forbid")`). The history chain must preserve immutability — `set_classification` continues to return a fresh catalogue with a fresh `Transaction`.
- `aeat review` is not yet an installed Typer sub-app. `#237` introduces a minimal `review` group that today owns only `history`; `#204` will extend it with `queue` / `approve` in follow-up work.
- Tests treat `UNCLASSIFIED` as the catalogue default. Factories under `src/aeat/domain/financial/transactions/test_*.py` must be updated to the new default.

## Constraints

- New state values must be member names of `BusinessClassification` so pydantic strict validation continues to guard catalogue boundaries.
- Legacy `"UNCLASSIFIED"` strings loaded from older catalogue JSON must normalise to `NOT_YET_PROCESSED` transparently; no data loss, no destructive write unless Kent explicitly re-saves.
- `business_pct` coupling stays intact — only `MIXED` may carry a percentage. All four new non-classified states must reject `business_pct`.
- History entries must be immutable tuples (`tuple[ClassificationHistoryEntry, ...]`) and survive JSON round-trip.
- The enum value labels are stable public strings — tooling, CLI output, and serialized JSON will consume them. No `str` conversion tricks.
- Error inheritance from `aeat.core.errors.AeatError` is preserved. Logging uses `aeat.core.logging.get_logger(__name__)`.

## Implementation

### Enum split

Replace `BusinessClassification.UNCLASSIFIED` with four explicit states. The classified states (`BUSINESS`, `PERSONAL`, `MIXED`) remain untouched:

```python
class BusinessClassification(StrEnum):
    BUSINESS = "BUSINESS"
    PERSONAL = "PERSONAL"
    MIXED = "MIXED"
    NOT_YET_PROCESSED = "NOT_YET_PROCESSED"
    PROCESSED_UNCLASSIFIED = "PROCESSED_UNCLASSIFIED"
    SKIPPED_BY_RULE = "SKIPPED_BY_RULE"
    FAILED_VALIDATION = "FAILED_VALIDATION"
```

The `UNCLASSIFIED` member is **removed** from the enum. `BusinessClassification("UNCLASSIFIED")` must raise `ValueError` so strict pydantic validation rejects any caller still emitting the legacy literal. The only surviving path for `"UNCLASSIFIED"` is the load-time alias described below.

Add a module-level helper `is_classified(state: BusinessClassification) -> bool` returning `True` for `{BUSINESS, PERSONAL, MIXED}` and `False` for the four pipeline states. The `business_pct` coupling rule becomes: pct is required iff `state is MIXED`; forbidden for every other state.

Call-site inventory — every occurrence of the legacy member is migrated by this PR:

- `src/aeat/domain/financial/transactions/_enums.py` — enum definition.
- `src/aeat/domain/financial/transactions/_models.py:71` — default value flips to `NOT_YET_PROCESSED`.
- `src/aeat/entrypoints/cli/financial/txs.py:30,35,43,90` — CLI help text, `--unclassified` flag semantics (now an alias), and `classify --as` help text listing legal targets drops `UNCLASSIFIED` in favour of the four explicit states plus `BUSINESS/PERSONAL/MIXED`.
- `src/aeat/domain/financial/transactions/test_cli.py:36,115` — factory default + JSON assertion.
- `src/aeat/domain/financial/transactions/test_catalogue.py:56,129` — factory default + before-state assertion.
- `docs/coverage/pipeline.md` — row states flip from ❌ to ✅ for #237.

### Legacy alias

Legacy serialized catalogues store `"UNCLASSIFIED"`. `Transaction._enforce_derived_transaction_id` already coerces string state values into the enum on validation; extend the coercion so `"UNCLASSIFIED"` maps to `BusinessClassification.NOT_YET_PROCESSED` *before* the enum is instantiated. The alias emits a one-line INFO log the first time it triggers per process so Kent knows to re-save.

The alias is advisory, not permanent. It is scheduled for removal at milestone `0.2.0` ("Kent can verify his filings") via a follow-up ADR; until then, the alias is free for loaders and forbidden for writers (the catalogue never emits `"UNCLASSIFIED"` after this PR).

### Default

`Transaction.business_classification` default becomes `BusinessClassification.NOT_YET_PROCESSED`. Catalogues produced by `aeat financial ingest` therefore start in `NOT_YET_PROCESSED` by design — the pipeline has not looked at them yet.

### `ClassificationHistory`

Add a frozen pydantic record. Explicit nullable slots are reserved now for future `#236` (`confidence`, `DecisionProvenance`) so entries written under `#237` remain forward-compatible with `extra="forbid"` validators once the provenance record lands:

```python
class ClassificationHistoryEntry(BaseModel):
    model_config = _STRICT_FROZEN  # strict=True, frozen=True, extra="forbid"

    business_classification: BusinessClassification
    business_pct: Decimal | None = None
    classified_at: datetime
    classified_by: str = Field(min_length=1)
    reason: str = ""
    # Reserved for #236; today every entry emits null. When #236 lands,
    # new entries populate these fields without a schema bump.
    confidence: Decimal | None = None
    provenance: dict[str, object] | None = None
```

`provenance: dict[str, object] | None` is a deliberate placeholder for the future `DecisionProvenance` pydantic record. `#236` will replace the dict with the real type and can do so without invalidating payloads written under this ADR — old payloads carry `None`, which is accepted by `Optional[DecisionProvenance]`. No writer in this PR sets `confidence` or `provenance`; both remain `None` until `#236` ships.

Add `classification_history: tuple[ClassificationHistoryEntry, ...] = ()` on `Transaction`. Every call to `set_classification` appends the *prior* (current) classification to the chain before stamping the new state. The chain is preserved in JSON via pydantic's default tuple serialization; replayed on load via a field validator that rebuilds the tuple from the parsed list.

`set_classification` signature gains `reason: str = ""` so Kent (or a rule author) can annotate overrides; the reason is embedded in the appended history entry, not on the top-level `Transaction`.

Append rule: a new entry is appended on every `set_classification` call **unless** every one of `business_classification`, `business_pct`, `classified_by`, and `reason` is byte-identical to the current head of the chain (or to the current `Transaction` fields when the chain is empty). This guards against trivial repeat calls while preserving every meaningful re-classification — including re-setting the same state with a new `reason` or a new `classified_by` identity.

### CLI surfaces

1. `aeat financial txs list --state <STATE>` — filter by any `BusinessClassification` value. `--state` accepts case-insensitive member names. The existing `--unclassified` flag stays alive and is equivalent to `--state PROCESSED_UNCLASSIFIED` (the Kent success moment); it is marked hidden in help and documented as "deprecated; prefer --state".
2. `aeat financial txs classify <tx> --as <STATE> --pct 0.5 [--reason TEXT]` — `--reason` is new and optional; defaults to `""`. Other semantics unchanged.
3. `aeat review history <tx-id>` — new command in a new `src/aeat/entrypoints/cli/review/` subpackage. Prints one JSON object per history entry plus the current head, oldest first, newest last. `aeat review` is registered at the CLI root app alongside `aeat financial`.

### Migration

No SQLite migration exists for transactions (catalogue persistence is JSON-only). The legacy-alias loader IS the migration. On-disk JSON payloads authored before `#237` that contain `"business_classification": "UNCLASSIFIED"` load successfully; on the next `set_classification` call the payload is rewritten with the new state names and a populated history chain.

### Coverage and tests

Unit tests (`pytest.mark.unit, pytest.mark.domain_financial_input`) cover:
- enum exposes the four new states; `UNCLASSIFIED` is *not* a valid member. Explicit negative test: `BusinessClassification("UNCLASSIFIED")` raises `ValueError`.
- default factory is `NOT_YET_PROCESSED`.
- legacy JSON payload with `"business_classification": "UNCLASSIFIED"` loads to `NOT_YET_PROCESSED` transparently.
- `set_classification` appends exactly one history entry per meaningful transition; does not append when every relevant field is byte-identical to the current head.
- `set_classification` appends when only `reason` changes, and when only `classified_by` changes.
- `aeat financial txs list --state BUSINESS` filters correctly.
- `aeat financial txs list --unclassified` behaves as alias for `--state PROCESSED_UNCLASSIFIED`.
- `aeat review history <tx-id>` prints the chain in oldest-first order and includes the current head last.
- `business_pct` coupling rejects pct for every non-MIXED state including the four new ones.
- `ClassificationHistoryEntry` round-trips through JSON with `confidence=None` and `provenance=None` present.

The coverage matrix `docs/coverage/pipeline.md` rows that reference `#237` flip from ❌ to ✅.

## Rationale

- Splitting the enum — rather than overlaying a second field — keeps existing strict-pydantic guarantees and avoids ambiguous combinations. The enum alone answers "what does Kent see?" at a glance.
- Keeping `classified_by` as the provenance-of-record (rather than demanding a full `DecisionProvenance` record up-front) avoids blocking `#237` on `#236`. The history entry is already forward-compatible; `#236` can extend it by adding optional provenance fields.
- The loader-side alias is a zero-config migration: no migration CLI, no Alembic script, no writer that emits legacy strings. Aligns with the ADR `2026-04-17-path-handling-safety-adr.md` principle of "no destructive state changes without explicit Kent action".
- An inline `ClassificationHistory` tuple is the simplest thing that preserves provenance, round-trips through JSON, and keeps `TransactionCatalogue` a self-describing artifact. The future append-only `var/decisions/YYYY-MM.jsonl` (EPIC C14d) is orthogonal — it records the *event stream* whereas the tuple records the *per-transaction trail*.
- A new `aeat review` sub-app (instead of stuffing `history` under `aeat financial txs`) matches the roadmap: `#204` C4l owns the unified review queue. Planting the Typer root now avoids a future rename.

## Consequences

- Any caller that pattern-matches on `BusinessClassification.UNCLASSIFIED` breaks at import time — intentional. Call sites must choose between the four new states. Every call site in the repository is enumerated in the Implementation → Enum split → Call-site inventory and migrated by this PR; none are left as TODOs.
- Kent's existing catalogues continue to work; they silently normalise on first load and migrate on first write.
- `set_classification` gains a `reason` keyword. No call site in the repository passes `reason` today; it defaults to `""` so behaviour is unchanged for existing invocations.
- `aeat review` becomes a new top-level CLI command group. Future `#204` work (queue, approve, bulk reject) lands inside this group.
- The legacy `--unclassified` flag is retained for one release cycle; it will be removed in the milestone `0.2.0` cleanup.
- Coverage floor (60% on `src/aeat` per `just test-cov`) remains; the new code ships with colocated unit tests.
- Alembic / SQLite migration is explicitly out of scope — no SQLite store exists for transactions on `main`.
