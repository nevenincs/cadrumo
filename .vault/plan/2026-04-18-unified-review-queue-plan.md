---
tags:
  - "#plan"
  - "#unified-review-queue"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-18-unified-review-queue-adr]]"
  - "[[2026-04-18-unified-review-queue-research]]"
---

# unified-review-queue plan

Implement the read-only `aeat.application.review` aggregator + `aeat review queue` CLI per `[[2026-04-18-unified-review-queue-adr]]`. Closes Kent's wall 32.

## guiding constraints

- **Parallel-safe.** New subpackage + new CLI sub-app + one wiring line in `src/aeat/entrypoints/cli/__init__.py`. Zero edits to existing models, enums, repositories, or CLIs in `src/aeat/{financial,sync,inbox,filing}/`.
- **Read-only.** Every adapter loads from disk and emits `tuple[ReviewItem, ...]`; no mutation of source state.
- **Pydantic v2 boundary discipline.** `ReviewItem` is a `Annotated[..., Field(discriminator="kind")]` strict frozen union; per-kind models are `ConfigDict(strict=True, frozen=True, extra="forbid")`.
- **Closed enums everywhere** for `--kind`, `--state`, `--format`, `severity`.
- **Trilingual `Translatable`** for `summary` content. English authoritative for the dev-facing summaries we author here.
- **Pytest-only.** Markers per `[[2026-04-17-pytest-markers-adr]]`: model / adapter / aggregator tests carry `[pytest.mark.unit, pytest.mark.domain_local_state]`; CLI tests carry `[pytest.mark.unit, pytest.mark.domain_infra]` (matches `cli/sync/test_cli.py` precedent and the marker description in `pyproject.toml`). Tests colocate with the module (Rust style).
- **Relative imports** inside `src/aeat/`. **Cross-subpackage imports use the subpackage root only** — never `._service` or other underscored modules. Concretely: `from ..financial.transactions import load_transactions, TransactionCatalogue, BusinessClassification`, `from ..financial.invoices import load_invoices, InvoiceCatalogue, PaymentStatus`, `from ..sync import JsonFileDivergenceRepository, DivergenceRecord, DivergenceClassification, ResolutionState`, `from ..inbox import Inbox, NotificacionPriority`, `from ..filing import FilingDraft, FilingDraftStatus, FilingFindingSeverity, FilingValidationFinding`.
- **No `aeat.core.errors.AeatError` skipping** — all domain errors inherit from it.

## file layout

New files (all under `src/aeat/`):

```
src/aeat/application/review/
  __init__.py            # public re-exports
  _enums.py              # ReviewItemKind, ReviewSeverity, ReviewState, ReviewFormat
  _errors.py             # ReviewError(AeatError)
  _models.py             # per-kind models + ReviewItem discriminated union
  _adapters.py           # five adapter functions, severity tables
  _aggregator.py         # ReviewQueue.collect(...)
  test_models.py         # pydantic shape + invariants (Rust-style colocated)
  test_adapters.py       # per-adapter pending-predicate + missing-source paths
  test_aggregator.py     # end-to-end across all five sources

src/aeat/entrypoints/cli/review/
  __init__.py            # typer sub-app
  queue.py               # `aeat review queue` command
  test_cli.py            # CliRunner happy path + flag combinations
```

Modified files:

```
src/aeat/entrypoints/cli/__init__.py     # one import + one app.add_typer line
```

Documentation:

```
docs/coverage/kent-capabilities.md   # mark "Kent can see everything pending in one place" → done
```

(No new env vars; no `.env.example` changes.)

## phases

### Phase 1 — module skeleton + enums + errors

1.  Create `src/aeat/application/review/_enums.py`:
    -   `ReviewItemKind(StrEnum)`: `TRANSACTION`, `INVOICE`, `DIVERGENCE`, `FINDING`, `INBOX`. Future-only members (`CLASSIFICATION`, `APPROVAL_STALE`) are documented in the module docstring as reserved per ADR D5 but **not** added until their source records exist.
    -   `ReviewSeverity(StrEnum)`: `CRITICAL`, `HIGH`, `NORMAL`, `INFO`. Add `__lt__` + `__le__` to support `sorted()` with `reverse=True` so CRITICAL is "greatest" — implement via a static rank table.
    -   `ReviewState(StrEnum)`: `PENDING`, `ALL`.
    -   `ReviewFormat(StrEnum)`: `TABLE`, `JSON`.
