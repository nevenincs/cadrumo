---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# `ledger-evidence-enforcement` `P01-P04` summary

Ledger evidence enforcement steps `S01` through `S19` are implemented or confirmed, with closeout evidence recorded per step.

- Modified: `src/aeat/domain/attachments/_models.py`
- Modified: `src/aeat/domain/attachments/_service.py`
- Modified: `src/aeat/adapters/persistence/storage/attachment.py`
- Modified: `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`
- Modified: `src/aeat/domain/attachments/tests/test_attachment_store_no_uri_list.py`
- Confirmed existing evidence changes: `src/aeat/application/aggregation/_evidence_advisory.py`, `src/aeat/application/aggregation/_source_mesh.py`, `src/aeat/application/aggregation/__init__.py`, `src/aeat/application/modelo/_verification_actions.py`, `src/aeat/adapters/outbound/google/tests/test_document_link_resolve_roundtrip.py`, `src/aeat/application/aggregation/tests/test_evidence_advisory.py`
- Created: `.vault/audit/2026-06-12-ledger-evidence-enforcement-code-review-audit.md`
- Created: `.vault/exec/2026-06-10-ledger-evidence-enforcement/2026-06-12-ledger-evidence-enforcement-P01-S01.md` through `P04-S19.md`

## Description

Deleted the link-only attachment path from the production surface, rewired `doclink` to fetch-and-encrypt or refuse, added model and store enforcement against link-only attachment manifests, confirmed missing-evidence advisories for outgoing business expenses and incoming cuota-bearing income, confirmed verify-path advisory projection with legal references, and recorded user-facing docs rewrites as a separate documentation deliverable.

Verification run:

- `uv run --no-sync pytest src/aeat/domain/attachments/ -q --tb=short` passed: 14 passed.
- `uv run --no-sync pytest src/aeat/adapters/outbound/google/ -q --tb=short` passed: 156 passed, 3 deselected.
- `uv run --no-sync pytest src/aeat/application/aggregation/ -q --tb=short` passed: 437 passed.
- `uv run --no-sync pytest --collect-only -q` passed: 16,961 collected, 1,786 deselected, 15,175 selected.
- `uv run --no-sync python -m dev.docs.apidocs scaffold --check` passed: no drift.
- `uv run --no-sync python -m aeat.locales scaffold --check` passed: all locale catalogues ok.
- `uv run --no-sync ruff check ...` passed on the evidence surface.
- `rg -n "uri-list|add_link_attachment" src/aeat --glob "!**/tests/**" -S` returned no production matches.

Remaining ledger paths lacking enforceable evidence: none found in the child scope after the attachment manifest/store guard and doclink refusal path. The user-facing how-to rewrite remains out of scope and must ride `vaultspec-documentation`.

Sibling dependencies: ledger amount/direction, modelo cross-reference, filter-period, and input-localization work were not taken over. This child can close once the plan rows are checked by the vaultspec CLI.
