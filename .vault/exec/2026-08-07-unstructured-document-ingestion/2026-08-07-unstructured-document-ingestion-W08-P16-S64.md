---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d617d86d39c5f4891d6d03e427c5aea5eacf6e0a574eb1e4de85dece964caf44'
step_id: 'S64'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Report progress through the notice channel in text mode and complete typed row sets in JSON mode, gated by the envelope schema conformance suite

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Stream one progress notice per completed document in text mode, built from
  the runner's existing per-item hook so no second progress channel is opened.
- Suppress that stream in JSON mode, where the complete typed row set on
  `result` already carries every item; duplicating each row as a notice would be
  the second channel and would bloat the one document a machine consumer parses.
- Rebuild the streamed text line from the same notice it reports, so the two
  surfaces cannot say different things.
- Report refusal, deferral and pending review as three distinct run-level
  notices with three codes, folded into the closing text block from the same
  builder that supplies the JSON notices channel.
- Carry the deferral's remediation from the provisioning probe that measured the
  condition, and carry the snapshot's own cause tokens through unflattened.

## Outcome

A text-mode operator watches the run progress document by document and reads a
closing block naming every refusal, every unreadable source and the pause. A
machine consumer reads one JSON document carrying every row, the per-status
tally with each status present at its count, and `any_failed` and `any_deferred`
as two separate booleans.

The two signals never merge. A refusal says a document was rejected and sets a
non-zero exit; a deferral says work this run did not attempt is still
outstanding, carries the probe's remediation, and leaves the exit status at
zero. A held draft is the third case and is reported as information pointing at
the review queue.

Files: `src/cadrumo/entrypoints/cli/_ledger_evidence_batch_cli.py`,
`src/cadrumo/entrypoints/cli/_ledger_evidence_batch_payloads.py`,
`src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_batch_cli.py`, and the
four locale catalogues.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py src/cadrumo/entrypoints/cli/tests/test_operator_surface_contract_drift.py -n0 -p no:cacheprovider -m "integration or not integration" -q
    1 failed, 516 passed in 128.57s (0:02:08)

The one failure names the `config provision` family, which belongs to another
lane. Every envelope check the new command is subject to is green: it resolves
as a registered CLI leaf, its schema specialises the envelope, and it carries no
bespoke notice, advisory or next-step field.

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_batch_cli.py src/cadrumo/application/ledger/tests/test_batch_ingest.py src/cadrumo/application/ledger/tests/test_batch_ingest_runner.py -n0 -p no:cacheprovider -m "integration or not integration" -q
    40 passed in 110.82s (0:01:50)

Two mutation proofs, both applied from outside the repository under
lane-specific filenames.

Collapsing the deferred signal into the failed one, by rebinding the run
result's `any_deferred` property at class level so it returns `any_failed`:

    MUTATION-B-APPLIED any_deferred was=<property object ...> now=<property object ...>
    1 failed, 8 passed in 47.98s

The red is the distinctness gate, failing on `assert deferred.any_deferred is
True` — the assertion under test, not fixture setup.

Removing the text-mode progress sink, leaving the closing summary intact so the
run still looks correct:

    MUTATION-C-APPLIED run_evidence_batch now=without_progress
    1 failed, 8 passed in 50.96s

The red is `assert len(progress) == 2` with an observed empty list, which is the
stream itself and not the report it precedes.

## Notes

The deferred-versus-failed rendering is proven against real result models
constructed directly rather than against a live paused run. A live pause is
available on this host — admission control fails closed here — but it is a
property of the machine, so a gate resting on it would pass for the wrong reason
on this box and fail on one with a readable accelerator. The engine's own suites
own the production of a pause; this gate owns its projection.

The per-item notice severity follows the row: only a refusal is a warning. A
no-op is the idempotent success and a held document is the review gate working,
and marking either as a warning would teach an operator to read a correct run as
a troubled one.

The Spanish and Catalan operator strings for this surface are written and
verified but not yet at HEAD; the reason and the prepared own-only patch are
recorded on the sibling Step record for S60.
