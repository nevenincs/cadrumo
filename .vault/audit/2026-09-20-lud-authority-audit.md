---
tags:
  - '#audit'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:fbb8aa44c298f36541e416b14ae06a04a2f97addbef82eddefc54a7664fdc884'
related:
  - "[[2026-09-20-lud-authority-plan]]"
---
# `lud-authority` audit: integrated startup dependency review

## Scope

Reviewed the completed L1 plan against its accepted ownership policy and the integrated diff across storage taxonomy/materialization, application provisioning, authority-store admission, CLI startup, and focused tests. The review checked failure ordering, explicit-versus-derived path provenance, authority non-generation, metadata isolation, typed CLI projection, logging use, strict typing, and the recorded project gates.

## Findings

### pre-existing-quality-gate-debt | low | Repository-wide gates remain red outside this feature

`just check-code` retains unrelated diagnostics in untouched modules and several pre-existing structural gates. `just test-gate` retains failures in `dev/tests/test_import_quality_gate.py` caused by its event/schema and count expectations. The full Vaultspec check likewise retains 25 errors in historical execution mappings and one unrelated ADR. All Lud Authority scoped Vaultspec checks, focused suites, CLI contracts, production-module type checks, logging gate, lint, and formatting pass.

### fresh-linux-authority-bootstrap | medium | Resolved CI setup refusal before lint dispatch

Fresh Linux CI proved the build hook's source-shape predicate could reject a clean checkout before invoking the canonical authority compiler. The explicit override and embedded-sdist arms already resolve first, so the remaining missing-default arm now invokes the compiler directly and fails there if source inputs are incoherent. A Git-archive `uv sync --locked` proved that path publishes authority successfully. CI also clears `CADRUMO_AUTHORITY_ROOT` only during clean-checkout setup so a self-hosted runner environment cannot alter the tested default posture; runtime and developer calls still fail on missing explicit overrides.

## Recommendations

Track the repository-wide quality-gate debt independently. The feature-caused medium finding is resolved, and no follow-on architectural decision is required for Lud Authority before delivery.
