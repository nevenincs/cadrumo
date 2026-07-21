---
tags:
  - '#adr'
  - '#arch-remediation-data-budget'
date: '2026-07-02'
modified: '2026-07-08'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-05-15-corpus-registry-packaging-adr]]"
  - '[[2026-07-06-arch-remediation-data-budget-research]]'
---
# `arch-remediation-data-budget` adr: `bundled data budget and wheel content boundary` | (**status:** `accepted`)

## Problem Statement

The architecture review (finding bundled-data-weight-unbudgeted) measured
`src/aeat/_data` at 516 MB (265 MB `corpus/aeat_official`, 176 MB
`corpus/manuals`, 48 MB `registry`), up from ~311 MB at the 2026-05-16
packaging audit - +65% in six weeks with no ceiling and no gate. The wheel
target packages `src/aeat` with no exclude, so every install additionally
ships `src/aeat/tests` (11 MB of fixtures including the PDF corpus) and
every per-domain `tests/` folder. Bundling the corpus is an accepted
decision (offline-verifiable legal grounding, corpus-registry-packaging
ADR); the unbudgeted growth and the test/fixture payload are not decisions
anyone made. This ADR sets the boundary and the gate.

## Considerations

- The corpus-registry-packaging ADR's core ruling stands: legal grounding
  verifies against BUNDLED authoritative text; nothing here weakens that.
- Growth is legitimate demand (new modelos ground against new corpus); the
  problem is that growth is invisible, not that it happens.
- Test modules and fixtures in the wheel serve no installed consumer: the
  suites run from the repo; the in-package topology is a repo-layout
  decision, not a distribution decision.
- Splitting the corpus into a separate data distribution is a real option
  but a large packaging change (resource-resolution seams, two-artifact
  release discipline) with no current forcing function.
- The licence-clean shipping rule scales with bundled corpus size; the
  budget gate doubles as the trigger to re-examine that surface.

## Considered options

- **Option A: status quo.** Unbudgeted growth, tests shipped; rejected.
- **Option B: split the corpus into an optional data package now.** Pro:
  small core wheel. Con: large packaging surface for a local-first app
  whose install size has produced no operator pain; premature; rejected for
  now, kept as the budget-breach escape hatch.
- **Option C (chosen): exclude tests/fixtures from the wheel + a declared
  size budget with a CI gate + split-as-target-condition.** The budget may
  only be raised by an accepted ADR; a breach forces either that ADR or
  Option B.

## Constraints

- The wheel must remain functionally complete: `_data` (corpus, registry,
  terminology, agent harness), `py.typed`, the BIP-39 wordlist, and
  `external_constants.toml` all stay packaged; the exclude is scoped to
  `tests/` trees and test fixture pools only.
- A post-build content assertion must prove the boundary (a gate that
  builds the wheel and asserts no `tests/` member and presence of the
  required data roots) - the exclude alone is config that can silently rot.
- The dev/test workflow is unaffected: suites run from the repo tree;
  nothing imports `aeat.tests` from an installed wheel.
- Budget arithmetic lives in one place (the gate), reads the tree size
  directly, and cites this ADR in its failure message.

## Implementation

Three small moves. First, the hatchling wheel target gains excludes for
`src/aeat/**/tests/**` and `src/aeat/tests/**`; a packaging gate builds the
wheel and asserts the content boundary both ways (no test members; data
roots present). Second, a size-budget gate asserts the `_data` tree at or
under 550 MB (current 516 plus bounded headroom), failing with a message
that names this ADR and the two options a breach permits (raise-by-ADR or
split). Third, the split option is recorded as deferral-as-data: a named
constant beside the budget with the target condition, so the escape hatch
is discoverable in code, not only in prose.

## Rationale

The audit's point was trajectory, not size: 311 to 516 MB happened
invisibly. A budget converts the next doubling from a surprise into a
decision. Tests out of the wheel is the free win (no consumer exists);
corpus splitting is deliberately NOT taken - the bundled corpus is
load-bearing for legal grounding and the operator pain that would justify
two artifacts has not appeared. The gate is what makes this a decision
instead of a hope.

## Consequences

- Installs shed the test payload immediately; the data payload becomes a
  monitored, ADR-governed number.
- A corpus-heavy campaign (e.g. multi-year M100 grounding) may hit the
  budget mid-flight: that is the mechanism working - the campaign brings a
  one-paragraph budget-raise ADR or triggers the split decision.
- One more gate in CI (build + assert), a few seconds of wall time.
- The wheel content boundary becomes testable; future packaging refactors
  inherit an executable contract instead of the current implicit one.
