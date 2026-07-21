---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W03.P07` summary

Phase P07 stood up the operator golden-task eval. All four steps closed; landed in
commit `2c8020cf5`.

- Created: `src/aeat/agent/eval/_models.py`
- Created: `src/aeat/agent/eval/scenarios/modelo_130.toml`
- Created: `src/aeat/agent/eval/_runner.py`
- Created: `src/aeat/agent/eval/tests/test_modelo_130_golden.py`
- Modified: `src/aeat/agent/tests/test_rule_surface_conformance.py`

## Description

- S24: `GoldenScenario` / `GoldenResult` strict models - the declared workflow
  expectation (modelo, year, period, skill, expected trajectory, provenance
  required) and the per-dimension verdict.
- S25: The modelo-130 scenario TOML declaring the expected tool trajectory and
  requiring registry provenance; no casilla value is asserted.
- S26: A pure runner (the resolvable command set is injected, so it never imports
  the entrypoints layer) asserting four dimensions: trajectory resolves against
  the live CLI keys, lifecycle order (create->calculate->verify->export), skill
  consistency (the playbook cites every trajectory verb), and provenance (the
  resolved revision's casillas carry legal_refs/source_refs via a pure registry
  snapshot read, no secrets).
- S27: The golden gate - the modelo-130 scenario passes every dimension; an
  anti-tautology pair proves the runner rejects a fabricated verb and an
  out-of-order lifecycle; a non-vacuous proof confirms the modelo-130 revision
  actually carries grounding (20 casillas, all with legal_refs/source_refs).
- Drift gate extension: `test_rule_surface_conformance.py` now validates persona
  and skill verbs in addition to rule verbs.

## Outcome

Ten agent tests pass (3 drift + 3 packaging + 4 golden). Ruff and the docstring
core-struct-links gate are green.

## Notes

The runner stays CLI-pure by taking `valid_commands` as an injected parameter; the
test wires it from the CLI schema registry. The value-oracle dimension (a seeded
calculation compared to an AEAT published modelo-130 figure) is a deliberate
follow-up: fabricating an expected value would be a tautological calculation test,
so the slice asserts trajectory, lifecycle, skill-consistency, and provenance
instead - all real and deterministic.
