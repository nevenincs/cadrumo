---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:930f37f48a55927797861694424678c705fd780cfe2e3558759e51dab9384b12'
step_id: 'S08'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Verify the attachments domain pinned inventory at execution time and relocate its repository behind a port if a production domain-to-adapters edge exists, otherwise confirm the domain is already ports-compliant and remove any stale test-edge entries

## Scope

- `src/aeat/domain/attachments`

## Description

- Inventory the `src/aeat/domain/attachments` production tree at execution time: `_enums`, `_errors`, `_ids`, `_models`, `_protocols`, `_service` — no `_repository` module and no production import of any adapters package.
- Confirm the concrete repository already lives in the adapter at `adapters/persistence/storage/attachment.py`, consumed through the domain `AttachmentStore` protocol in `_protocols`.
- Grep the domain production modules for adapters imports outside `TYPE_CHECKING`/tests: none found.
- Audit the `.importlinter` `domain.attachments.*` entries: all six are live test-edge ignores whose backing test files (`test_service`, `test_repository`, `test_attachment_store_no_uri_list`) exist on disk — none stale.

## Outcome

- The attachments domain is already ports-compliant: it owns only the typed models and the repository port, with the secure-object-backed implementation resident in the adapter layer. No production `domain -> adapters` edge exists, so no relocation is required.
- No stale test-edge entries to remove; the `.importlinter` attachments ignores are all backed by present test files.
- Verify-only step: no code change, no commit to production sources.

## Notes

- This verify-only step and the modelos runtime-repository relocation (S17) are two leaves of register item D2; they do not close it. The filing-repositories wave (`domain/filing/_repository.py`, `_complementaria_repository.py`, `_runtime_repository.py`; `.importlinter` pins 686/687/704) remains open, and the graph-wide zero-domain-to-adapters check is the definitive D2 gate.
