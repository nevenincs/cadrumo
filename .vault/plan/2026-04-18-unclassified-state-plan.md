---
tags:
  - "#plan"
  - "#unclassified-state"
date: "2026-04-18"
modified: '2026-04-18'
related:
  - "[[2026-04-18-unclassified-state-adr]]"
  - "[[2026-04-18-unclassified-state-research]]"
  - "[[2026-04-14-transaction-catalogue-adr]]"
---

# `unclassified-state` plan: `split-unclassified-and-track-classification-history` | (**status:** `accepted`)

Executes `[[2026-04-18-unclassified-state-adr]]` against issue `#237`. Single phase; every step is mechanical with a colocated test.

## Phase 1 — implementation

### Step 1 — split the `BusinessClassification` enum

Edit `src/aeat/domain/financial/transactions/_enums.py`:

- Remove the `UNCLASSIFIED = "UNCLASSIFIED"` member.
- Add `NOT_YET_PROCESSED`, `PROCESSED_UNCLASSIFIED`, `SKIPPED_BY_RULE`, `FAILED_VALIDATION`.
- Add `CLASSIFIED_STATES: frozenset[BusinessClassification] = frozenset({BUSINESS, PERSONAL, MIXED})` and `is_classified(state) -> bool`.

### Step 2 — introduce `ClassificationHistoryEntry` and hook it into `Transaction`

Edit `src/aeat/domain/financial/transactions/_models.py`:

- Define `ClassificationHistoryEntry` frozen pydantic model with `business_classification`, `business_pct`, `classified_at`, `classified_by`, `reason`, `confidence=None`, `provenance=None`. `model_config = _STRICT_FROZEN`.
- Add `classification_history: tuple[ClassificationHistoryEntry, ...] = ()` on `Transaction`.
- Add a `field_validator(mode="before")` on `classification_history` that rebuilds a tuple from any sequence.
- Change `Transaction.business_classification` default to `BusinessClassification.NOT_YET_PROCESSED`.
- Extend the `_enforce_derived_transaction_id` pre-validator: when `business_classification` arrives as the string `"UNCLASSIFIED"`, normalise to `BusinessClassification.NOT_YET_PROCESSED` and log one INFO line per process via `aeat.core.logging.get_logger(__name__)`. Use a module-level `_ALIASED_ONCE = False` guard to rate-limit.
- Update `_validate_business_pct` so `pct is not None` is allowed only for `MIXED`; every other state (including the four new ones) rejects a non-`None` pct.
- Export `ClassificationHistoryEntry` from `src/aeat/domain/financial/transactions/__init__.py`.

### Step 3 — extend `set_classification` to append history

Edit `src/aeat/domain/financial/transactions/_service.py`:

- Add `reason: str = ""` keyword to `set_classification`.
- Before rebuilding the transaction, compute `head = transaction.classification_history[-1] if transaction.classification_history else ClassificationHistoryEntry(business_classification=transaction.business_classification, business_pct=transaction.business_pct, classified_at=transaction.classified_at or datetime.now(UTC), classified_by=transaction.classified_by, reason="")` — synthesising a head from current state when history is empty.
- Compare head with the proposed new entry. If `(state, pct, classified_by, reason)` are all byte-identical, skip the append.
- Otherwise prepend the synthesised head (when chain empty) or the existing chain, then append the new entry.

A minimal compare helper `_entry_signature(entry_or_kwargs) -> tuple` keeps the comparison inline and typed.

### Step 4 — CLI `aeat financial txs list --state`

Edit `src/aeat/entrypoints/cli/financial/txs.py`:

- Add `state: BusinessClassification | None = typer.Option(None, "--state", case_sensitive=False, help="Filter to one BusinessClassification value.")` to `list_cmd`.
- Keep `--unclassified: bool` but mark it `hidden=True` and update its help text to `"Deprecated; alias for --state PROCESSED_UNCLASSIFIED."`.
- Resolve effective filter: `--state` wins; when only `--unclassified` is passed, treat as `--state PROCESSED_UNCLASSIFIED`; reject the combination (`--state` + `--unclassified` together) with exit 2.
- Filter predicate: `transaction.business_classification is effective_state` when an effective state is set.

### Step 5 — CLI `aeat financial txs classify --reason`

Edit `src/aeat/entrypoints/cli/financial/txs.py`:

- Add `reason: str = typer.Option("", "--reason", help="Why Kent (or a rule) classified this transaction.")` to `classify_cmd`.
- Pass it through to `set_classification(..., reason=reason)`.
- Update the `--as` help text to list the four new values alongside `BUSINESS/PERSONAL/MIXED`.
- Update the `list` command docstring and help to drop the `UNCLASSIFIED` wording.

### Step 6 — new `aeat review history` sub-app

Create `src/aeat/entrypoints/cli/review/__init__.py`:

```
src/aeat/entrypoints/cli/review/
    __init__.py      # Typer sub-app plus registration helper
    history.py       # history command
    test_review.py   # colocated unit tests
```

