---
tags:
  - '#plan'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
tier: L1
related:
  - '[[2026-07-25-declaracion-profile-printed-box-scope-adr]]'
  - '[[2026-07-25-declaracion-profile-printed-box-scope-research]]'
  - '[[2026-07-25-declaracion-profile-printed-box-scope-revision-scope-and-coverage-evidence-audit]]'
---

# `declaracion-profile-printed-box-scope` plan

- [ ] `S01` - Drop the six non-printed-box targets from the extraction profile target list, retaining the printed-box targets it already carries, across both revisions per the operator ruling; `extraction profiles, 2 TOML files`.
- [ ] `S02` - Restate min_coverage at the level the form genuinely yields across all four annex quarters, accommodating legitimately blank optional boxes rather than assuming the 1T shape; `extraction profiles`.
- [ ] `S03` - Stop the generator printing the six Primitivo line items, judging its remaining output against the printed form rather than against the profile, which reverses the causality that produced the defect; `dev/, generator`.
- [ ] `S04` - Sweep the TOML-dominated id footprint, 38 registry files plus 2 extraction profiles carrying the six ids, since the registry TOMLs are where the edit actually lands and a module-count sizing understates the work by more than half; `src/cadrumo/_data/registry/, 40 TOML files`.
- [ ] `S05` - Update the 15 synthetic corpus fixtures and 48 expected-value entries across 8 fixture blocks that carry the moved expectations; `test fixtures, corpus`.
- [ ] `S06` - Update the three parser-boundary modules the layout change reaches; `parser boundary modules`.
- [ ] `S07` - Report as a finding any synthetic M303 expectation that stays green through this layout change, because a green expectation across a layout change is itself evidence the corpus is not measuring layout, rather than quietly leaving it alone; `.vault/audit/, synthetic M303 expectations`.
- [ ] `S08` - Confirm the 24 Python modules carrying the six ids stay unaffected, 16 tests and 7 registry and 1 fixture with zero production application modules, since the engine reaches these ids through registry TOML rather than through Python; `src/cadrumo/, dev/`.

## Description

## Steps

## Parallelization

## Verification

## Context

Accepted ADR ruling both revisions in scope per operator decision, carrying no plan and no exec records. A companion coverage-evidence audit records the measured coverage floor.
