---
tags:
  - "#adr"
  - "#unclassified-state"
date: '2026-04-18'
modified: '2026-07-17'
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

- The catalogue on-disk format stores only current `BusinessClassification`
  values. The retired `"UNCLASSIFIED"` token is outside the accepted format.
- Classification history carries the canonical typed `DecisionProvenance`
  record and optional confidence directly; a bare dictionary is not accepted.
- `TransactionCatalogue` is immutable by contract (`model_config = ConfigDict(strict=True, frozen=True, extra="forbid")`). The history chain must preserve immutability — `set_classification` continues to return a fresh catalogue with a fresh `Transaction`.
- `aeat review history` is the operator surface for the immutable decision
  chain.
- Tests construct current explicit states and prove the retired literal is
  rejected.

## Constraints

- New state values must be member names of `BusinessClassification` so pydantic strict validation continues to guard catalogue boundaries.
- Unknown or retired classification strings are rejected at the catalogue
  boundary; readers do not translate them into current states.
- `business_pct` coupling stays intact — only `MIXED` may carry a percentage. All four new non-classified states must reject `business_pct`.
- History entries must be immutable tuples (`tuple[ClassificationHistoryEntry, ...]`) and survive JSON round-trip.
- The enum value labels are stable public strings — tooling, CLI output, and serialized JSON will consume them. No `str` conversion tricks.
- Error inheritance from `cadrumo.core.errors.CadrumoError` is preserved. Logging uses `cadrumo.core.logging.get_logger(__name__)`.

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

The `UNCLASSIFIED` member is **removed** from the enum.
`BusinessClassification("UNCLASSIFIED")` raises `ValueError`; no load-time
alias or CLI alias preserves the retired literal.

Add a module-level helper `is_classified(state: BusinessClassification) -> bool` returning `True` for `{BUSINESS, PERSONAL, MIXED}` and `False` for the four pipeline states. The `business_pct` coupling rule becomes: pct is required iff `state is MIXED`; forbidden for every other state.

Current call-site authority:

- `src/cadrumo/domain/transactions/_enums.py` — enum definition.
- `src/cadrumo/domain/transactions/_models.py:71` — default value flips to `NOT_YET_PROCESSED`.
- `src/cadrumo/entrypoints/cli/financial/txs.py` — CLI help and `classify
  --as` list only the explicit current states; no retired option remains.
- `src/cadrumo/domain/transactions/test_cli.py:36,115` — factory default + JSON assertion.
- `src/cadrumo/domain/transactions/test_catalogue.py:56,129` — factory default + before-state assertion.
- `docs/coverage/pipeline.md` — row states flip from ❌ to ✅ for #237.

### Canonical state

Serialized catalogues use `"NOT_YET_PROCESSED"` directly. The retired
`"UNCLASSIFIED"` token is not accepted, translated, logged, or preserved.

### Default

`Transaction.business_classification` default becomes `BusinessClassification.NOT_YET_PROCESSED`. Catalogues produced by `aeat financial ingest` therefore start in `NOT_YET_PROCESSED` by design — the pipeline has not looked at them yet.

### `ClassificationHistory`

`ClassificationHistoryEntry` is a frozen pydantic record with typed
provenance:

```python
class ClassificationHistoryEntry(BaseModel):
    model_config = _STRICT_FROZEN  # strict=True, frozen=True, extra="forbid"

    business_classification: BusinessClassification
    business_pct: Decimal | None = None
    classified_at: datetime
    classified_by: str = Field(min_length=1)
    reason: str = ""
    confidence: Decimal | None = None
    provenance: DecisionProvenance | None = None
```

`DecisionProvenance` carries the deciding actor, aware timestamp, reason,
optional confidence, and manual-override signal. Strict validation rejects a
malformed or dictionary-widened provenance payload.

Add `classification_history: tuple[ClassificationHistoryEntry, ...] = ()` on `Transaction`. Every call to `set_classification` appends the *prior* (current) classification to the chain before stamping the new state. The chain is preserved in JSON via pydantic's default tuple serialization; replayed on load via a field validator that rebuilds the tuple from the parsed list.

`set_classification` signature gains `reason: str = ""` so Kent (or a rule author) can annotate overrides; the reason is embedded in the appended history entry, not on the top-level `Transaction`.

