---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:e564cbaa1a2a318591ad0da37eb6f947792acfbd9dd9bb3bc3b0ac3f65d305dc'
step_id: 'S57'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# `aeat-design-relayout-boundary` execution record: `W05.P11.S57`

Run the hardened span gate at HEAD, record its verdict, and prove it non-vacuous.

## Verdict at HEAD (2026-08-18)

`test_revision_span_matches_published_designs.py`: **9 failed, 14 passed** (164 s). The nine failures enumerate standing findings, none introduced by this campaign's landed steps:

- Modelos with unbundled design years or single-year spans without bundled designs (036, 038, 100, 111, 115, 117, 122, 123, 126, 128, 130, 136, 145, 151, 156, 165, 180, 181, 182, 185, 187, 188, 189, 193).
- Relayout crossings demanding splits not yet authored (184 2023/2025, 190 2024/2025).
- Modelo 303's two 2024 revisions: NO LEGAL EVIDENCE OF REVISION RECORDED (the 2024 epoch split cites only the founding orden in the legal catalogue) plus the mid-year relayout signal the split itself exists to serve.
- Modelo 100's 2020-2025 single-year revisions with no bundled design at all.

The renamed `303 revision 2022` produces NO span-gate finding of its own, confirming the window narrowing left the corpus-proven spans intact.

## Non-vacuity proof

One authored revision was withheld from a runtime copy of the registry (sitecustomize redirect under `tmp/`, the tracked tree untouched): modelo 303 revision `2025` deleted. The gate re-run against the mutated copy reds with a finding the HEAD run does not produce — `modelo 303 revision '2026-y-siguientes'` — proving the gate detects a withheld revision rather than redding vacuously. Injection at `tmp/sitecustomize.py`; verdicts at `tmp/s57_span_gate_head.txt` and `tmp/s57_mutated.txt`.
