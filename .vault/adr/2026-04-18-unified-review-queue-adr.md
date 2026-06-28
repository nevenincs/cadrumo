---
tags:
  - "#adr"
  - "#unified-review-queue"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-18-unified-review-queue-research]]"
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
  - "[[2026-04-12-filing-draft-engine-adr]]"
  - "[[2026-04-12-notifications-inbox-adr]]"
---

# unified-review-queue-adr

## status

Proposed — 2026-04-18. Sub-EPIC of [#202](https://github.com/wgergely/aeat/issues/202) (review umbrella) and direct fulfilment of [#232](https://github.com/wgergely/aeat/issues/232).

## context

Kent's revise/review audit (`[[2026-04-17-kent-revise-review-audit#scenario b — kent inspects what the semi-autonomous pipeline decided|scenario B]]`, wall 32) records that there is no unified surface answering "where do I start today?". To find every record across the produce → verify → export pipeline that wants his attention, Kent must run six unrelated commands and mentally join their output:

1. `aeat financial txs list --unclassified`
2. `aeat financial invoices unmatched` (planned)
3. `aeat financial invoices verify` (planned)
4. `aeat sync list-divergences --state pending`
5. `aeat filing show <draft> --findings-only`
6. `aeat inbox next-deadline`

The research document (`[[2026-04-18-unified-review-queue-research]]`) confirms five distinct decision-bearing record types live in five distinct subpackages. Each has:

- A strict frozen pydantic v2 record with a stable identifier.
- A closed enum that distinguishes pending from resolved.
- An on-disk repository with atomic writes.
- A dedicated CLI surface.

What none has:

- A common shape `(id, kind, modelo|null, severity|priority, summary, drill_command, since)` that can be rendered in a single table and serialised for downstream consumers.
- A shared `--kind` / `--state` flag namespace.
- An aggregator.

Sibling issues #224 (`REVIEWED_EXCLUDED` enum value), #225 (rename corpus `reviewed_by` → `definition_reviewed_by`), #230 (`FilingDraftStatus.APPROVED`), and #231 (approval CLI + diff + staleness) are **separate parallel-safe issues**. This ADR explicitly does not pre-empt their scope.

## decision

Add a new, additive, read-only `aeat.application.review` subpackage and a single new top-level CLI command — `aeat review queue` — that aggregates pending review items from the five existing on-disk sources into one unified `tuple[ReviewItem, ...]` and renders them as a single rich table.

### D1 — `ReviewItem` is a discriminated union over per-kind models

The unified record type is a `pydantic.Annotated[…, Field(discriminator="kind")]` union. Each member is a strict frozen pydantic v2 model that carries the same set of unified fields (`item_id`, `kind`, `modelo`, `severity`, `summary`, `drill_command`, `since`) **plus** a verbatim copy of the underlying source record (`source: Transaction | Invoice | DivergenceRecord | DraftFinding | Notificacion`).

Rationale: the discriminated-union shape mirrors the proven `DivergencePayload` pattern (`src/aeat/application/sync/_divergence.py:174`); per-kind models keep source-specific richness accessible for a future `aeat review show <item-id>` drill command without re-fetching from disk; the whole tuple is JSON-serialisable for `--format json` output.

Rejected alternatives:

- **Protocol over native records** — would force `record_id` → `item_id` renames in `DivergenceRecord`, `Transaction`, etc. Violates parallel-safety. Rejected.
- **Plain wrapper with no source field** — would force a follow-up `aeat review show` command to re-fetch from each source's repository. Rejected because the source record is already loaded; persisting it costs nothing.

### D2 — One adapter per source, all read-only

Five concrete adapter functions live in `src/aeat/application/review/_adapters.py`. Each adapter:

- Takes a `Settings` instance and any pre-loaded source data (for testability).
- Returns `tuple[ReviewItem, ...]`.
- Filters its source down to "pending" by the source's own state semantics:

| Adapter | Source | Pending predicate |
|---|---|---|
| `transactions_pending` | `TransactionCatalogue` (`<aeat_financial_txs_dir>/transactions.json`) | `not is_classified(business_classification)` AND `business_classification is not BusinessClassification.SKIPPED_BY_RULE` (post-#237 state model: NOT_YET_PROCESSED → NORMAL, PROCESSED_UNCLASSIFIED → HIGH, FAILED_VALIDATION → CRITICAL; SKIPPED_BY_RULE has a final disposition and is excluded) |
| `invoices_pending` | `InvoiceCatalogue` loaded via `aeat.domain.financial.invoices.load_invoices(<aeat_invoices_dir>/invoices.json)` | `linked_transaction_ids == ()` OR `payment_status in {PENDING, PARTIALLY_PAID, OVERDUE}` (severity per D5 first-match-wins table) |
| `divergences_pending` | `JsonFileDivergenceRepository.list()` | `resolution_state is ResolutionState.PENDING` |
| `drafts_pending` | every JSON under `<aeat_drafts_dir>` (loaded via `Path.glob("*.json")` + `FilingDraft.model_validate_json`) | one row per finding with severity `ERROR`/`WARNING`/`INFO` (kind=FINDING); plus, **only if** the draft has zero findings AND `status in {DRAFT, VALIDATED}`, one extra row (kind=FINDING, severity=NORMAL, summary "draft not ready to submit"). Deduped by `(draft_path, finding.code, finding.casilla_id)` |
| `inbox_pending` | `Inbox.model_validate_json(<aeat_inbox_dir>/inbox.json)` (direct read — `InboxFetcher` requires a `NotificacionSource` we do not need for read-only aggregation) | `acknowledged_at is None` (severity per D5 first-match-wins inbox table) |

Each adapter degrades to `()` when its source directory is missing or empty. No adapter mutates its source.

### D3 — Aggregator orchestrates and filters

`ReviewQueue.collect(settings, *, kinds=None, modelo=None) -> tuple[ReviewItem, ...]` calls every adapter, concatenates their output, applies the `kinds` and `modelo` filters, and sorts by `(severity desc, since asc, item_id)` so the most urgent oldest item lands at the top.

`kinds` is `frozenset[ReviewItemKind] | None`. `None` means all kinds. The CLI flag `--kind` is repeatable.

`modelo` is `str | None`. `None` means no filter. When set, items whose underlying record has no modelo concept (inbox notifications without `references_modelo`) are excluded.

### D4 — `aeat review queue` is the single CLI surface

Wired into `src/aeat/entrypoints/cli/__init__.py` as `app.add_typer(review_module.app, name="review", ...)`.

```
aeat review queue [--kind transaction|invoice|divergence|finding|inbox] ...
                  [--state pending|all]
                  [--modelo MODELO]
                  [--format table|json]
```

- `--kind` is repeatable (`--kind transaction --kind divergence`).
- `--state pending` (default) returns only pending items. `--state all` returns every item the adapters can see (useful for debugging).
- `--modelo` filters to one modelo across kinds that have one.
- `--format table` (default) renders a `rich.table.Table` with columns: `kind`, `id` (truncated), `modelo`, `severity`, `summary`, `since`, `drill →`. `--format json` outputs `tuple[ReviewItem, ...].model_dump(mode="json")` to stdout.
- Footer line: `[N item(s) — K kind(s)]`.

### D5 — Closed enums for kind, severity, and state

```python
class ReviewItemKind(StrEnum):
    TRANSACTION = "transaction"
    INVOICE = "invoice"
    DIVERGENCE = "divergence"
    FINDING = "finding"
    INBOX = "inbox"

class ReviewSeverity(StrEnum):
    CRITICAL = "critical"   # blocks export / blocks filing
    HIGH = "high"           # likely needs attention this week
    NORMAL = "normal"       # routine review
    INFO = "info"           # informational only

class ReviewState(StrEnum):
    PENDING = "pending"
    ALL = "all"
```

#### kind-namespace reservations

The issue body's `--kind` token list contains two future-only members that this PR does **not** ship:

- `classification` — the `ClassificationDecision` record type listed in `[[2026-04-17-kent-revise-review-audit#scenario b — kent inspects what the semi-autonomous pipeline decided|kent-revise-review-audit walls 28-31]]` does not exist in `src/aeat/` today. When it lands (umbrella #202 child issue C4h), a `CLASSIFICATION = "classification"` enum member and a matching adapter are added. Until then the token is reserved and the CLI rejects it with a clear message that names the blocking issue.
- `approval-stale` — depends on the `FilingDraftStatus.APPROVED` lifecycle (sibling #230) and the staleness detector (sibling C4f). When both land, `APPROVAL_STALE = "approval-stale"` is added with a matching adapter. Reserved until then.

The issue body also uses `aeat-inbox`. This ADR adopts the shorter `inbox` token because (a) it matches the subpackage name (`aeat.inbox`) and CLI sub-app (`aeat inbox …`), (b) it avoids a hyphen in a `--kind` value, and (c) the `aeat-` prefix is redundant inside the `aeat review` namespace. Documented here as an intentional rename from the issue body's token.

#### severity mapping

Severity is **derived per adapter**, not stored on the source. The evaluation rule per source is **first-match-wins, top-down** within the source's section. An item that matches multiple rows lands in the first matching severity bucket — never two.

`transactions` source (top-down) — using the post-#237 `BusinessClassification` state model:

| Predicate | Severity |
|---|---|
| `is_classified(state)` (BUSINESS / PERSONAL / MIXED) | (skipped — final disposition) |
| `state is BusinessClassification.SKIPPED_BY_RULE` | (skipped — final disposition) |
| `state is BusinessClassification.FAILED_VALIDATION` | CRITICAL |
| `state is BusinessClassification.PROCESSED_UNCLASSIFIED` | HIGH |
| `state is BusinessClassification.NOT_YET_PROCESSED` | NORMAL |

`invoices` source (top-down) — using the actual `PaymentStatus` enum from `aeat.domain.financial.invoices` (`PAID`, `PENDING`, `PARTIALLY_PAID`, `OVERDUE`, `CANCELLED`):

| Predicate | Severity |
|---|---|
| `linked_transaction_ids == ()` (unmatched dominates payment status) | HIGH |
| `payment_status is PaymentStatus.OVERDUE` | HIGH |
| `payment_status is PaymentStatus.PENDING` | NORMAL |
| `payment_status is PaymentStatus.PARTIALLY_PAID` | NORMAL |
| `payment_status in {PaymentStatus.PAID, PaymentStatus.CANCELLED}` | (skipped — not pending) |

`divergences` source (top-down):

| Predicate | Severity |
|---|---|
| `classification in {DivergenceClassification.BREAKING, DivergenceClassification.SUSPICIOUS}` | CRITICAL |
| `classification in {DivergenceClassification.ADDITIVE, DivergenceClassification.BENIGN}` | NORMAL |

`findings` source (per-finding row from a draft, top-down):

| Predicate | Severity |
|---|---|
| `severity is FilingFindingSeverity.ERROR` | CRITICAL |
| `severity is FilingFindingSeverity.WARNING` | HIGH |
| `severity is FilingFindingSeverity.INFO` | INFO |

Plus one row per draft whose `status in {FilingDraftStatus.DRAFT, FilingDraftStatus.VALIDATED}` and that has *no* findings — severity NORMAL, summary "draft not ready to submit".

`inbox` source (top-down):

| Predicate | Severity |
|---|---|
| `priority is NotificacionPriority.CRITICAL` | CRITICAL |
| `priority is NotificacionPriority.HIGH` OR `appeal_deadline ≤ today + AEAT_INBOX_ALERT_LEAD_DAYS` | HIGH |
| `priority is NotificacionPriority.NORMAL` | NORMAL |
| `priority is NotificacionPriority.INFO` | INFO |

Rationale: severity is the queue's editorial answer to "should I look at this today?", not a property of the underlying record. Centralising the mapping in `_adapters.py` per source with explicit first-match-wins ordering removes the dual-match risk that an unmatched-and-disputed invoice could be downgraded.

### D6 — `drill_command` is a literal CLI string

Each adapter sets `drill_command` to the exact CLI Kent runs to act on the item:

| Kind | drill_command |
|---|---|
| TRANSACTION | `aeat financial txs classify <id> --as ...` |
| INVOICE | `aeat financial invoices show <id>` |
| DIVERGENCE | `aeat sync show-divergence <id>` |
| FINDING | `aeat filing show <draft-path> --findings-only` |
| INBOX | `aeat inbox show <id>` |

Rendered in the table's last column. Acceptance criterion: Kent never needs to remember six commands — the queue tells him which one to run.

### D7 — Forward compatibility: new sources land as new adapters

When sibling issues land:

- **#224** (`REVIEWED_EXCLUDED`): the `transactions_pending` adapter's filter naturally excludes the new state without code change once added to the `_classify_transaction` early-return branch alongside `SKIPPED_BY_RULE`. **Assumption:** #224 introduces `REVIEWED_EXCLUDED` as a new `BusinessClassification` enum member (additive, post-#237 model). One-line predicate update required.
- **#237** (state-distinguished `BusinessClassification`): **shipped** via PR #252 (merged 2026-04-18). The adapter now uses the `is_classified()` helper plus first-match-wins severity per the four pending states (`NOT_YET_PROCESSED` → NORMAL, `PROCESSED_UNCLASSIFIED` → HIGH, `FAILED_VALIDATION` → CRITICAL, `SKIPPED_BY_RULE` excluded).
- **#230 / #231** (`APPROVED` + `APPROVAL_STALE`): a new `approval_stale_pending` adapter is added; aggregator concatenation picks it up; `ReviewItemKind.APPROVAL_STALE` member added.
- **C4h** (`ClassificationDecision`): a new `classifications_pending` adapter is added; `ReviewItemKind.CLASSIFICATION` member added.
- **C4p-port** (Catalogue/Invoice/Attachment findings): each new findings type adds one adapter; existing `FINDING` enum member is reused (per-source attribution lives on the wrapped record).

No existing adapter changes. The discriminated union grows by one member per new kind.

### D8 — Defer scope items that require modifying shared models or absent sources

The issue body lists three model-changing scope items and two future kinds. Each is moved to its own sibling issue or explicitly deferred to keep #232 parallel-safe:

- **`BusinessClassification.REVIEWED_EXCLUDED`** → tracked separately as #224. No change in this PR.
- **Rename `reviewed_by` → `definition_reviewed_by`** → tracked separately as #225. No change in this PR.
- **Port `FilingValidationFinding` to `CatalogueFinding` / `InvoiceFinding` / `AttachmentFinding`** → defer to a follow-up sibling issue (call it C4p-port). The unified queue is forward-compatible: when those new findings types land, each gets a new adapter that emits items with the existing `FINDING` kind.
- **`--kind classification`** → blocked on the `ClassificationDecision` record type (umbrella #202 child C4h). The token is reserved (see D5 kind-namespace reservations); the CLI rejects it today with a message naming the blocking issue.
- **`--kind approval-stale`** → blocked on `FilingDraftStatus.APPROVED` (#230) and the staleness detector (C4f). The token is reserved per D5; CLI rejects it with a message naming the blockers.

The remaining in-scope items for #232 are: the `ReviewItem` abstraction (C4k), the `aeat review queue` CLI (C4l), and the five read-only adapters that prove the abstraction across all current pending surfaces.

## consequences

**Positive:**

- Kent's wall 32 closes: one command, one table, every pending item.
- The aggregator is purely additive — sibling agents working on `aeat.domain.financial.*`, `aeat.application.sync.*`, `aeat.inbox.*`, or `aeat.application.filing.*` are not blocked.
- The discriminated union mirrors the existing `DivergencePayload` pattern — no new architectural shape to learn.
- JSON output mode (`--format json`) makes the queue scriptable and LLM-consumable, supporting downstream automation.
- Forward-compatible with #224, #225, #230, #231, and C4p-port without retroactive changes.

**Negative / costs:**

- The aggregator depends on the public surfaces of five subpackages. If any of those public APIs changes (e.g. a load function gets renamed), the aggregator breaks. Mitigation: each adapter is one function in one file with one test; CI surfaces breakage immediately.
- The `severity` mapping is editorial — Kent might disagree with one of its choices. Mitigation: the mapping table lives in one place (`_adapters.py`) and is documented in the ADR, so feedback resolves into one edit.
- Loading every draft on every queue invocation is O(N drafts). For Kent's expected scale (tens of drafts, never hundreds) this is inconsequential. If it becomes hot, an index file or storage-backed query lands later.

**Neutral:**

- No new env vars. No changes to existing models, enums, or repositories.
- No new dependencies. `rich` and `typer` are already in `pyproject.toml`.

## scope

**In scope for this ADR (what changes):**

- New subpackage `src/aeat/application/review/` with `_enums.py`, `_errors.py`, `_models.py`, `_adapters.py`, `_aggregator.py`.
- New CLI sub-app `src/aeat/entrypoints/cli/review/` with the `queue` command.
- One-line wiring in `src/aeat/entrypoints/cli/__init__.py`.
- Unit tests under `pytest.mark.unit` + `pytest.mark.domain_local_state` for models, adapters, aggregator, and CLI.

**Explicitly out of scope:**

- Modifying any existing model, enum, or repository.
- Implementing `BusinessClassification.REVIEWED_EXCLUDED` (lives in #224).
- Renaming corpus `reviewed_by` (lives in #225).
- Implementing `FilingDraftStatus.APPROVED` or staleness detection (lives in #230 / #231).
- Porting `FilingValidationFinding` to non-draft records (deferred to C4p-port).
- Resolving items from the queue (no `aeat review approve <id>` here — that's #231).

## acceptance criteria

- `aeat review queue` runs and emits a single rich table when at least one pending item exists in any source.
- The table contains one row per pending item, with `kind`, `id`, `modelo`, `severity`, `summary`, `since`, and `drill →` columns.
- `aeat review queue --kind divergence` filters to divergences only.
- `aeat review queue --kind transaction --kind invoice` filters to two kinds.
- `aeat review queue --modelo 130` filters to items bound to modelo 130.
- `aeat review queue --format json` outputs a JSON tuple of validated `ReviewItem` records to stdout.
- Every adapter degrades to `()` when its on-disk source is missing.
- Unit tests assert each adapter's pending predicate, the aggregator's sort order, the CLI happy path, and the JSON round-trip.
- Coverage on `src/aeat/review` ≥ 90% lines.
- No edits land in `src/aeat/application/sync/`, `src/aeat/domain/financial/`, `src/aeat/inbox/`, or `src/aeat/application/filing/`.

## verification

- `uv run pytest src/aeat/review src/aeat/entrypoints/cli/review` passes.
- `uv run aeat review queue --help` shows the documented flags.
- `git diff --stat HEAD~1` shows changes only under `src/aeat/application/review/`, `src/aeat/entrypoints/cli/review/`, `src/aeat/entrypoints/cli/__init__.py`, and `tests/` if applicable.
- `just test-cov` keeps the project floor at ≥ 60%.
