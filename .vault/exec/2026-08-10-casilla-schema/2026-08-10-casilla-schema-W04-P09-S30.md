---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:f4e1694a0bac398cc9417edfbcbac3f5be5fee0a5f7b5d112dc0395a07145f93'
step_id: 'S30'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---




# delete the application verification package, its tests and the registry application-links consumer rows in one commit, absorbing any missing semantics into reconcile first

## Scope

- `src/cadrumo/application/verification/`

## Description

- Run mandatory semantic code and ADR discovery, then read the accepted dead-surface ADR, the S29 capability adjudication, the complete package, and the living reconcile implementation.
- Delete all seven tracked files under `src/cadrumo/application/verification`, including both package test modules, without leaving an alias, shim, or replacement implementation.
- Remove 83 registry application-link rows naming `cadrumo.application.verification` across 83 revisions, delete the 13 dedicated one-row TOML files, and remove all 85 corresponding construct ownership references.
- Remove the obsolete `verification` application-link surface from the registry schema and closure validator while preserving verification expectations and the canonical `RegistryVerificationPolicy` consumed by living reconciliation.
- Remove dead production docstrings, error-registry registration, import-layout and dependency baselines, generated API stubs, and the application API index entry; retarget directly affected registry tests to living surfaces.
- Add a structural regression proving the package path and import are absent and that source, API docs, and registry TOML contain no deleted consumer string.

## Outcome

- The standalone application verification package is absent and cannot be imported. Its seven source/test files, four generated API stubs, 83 consumer rows, and 85 construct references are deleted.
- `aeat app registry verify` succeeds against all 73 modelos and 94 revisions. The resulting 565 application links expose no `verification` application surface while all 82 verification expectations remain validated registry facts.
- The structural deletion gate passes three tests; the directly affected registry selection passes 162 tests and the surviving reconciliation selection passes 53 tests.
- Path-scoped Ruff format/check and BasedPyright complete with zero diagnostics on the changed Python surface.
- No missing S29 semantic was copied into reconciliation: the S29 disposition established that the living persisted-revision flow already owns the relevant comparison semantics and that retaining fresh standalone recalculation would duplicate authority.

## Notes

- A first guarded directory removal stopped before deleting package files because 16 generated `__pycache__` artifacts accompanied the seven tracked files. They were inventoried and explicitly removed as generated artifacts; no unknown source was deleted.
- The first exact registry verifier exposed one construct record stored under `records/constructs.part-002b.toml`, outside the ordinary `constructs/` directory convention. Its single dangling ownership reference was removed and the verifier then passed.
- An initial 270-test registry selection reported 259 passes and 11 failures. Two S30-owned stale baselines were corrected. The remaining nine failures are outside S30: five current Modelo 200 export-fixture gaps and four current Modelo 303 explicit-scope / IVA-deduction-fact gaps. The narrowed S30-owned selection passed in full.
- A required API scaffold run also discovered unrelated pre-existing missing stubs. Those unrelated generated changes were removed; only the four dead package stubs and the dead application index entry belong to this Step.
- A concurrent coordinator commit, `2cb136c892`, landed the main deletion payload while verification was running. This execution record does not claim to have staged or committed that race result; the two stale test-baseline corrections discovered afterward remain explicit follow-up working-tree changes for the coordinator.
