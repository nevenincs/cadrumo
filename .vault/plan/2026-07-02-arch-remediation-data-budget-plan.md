---
tags:
  - '#plan'
  - '#arch-remediation-data-budget'
date: '2026-07-02'
modified: '2026-07-08'
tier: L1
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-07-02-arch-remediation-data-budget-adr]]'
  - '[[2026-07-06-arch-remediation-data-budget-research]]'
---
# `arch-remediation-data-budget` plan

- [x] `S01` - Add hatchling wheel excludes for src/aeat/**/tests/** and src/aeat/tests/** so no test module or fixture ships in the installed wheel; `pyproject.toml`.
- [x] `S02` - Add a packaging content-boundary gate that builds the wheel and asserts no tests member is present; `src/aeat/tests/test_wheel_content_boundary.py`.
- [x] `S03` - Extend the packaging gate to assert the wheel contains the required data roots plus py.typed, the BIP-39 wordlist, and external_constants.toml so the exclude cannot silently strip functional payload; `src/aeat/tests/test_wheel_content_boundary.py`.
- [x] `S04` - Add a size-budget gate asserting the _data tree is at or under 550 MB, failing with a message that names the data-budget ADR and the two breach options raise-by-ADR or split; `src/aeat/tests/test_data_size_budget.py`.
- [x] `S05` - Declare the corpus-split escape hatch as a named constant beside the budget carrying its target condition so the option is discoverable in code; `src/aeat/tests/test_data_size_budget.py`.
## Description

This is a small single-concern L1 plan implementing the data-budget ADR, which
discharges the audit finding that the bundled `_data` tree grew 311 to 516 MB in
six weeks with no ceiling and no gate, while the wheel target packages `src/aeat`
with no exclude and therefore ships every `tests/` tree and fixture pool to
consumers who never run them.

The plan lands three moves as five steps. First, hatchling wheel excludes for
`src/aeat/**/tests/**` and `src/aeat/tests/**` shed the test payload immediately.
Second, a packaging content-boundary gate builds the wheel and asserts the
boundary both ways: no `tests/` member is present, and the required functional
payload (the `_data` roots, `py.typed`, the BIP-39 wordlist, and
`external_constants.toml`) is present, so the exclude cannot silently strip
something the installed package needs. Third, a size-budget gate asserts the
`_data` tree stays at or under 550 MB (the current 516 plus bounded headroom) and
fails with a message naming the ADR and the two options a breach permits
(raise-by-ADR or split the corpus), and the corpus-split escape hatch is recorded
as a named constant beside the budget so the option is discoverable in code, not
only in prose.

The ADR keeps the corpus-registry-packaging ruling intact: legal grounding still
verifies against the bundled authoritative text, and the exclude is scoped to
`tests/` trees only. The budget converts the next doubling from a silent surprise
into an ADR-governed decision.

## Steps

## Parallelization

S01 (the hatchling exclude) must land before S02 and S03, which build the wheel
and assert the exclude took effect. S02 and S03 are two assertions in the same
content-boundary gate and land together. S04 and S05 are the size-budget gate and
its escape-hatch constant, independent of the packaging-boundary work; they may
land in either order relative to S01 through S03. This is a single-owner
single-file-plus-two-test-modules plan confined to packaging config and the test
surface; it does not touch production behaviour and does not compete for any
contended file.

## Verification

- The wheel build produces no `src/aeat/tests/**` or `src/aeat/**/tests/**`
  member (S02).
- The wheel contains the `_data` roots, `py.typed`, the BIP-39 wordlist, and
  `external_constants.toml` (S03), so the exclude did not strip functional
  payload.
- `test_data_size_budget.py` passes at the current tree size and fails with an
  ADR-citing, two-option message when the `_data` tree exceeds 550 MB (S04).
- The corpus-split escape hatch is a named constant beside the budget carrying
  its target condition (S05).
- The plan is complete when every Step is closed and each Step carries an exec
  record per the plan-closure discipline.