2.  Create `src/aeat/application/review/_errors.py`:
    -   `ReviewError(AeatError)` (inherits from `aeat.core.errors.AeatError`).
    -   `ReviewSourceLoadError(ReviewError)` raised when a source file is present but unparseable.
    -   `ReviewKindReservedError(ReviewError)` raised when the CLI sees a reserved-but-not-implemented kind token (`classification`, `approval-stale`).
3.  Create `src/aeat/application/review/__init__.py`: re-export the public surface listed in `__all__`.

### Phase 2 — `ReviewItem` discriminated union

4.  Create `src/aeat/application/review/_models.py`. Per-kind models, each strict frozen, all sharing the unified field set:
    ```python
    class _ReviewItemBase(BaseModel):
        model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
        item_id: str = Field(min_length=1)               # opaque, source-derived
        modelo: str | None                                # None when no modelo concept applies
        severity: ReviewSeverity
        summary: Translatable                             # short trilingual line
        drill_command: str = Field(min_length=1)          # the literal CLI to act
        since: datetime                                   # when the item entered pending
    ```
    Concrete members:
    -   `TransactionReviewItem(_ReviewItemBase)`: `kind: Literal[ReviewItemKind.TRANSACTION]`, `source: Transaction`.
    -   `InvoiceReviewItem(_ReviewItemBase)`: `kind: Literal[ReviewItemKind.INVOICE]`, `source: Invoice`.
    -   `DivergenceReviewItem(_ReviewItemBase)`: `kind: Literal[ReviewItemKind.DIVERGENCE]`, `source: DivergenceRecord`.
    -   `FindingReviewItem(_ReviewItemBase)`: `kind: Literal[ReviewItemKind.FINDING]`, `source: FilingValidationFinding | None` (None for the "no findings yet" placeholder row), `draft_id: str`, `draft_path: str`.
    -   `InboxReviewItem(_ReviewItemBase)`: `kind: Literal[ReviewItemKind.INBOX]`, `source: Notificacion`.
    -   `ReviewItem = Annotated[TransactionReviewItem | InvoiceReviewItem | DivergenceReviewItem | FindingReviewItem | InboxReviewItem, Field(discriminator="kind")]`.

5.  Create `test_models.py`: assert each per-kind model rejects an empty `item_id`, requires `since` to be timezone-aware, and round-trips through `model_dump_json` → `model_validate_json` preserving the discriminator.

### Phase 3 — five source adapters

