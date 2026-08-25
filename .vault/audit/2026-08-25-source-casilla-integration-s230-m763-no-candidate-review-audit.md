---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:2f30574b953e663d70d2896f2c376372613d2a9c9c7f68bcaa4c2fcb96cf87b2'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S230 M763 no-candidate review`

## Scope

Independent review of `94dd48c1ac`: three official M763 design eras, six
applicability revisions, header/non-header boundary, source lifecycle evidence,
and no-candidate census wording.

## Findings

### era evidence | low | three primary designs and selectors are exact

The bundled 2012, 2015, and 2018-onward design hashes recompute respectively as
`b9da58969e0a5cbea00c2f0780c3cbdc8fba3c5b9fc26d17042f8f277278d2fd`,
`124c40d7cdadced45e21a2b6b01bb9d76d30e78551ae7316508c14ceaec4f62e`, and
`590db67f074251ad1ddfcbebfffbf8d58f6157848b62661fadc334bc5e7af5d4`.
The six selected revisions preserve the supported 2012 Q2/Q3, 2013-14,
2015-17, 2018 Q1-Q3, Q4 2018, and 2019+ coordinates; 2011, 2012 Q1, and
2012 Q4 are refused.

### candidate boundary | low | no source fact is inferred from destinations

Every selected revision is applicability-grade and carries only the two
informational scheduling headers. No non-header manual casilla, binding,
formula, export layout, source owner, producer, calculation, filing
implementation, census row, or discovery inventory entry exists. Official
money, territory, payment, and identity targets are genuine, but their source
fact, grain, provenance, absence semantics, secure owner, and reviewed mapping
remain unestablished.

### document boundary | low | factual research needs no new ADR

Research is factual-only and correctly says `not_applicable` only for current
candidate enrollment, not for Modelo 763 tax facts. The existing accepted
source-connectivity framework governs any future candidate; no model-specific
normative decision or runtime/census promotion was introduced.

### verification | low | exact static checks are clean

The 16-item M763 registry gate collected after all three primary hashes matched,
but exceeded the local shell''s 30-second execution ceiling before completion.
Ruff was queued in the same capped invocation and therefore has no independent
completion result. This is an environment execution limit, not a test failure;
the focused gate must be rerun in an unrestricted session before release.

## Recommendations

PASS for the documentary no-candidate decision. Retain no M763 census entry.
A future exact-era candidate must establish authoritative source fact and grain,
identity, semantics, encrypted owner/provenance, and reviewed destination before
the framework permits a source slice. Rerun the 16-test gate and Ruff in an
unrestricted runner.
