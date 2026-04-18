---
tags:
  - "#research"
  - "#unified-review-queue"
date: 2026-04-18
related:
  - "[[2026-04-17-kent-revise-review-audit]]"
  - "[[2026-04-17-kent-ux-journey-audit]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
  - "[[2026-04-12-filing-draft-engine-adr]]"
  - "[[2026-04-12-notifications-inbox-adr]]"
---

# unified-review-queue research

## context

GitHub issue [#232](https://github.com/wgergely/aeat/issues/232) under EPIC umbrella [#202](https://github.com/wgergely/aeat/issues/202) (C4 review surface). Kent must run **one** command and see *everything* across the produce → verify → export pipeline that wants his attention. Today, six unrelated commands surface six unrelated review surfaces, and Kent has to mentally join them. See [[2026-04-17-kent-revise-review-audit#scenario b — kent inspects what the semi-autonomous pipeline decided|kent-revise-review-audit scenario B walls 28-33]] (esp. wall 32: *no unified pipeline review queue dashboard*).

## existing review surfaces (audit)

Five distinct decision-bearing records carry "needs my attention" semantics today. Each lives in its own subpackage with its own state machine, repository, and CLI. None share a common abstraction.

### 1 — sync divergences (`src/aeat/sync/`)

Canonical pattern. Every other source should align to this shape.

- `DivergenceRecord` (`src/aeat/sync/_divergence.py:210`) — strict frozen pydantic v2 record with `record_id`, `detected_at`, `modelo`, `classification` (ADDITIVE | BREAKING | BENIGN | SUSPICIOUS), `payload` (discriminated union of nine concrete kinds), `resolution_state`, `notes`.
- `ResolutionState` (`src/aeat/sync/_divergence.py:66`) — closed `StrEnum` with PENDING / AUTO_HEALED / HUMAN_APPROVED / REJECTED.
- `JsonFileDivergenceRepository` (`src/aeat/sync/_repository.py:54`) — one JSON file per record under `AEAT_SYNC_DIVERGENCE_FILE_DIR` (default `var/divergences`). Atomic writes via `tempfile` + `os.replace`.
- CLI surface: `aeat sync list-divergences --state pending` (`src/aeat/cli/sync/list.py:15`) renders a `rich.table.Table` with id, modelo, classification, kind, state.

This is the only working "review queue" today, and it is scoped to sync deltas.

### 2 — transactions (`src/aeat/financial/transactions/`)

- `Transaction` (`src/aeat/financial/transactions/_models.py:63`) carries `business_classification`, `business_pct`, `classified_by` (`auto` | `manual` | `rule:<rule-id>`), `classified_at`, `notes`, plus links to `invoice_id` and `category_id`.
- `BusinessClassification` (`src/aeat/financial/transactions/_enums.py:16`) — closed enum: BUSINESS / PERSONAL / MIXED / UNCLASSIFIED.
- `TransactionCatalogue` (`_models.py:166`) — frozen mapping keyed by `transaction_id`. Loaded via `load_transactions(path)` (`_service.py:21`) from `<aeat_financial_txs_dir>/transactions.json`.
- CLI surface: `aeat financial txs list --unclassified` (`src/aeat/cli/financial/txs.py:30`) filters to UNCLASSIFIED rows. No needs-review queue.

Pending = `business_classification is BusinessClassification.UNCLASSIFIED`.

The audit (kent-revise-review wall 28) records that `UNCLASSIFIED` conflates four states (not-yet-seen / could-not-decide / skipped / personal) — the planned `REVIEWED_EXCLUDED` state lives in [#224](https://github.com/wgergely/aeat/issues/224). For #232 we surface "still UNCLASSIFIED" as pending and accept this conflation; #224 will refine the state without changing the queue contract.

### 3 — invoices (`src/aeat/financial/invoices/`)

- `Invoice` (`src/aeat/financial/invoices/_models.py:174`) carries `invoice_id` (64-char SHA-256), `kind`, `payment_status` (`PaymentStatus` enum: PENDING / PAID / PARTIAL / VOID / DISPUTED — `_enums.py:34`), `linked_transaction_ids: tuple[str, ...]`.
- `InvoiceCatalogue` — frozen mapping. Loaded from `<aeat_invoices_dir>/...` via `_service.py`.
- Pending review semantics:
  - **Unmatched invoice** → `linked_transaction_ids == ()` (no bank transaction reconciles to it).
  - **Payment uncertain** → `payment_status` ∈ {`PaymentStatus.PENDING`, `PaymentStatus.DISPUTED`}.

### 4 — filing drafts (`src/aeat/filing/`)

- `FilingDraft` (`src/aeat/filing/_schema.py:120`) carries `findings: tuple[FilingValidationFinding, ...]`, `status: FilingDraftStatus`.
- `FilingValidationFinding` (`_schema.py:96`) — strict frozen, has `casilla_id`, `severity` (ERROR / WARNING / INFO), `code`, trilingual `Translatable` `message`, `references_rules`.
- `FilingDraftStatus` (`_schema.py:26`) — DRAFT / VALIDATED / READY_TO_SUBMIT / SUBMITTED / ACKNOWLEDGED / REJECTED / AMENDED / CANCELLED.
- Persistence: drafts live as JSON files under `<aeat_drafts_dir>` (default `var/drafts`); naming `<modelo>_<period>_<draft_id>.json` (`src/aeat/cli/filing/__init__.py:77`).
- Pending review semantics:
  - draft has any `ERROR`/`WARNING` finding, or
  - draft is in `DRAFT` or `VALIDATED` status (i.e. has not yet reached READY_TO_SUBMIT, blocking export).

When the planned `APPROVED` state (C4a, [#230](https://github.com/wgergely/aeat/issues/230)) lands, "approved drafts that became stale" become a sixth pending kind. Out of scope here; the queue is forward-compatible because each kind has its own adapter.

### 5 — inbox notifications (`src/aeat/inbox/`)

- `Notificacion` (`src/aeat/inbox/_models.py:54`) — `notificacion_id`, `kind` (NotificacionKind), `priority` (NotificacionPriority), `effective_at`, optional `appeal_deadline: date`, `acknowledged_at`, `acknowledged_by`, `notes`.
- `Inbox` container — `dict[str, Notificacion]`, persisted to `<aeat_inbox_dir>` (default `var/inbox`).
- CLI surface: `aeat inbox list --unread` (`src/aeat/cli/inbox/list.py:15`) filters to `acknowledged_at is None`.
- Pending review semantics: `acknowledged_at is None` (Kent has not signed off) — esp. CRITICAL/HIGH priority records and any record with an `appeal_deadline` in the next `AEAT_INBOX_ALERT_LEAD_DAYS` window.

## pattern observations

Every existing source already has:

- A strict frozen pydantic model with a stable identifier.
- A closed enum that distinguishes pending from resolved.
- An on-disk repository (atomic writes; load/list semantics).
- One or more dedicated CLI surfaces.

What no source has:

- A common shape for `(id, kind, modelo|null, severity|priority, summary, source_command, since)` that can be rendered in a single table.
- A shared CLI flag namespace for `--kind` and `--state`.
- An aggregator that pulls from all five.

## the unification gap

Kent's audit (wall 32) lists six commands he must currently run and mentally join:

1. `aeat financial txs list --unclassified`
2. `aeat financial invoices unmatched` (planned)
3. `aeat financial invoices verify` (planned)
4. `aeat sync list-divergences --state pending`
5. `aeat filing show <draft> --findings-only`
6. `aeat inbox next-deadline`

Six command-discovery surfaces, six output formats, no cross-reference, no overall count. The unification target is one command (`aeat review queue`) producing one rich table with rows that carry source kind + id + summary + the original command Kent should run to drill in.

## constraints observed

### parallel-safety

The handover mandates `parallel-safe` — i.e. a sibling agent might be editing one of the underlying subpackages right now. The aggregator therefore must:

- Be **purely additive** — a new `src/aeat/review/` subpackage and CLI sub-app; no edits to existing models, enums, or repositories.
- Be **read-only** — depend on the public load/list surfaces (`load_transactions`, `JsonFileDivergenceRepository.list`, `InboxFetcher.load_inbox`, draft-dir glob), never mutating them.
- Tolerate **missing sources** — every adapter must degrade to "no items" when its disk source does not exist (Kent might not have run `aeat sync run` yet).

### #224, #225, #230, #231 are siblings — do not absorb their scope

The umbrella #202 explicitly splits the C4 cluster:

- #224 — `BusinessClassification.REVIEWED_EXCLUDED` enum value.
- #225 — Rename corpus `reviewed_by` → `definition_reviewed_by`.
- #230 — `FilingDraftStatus.APPROVED` lifecycle.
- #231 — Approval CLI + diff + staleness.

Each is a separate `parallel-safe` issue. #232 must **not** make changes that pre-empt them. The queue's adapter for transactions filters on `BusinessClassification.UNCLASSIFIED` only; when #224 lands and `REVIEWED_EXCLUDED` exists, the adapter's filter naturally excludes it without code change. The queue's adapter for drafts treats DRAFT/VALIDATED as pending; when #230's APPROVED state lands, it can extend the filter.

### `FilingValidationFinding` port (C4p) — defer

Issue body lists "Port `FilingValidationFinding` pattern to `CatalogueFinding`, `InvoiceFinding`, `AttachmentFinding`" as scope. Producing those new findings types implies emitting new findings *during validation* — i.e. modifying transaction/invoice/attachment loaders to attach findings. That is **not parallel-safe** with the financial-domain agents.

Recommendation: scope #232 to the **unified surface** (the ReviewItem aggregator + CLI). The findings port becomes a follow-up sibling issue (call it C4p, to be filed) once the queue has consumers. The queue is forward-compatible — adding a `findings` source adapter later is one new file plus a tuple entry.

### CLI conventions

- `rich.console.Console` + `rich.table.Table` for tabular output (matches `aeat sync list-divergences` and `aeat inbox list`).
- Typer sub-app with `no_args_is_help=True` for parent groups.
- Closed enums for `--kind` and `--state` flags — Typer auto-validates.
- Error path: typer.Exit(2) with a one-line stderr message on missing or malformed sources (matches `aeat financial txs show`).

### settings

All five disk roots are already declared in `src/aeat/config.py`:

- `aeat_financial_txs_dir` (line 129)
- `aeat_invoices_dir` (line 133)
- `aeat_sync_divergence_file_dir` (line 433)
- `aeat_inbox_dir` (line 447)
- `aeat_drafts_dir` (line 481)

No new env vars required. The aggregator reads `load_settings()` once and dispatches to the five adapters.

### testing

Existing patterns:

- `pytestmark = [pytest.mark.unit, pytest.mark.domain_<x>]` per [[2026-04-17-pytest-markers-adr]].
- Adapters can be exercised with synthetic catalogues built in-process (no fixtures dir).
- Aggregator test: build five mini-fixtures (one transaction UNCLASSIFIED, one invoice unmatched, one divergence PENDING, one draft with ERROR finding, one notificacion unacked), point the aggregator at a `tmp_path`, assert the unified queue lists exactly five rows with expected kinds.

## options considered

### option A — `ReviewItem` as a pydantic frozen wrapper around the underlying record

Each adapter wraps the original record in a `ReviewItem` carrying `(item_id, kind, source_id, modelo, severity, summary, since, drill_command)`.

- **Pros:** strongest type discipline; forward-compatible via discriminated union over kind; queue can be rendered, sorted, and filtered without leaking source-specific fields.
- **Cons:** loses access to source-specific richness inside the queue; an extra `ReviewItem.show` command would re-fetch from the source.

### option B — `ReviewItem` as a `Protocol` with per-source concrete implementations

Each adapter returns its native record (e.g. `DivergenceRecord`) which structurally satisfies a `ReviewItem` protocol.

- **Pros:** zero copy; native records keep their full shape.
- **Cons:** protocol fields force renames in the underlying records (e.g. `record_id` → `item_id`) — which violates parallel-safety. Rejected.

### option C — discriminated union over per-kind record

`ReviewItem = Annotated[TransactionReview | InvoiceReview | DivergenceReview | DraftReview | InboxReview, Field(discriminator="kind")]` — same as `DivergencePayload`'s shape.

- **Pros:** matches the existing canonical pattern; per-kind models can hold the original record verbatim alongside the unified fields; serializable to/from JSON for caching or LLM consumption.
- **Cons:** marginally more code than option A.

**Recommendation: option C.** It mirrors the proven `DivergencePayload` discriminated-union pattern, keeps source-specific data accessible for downstream consumers (e.g. an `aeat review show <item-id>` follow-up command), and makes the queue serializable.

## proposed module shape

```
src/aeat/review/
  __init__.py          # public API re-exports
  _enums.py            # ReviewItemKind, ReviewSeverity, ReviewState
  _errors.py           # ReviewError (inherits aeat.errors.AeatError)
  _models.py           # ReviewItem discriminated union + per-kind models
  _adapters.py         # five source adapters, each returning tuple[ReviewItem, ...]
  _aggregator.py       # ReviewQueue.collect(...)
  test_models.py       # pydantic shape + invariants
  test_adapters.py     # per-adapter happy-path + missing-source path
  test_aggregator.py   # end-to-end with five synthetic sources

src/aeat/cli/review/
  __init__.py          # typer sub-app
  queue.py             # `aeat review queue` command
  test_cli.py          # CliRunner happy-path
```

Wired into `src/aeat/cli/__init__.py` as a single `app.add_typer(review_module.app, name="review", ...)`.

## open questions answered

- **Should the queue surface ACK'd / RESOLVED items?** No. The default is pending only. A `--state` flag accepting `pending|all|resolved` covers the audit case.
- **Per-modelo filter?** Yes. Useful when Kent is preparing a specific quarter. Optional `--modelo 130` flag; adapter that has no modelo concept (inbox notifications without `references_modelo`) is excluded when the flag is set.
- **JSON output mode?** Yes. `--format json` outputs the validated `tuple[ReviewItem, ...]` as JSON for piping into `jq`. Matches Kent's developer-tier flow when scripting amendments.
- **Cross-reference drill commands?** Yes. Each `ReviewItem` carries `drill_command: str` — the literal CLI Kent runs to act on the item (e.g. `aeat sync show-divergence <id>`, `aeat financial txs classify <id> --as ...`). Rendered in the table.

## acceptance criteria mapping

From the issue body:

- *"One command → one table → everything pending"* → `aeat review queue` → rich.table.Table with rows from all five adapters.
- *"Zero instances of Kent having to remember the sync / inbox / classify / invoice / findings commands separately"* → `drill_command` column tells him exactly which command to run.

## verdict

Building a read-only aggregator over the five existing public load surfaces is parallel-safe, additive, and high-leverage. The discriminated-union model mirrors the canonical `DivergencePayload` pattern, keeps source-specific richness accessible, and is forward-compatible with the four sibling C4 issues (#224, #225, #230, #231) without taking on their scope. Recommend proceeding to ADR.
