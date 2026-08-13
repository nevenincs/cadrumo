---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:939e43d2ba9b93466531725c0d6cefed7b6ffbd84bb0965fca933d6d87502038'
step_id: 'S14'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
  - "[[2026-08-13-legal-corpus-vintage-vintage-screen-review-audit]]"
  - "[[2026-08-10-legal-corpus-vintage-adr]]"
---

# Refuse the version pile structurally, rather than resting on nothing pointing at it yet. The 58 acquired article payloads carry BOE's full redaction history by design, but the extractor folds every version into ONE undelimited unit with no fecha_vigencia attribution, and boe-a-1991-14392-a30-redacciones is ten versions in a single 15.8k-character unit. Any corpus_ref resolving there fuses repealed and current law, and a required_text presence check passes on REPEALED text, which is the trap the grounding rule states verbatim and the trap the S05 row names in its own heading. S06 handled it for the screen by reading the raw payload and reducing to the redaction in force, but the committed DATA is still a pile. Either split the article-endpoint extraction one unit per version carrying its fecha_vigencia, or refuse at registry build any corpus_ref resolving to a redacciones sidecar. Prove the refusal bites by breaking it on purpose from outside the repo

## Scope

- `dev/docs/preprocess/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/_data/corpus/normatives/html/`

## Description

## Outcome

## Notes
