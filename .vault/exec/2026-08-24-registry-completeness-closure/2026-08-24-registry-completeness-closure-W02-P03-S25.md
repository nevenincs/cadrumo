---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d64c324ee893b4f3836538ce94e18bec6a6fe95f052a8fc70176f82a868f87f3'
step_id: 'S25'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Adjudicate Modelo 840 revision 2003-y-siguientes record-terminator semantics and official extent

## Scope

- `.vault/reference/`

## Description

- Locate Modelo 840 registry, fixed-width codec, record-design parser, and
  generator authorities with Vaultspec-RAG; read the canonical codec and
  semantic-map authority in full; confirm exact symbols with `rg`.
- Re-read the hash-pinned official PDF, extract all three records through the
  committed parser, and compare its terminal rows and totals with the AEAT
  current and historic catalogues and BOE-A-2003-17642.
- Record the supported applicability boundary and route the one generic
  source-to-transport terminator bridge, source bindings, authority-grade
  decision, generated export, and emitted-byte proof to their existing owners.

## Outcome

Modelo 840 remains applicability grade and non-fileable. AEAT currently
publishes a single 2003 Modelo 840 design and no historic alternative; the
hash-pinned PDF parses completely into page-one, page-two, and annex records of
1,132, 1,165, and 1,067 bytes, respectively. Every record finishes with its
own ten-byte closing identifier followed by an explicit two-byte CRLF source
row.

The result does not author a layout. The existing canonical codec can append
the declared CRLF through `line_ending`, but the exact semantic-map bijection
cannot yet represent that official source row as transport-owned rather than as
a normal field. Literal, filler, omission, and ordinary-field alternatives each
emit the wrong bytes or correctly refuse. This is a bounded generic-generator
contract gap, not grounds for an M840-specific writer or schema.

The reference assigns the generator bridge and all map/profile/generated-byte
work to `W02.P04.S28`, source and repeated-row lifecycles to `S27`, and any
revision/grade decision to `S26`. The worklist remains live through `S29` until
those owners prove a real canonical export and an accepted authority decision.

## Notes

- No production source, registry data, test, local writer, submission route, or
  remote AEAT state changed.
- Focused parser, registry, and codec/generator checks are recorded with this
  Step after execution. Shared-worktree changes outside the two new records and
  the plan/index are not attributed to this Step.
