---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:9e776efc018ccbdd78ebb187012457e5d888f5cc95b65929931861dc8a640270'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-s31-render-profile-audit]]"
---
# `aeat-export-fragment-generator-authority` audit: `s32 render profile integration`

## Scope

Verdict: **PASS. No open critical, high, medium, or low findings remain.**

This final independent review reconciled `W02.P03.S32` with the accepted generator-authority ADR, its authority-gap research, completed profile and fixed-width steps, and the current generation, provenance, publication, recovery, validation, and check boundaries. It confirmed one wire-authority `RenderProfile`, one transport-only profile, one canonical `render_profile_digest`, and the canonical core link-safety predicate. No legacy layout, profile alias, fallback, default, or duplicate inference capability remains in the reviewed boundary.

Real behavior evidence passed: the focused generator/profile/provenance/publication/check/envelope selector collected 106 tests; the full development-registry unit lane collected 190 tests. Scoped Ruff and strict BasedPyright were clean, and `git diff --check` was clean. The default pytest selector that collected zero tests was discarded rather than treated as evidence.

## Findings

### publication-recovery-authority-bypass | high | Interrupted publication could finalize stale profile provenance

Resolution: **RESOLVED.** Recovery now carries the current joined design, semantic map, rendered layout, profile, and evidence through every candidate and target acceptance branch. It loads the exact layout and invokes the canonical provenance verifier before any promotion, rollback deletion, journal finalization, or early return. Real interrupted-recovery mutations of the profile and source evidence refuse while retaining the live target, rollback, and journal bytes.

### variable-envelope-validation-order | medium | A bad profile could fail before the variable envelope hard stop

Resolution: **RESOLVED.** Fixed-width generation now rejects every typed variable envelope immediately after transport validation and before profile validation or target creation. The real Modelo 200 envelope test deliberately supplies an inapplicable profile and proves the envelope refusal still wins, so restoring the old order fails the test.

### linked-official-source-guard | low | Source evidence did not use the canonical link predicate

Resolution: **RESOLVED.** The source-evidence loader now uses the sole `is_link_like` core predicate. A real linked official binary refuses before hashing, and an AST guard fails if inline or redeclared source-link logic replaces the canonical owner.

## Recommendations

Accept `W02.P03.S32`. Preserve exact-anchor-only blank-wire resolution, profile schema/digest provenance, canonical core link safety, current-authority recovery verification, variable-envelope-first refusal, the hard removal of `ExportRenderProfile`, and the real-source regression boundaries.
