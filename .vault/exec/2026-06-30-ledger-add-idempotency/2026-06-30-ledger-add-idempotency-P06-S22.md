---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:be0091e37384b8c156f325c39d1db8906c01afd6e59f88549368f71a5fe896bd'
step_id: 'S22'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Surface the idempotent re-file no-op outcome as an info Notice on the modelo file envelope through the typed notice channel, never as a bespoke result field

## Scope

- `src/aeat/entrypoints/cli/_modelo_filing_cli.py`

## Description

- Detect the re-file no-op in the `work file` CLI handler from the resolved revision state (already PRESENTADO) and emit an info `Notice` on the `modelo.work.file` envelope through the typed notice channel, carrying `calculation_revision_id` and `filing_record_id` on `Notice.context`.
- Fold the same message into the text `lines` so JSON and text output cannot drift.

## Outcome

Landed in commit `d4f2407cb`. ruff, ruff-format, and ty clean.

## Notes

The operator message is an inline string, mirroring the existing hardcoded `filing_disambiguation` line emitted in the same handler. A locale key was deliberately avoided: all four locale catalogues were under concurrent multi-campaign rewrites (whole-file CRLF/canonical churn) and the shared git index held peer-staged locale files, so introducing and committing a new key cleanly was not safe this cycle. Surfaced to the coordinator; a follow-up locale pass can promote the message to a `tr` key once the locale surface settles.
