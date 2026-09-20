---
tags:
  - '#audit'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:7c3e74656d5a8d02f13dbbc18ea61b254a5d9f5dcd6cd35624f12b961cf9ae5b'
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

Fresh Linux CI exposed redundant filesystem inference around canonical authority publication. After explicit override and embedded-sdist arms are excluded, the missing-default arm now invokes the compiler directly and returns its destination instead of re-probing directory existence; `_selected_pair` remains the hard verification of the descriptor and exact database bytes. A Git-archive `uv sync --locked` proved the publication path. CI also clears `CADRUMO_AUTHORITY_ROOT` only during clean-checkout setup so a self-hosted runner environment cannot alter the tested default posture; runtime and developer calls still fail on missing explicit overrides.

## Recommendations

Track the repository-wide quality-gate debt independently. The feature-caused medium finding is resolved, and no follow-on architectural decision is required for Lud Authority before delivery.
