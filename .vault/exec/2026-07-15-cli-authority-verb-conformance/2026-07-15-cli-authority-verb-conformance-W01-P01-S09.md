---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:bdb5325f562bb52b7c4e3d3557551ab8218bd2596c74785fe82a75c5aafd25c2'
step_id: 'S09'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace verification's concrete invoice-repository boundary with InvoiceCatalogueRepositoryProtocol

## Scope

- `src/cadrumo/application/modelo/_verification_actions.py`

## Description

- Remove the concrete invoice persistence-adapter import from modelo verification.
- Import the public domain `InvoiceCatalogueRepositoryProtocol` port.
- Type all four injected invoice-repository boundaries against the public port.
- Update the directly affected verifier argument documentation without changing runtime logic.

## Outcome

The mandatory semantic query `modelo verification invoice repository protocol OSS IOSS resolver` located the legacy M369 resolver call and all concrete annotations. Targeted symbol searches confirmed that the verifier only forwards `invoice_repository` through its gate and finding collectors into `OssIossLedgerSourceResolver`; it contains no `InvoiceCatalogueRepository(...)` construction. The public runtime-checkable port exposes the repository contract through `bucket_id`, `exists`, `load`, and `save`.

The overlap classification was isolated: the implementation file had no staged or unstaged work before editing. The resulting diff changes only one import, four annotations, and directly affected documentation. Ruff passed, and the real dormant M369 suite passed all five tests against encrypted runtime storage.

## Notes

No behavior, condition, call, or composition path changed. Step S10 remains open: the receiving OSS/IOSS annotations and its sole concrete default-construction path were not touched. The supervisor-authored plan is untracked in this worktree, so it is updated only through the plan CLI and excluded from this Step's commit.
