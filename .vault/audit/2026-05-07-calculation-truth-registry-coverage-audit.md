---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-07-calculation-truth-registry-phase0b-coverage-exec]]'
---



# `calculation-truth-registry` Code Review


CTR-COVERAGE-001 | CRITICAL | Focused registry catalogue suite must pass before accepting the gate

The reviewer observed a transient failure in
`test_committed_registry_tree_has_required_model_law_coverage` through
`audit_registry_model_law_coverage`, reporting Modelo 100 source-citation
validation failures. Re-run after the review passed with 31 tests. No code
change was required for this item.

CTR-COVERAGE-002 | HIGH | Workbook refs must not satisfy a coverage tier without matching source-tier evidence

The initial layout gate could count a workbook parity reference by
`formula_coverage` alone. The implementation now requires the workbook source
itself to carry the matching evidence tier before it can satisfy executable
parity or layout authority.

CTR-COVERAGE-003 | MEDIUM | Existing plan body contains development-condition metadata

The plan body still contains pre-existing commit references and transient
environment notes outside this coverage-audit slice. The current slice did not
add new process metadata, but the sanitization gate remains open for a separate
plan cleanup pass.

CTR-COVERAGE-004 | LOW | Catalogue verification pays whole-tree validation cost twice

The new audit validates the whole registry in addition to the existing
catalogue coherence test. Runtime is currently acceptable for the focused gate,
but the suite can be consolidated if this becomes a persistent performance
problem.
