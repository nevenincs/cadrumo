---
tags:
  - '#audit'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:c1c99b0be6db5d362421a34fa1d606f8dcc5a1858f071ef2d456ed11d09a2509'
related:
  - "[[2026-09-20-lud-authority-plan]]"
---
# `lud-authority` audit: integrated startup dependency review

## Scope

Reviewed the completed L1 plan against its accepted ownership policy and the integrated diff across storage taxonomy/materialization, application provisioning, authority-store admission, CLI startup, and focused tests. The review checked failure ordering, explicit-versus-derived path provenance, authority non-generation, metadata isolation, typed CLI projection, logging use, strict typing, and the recorded project gates.

## Findings

### local-quality-pipeline | informational | Resolved all code and test gate findings before CI

The committed tree passes `just check-code`, including strict typing, import boundaries, dependency declarations, reachability, symbol and export consumption, secure-storage and persistence-write checks, and documentation references. `just test-ci-contracts` passes its 967-case main population, two serialized IVA performance cases, and one repair-performance case. The diff-aware `just test-gate origin/main` independently passes its 128 broad-change contracts, repeats those CI-contract populations, and passes all four pytest-harness cases. The focused Lud Authority storage, provisioning, build-hook, startup, authority-root, logging, and strict-type checks also pass.

### modelo-130-performance-control | medium | Resolved latent full-pipeline performance failure without weakening the contract

The full local pipeline exposed a Modelo 130 p95 CPU regression in the repository's existing scale benchmark. The transaction read path now reuses calculation-scoped validated state and queries the complete indexed partition directly. The unchanged performance budget and its full-scan control pass both standalone and through the top-level diff-aware gate; no threshold, marker, or fixture was relaxed.

### historical-vault-corpus | low | Unscoped debt remains outside Lud Authority

`vaultspec-core vault check all --feature lud-authority` is clean. The unscoped repository check still reports historical records outside this feature: 26 feature warnings, 116 execution-mapping findings, 392 body-section findings, and one unrelated ADR grounding error. Those records pre-date and do not govern Lud Authority, so this delivery does not rewrite them.

### fresh-linux-authority-bootstrap | medium | Resolved synthesized default crossing the setup subprocess boundary

Developer path initialization seeds `CADRUMO_AUTHORITY_ROOT` with the checkout's default `.authority` location. Fresh setup inherited that synthesized value into `uv sync`, so the build hook correctly treated it as an explicit dependency and refused it before default publication. The sync subprocess now removes only the canonical checkout default while preserving genuine relocated overrides. A clean Linux Git-archive run built the package and authority, passed Linux Ruff and formatting, all three type checkers on changed production modules, 37 affected setup/packaging/storage/application tests, and all 99 CLI contract tests. Runtime authority generation remains forbidden.

## Recommendations

Track the historical unscoped Vaultspec corpus independently. All Lud Authority findings and all local code/test pipeline blockers are resolved; no follow-on architectural decision is required before delivery.
