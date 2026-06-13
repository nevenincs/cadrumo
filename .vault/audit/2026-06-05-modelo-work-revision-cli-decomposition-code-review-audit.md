---
tags:
  - '#audit'
  - '#modelo-work-revision-cli-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
---

# `modelo-work-revision-cli-decomposition` Code Review

## MWRC-001 | INFO | Revision command extraction preserves the application boundary

Reviewed the extracted revision read and verify/file command registrars. The CLI modules remain Typer adapters over application services and public application facades. The command-specific defaults for verify and file route through `resolve_modelo_revision_for_operator_target`, which dispatches to the application-owned verifiable and fileable revision resolvers. No command-local work-unit selection, registry authority, calculation policy, verification policy, or filing policy was introduced in this slice.

## MWRC-002 | INFO | Focused behavior and architecture checks pass

Focused real-behavior CLI tests pass for revision reads, verify/file defaults, natural-key workflows, and legacy id-type hints. Application selector tests pass for command-specific revision state. Architecture boundary tests pass for public application facade consumption.

## MWRC-003 | CLOSED | Broad module-size guard residual was promoted to W04

The W03 closeout found `_app_live.py` and `_ledger.py` over their frozen budgets. The user explicitly requested those residuals be added to the plan and executed. W04 now closes this finding.

## MWRC-004 | PASS | W04 residual monolith offenders are closed

W04 extracted the live `borrador 100` subgroup and the ledger `evidence` subgroup into focused CLI modules. `_app_live.py` is now 2061 lines against a 2061 frozen budget; `_ledger.py` is now 4084 lines against a 4084 frozen budget. The broad production CLI monolith guard now passes.

## MWRC-005 | PASS | Residual extraction preserves backend-owned policy

The extracted live borrador commands delegate snapshot policy and persistence to `Borrador100SnapshotService`. The extracted ledger evidence commands delegate evidence persistence and mutation policy to `PurchaseInvoiceEvidenceService`. The root CLI modules now mount focused registrars; they do not own the extracted subgroup command bodies.

## MWRC-006 | INFO | Marker hook aligned with active hexagonal taxonomy

Residual verification exposed that the pytest collection hook still enforced retired `domain_*` markers while the current suite and `pyproject.toml` use `hex_*` markers. The hook now enforces exactly one execution marker and at least one `hex_*` marker. `test_marker_integrity.py` passes with 2101 checks.
