---
tags:
  - '#audit'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-research]]'
---

# `modelo-addressing-ux` Code Review

## MODELO-UX-001 | LOW | Legacy `_modelo.py` boundary guard remains allowlist-based

The W06 static architecture guard covers extracted `_modelo*` command modules and prevents them from importing the monolithic root or private application modules. The legacy `_modelo.py` root remains outside that strict guard and still contains known residual authority reads and private-domain/domain-internal imports. This is consistent with the W06 residual-risk record and the frozen size-budget approach, but it means future edits inside `_modelo.py` can still add boundary debt unless reviewers enforce the W06 discipline manually.

Recommended follow-up: add a baseline/freeze guard for `_modelo.py` private imports and registry authority reads, similar to the size-budget freeze, so the legacy root cannot grow new boundary violations while the remaining command groups are extracted.

## MODELO-UX-002 | LOW | IVA wallet seed facade lacks direct application-service edge tests

The CLI regression lane covers the IVA wallet seed command happy path and duplicate refusal, and the application calculations lane covers compensation history. The new `seed_iva_compensation_period_for_bucket` facade should also get direct application tests for the no-taxpayer and negative-amount errors so those policy decisions are pinned at the backend boundary, not only through CLI behavior.

Recommended follow-up: add real-runtime application tests around a bucket with no `identity.tax_id` and a negative seed amount, asserting `ModeloIvaWalletSeedNoTaxpayerError` and `ModeloIvaWalletSeedNegativeAmountError`.

## MODELO-UX-003 | LOW | `work_calculate` remains frozen legacy debt

The plan now freezes `work_calculate` at its current command-size budget and RAG/exact audits show the calculation input business logic is owned by `application/modelo/_calculate_input.py`. The command function itself is still large because the Typer option surface is verbose and some parse/render orchestration remains local to `_modelo.py`.

Recommended follow-up: extract `work calculate` into a bounded work-calculation registrar and split parsing/render helpers further, preserving the backend-owned input bundle and calculation service.

## MODELO-UX-004 | LOW | Workflow-run exact-id parsing remains duplicated

The final review found no blocking regression in the extracted `modelo export`, rendering, support, and workflow-run modules. One maintainability debt remains: `_modelo_work_runs_cli.py` still declares its own 64-character work-unit-id regex for the advanced `work resume <work_unit_id>` escape hatch instead of reusing the new CLI support id-shape helper. This does not change the accepted natural-key workflow and is covered by `test_work_resume.py`, but it leaves one duplicate raw-id parser to keep aligned while the CLI continues moving toward modelo/year/period matching.

Recommended follow-up: have `_modelo_work_runs_cli.py` call the shared support validator, or retire the work-unit-id resume shortcut when the future period-matching workflow replaces that exact-addressing path.