6.  Create `src/aeat/application/review/_adapters.py`. Pure functions; each takes a `Settings` and returns `tuple[ReviewItem, ...]`. Pre-load helpers accept already-loaded sources for testability.

    Implementation order (lowest dependency first):

    1.  `transactions_pending(settings) -> tuple[TransactionReviewItem, ...]`
        -   Path: `settings.aeat_financial_txs_dir / "transactions.json"` (matches `cli/financial/txs.py:21`).
        -   Missing file → `()`.
        -   Predicate (post-#237 state model): `not is_classified(t.business_classification)` AND `t.business_classification is not BusinessClassification.SKIPPED_BY_RULE`. Severity per first-match-wins table: NOT_YET_PROCESSED → NORMAL, PROCESSED_UNCLASSIFIED → HIGH, FAILED_VALIDATION → CRITICAL.
        -   Severity: NORMAL (per D5 transactions table).
        -   `item_id`: `t.transaction_id`.
        -   `since`: `t.classified_at` if not None, else `datetime.combine(t.raw.value_date or t.raw.booked_date, time.min, tzinfo=UTC)`.
        -   `modelo`: `None` (transactions are not modelo-bound).
        -   `summary` (en): `f"{t.direction.value} {t.raw.amount} {t.raw.currency}: {t.raw.description[:80]}"` plus es / hu translations of the same shape.
        -   `drill_command`: `f"aeat financial txs classify {t.transaction_id} --as ..."`.

    2.  `invoices_pending(settings) -> tuple[InvoiceReviewItem, ...]`
        -   Path: `settings.aeat_invoices_dir / "invoices.json"` (matches `cli/financial/invoices.py:30`).
        -   Missing file → `()`.
        -   Predicate (first-match-wins per D5; uses the live `PaymentStatus` enum: `PAID`, `PENDING`, `PARTIALLY_PAID`, `OVERDUE`, `CANCELLED`):
            ```python
            if invoice.linked_transaction_ids == ():            severity = HIGH; reason="unmatched"
            elif invoice.payment_status is OVERDUE:             severity = HIGH; reason="overdue"
            elif invoice.payment_status is PENDING:             severity = NORMAL; reason="payment-pending"
            elif invoice.payment_status is PARTIALLY_PAID:      severity = NORMAL; reason="partially-paid"
            else:                                                skip   # PAID / CANCELLED never enter the queue
            ```
        -   `item_id`: `invoice.invoice_id`.
        -   `since`: `datetime.combine(invoice.issued_at, time.min, tzinfo=UTC)`.
        -   `modelo`: `None`.
        -   `summary`: includes counterparty, grand_total, currency, and reason token.
        -   `drill_command`: `f"aeat financial invoices show {invoice.invoice_id}"`.

    3.  `divergences_pending(settings) -> tuple[DivergenceReviewItem, ...]`
        -   Loaded via `JsonFileDivergenceRepository(settings.aeat_sync_divergence_file_dir).list()`.
        -   `JsonFileDivergenceRepository.__init__` calls `mkdir(parents=True, exist_ok=True)` — safe under missing-dir.
        -   Predicate: `record.resolution_state is ResolutionState.PENDING`.
        -   Severity (first-match-wins per D5):
            ```python
            BREAKING / SUSPICIOUS  → CRITICAL
            ADDITIVE  / BENIGN     → NORMAL
            ```
        -   `item_id`: `record.record_id`.
        -   `since`: `record.detected_at`.
        -   `modelo`: `str(record.modelo) if record.modelo else None`.
        -   `summary`: `f"[{record.classification.value}] {record.payload.kind.value}"`.
        -   `drill_command`: `f"aeat sync show-divergence {record.record_id}"`.

    4.  `drafts_pending(settings) -> tuple[FindingReviewItem, ...]`
        -   Iterate `Path(settings.aeat_drafts_dir).glob("*.json")`. Missing dir → `()`.
        -   For each path, attempt `FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))`. On `ValidationError`, log a warning and skip (matches `cli/filing/__init__.py:339` behaviour).
        -   For each draft:
            -   For each `finding` in `draft.findings`, emit one `FindingReviewItem` with severity per D5:
                ```python
                ERROR    → CRITICAL
                WARNING  → HIGH
                INFO     → INFO
                ```
            -   If `draft.findings == ()` and `draft.status in {FilingDraftStatus.DRAFT, FilingDraftStatus.VALIDATED}`, emit a single placeholder `FindingReviewItem` with `source=None`, severity NORMAL, summary "draft not ready to submit".
        -   Dedup invariant per D2: `(draft.draft_id, finding.code, finding.casilla_id)` triple. Within a single draft this triple is unique by virtue of the validator's logic; defensive dedup is added in the adapter as a safety net using a `set` of seen triples.
        -   `item_id`: `f"{draft.draft_id}:{finding.code}:{finding.casilla_id or '-'}"` — stable + unique.
        -   `since`: `draft.updated_at`.
        -   `modelo`: `draft.modelo`.
        -   `summary`: `finding.message["en"]` if available, else first-available language, prefixed with `[casilla {finding.casilla_id}]` when not None.
        -   `drill_command`: `f"aeat filing show {path} --findings-only"`.

    5.  `inbox_pending(settings) -> tuple[InboxReviewItem, ...]`
        -   Path: `settings.aeat_inbox_dir / "inbox.json"`.
        -   Missing file → `()`. Read directly with `Inbox.model_validate_json(path.read_text(encoding="utf-8"))` — no `InboxFetcher`, no `NotificacionSource` required (ADR D2 explicit).
        -   Predicate: `n.acknowledged_at is None`.
        -   Severity (first-match-wins per D5):
            ```python
            CRITICAL                                                              → CRITICAL
            HIGH OR (appeal_deadline ≤ today + AEAT_INBOX_ALERT_LEAD_DAYS)        → HIGH
            NORMAL                                                                → NORMAL
            INFO                                                                  → INFO
            ```
        -   `item_id`: `n.notificacion_id`.
        -   `since`: `n.received_at`.
        -   `modelo`: `n.references_modelo`.
        -   `summary`: `n.subject["en"]` if present, else first-available language, prefixed with `[{n.kind.value}]` and `[deadline {n.appeal_deadline}]` when set.
        -   `drill_command`: `f"aeat inbox show {n.notificacion_id}"`.

7.  Create `test_adapters.py`. One test per adapter:
    -   Pending-predicate happy path: build a synthetic source on `tmp_path`, point a fresh `Settings(_env_file=None, **{...path overrides...})` at it, call the adapter, assert exact output.
    -   Missing-source path: do NOT create the file/dir, assert `() == adapter(settings)`.
    -   Severity table: parametric test that builds the source with each input state and asserts the resulting severity.
    -   Inbox lead-window: parametric `appeal_deadline` ∈ {today, today+8d}; assert HIGH only inside window.
    -   Drafts dedup: build a draft with three identical-code findings (only achievable via constructed JSON, since the validator does not produce duplicates) and assert the adapter dedups to one row.
    -   Drafts placeholder: build a draft with `findings == ()` and `status == FilingDraftStatus.VALIDATED`; assert exactly one row with `source is None`.

### Phase 4 — aggregator

8.  Create `src/aeat/application/review/_aggregator.py`:
    ```python
    class ReviewQueue:
        @staticmethod
        def collect(
            settings: Settings,
            *,
            kinds: frozenset[ReviewItemKind] | None = None,
            modelo: str | None = None,
            state: ReviewState = ReviewState.PENDING,
        ) -> tuple[ReviewItem, ...]: ...
    ```
    -   Calls every adapter; concatenates their output.
    -   Filters by `kinds` (None → all) and `modelo` (None → no filter; when set, items with `modelo is None` are excluded).
    -   `state == ALL` is reserved for a future "show resolved too" mode and **today is identical to PENDING** because adapters only emit pending items. The flag is wired so the CLI surface is forward-compatible without breaking changes.
    -   Sort key: `(-_severity_rank(item.severity), item.since, item.item_id)` so highest severity, oldest first, deterministic.
9.  Create `test_aggregator.py`: build five mini-sources on `tmp_path` with one pending item each (one transaction NOT_YET_PROCESSED, one invoice unmatched, one divergence PENDING + BREAKING, one draft with one ERROR finding, one notification with priority CRITICAL); assert the aggregator returns exactly five items, sort order is severity-desc-then-since, and `kinds=frozenset({DIVERGENCE, INBOX})` returns exactly two items.

### Phase 5 — CLI surface

10. Create `src/aeat/entrypoints/cli/review/__init__.py`:
    ```python
    app = typer.Typer(name="review", no_args_is_help=True, help="Unified review queue (#232).")
    app.command(name="queue", help="...")(queue_cmd)
    ```
11. Create `src/aeat/entrypoints/cli/review/queue.py` implementing `queue_cmd`:
    -   Flags:
        -   `--kind` (`list[str] | None`, repeatable): translate each token to `ReviewItemKind`. Reject `classification` and `approval-stale` with `ReviewKindReservedError` and a one-line stderr message naming the blocking issue. Reject any other unknown token with `typer.BadParameter`.
        -   `--state` (`ReviewState = ReviewState.PENDING`).
        -   `--modelo` (`str | None`).
        -   `--format` (`ReviewFormat = ReviewFormat.TABLE`).
    -   Calls `ReviewQueue.collect(...)`.
    -   `TABLE` mode: `rich.table.Table(title="review queue", header_style="bold")` with columns `kind`, `id`, `modelo`, `severity` (color-coded: CRITICAL red, HIGH yellow, NORMAL default, INFO dim), `summary`, `since` (relative: "3d ago"), `drill →`. Footer line: `[{N} item(s) — {K} kind(s)]`.
    -   `JSON` mode: `typer.echo(json.dumps([item.model_dump(mode="json") for item in items], indent=2, default=str))`.
    -   Empty result: a single `[dim]No pending review items.[/dim]` line for TABLE; `[]` for JSON.
12. Wire the sub-app into `src/aeat/entrypoints/cli/__init__.py`:
    ```python
    from . import review as review_module    # alongside existing imports
    ...
    app.add_typer(review_module.app, name="review", help="Unified review queue across the pipeline (#232).")
    ```
13. Create `test_cli.py` using `typer.testing.CliRunner`:
    -   Empty environment (`tmp_path`-rooted Settings via env-var monkeypatch) → "No pending review items." + exit 0.
    -   With one of every source pending → table contains five rows + footer "[5 item(s) — 5 kind(s)]".
    -   `--kind divergence` → only divergence row.
    -   `--kind transaction --kind invoice` → two rows.
    -   `--modelo 130` → only items whose `modelo == "130"`.
    -   `--format json` → stdout parses to a list of length 5; each entry has `kind`, `item_id`, `severity`.
    -   `--kind classification` → exit 2, stderr mentions "blocked on" + "C4h".
    -   `--kind approval-stale` → exit 2, stderr mentions "blocked on" + "#230".
    -   `--state all` → today identical to `--state pending` (no adapter emits non-pending items yet); assert the same row count as the equivalent `--state pending` invocation. This locks the forward-compatible flag to a meaningful contract.

### Phase 6 — coverage matrix update

14. Open `docs/coverage/kent-capabilities.md`. The row "See pending reviews in one dashboard" already exists at line 26 with status `❌ ❌ ❌ ❌` and tracking link to #232. **Update the existing row in place** — flip CLI-supported to ✅ and Tested to ✅; leave Documented and Success-observable as ❌ (no Kent-facing docs in this PR; success-observable still pending end-to-end Kent UX validation in 0.1.0 milestone gate). Do not add a new row, do not refactor neighbouring rows.

### Phase 7 — verification

15. Run the local quality gates:
    -   `uv run pytest src/aeat/review src/aeat/entrypoints/cli/review -v` → all pass.
    -   `uv run pytest -m unit` → all pass (cross-check no regressions elsewhere).
    -   `uv run ruff check src/aeat/review src/aeat/entrypoints/cli/review` → clean.
    -   `uv run ruff format src/aeat/review src/aeat/entrypoints/cli/review --check` → clean.
    -   `uv run mypy src/aeat/review src/aeat/entrypoints/cli/review` → clean.
    -   `uv run aeat review queue --help` → renders the documented flags.
    -   `uv run aeat review queue` against an empty `var/` → "No pending review items.".
16. `git diff --stat HEAD` confirms changes are confined to:
    -   `src/aeat/application/review/**`
    -   `src/aeat/entrypoints/cli/review/**`
    -   `src/aeat/entrypoints/cli/__init__.py` (one import + one `add_typer` line)
    -   `docs/coverage/kent-capabilities.md` (one row)
    -   `.vault/research/2026-04-18-unified-review-queue-research.md`
    -   `.vault/adr/2026-04-18-unified-review-queue-adr.md`
    -   `.vault/plan/2026-04-18-unified-review-queue-plan.md`
    -   `.vault/exec/2026-04-18-unified-review-queue/**`
17. Commit history follows conventional commits:
    -   `docs(review): research, ADR, and plan for unified review queue (#232)` — vault artifacts.
    -   `feat(review): add aeat.application.review aggregator + CLI (#232)` — production code + tests.
    -   `docs(coverage): mark unified-review-queue capability done (#232)` — coverage matrix.

## parallelization

This work is single-track because Phases 2 → 3 → 4 → 5 are strict dependencies (models needed before adapters; adapters needed before aggregator; aggregator needed before CLI). Phase 1, 6, 7 may interleave only with their own phase boundaries.

The whole feature is **parallel-safe** with respect to **other agents** because:

-   No file outside `src/aeat/application/review/`, `src/aeat/entrypoints/cli/review/`, and the single CLI registration line is touched.
-   Every adapter is read-only on a stable public surface in another subpackage.
-   No new env vars; no `pyproject.toml` changes; no new dependencies.

## verification

Mission success requires all of the following:

-   `uv run pytest src/aeat/review src/aeat/entrypoints/cli/review -v` — every test passes.
-   `uv run pytest -m unit` — no regressions across the project.
-   `uv run ruff check src/aeat/review src/aeat/entrypoints/cli/review` — clean.
-   `uv run ruff format src/aeat/review src/aeat/entrypoints/cli/review --check` — clean.
-   `uv run mypy src/aeat/review src/aeat/entrypoints/cli/review` — clean.
-   `uv run aeat review queue --help` renders flags `--kind`, `--state`, `--modelo`, `--format`.
-   Manual smoke: build one synthetic instance of every source under `var/` and confirm `uv run aeat review queue` lists all five with correct severity ordering.
-   PR #232 references this plan, the ADR, the research doc, and at least one exec step.
-   No edits land in `src/aeat/application/sync/`, `src/aeat/domain/financial/`, `src/aeat/inbox/`, or `src/aeat/application/filing/`.

## risk register

-   **Risk:** A sibling agent renames `Transaction.business_classification` or `DivergenceRecord.resolution_state` mid-flight. **Mitigation:** Adapters import the public symbols by name; CI breaks immediately; one-line fix per adapter.
-   **Risk:** `FilingDraft.model_validate_json` chokes on partially-written drafts during execution. **Mitigation:** Adapter wraps the parse in try/except → log warning + skip (matches existing CLI behaviour at `cli/filing/__init__.py:339`).
-   **Risk:** Severity classification disagrees with Kent's gut. **Mitigation:** Single editable mapping table per source in `_adapters.py`; documented in ADR D5; trivial to revisit.
-   **Risk:** The `Inbox.model_validate_json` direct read pre-empts an `Inbox.load_from(path)` constructor that the inbox subpackage might add. **Mitigation:** When that constructor lands, swap the one call site in `inbox_pending`. No breaking change to the queue.
