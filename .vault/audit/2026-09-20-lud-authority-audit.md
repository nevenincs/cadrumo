---
tags:
  - '#audit'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:0088c35ba3a04a868abe9cc3b7823f547e35a71285a7f9994f1a121be9ce4af4'
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

The first PR run exposed a branch-integrated bootstrap defect: fresh Linux setup entered the editable build before `.authority` existed, and duplicated source-shape checks prevented the build hook from invoking its canonical compiler. The correction makes a missing default source publication compile directly after explicit-override and embedded-sdist arms have already been excluded. Focused packaging tests, Ruff, and ty pass; the owning authority-bootstrap audit carries the detailed review.

## Recommendations

Track the repository-wide quality-gate debt independently. The feature-caused medium finding is resolved, and no follow-on architectural decision is required for Lud Authority before delivery.
