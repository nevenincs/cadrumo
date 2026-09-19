---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:8ebc85ed4c4e0ac8e8e276671e0765804c187c933e917fd6b1a597495ed0c1fb'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-08-10-m303-carry-reconciliation-s13-filed-population-measurement-blocker-audit]]"
---

# `m303-carry-reconciliation` audit: `M303 S13 measurement closure review`

## Scope

Independent read-only review of the S13 production measurement, its encrypted
store reader, the filed-observation and artefact models, and the plan's explicit
zero-target closure condition. The review replayed the aggregate query against
the currently active profile and assessed its output boundary. It did not inspect
or emit individual observation identities, artefact content, values, paths,
digests, storage references, or taxpayer data.

## Findings

No findings. The production query activated the configured master-key provider
and called `FiledDeclaracionObservationStore(Path('.')).list_observations()`.
The store resolves its repository from the active encrypted bucket; the legacy
path argument does not redirect the query to a fixture or plaintext store. The
replayed query returned `total_m303=0`, `m303_with_submitted_file=0`,
`m303_with_declaration_pdf=0`, and
`m303_declaration_pdf_without_submitted_file=0`.

The query's projection is privacy-bounded: it filters only the observation
`modelo`, reduces each retained observation to membership of the artefact
`kind` values `submitted_file` and `declaration_pdf`, and emits only four integer
counts. The capture code and model confirm those artefact kinds are independent:
a declaration PDF is captured when its copy link exists, while a submitted file
is attempted only when the archive link exists, and the observation schema does
not require either kind individually.

This is sufficient for S13's stated decision criterion. The target population
inside the current active-profile corpus is empty, so there is no declaration
render for S13 to parse and no parser should be added. The result is not evidence
that every Modelo 303 filing exposes a submitted file, nor a claim about any
other profile, a future capture, or the AEAT population generally.

## Recommendations

- Close S13 as measured-empty under its explicit zero-target condition, without
  implementing a declaration-render disposition parser.
- Preserve the measurement boundary in the closure record: current active-profile
  corpus at review time only. Reopen the recovery question if a later aggregate
  finds a Modelo 303 declaration PDF without a submitted file.
