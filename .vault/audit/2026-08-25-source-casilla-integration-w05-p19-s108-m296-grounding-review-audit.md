---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:4925b43abb5aa74a30030ffa52e34c4e4ec5bcae1e9f2210258ae735af904a9b'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `w05 p19 s108 m296 grounding review`

## Scope

Independent review of S108 evidence commits `19974a1c7f` and `c132efbc52`, current M296 registry/census, the withholding owner, and the M193 S106 mixed-sweep boundary.

## Findings

### s108-m296-grounding | resolved | evidence supports registry-blocked refusal

The locally pinned M296 design, procedure, and 193/296 note hashes recompute to the values recorded in the research. The official row requires recipient and representative identity, country and IRNR keys, declarant record identity, and Annex association. The candidate aggregates rows and synthesises identity; the encrypted M180/M193 withholding store has no M296 scheme or resolver and omits the required grain. Existing manual box entry and caller-populated export are not source ownership. No connected M296 persistence, replay, review, or source-owned export is present.

## Recommendations

Retain `registry_blocked`. Reopen only after official M296 bindings and a non-lossy secure row owner, resolver, lifecycle proof, and Annex-preserving repeated-record export are accepted.
