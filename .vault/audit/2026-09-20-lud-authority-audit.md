---
tags:
  - '#audit'
  - '#lud-authority'
date: '2026-09-20'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:1f185e01491f1ecd29c52c4c3400df0bbab977b4daa77e293a2eabe9e4cb6f0b'
related:
  - "[[2026-09-20-lud-authority-plan]]"
---
# `lud-authority` audit: integrated startup dependency review

## Scope

Reviewed the completed L1 plan against its accepted ownership policy and the integrated diff across storage taxonomy/materialization, application provisioning, authority-store admission, CLI startup, and focused tests. The review checked failure ordering, explicit-versus-derived path provenance, authority non-generation, metadata isolation, typed CLI projection, logging use, strict typing, and the recorded project gates.

## Findings

### local-quality-pipeline | informational | Resolved all code and test gate findings before CI

The committed tree passes `just check-code`, including strict typing, import boundaries, dependency declarations, reachability, symbol and export consumption, secure-storage and persistence-write checks, and documentation references. After the Linux CI repair, `just test-ci-contracts` passes its 966-case parallel population, three serialized performance cases, and one repair-performance case. The earlier diff-aware `just test-gate origin/main` independently passed its 128 broad-change contracts, the complete CI-contract population, and all four pytest-harness cases. The focused Lud Authority storage, provisioning, build-hook, startup, authority-root, logging, and strict-type checks also pass.

### modelo-130-performance-control | medium | Resolved latent full-pipeline performance failure without weakening the contract

The full local pipeline exposed a Modelo 130 p95 CPU regression in the repository's existing scale benchmark. The transaction read path now reuses calculation-scoped validated state and queries the complete indexed partition directly. The unchanged performance budget and its full-scan control pass both standalone and through the top-level diff-aware gate; no threshold or fixture was relaxed.

### linux-type-sweep-resource-bound | medium | Resolved same-checker process multiplication

The first post-push Linux lint run exposed a resource-sensitive defect in the existing cross-platform type orchestrator: its global nine-task queue could overlap multiple processes from the same checker family. Historical runner evidence included a BasedPyright timeout, and this run lost the Darwin Ty subprocess without a report. The scheduler now runs Ty, Pyrefly, and BasedPyright families concurrently while serializing each family's three-platform sweep, preserving all nine measurements with bounded same-engine residency. Empty-report errors also name the subprocess return code. The repaired gate passes locally on Windows and in the locked Python 3.13.11 Linux development image; 24 focused harness tests, the complete code gate, and the top-level test gate also pass.

### linux-contract-portability-and-ledger-performance | medium | Resolved fixture defect and real repeated-read cost

The second post-push scoped gate exposed a platform-dependent fixture and then a real repeated-read cost. The distribution-readiness conflict fixture hard-coded Linux/x86_64, which matched the runner on the identity axes production intentionally compares; it now derives a guaranteed-different operating-system identity from the executing platform. Moving the M130 30,000-row CPU benchmark into the existing serial performance lane removed worker contention but honestly revealed that both the IVA and M130 period paths still exceeded the unchanged 3.0 CPU-second ceiling on Linux. The transaction repository now reuses an immutable decoded row only while a cheap persisted-revision probe proves that exact row remains current. Cold reads still perform schema cutover, outer integrity, decryption, and payload validation in one addressed snapshot; external updates, deletions, and revision-less rows reload and revalidate. Production behavior, sample sizes, thresholds, and full-scan anti-vacuity controls are unchanged. The 23-case persistence suite, all three strict module type checkers, all three serial scale contracts in the locked Linux image, and the complete local `just test-ci-contracts` recipe pass.

### historical-vault-corpus | low | Unscoped debt remains outside Lud Authority

`vaultspec-core vault check all --feature lud-authority` is clean. The unscoped repository check still reports historical records outside this feature: 26 feature warnings, 116 execution-mapping findings, 392 body-section findings, and one unrelated ADR grounding error. Those records pre-date and do not govern Lud Authority, so this delivery does not rewrite them.

### fresh-linux-authority-bootstrap | medium | Resolved synthesized default crossing the setup subprocess boundary

Developer path initialization seeds `CADRUMO_AUTHORITY_ROOT` with the checkout's default `.authority` location. Fresh setup inherited that synthesized value into `uv sync`, so the build hook correctly treated it as an explicit dependency and refused it before default publication. The sync subprocess now removes only the canonical checkout default while preserving genuine relocated overrides. A clean Linux Git-archive run built the package and authority, passed Linux Ruff and formatting, all three type checkers on changed production modules, 37 affected setup/packaging/storage/application tests, and all 99 CLI contract tests. Runtime authority generation remains forbidden.

## Recommendations

Track the historical unscoped Vaultspec corpus independently. All Lud Authority findings and all local code/test pipeline blockers are resolved; no follow-on architectural decision is required before delivery.
