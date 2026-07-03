---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W02.P04` summary

Phase P04 authored the four operator operating rules and the co-commit drift gate
that keeps them honest. All five steps closed; landed in commit `9fa93526c`.

- Created: `src/aeat/_data/agent/rules/operator-operating-rules.md`
- Created: `src/aeat/_data/agent/rules/operator-safety-handoff.md`
- Created: `src/aeat/_data/agent/rules/operator-envelope-reading.md`
- Created: `src/aeat/_data/agent/rules/operator-grounding.md`
- Created: `src/aeat/agent/tests/test_rule_surface_conformance.py`

## Description

- S14: The operating contract - never compute, estimate, or invent a tax value;
  relay CLI JSON verbatim with `legal_refs`/`source_refs`; never fabricate a tool
  result; stay inside the two-root surface and respect mutability.
- S15: Safety and filing handoff - never live-submit; a local `fichero-BOE` export
  is not official AEAT evidence; act on `warning` notices; treat zero tax on
  positive income as suspect; custody and confirmation discipline.
- S16: Envelope and exit-code reading - read `status` not stdout/stderr; exit `1`
  is an actionable verdict, only `6` is an abort; recover via the instructive
  surface; diagnostics ride only on `notices`.
- S17: Grounding - law-determined revisions (never inject one); provenance flows
  from the registry; do not present an under-declaration as complete; reach ledger
  values through the calculation path; run a command rather than guess.
- S18: The rule-surface drift gate parses every shipped rule, extracts each
  `aeat ...` command path and named envelope-spine field, and asserts they all
  resolve against the live operator-surface manifest and the real envelope models.

## Outcome

Three drift-gate tests pass: the rules exist, every cited verb resolves, and the
cited envelope-spine fields still exist on `SchemaEnvelope`/`Notice`. Ruff and the
docstring core-struct-links gate are green.

## Notes

The drift gate did its job during authoring: it (and a manual cross-check against
the manifest) caught a rule citing `aeat app modelo work export`, which does not
exist - the real verb is `aeat app modelo export` (registry key `modelo.export`);
the rule was corrected before commit.

The gate lives at `src/aeat/agent/tests/test_rule_surface_conformance.py`, not the
plan's stated `src/aeat/_data/agent/tests/` path: `_data` is shipped data, not a
Python package, so a test there would not be collected. Per the test-topology
rule, the gate belongs with its owning accessor package `aeat.agent`.
