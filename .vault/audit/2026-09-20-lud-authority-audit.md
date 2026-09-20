---
tags:
  - '#audit'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:fafc94608e44f6bcd7e39691551db0fa58d6b11e99ede48efbe0f830c9527eb1'
related:
  - "[[2026-09-20-lud-authority-plan]]"
---
# `lud-authority` audit: integrated startup dependency review

## Scope

Reviewed the completed L1 plan against its accepted ownership policy and the integrated diff across storage taxonomy/materialization, application provisioning, authority-store admission, CLI startup, and focused tests. The review checked failure ordering, explicit-versus-derived path provenance, authority non-generation, metadata isolation, typed CLI projection, logging use, strict typing, and the recorded project gates.

## Findings

### pre-existing-quality-gate-debt | low | Repository-wide gates remain red outside this feature

`just check-code` retains unrelated diagnostics in untouched modules and several pre-existing structural gates. `just test-gate` retains failures in `dev/tests/test_import_quality_gate.py` caused by its event/schema and count expectations. The full Vaultspec check likewise retains 25 errors in historical execution mappings and one unrelated ADR. All Lud Authority scoped Vaultspec checks, focused suites, CLI contracts, production-module type checks, logging gate, lint, and formatting pass.

### fresh-linux-authority-bootstrap | medium | Resolved inherited runner override before lint dispatch

Fresh Linux CI entered the editable build with a non-empty, unavailable `CADRUMO_AUTHORITY_ROOT`, so the build hook correctly took its explicit-override refusal arm before default source bootstrap. A Git-archive `uv sync --locked` with no override proved default bootstrap succeeds. The shared CI setup action now clears the workstation override only for clean-checkout initialization; runtime and developer calls still fail on missing explicit overrides. Actionlint, focused packaging tests, Ruff, and ty pass.

## Recommendations

Track the repository-wide quality-gate debt independently. The feature-caused medium finding is resolved, and no follow-on architectural decision is required for Lud Authority before delivery.
