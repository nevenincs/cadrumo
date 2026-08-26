---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-06-11'
modified: '2026-08-26'
body_hash: 'sha256:af796ba7f42cca8802ca0cf521c46b397c3a3574a40aaeb1aca8d36fe534ceee'
related:
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-research]]'
  - '[[2026-06-10-docs-terminology-search-plan]]'
  - '[[2026-06-12-docs-terminology-search-close-honesty-audit]]'
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

## REVIEW-004 | LOW | S31 self-hosting vocabulary passed after concept-id correction

Reviewed the S31 architectural-vocabulary enrolment against the ADR D1-D9 definitions, the Handbook loader gates, the concept-card projection surface, and the package-data guard. The first pass used an English concept id for the Terminology Handbook concept; this was corrected to the Spanish-stem `manual-terminologia` concept id while preserving `Terminology Handbook` as an admitted/preferred term label. The file remains at the existing tracked path so the wheel data guard still validates every tracked terminology file.

No blocking findings remain for S31. The seven self-hosting concepts are approved, ADR-grounded, relation-linked under `manual-terminologia`, projected into concept cards, and covered by the S31 test. The curation ratchet remains clean at 75 draft concepts and 75 empty short descriptions.

## REVIEW-005 | LOW | S01 upstream preprocess-hook kickoff is tracked

Reviewed S01 against ADR D6 and the plan requirement for an upstream vaultspec-rag issue reference. The installed `vaultspec-rag` package metadata points to `operator/vaultspec-rag`; the repository has issues enabled, and issue #185 is open. Its body covers the generic hook contract: per-project preprocessor registration, versioned structured output, cache keys over source hash plus preprocessor/schema identity, explicit failure semantics, watcher integration, size-limit interaction, and adjacent default-extension asks. The AEAT workstream is linked from upstream comment `https://github.com/operator/vaultspec-rag/issues/185#issuecomment-4687704833`, and the local plan row now carries the issue URL.

No blocking findings remain for S01. The issue is intentionally upstream and generic; AEAT-specific extractors remain local under the interim sidecar path documented by S02.

## REVIEW-006 | LOW | S32 honesty review and codification are structurally complete

Reviewed S32 against the campaign-close honesty rule, the accepted ADR codification candidates, the plan/exec coverage check, and the synced provider rule outputs. The close-honesty audit explicitly verifies plan/exec consistency, records the S30 degraded-relevance residual instead of overclaiming coverage, and confirms the three codified rules were scaffolded through `vaultspec-core spec rules add`, authored with Rule/Why/How bodies, verified with `spec rules show`, and synced through `vaultspec-core sync`.

No blocking findings remain for S32. The feature index must be refreshed after this new audit document, and the known unrelated vault-wide structure errors remain outside this feature.
