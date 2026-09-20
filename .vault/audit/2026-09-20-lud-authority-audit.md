---
tags:
  - '#audit'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:eb18901f4634cb64916639bd1a23203bf211d100da69ea207d5dc8ca32f0cead'
related:
  - "[[2026-09-20-lud-authority-plan]]"
---
# `lud-authority` audit: integrated startup dependency review

## Scope

Reviewed the completed L1 plan against its accepted ownership policy and the integrated diff across storage taxonomy/materialization, application provisioning, authority-store admission, CLI startup, and focused tests. The review checked failure ordering, explicit-versus-derived path provenance, authority non-generation, metadata isolation, typed CLI projection, logging use, strict typing, and the recorded project gates.

## Findings

### pre-existing-quality-gate-debt | low | Repository-wide gates remain red outside this feature

`just check-code` retains unrelated diagnostics in untouched modules and several pre-existing structural gates. `just test-gate` retains failures in `dev/tests/test_import_quality_gate.py` caused by its event/schema and count expectations. The full Vaultspec check likewise retains 25 errors in historical execution mappings and one unrelated ADR. All Lud Authority scoped Vaultspec checks, focused suites, CLI contracts, production-module type checks, logging gate, lint, and formatting pass.

### fresh-linux-authority-bootstrap | medium | Resolved synthesized default crossing the setup subprocess boundary

Developer path initialization seeds `CADRUMO_AUTHORITY_ROOT` with the checkout's default `.authority` location. Fresh setup inherited that synthesized value into `uv sync`, so the build hook correctly treated it as an explicit dependency and refused it before default publication. The sync subprocess now removes only the canonical checkout default while preserving genuine relocated overrides. A clean Linux Git-archive run built the package and authority, passed Linux Ruff and formatting, all three type checkers on changed production modules, 37 affected setup/packaging/storage/application tests, and all 99 CLI contract tests. Runtime authority generation remains forbidden.

## Recommendations

Track the repository-wide quality-gate debt independently. The feature-caused medium finding is resolved, and no follow-on architectural decision is required for Lud Authority before delivery.