Append rule: a new entry is appended on every `set_classification` call **unless** every one of `business_classification`, `business_pct`, `classified_by`, and `reason` is byte-identical to the current head of the chain (or to the current `Transaction` fields when the chain is empty). This guards against trivial repeat calls while preserving every meaningful re-classification — including re-setting the same state with a new `reason` or a new `classified_by` identity.

### CLI surfaces

1. `aeat financial txs list --state <STATE>` — filter by any `BusinessClassification` value. `--state` accepts case-insensitive member names. The retired `--unclassified` flag is absent.
2. `aeat financial txs classify <tx> --as <STATE> --pct 0.5 [--reason TEXT]` — `--reason` is new and optional; defaults to `""`. Other semantics unchanged.
3. `aeat review history <tx-id>` — new command in a new `src/cadrumo/entrypoints/cli/review/` subpackage. Prints one JSON object per history entry plus the current head, oldest first, newest last. `aeat review` is registered at the CLI root app alongside `aeat financial`.

### Format authority

Transactions use the current JSON catalogue shape directly. There is no
compatibility loader or state rewrite: a payload containing the retired token
is invalid and must be corrected at its source before import.

### Coverage and tests

Unit tests (`pytest.mark.unit, pytest.mark.domain_financial_input`) cover:
- enum exposes the four new states; `UNCLASSIFIED` is *not* a valid member. Explicit negative test: `BusinessClassification("UNCLASSIFIED")` raises `ValueError`.
- default factory is `NOT_YET_PROCESSED`.
- retired JSON literals are rejected by the real catalogue loader.
- `set_classification` appends exactly one history entry per meaningful transition; does not append when every relevant field is byte-identical to the current head.
- `set_classification` appends when only `reason` changes, and when only `classified_by` changes.
- `aeat financial txs list --state BUSINESS` filters correctly.
- the retired `--unclassified` option is absent; callers use `--state` with an
  explicit current state.
- `aeat review history <tx-id>` prints the chain in oldest-first order and includes the current head last.
- `business_pct` coupling rejects pct for every non-MIXED state including the four new ones.
- `ClassificationHistoryEntry` round-trips both empty optional provenance and
  a populated typed `DecisionProvenance` through JSON.

The coverage matrix `docs/coverage/pipeline.md` rows that reference `#237` flip from ❌ to ✅.

## Rationale

- Splitting the enum — rather than overlaying a second field — keeps existing strict-pydantic guarantees and avoids ambiguous combinations. The enum alone answers "what does Kent see?" at a glance.
- `classified_by` remains the concise decision-source label while the typed
  `DecisionProvenance` carries the complete optional audit context; the two
  fields are complementary rather than alternate schemas.
- Rejecting retired literals keeps classification state explicit and prevents
  a reader from silently changing the meaning of persisted financial data.
- An inline `ClassificationHistory` tuple is the simplest thing that preserves provenance, round-trips through JSON, and keeps `TransactionCatalogue` a self-describing artifact. The future append-only `var/decisions/YYYY-MM.jsonl` (EPIC C14d) is orthogonal — it records the *event stream* whereas the tuple records the *per-transaction trail*.
- A new `aeat review` sub-app (instead of stuffing `history` under `aeat financial txs`) matches the roadmap: `#204` C4l owns the unified review queue. Planting the Typer root now avoids a future rename.

## Consequences

- Any caller that pattern-matches on `BusinessClassification.UNCLASSIFIED` breaks at import time — intentional. Call sites must choose between the four new states. Every call site in the repository is enumerated in the Implementation → Enum split → Call-site inventory and migrated by this PR; none are left as TODOs.
- Current catalogues continue to round-trip exactly; non-current payloads are
  rejected rather than silently normalised.
- `set_classification` gains a `reason` keyword. No call site in the repository passes `reason` today; it defaults to `""` so behaviour is unchanged for existing invocations.
- `aeat review` becomes a new top-level CLI command group. Future `#204` work (queue, approve, bulk reject) lands inside this group.
- The retired `--unclassified` flag is absent.
- Coverage floor (60% on `src/cadrumo` per `just test-cov`) remains; the new code ships with colocated unit tests.
- Alembic / SQLite migration is explicitly out of scope — no SQLite store exists for transactions on `main`.
