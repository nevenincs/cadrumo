---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-06-11'
related:
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-research]]'
  - '[[2026-06-10-docs-terminology-search-plan]]'
  - '[[2026-06-10-docs-terminology-search-W05-P13-S29]]'
  - '[[2026-06-10-docs-terminology-search-W05-P13-S30]]'
  - '[[2026-06-12-docs-terminology-search-rung2-adjudication-audit]]'
---

# `docs-terminology-search` Code Review

## REVIEW-001 | LOW | No blocking findings in S29 curation-ratchet closeout

Reviewed the S29 curation-backlog ratchet against ADR D3 and D8 expectations, the primary plan, the generated API stub surface, and the focused real-behavior gates. The implementation files for `check_curation_backlog_ratchet()`, the committed 75/75 baseline, and the `audit --ratchet-check` CLI surface are already present in HEAD and are covered by the ratchet tests. The API stub tree is conformant, plan status reports 27 of 32 steps complete, and the current local closeout diff only adds the S29 exec evidence.

Residual risk is coordination-only: the shared worktree received concurrent commits while this review was running, so later PM handoff should treat HEAD as authoritative and avoid assuming local dirty status reflects the whole S29 implementation.

## REVIEW-002 | LOW | S21 ratification validation needed shipped-vocabulary proof

Reviewed the S21 synonym-candidate mining and ratification queue against ADR D6 and the plan requirement that unratified candidates never reach the shipped index. The first pass proved ratified rows landed in the Handbook and unratified rows were absent from the query vocabulary, but a ratified hidden search form could have passed if it existed only on a non-shipping term row. The validation was tightened in `dev/docs/terminology/_synonym_mining.py` so ratified candidates must also be present in the shipped query vocabulary. Post-fix gates passed: focused synonym/sweep/relevance tests, full `dev/docs/terminology` test slice, ruff, targeted ty, queue CLI validation, and the wheel data packaging test.

No blocking findings remain for S21. The remaining risk is operational: the embedding observation export still runs outside CI by design, so CI validates only the committed plain-data queue and its relation to the Handbook.

## REVIEW-003 | LOW | No blocking findings in S30 miss-rate adjudication

Reviewed the S30 held-out miss-rate harness against ADR D6, the step requirement, the committed relevance artifact, and the new vault adjudication record. The evaluator loads the real bundled held-out corpus and the real committed `SweepResult`; it does not run live RAG in CI, does not ship model-derived vectors/scores, and classifies misses by reason before producing the rung-2 decision. The current measurement is intentionally recorded as degraded-input evidence: 5 held-out cases, 1 hit, 4 targetless misses, 80.00% miss-rate, 76 failed compiled queries, and decision `refresh-relevance-first`.

No blocking findings remain for S30. The remaining risk is operational and already captured in the adjudication: the static embedding matrix should not be implemented until a full non-degraded relevance refresh is available and the same harness still exceeds the 20% miss-rate threshold.
