---
tags:
  - "#exec"
  - "#unified-review-queue"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-18-unified-review-queue-plan]]"
  - "[[2026-04-18-unified-review-queue-adr]]"
  - "[[2026-04-18-unified-review-queue-research]]"
---

# unified-review-queue phase-1 summary

Single-pass execution of the `[[2026-04-18-unified-review-queue-plan]]` for issue [#232](https://github.com/wgergely/aeat/issues/232).

## what landed

### new code — `src/aeat/application/review/`

- `_enums.py` — `ReviewItemKind`, `ReviewSeverity`, `ReviewState`, `ReviewFormat`, plus `severity_rank()` helper and `_RESERVED_KINDS` table for the reserved-but-unimplemented `classification` and `approval-stale` tokens (per ADR D5 namespace reservations).
- `_errors.py` — `ReviewError(AeatError)`, `ReviewSourceLoadError`, `ReviewKindReservedError(token, reason)`.
- `_models.py` — `_ReviewItemBase` strict frozen, five concrete per-kind models (`TransactionReviewItem`, `InvoiceReviewItem`, `DivergenceReviewItem`, `FindingReviewItem`, `InboxReviewItem`), and the `ReviewItem` discriminated union (`Annotated[..., Field(discriminator="kind")]`).
- `_adapters.py` — five read-only adapters (`transactions_pending`, `invoices_pending`, `divergences_pending`, `drafts_pending`, `inbox_pending`) with first-match-wins severity tables and missing-source tolerance.
- `_aggregator.py` — `ReviewQueue.collect(...)` orchestrates the five adapters, applies kind/modelo filters, and sorts by `(severity desc, since asc, item_id)`.
- `__init__.py` — public re-exports.
- Tests (Rust-style colocated) — `test_models.py`, `test_adapters.py`, `test_aggregator.py`. All carry `[pytest.mark.unit, pytest.mark.domain_local_state]`.

### new code — `src/aeat/entrypoints/cli/review/`

- `__init__.py` — Typer sub-app.
- `queue.py` — `aeat review queue` command with `--kind` (repeatable), `--state`, `--modelo`, `--format` (table/json) flags. Reserved-kind tokens emit a `typer.BadParameter` naming the blocking issue.
- `test_cli.py` — CliRunner happy path + reserved-kind rejections + JSON-format invariants. Carries `[pytest.mark.unit, pytest.mark.domain_infra]`.

### modified

- `src/aeat/entrypoints/cli/__init__.py` — one import + one `app.add_typer(...)` line wiring the sub-app at `aeat review`.
- `docs/coverage/kent-capabilities.md` — updated existing row at line 26 ("See pending reviews in one dashboard") from `❌ ❌ ❌ ❌` to `❌ ✅ ✅ ❌`.

### vault artifacts

- `.vault/research/2026-04-18-unified-review-queue-research.md`
- `.vault/adr/2026-04-18-unified-review-queue-adr.md`
- `.vault/plan/2026-04-18-unified-review-queue-plan.md`
- `.vault/exec/2026-04-18-unified-review-queue/2026-04-18-unified-review-queue-phase1-summary.md` (this document)

## verification results

- `uv run pytest src/aeat/review src/aeat/entrypoints/cli/review` — **49 passed in 2.82s**.
- `uv run pytest -m unit` — **1756 passed, 1 skipped, 27 deselected** (no regressions).
- `uv run ruff check src/aeat/review src/aeat/entrypoints/cli/review src/aeat/entrypoints/cli/__init__.py` — clean.
- `uv run ruff format src/aeat/review src/aeat/entrypoints/cli/review --check` — clean.
- `uv run ty check src/aeat/review src/aeat/entrypoints/cli/review` — clean.
- `uv run ty check src tests` — clean (project-wide).
- `uv run aeat review queue --help` — renders the documented flags.
- `uv run aeat review queue` against an empty `var/` — prints `No pending review items.`.

## scope discipline

Per ADR D8 the following were explicitly **not** implemented in this PR (each is tracked as a separate parallel-safe issue):

- `BusinessClassification.REVIEWED_EXCLUDED` enum value → #224.
- Rename corpus `reviewed_by` → `definition_reviewed_by` → #225.
- `FilingDraftStatus.APPROVED` lifecycle and approval CLI → #230 / #231.
- Port `FilingValidationFinding` to `CatalogueFinding`, `InvoiceFinding`, `AttachmentFinding` → deferred (call it C4p-port).

The aggregator is forward-compatible with all four — when each lands, one new adapter file is added and the discriminated union grows by one member.

## audit trail

- ADR audit (vaultspec-code-reviewer) flagged one `[BLOCK]` (kind-namespace reservations missing) and three `[ADJUST]` items; all four were addressed in-line before plan writing.
- Plan audit (vaultspec-code-reviewer) flagged one `[BLOCK]` (private `_service` imports) and three `[ADJUST]` items; all four were addressed in-line before execution.
- Code review pass — pending (next step).

## drift caught during execution

- `PaymentStatus` enum in `aeat.domain.financial.invoices` exposes `PAID / PENDING / PARTIALLY_PAID / OVERDUE / CANCELLED` — the original ADR draft incorrectly referenced a non-existent `DISPUTED` member. Both ADR D5 and the plan's invoice severity table were corrected to use the live enum.
- `ModeloIdentifier` is a typed `str` subclass that the project's `ty` type-checker enforces strictly. Test fixtures wrap modelo strings via `ModeloIdentifier("130")`.
- `Inbox` does not need an `InboxFetcher` for read-only loading — the adapter validates the persisted JSON directly via `Inbox.model_validate_json`. ADR D2 documents this choice.

## next steps

- Code review pass (vaultspec-code-reviewer agent).
- Open PR with full vaultspec annotations.