- `history.py` exposes `history_cmd(transaction_id: str)` that loads the configured catalogue (via the shared helper used by `aeat financial txs`, extracted to `src/aeat/entrypoints/cli/financial/_catalogue.py` so both CLIs call the same loader) and prints a JSON list of history entries + the current head, oldest first. Missing transactions exit 2 with a clear message.
- Wire `app.add_typer(review_module.app, name="review", help="Pipeline decision review surfaces (#237/#232/#204).")` in `src/aeat/entrypoints/cli/__init__.py`.
- Relative-imports mandate (#162): every import inside `src/aeat/entrypoints/cli/review/` uses `.history`, `..financial._catalogue`, `...financial.transactions`, etc. No absolute `aeat.*` imports; the `scripts/check_relative_imports.py` guard enforces this in CI.

**Scope note** — the `_catalogue_path` / `_load_catalogue_required` helpers already live in `src/aeat/entrypoints/cli/financial/txs.py` and need to be shared by the new `review` command. The extraction to `src/aeat/entrypoints/cli/financial/_catalogue.py` is a pure code move, no behaviour change, and is called out explicitly so it does not surprise the code reviewer as an un-ADR'd refactor.

### Step 7 — tests

Update existing tests and add new ones; all `pytest.mark.unit, pytest.mark.domain_financial_input` at the module level:

- `src/aeat/domain/financial/transactions/test_catalogue.py` — replace every `BusinessClassification.UNCLASSIFIED` with `BusinessClassification.NOT_YET_PROCESSED`; add a test that `set_classification` appends exactly one history entry; add a test that re-setting the same triple (`state`, `pct`, `classified_by`, `reason`) does not append; add a test that changing only `reason` does append; add a test that legacy `"UNCLASSIFIED"` JSON loads to `NOT_YET_PROCESSED`.
- `src/aeat/domain/financial/transactions/test_cli.py` — replace `UNCLASSIFIED` string / enum; update the `test_financial_txs_show_emits_json_payload` assertion from `"UNCLASSIFIED"` to `"NOT_YET_PROCESSED"`; add tests for `--state`, for `--state + --unclassified` rejection, and for `classify --reason`.
- `src/aeat/domain/financial/transactions/test_models.py` — keep passing; add a negative test `BusinessClassification("UNCLASSIFIED")` raises `ValueError`; add `ClassificationHistoryEntry` JSON round-trip.
- `src/aeat/entrypoints/cli/review/test_review.py` — new. Exercise `aeat review history` on a seeded catalogue across three classifications (e.g. initial `NOT_YET_PROCESSED` → manual `BUSINESS` → override `MIXED`), asserting oldest-first order and the current head appended last.
- Add a dedicated **four-state observability** test in `test_cli.py` that seeds one catalogue with at least one transaction in each of `NOT_YET_PROCESSED`, `PROCESSED_UNCLASSIFIED`, `SKIPPED_BY_RULE`, `FAILED_VALIDATION`, and asserts every `--state <VALUE>` filter returns exactly the expected subset. This is the literal translation of the Kent success moment from `#237`.
- Add a test in `test_catalogue.py` that `set_classification` does **not** append when only `classified_at` changes between two calls with identical `(state, pct, classified_by, reason)` — the byte-identical skip rule must ignore timestamp drift.

### Step 8 — documentation

- `docs/coverage/pipeline.md` — flip the two `#237` rows from ❌ to ✅; bump updated-at line if present.
- `docs/coverage/kent-capabilities.md` — mark the "Kent can distinguish pipeline-skipped from not-yet-seen" row as shipped.

### Step 9 — verify

Run the canonical `just` recipes from `justfile`:

- `just lint` (runs `ruff check .` plus `scripts/check_relative_imports.py` for the #162 mandate)
- `just typecheck` (`uv run ty check src tests`)
- `just fmt` with `--check` locally (CI runs it strict)
- `just test` (full unit suite — `pyproject.toml` `addopts` pins `-m 'unit'`)
- `just test-cov` (reconfirms the 60% floor on `src/aeat`)

Any failure: stop, diagnose, fix at root cause. Do not insert skips or mocks.

## Risks

- **Pydantic v2 tuple fields** — pydantic serializes tuples to lists in JSON. The existing `TransactionCatalogue._serialize_transactions` handles the map; tuple fields round-trip natively, but the `field_validator(mode="before")` on `classification_history` must accept both `tuple` and `list` inputs.
- **Legacy alias correctness** — the pre-validator runs before field validators, so string coercion must happen there. Guarded against re-entry when `data` is already a `Transaction` instance.
- **Enum coercion by Typer** — `BusinessClassification | None` on a `typer.Option` default works out of the box for StrEnum in Typer 0.20.0; double-check with the smoke test.
- **Catalogue loader sharing** — extracting `_catalogue_path` / `_load_catalogue_required` into `src/aeat/entrypoints/cli/financial/_catalogue.py` is a pure move. Imports in `txs.py` and the new review command both read from it.

## Definition of done

- Every file in the Call-site inventory is updated; no occurrence of `UNCLASSIFIED` remains in `src/aeat/domain/financial/transactions/` or `src/aeat/entrypoints/cli/financial/` outside the legacy-alias test.
- `aeat financial txs list --state PROCESSED_UNCLASSIFIED` and `aeat review history <tx>` behave per the Kent success moment.
- All commands used by `just test`, `just test-cov`, and `just lint` pass locally.
- The PR body links `#237`, references this plan, and attaches the "Kent capability" success moment verbatim from the issue.
