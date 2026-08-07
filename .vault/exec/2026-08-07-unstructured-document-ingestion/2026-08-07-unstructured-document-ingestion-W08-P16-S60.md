---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:94dc8d501bd6ccce39bce65c00e27a14f73e5831220f68050585317c59d00e6e'
step_id: 'S60'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Add the batch verb family accepting a directory or repeated --file and executing the full per-item pipeline into typed per-item result rows, never aborting on one item, with exit status reflecting any-item failure, gated by a poisoned-item fixture batch completing and reporting the refusal row

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Mount `aeat app ledger evidence batch` on the evidence sub-app, taking an
  optional positional directory and a repeatable `--file`, with the run's
  direction declared once as `--kind`.
- Delegate the run itself to the existing application-layer runner rather than
  adding a second one; the surface resolves sources, projects rows and reports,
  and decides nothing about what a row means.
- Refuse only when no source at all was supplied. A non-existent path is NOT
  pre-validated, so it reaches the runner and is reported as an unreadable
  source rather than preventing the rest of the batch.
- Register the wire schema for `ledger.evidence.batch` in its own transport
  module, following the split pattern the ledger payload modules already
  document, and build it by re-validating the runner result's own dump so an
  upstream field either arrives by name or reds the strict schema.
- Exit non-zero on "any item was refused" only. A held draft and a deferred
  item both leave the exit status at zero.
- Add operator strings for the new surface in all four catalogues.

## Outcome

The operator half of batch ingestion is live: pointing the verb at a folder runs
every document through the full pipeline in one invocation and reports one typed
row each. A poisoned document becomes a refusal row carrying its code and its
detail while every other document in the same run still completes, which is the
property the adjacent statement folder-import path did not have.

Files: `src/cadrumo/entrypoints/cli/_ledger_evidence_batch_cli.py`,
`src/cadrumo/entrypoints/cli/_ledger_evidence_batch_payloads.py`,
`src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`,
`src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_batch_cli.py`, and the
four locale catalogues.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_batch_cli.py src/cadrumo/application/ledger/tests/test_batch_ingest.py src/cadrumo/application/ledger/tests/test_batch_ingest_runner.py -n0 -p no:cacheprovider -m "integration or not integration" -q
    40 passed in 110.82s (0:01:50)

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py src/cadrumo/entrypoints/cli/tests/test_operator_surface_contract_drift.py -n0 -p no:cacheprovider -m "integration or not integration" -q
    1 failed, 516 passed in 128.57s (0:02:08)

The single failure is `test_operator_surface_contract_covers_the_live_tree`,
reporting the `config provision` family mounted without a contract entry. That
family belongs to another lane and is untouched here; the ledger family and
every schema-registry check are green.

Mutation proof, applied from outside the repository under a lane-specific
filename so no tracked file was opened for editing. The runner's per-item guard
was replaced with one that re-raises on a refused row, reproducing the
abort-on-first-failure defect this Step exists to prevent:

    MUTATION-A-APPLIED target=_ingest_one_batch_item now=aborting
    4 failed, 5 passed in 68.40s (0:01:08)

The four reds are the poisoned-batch tests, and each failed on the production
path rather than in fixture setup: the run raised out of the runner and the CLI
error boundary emitted an `INTERNAL_CLI_UNEXPECTED_BOUNDARY` document in place of
the row set. The all-good positive control still passed under the mutation,
which is the reading that attributes the reds to the poison specifically.

## Notes

The host reports no readable accelerator, so admission control fails closed and
the poisoned PDF is deferred before the extractor sees it. Left alone, every
refusal assertion would have silently measured the pause path instead. The
session fixture therefore sets the documented contention-check override — the
setting the pause's own remediation text names for this machine class — so the
guard is configured rather than bypassed and the run still goes through the real
extraction path. No model is loaded, pulled or contacted at any point.

A malformed structured record was tried first as a host-independent poison and
rejected: the shape probe requires a well-formed parse, so a corrupted XML
probes as unknown and takes the same model-needing path as a scan.

The registration line reached HEAD ahead of this record through another lane's
broad sweep commit, which imported the new module before it was tracked. The
module, its transport schema and its gate were committed by the same sweep and
are at HEAD unmodified.

The Spanish and Catalan catalogue leaves are NOT yet at HEAD: the same sweep
took the English and Hungarian files and left those two behind, and both now
carry another lane's in-flight registry-localisation work while the locales
tooling relocation sits staged in the index. Committing them by either available
shape would take that peer content, so they are held with a HEAD-anchored
own-only patch prepared and the break reported rather than contended.
