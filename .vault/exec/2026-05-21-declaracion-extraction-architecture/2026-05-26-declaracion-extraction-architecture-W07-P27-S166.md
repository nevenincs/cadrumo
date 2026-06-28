---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W07.P27.S166'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# declaracion-extraction-architecture W07.P27.S166

Authored a new amendment block in the declaracion-extraction-architecture ADR formalising the `corpus_round_trip_verified` field and the round-trip gate. Added plan steps S164-S166 under W07.P27 via CLI and marked all three closed.

## Files modified

- `.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md` — appended "2026-05-26 amendment (round-trip gate)" section
- `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md` — added and closed S164, S165, S166 under W07.P27

## ADR amendment summary

The amendment documents:
- The silent-failure class the M111/M130 finding exposed (fixture existence != extraction correctness)
- The new `corpus_round_trip_verified` field semantics
- The `validate_declaracion_pdf_round_trip_gate` logic and its non-overlap with the existing specimen gate
- Full ground-truth tagging table (VERIFIED / CORPUS-GAP / NO-FIXTURE-ALREADY-PROVISIONAL)
- The going-forward discipline: fixture present requires one of two flags or the build gate fails
