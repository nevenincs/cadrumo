---
tags:
  - '#audit'
  - '#compatibility-lifecycle'
date: '2026-07-09'
modified: '2026-07-09'
related:
  - "[[2026-07-09-compatibility-lifecycle-plan]]"
---

# `compatibility-lifecycle` audit: `honesty review (campaign close): PASS + verified findings`

## Scope

Mandatory fresh-context honesty review (`aeat-campaign-close-honesty-review`) of the
dormant compatibility-lifecycle checkpoint mechanism — commits `ffb2f94605` (code) and
`0a3367f56d` (companion rule) — against ADR `2026-07-09-compatibility-lifecycle-adr`. An
independent Opus reviewer read the module, the central gate, the three regime-aware tier
gates, and the rule in full and ran the affected suites; the coordinator re-verified every
finding against HEAD.

**Verdict: PASS.** Truly dormant today — `ffb2f94605` touches zero production modules
(only the new isolated `core/compatibility_lifecycle.py`, an additive facade re-export, the
three tier-gate TEST files, two new test files, an empty-corpus README, regenerated stubs);
no production read path, floor, or registry changed by a byte; 34 passed. The tier gates
assert exactly what they did before (the archive pin was renamed, not weakened — under
`PRE_RELEASE`, `expected_floor()` returns `current`, so the assertion reduces to the same
equality). The predicates are pure and honest; the 9 synthetic tests assert output against
independently-reasoned expectations (not re-implementing the predicate) and exercise both
regimes — real teeth, not tautological. The tripwire reads real `aeat-cli` metadata
(`0.1.1` → major 0 < 1) and would red a 1.0 cut made unflipped; coherence is truly
bidirectional; no old-shape fixture, upgrader, or read-tolerance was added; the rule matches
the code; import hygiene holds. No REVISION required.

## Findings

### third-flip-constant-uncovered-by-coherence | medium | RESOLVED — _RELEASED_FORMAT_CURRENT_VERSIONS was not bound to the coherence gate

`_RELEASED_FORMAT_CURRENT_VERSIONS` (`test_compatibility_lifecycle_gate.py:62`, the coverage
harness's range source) must be populated at flip alongside `RELEASED_FORMAT_FLOORS`, but the
coherence gate bound only the floors to the regime — so a flip that froze floors but forgot
the current-versions would fail with a bare `KeyError` at the coverage loop (loud, not silent;
no correctness hazard) rather than an instructive gate failure. Disposition: FIXED now (commit
`4f521273d2`) — a new `test_every_flip_time_constant_moves_together` asserts
`set(_RELEASED_FORMAT_CURRENT_VERSIONS) == set(RELEASED_FORMAT_FLOORS or {})`, vacuously green
today (both empty) so it changes no pre-release behaviour, and it catches the incoherent flip
with a clear message. This is gate self-consistency (dormant policy metadata, the same category
as the existing floor coherence), not flip-enforcement, so fixing it now does not brush
`no-legacy-compatibility`.

### upgrader-arm-not-wired-to-live-enforcement | low | the predicate's missing_upgraders arm is decorative capacity today

The central coverage gate passes `has_registered_upgraders_for_gap=True`
(`test_compatibility_lifecycle_gate.py:153`) and the tier regime tests never call
`lineage_obligations`, so the predicate's upgrader axis is not wired to a live enforcement
path. It is NOT lost: upgrader-chain completeness is enforced by the PRE-EXISTING chain tests
(`test_every_registered_namespace_upgrade_chain_is_complete`,
`test_bundle_upgrade_chain_is_complete_from_floor_to_current`, and the archive
importable-range test) which survive and cover `range(floor, current)`. Disposition: DEFERRED
to the checkpoint-flip campaign — wiring the flag from real registry state is building
flip-enforcement, which `no-legacy-compatibility` forbids before a real post-flip bump exists.
Recorded on the flip checklist that the chain tests carry upgrader enforcement.

### archive-no-structural-upgrader-gate-post-flip | low | the archive tier leans on the mandated restorability test, not a chain gate

The archive tier has no dispatch registry, so post-flip nothing structurally proves a
version-aware `read_sealed_archive` reader exists — the companion rule mandates a hand-written
restorability test in the flip commit as the enforcement instead. Inherent to the archive
tier; no today-defect. Disposition: DEFERRED to the flip campaign (the restorability test is
authored in the flip commit, per the rule).

## Recommendations

- The MEDIUM is closed at commit (`4f521273d2`); the two LOW findings are correctly deferred to
  the future checkpoint-flip campaign because building their enforcement now would violate
  `no-legacy-compatibility` (fabricating enforcement for a flip that has not happened) — this is
  the ADR's already-accepted "literal future flip" scope, not a new deferral.
- With the MEDIUM fixed and the two LOWs on the flip checklist, the compatibility-lifecycle
  campaign is structurally complete: the mechanism is honestly dormant today, its future teeth
  are real, and the governance rule is faithful to the code.
