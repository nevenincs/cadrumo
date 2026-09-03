---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:def69474956546213d039c27283ff67e7879f623b9f513b82090eff5ad2d19f9'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
---
# `tui-architecture` audit: `W08.P27.S375 holistic final review`

## Scope

Replacement holistic final review of the complete live Ledger TUI package, its locale vocabulary, and the canonical application workspace projection against W08.P27.S375 and the accepted unreachable-capability navigation decision. The review consolidated and re-probed the three independently closed slice audits across route completeness, truthful availability, architecture boundaries, action authority and admission, security and redaction, localization, responsive geometry, semantic focus, asynchronous lifecycle, Ledger-versus-AEAT separation, and combined regression behavior.

## Findings

No open high, medium, or low finding remains.

The seven-route catalogue is exact and total: overview, entries, review, import, classification, evidence, and reconciliation each resolve to a real screen when their required injected application authority is present. Missing authority, unavailable application state, and missing flow dependencies resolve to visible typed refusal screens rather than false affordances. The route test whose historical name mentions deferred bodies exercises dependency-driven refusals; the live catalogue itself contains real factories for all seven routes.

The previously recorded slice findings remain closed. Authored locale copy exists for all shipped languages; unmeasured counts remain unknown rather than false zero; review status and action authority follow the projection and canonical catalogue; classification exposes and admits its visible target; prepared import commands remain opaque, immutable, non-serializable, and free of protected path/provider leakage; asynchronous flows guard double submission, terminal state, failure text, and in-flight Escape; evidence hides hashes, provider locators, linked identities, and full internal identities; reconciliation selects by semantic row key and presents canonical score, separate match facts, explicit inconsistency direction, and affected-declaration change counts; and exact all-locale assertions pin the local-Ledger/AEAT separation.

## Architecture and interaction disposition

The TUI layer consumes injected immutable application projections and narrow protocols. It does not construct services, import adapters or CLI modules, read files, perform network access, or acquire business authority. Catalogue action identities are checked against their canonical application command keys, submitted identities are admitted against visible projection rows, and returned identities are validated. Read-only routes do not invent mutations; mutating routes require explicit selection and confirmation.

All screens preserve a single page scroll owner at eighty columns, avoid horizontal table scroll, use keyboard-reachable row semantics, and restore focus through stable semantic identities where applicable. Lifecycle transitions are monotonic, controls are disabled during mutation, Escape cannot abandon an in-flight operation, and failures render generic localized text. Ledger evidence remains explicitly local; AEAT Sync is described as a separate workspace and no AEAT authority is joined into the Ledger projection.

## Verification

Combined focused smoke: all 45 Ledger package tests passed with all markers enabled. Focused Ruff over the complete Ledger package and canonical application workspace passed. A direct prohibited-dependency/I-O scan returned no adapter, CLI, filesystem, network-client, or `open` use. Earlier slice gates additionally passed ty and basedpyright with zero reported diagnostics.

## Recommendation

CLOSE. W08.P27.S375 is safe to mark complete and proceed to the wider workbench phases. No high or medium issue remains.
