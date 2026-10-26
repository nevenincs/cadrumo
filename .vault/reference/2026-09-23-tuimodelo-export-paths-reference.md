---
tags:
  - '#reference'
  - '#tuimodelo'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:6a5a226543de3a7637fc1822a7cda955ffd67878a1604efcaf42e4ba52cba4c1'
related:
  - "[[2026-09-07-tuimodelo-export-destinations-adr]]"
---

# `tuimodelo` reference: `export paths across the CLI, TUI and review package`

Every entrypoint that writes a fichero-BOE artefact was traced to the application
function it calls, and the result contract each one emits was compared. Sources are
the live tree at `3ddd8d54b7` plus the uncommitted election threading in this
worktree, and the operation journal of one installed TUI export.

## Summary

Three entrypoint routes reach the same application export function,
`export_modelo_revision` (`src/cadrumo/application/modelo/export.py:1573`):

- The supervised `modelo.export` operation, used by the TUI.
  `ModeloExportExecutor` (`src/cadrumo/application/modelo/operation_definitions.py:1084`)
  builds `ModeloExportCommand` from the journalled `ModeloExportRequest`
  (`operation_definitions.py:1034`) and returns only the artefact digest. The
  public result `ModeloExportPublicResultV1` (`operation_definitions.py:1062`)
  carries revision id, output path, byte size, file digest, export format and
  `handoff_required`.
- The CLI verb `app modelo export`, which bypasses supervision.
  `modelo_export_verb` (`src/cadrumo/entrypoints/cli/_modelo_export_cli.py:155`)
  calls the wrapper `export_modelo_revision_for_cli` (`_modelo_export_cli.py:102`),
  which calls the application function directly. It emits `ModeloExportPayload`
  (`src/cadrumo/entrypoints/cli/_modelo_payloads.py:1159`), which has sixteen fields,
  among them work unit, bucket, modelo, filing year, period, `bucket_event_id`,
  `resolved_result_disposition` and the three elections. It also emits two notices
  built from the rich `ModeloExportResult`: local export is not official evidence,
  and completeness is unverified (`_modelo_export_cli.py:48`,
  `_modelo_export_cli.py:76`).
- The CLI verb `app modelo review-package build`
  (`src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py:148`), which runs a
  business flow inside the command handler. It exports to a temporary draft
  through the same CLI wrapper (`_modelo_review_package_cli.py:201`), reads the
  bytes back, calls `build_review_package`, and prints the export's
  `bucket_event_id` (`_modelo_review_package_cli.py:239`). No application service
  or operation owns this sequence.

`application/modelo/quickfile.py:450` also calls `export_modelo_revision`, but from
inside an application service, so it is not a second entrypoint path.

The operation used to forward none of the three elections the CLI supplies
(refund, payment, prior domiciliation). An installed TUI export of a Modelo 303
therefore settled `failed` with `FAIL_MODELO_EXPORT` in phase
`modelo.export.preconditions`. The cause was the missing-election check at
`export.py:1452`, which runs before the product-identity gate at `export.py:1463`.
The CLI, supplying its defaults, reached the product-identity refusal instead.
The worktree now threads the elections through the request with the CLI's
defaults, and an integration test drives one revision through both routes to the
same refusal code
(`src/cadrumo/entrypoints/cli/tests/test_modelo_export_verb.py`).

Collapsing the CLI onto the operation meets three dependencies:

- The CLI envelope reports facts the public operation result does not carry:
  the export event id, the resolved disposition, the address coordinates, the
  evidence status and the completeness advisory.
- Seventeen docs sequence contracts under `docs/_sequences/contracts` invoke
  `modelo export`. Their goldens are generated from live CLI output.
- The review-package flow is the second consumer of the CLI wrapper. The wrapper
  cannot be deleted while it depends on it.
