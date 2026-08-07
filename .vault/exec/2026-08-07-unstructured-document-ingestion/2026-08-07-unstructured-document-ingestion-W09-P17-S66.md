---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0181f7f76ed7b21f5937b118196ef24ae0674bff174e730e6110978ea6e32e12'
step_id: 'S66'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the review list and filter verbs surfacing per-field value, origin, verbatim anchor, grounding outcome, ambiguity candidates, findings and suggestions, gated by documented-command and JSON schema conformance

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Add a `review` subgroup under `evidence` with `list` and `show`, mounted from the existing evidence registration.
- Project the pending extraction drafts already held in the encrypted draft store; the review surface reads that store rather than re-running any reader.
- Emit one row per scalar draft field carrying value, origin, verbatim anchor, grounding outcome, self-reported-anchor flag, ambiguity candidates and note; emit the field even when no envelope exists, with the axes null.
- Emit the deterministic findings, the blocking findings with the id a resolution names, and the direction suggestion with the basis it was read from.
- Filter the queue by blocking reason, by deterministic check kind, and by "blocking only".
- Add `--resolve <finding-id>=<choose|supply|attest>:<value-or-reason>` to the confirm verb, repeatable, with no bulk form.
- Register two output schemas and set the operator strings in all four locale catalogues.

## Outcome

The operator meets a machine reading with everything the review gate requires in front of them. An exactly-parsed structured figure and an ambiguous text-layer reading are visibly different at the moment a person decides whether to accept either. Diagnostics ride the typed notice channel; the field rows, findings and blockers are primary result data.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_cli.py -n0 -p no:cacheprovider -q -m integration
    6 passed in 7.83s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -n0 -p no:cacheprovider -q -m integration
    352 passed in 22.89s

    uv run --no-sync python -m cadrumo.locales scaffold --check
    ca.yml: ok / en.yml: ok / es.yml: ok / hu.yml: ok

## Notes

Cache posture: `-p no:cacheprovider`, serial `-n0`. The marker expression is stated on each invocation because this file's tests are `integration` while the default lane is `unit`.

The `--resolve` option lands on the confirm verb, which is nominally the neighbouring Step's scope. Without it the gate that Step installs would be unreachable from the CLI, so it is recorded here as the CLI half.
