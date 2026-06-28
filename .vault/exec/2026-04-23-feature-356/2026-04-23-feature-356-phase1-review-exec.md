---
tags:
  - "#exec"
  - "#feature-356"
date: 2026-04-23
modified: '2026-04-23'
related:
  - "[[2026-04-23-feature-356-phase1-step1-exec]]"
---

# 2026-04-23-feature-356-phase1-review

## verdict: APPROVED

## reviewed commits

6 commits on `feature/356-category-assignment-followup` (84f8cda..f914b64)
against main (09e343b). PR #368.

## findings

### safety checks

- No live-write path introduced; no `live_transport_supported=True` added.
- No absolute `aeat.*` imports inside `src/aeat/`.
- No secrets committed.
- No `.github/workflows/release-please.yml` added.
- All new models use `ConfigDict(strict=True, frozen=True, extra="forbid")`.

### correctness

**ClassificationHistoryEntry**: `category_id` and `notes` fields added in
the right position (after `reason`, before `confidence`). Validators mirror
the existing `Transaction` model validators exactly. The `_coerce_inbound`
model validator does not need updating because Pydantic's field-level
coercion handles `str | None` and `str` without extra logic.

**_EntrySignature**: The 7-tuple order is
`(classification, pct, classified_by, reason, category_id, notes, confidence)`.
The proposed_signature uses `category_id if category_id is not None else
transaction.category_id` — correctly handles metadata-only calls where the
caller passes `None` for classification.

**_read_ndjson_text**: UTF-16 detection uses BOM bytes `\xff\xfe` / `\xfe\xff`.
Without this guard, UTF-16 decoding always succeeds (no UnicodeDecodeError)
and silently mis-interprets CP1252 bytes as paired UTF-16 code units. Fix is
correct and well-documented.

**classify_cmd optional --as**: The no-classification branch reuses the
`_resolve_classify_pct` helper correctly. The guard that rejects no-argument
calls (`no changes requested`) prevents silent no-ops.

**category validation**: Correctly checks OUTGOING direction and existing
business/personal/mixed classification before assigning. Guard message is
clear.

### test quality

- No mocks, patches, fakes, or stubs in new tests.
- Tests use real filesystem via `tmp_path`; no monkeypatching.
- Assertions are derived from specification, not from observed output.
- CP1252 encoding test exercises the actual encoding detection path.

### issues found and resolved during implementation

- Initial encoding detection tried UTF-16 before CP1252; UTF-16 always
  succeeds on even-length byte sequences. Fixed by BOM-gating UTF-16.
- Stale worktree's `save_transactions_fn` injection seam broke
  `test_reconciliation.py`'s `monkeypatch.setattr` approach. Dropped
  the seam; main's direct call pattern is correct.
- Stale worktree's `test_categories_cli.py` changes asserted `label_es`
  which doesn't exist in `categories list` JSON. Dropped.

## status

APPROVED — all pre-commit hooks pass, 39 transaction CLI tests + 256
module tests green. PR #368 ready for merge.
