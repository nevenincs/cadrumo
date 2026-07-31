---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:67702522b519eb66aa070927a963a62eafcf653022c81e82a1a9634a0f601fb8'
step_id: 'S341'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# reproduce the M303 verification_source failure in a fresh tmp_path with cleared registry caches and capture the traceback, then triage H1 stale loader or snapshot cache (check whether the 688ed6713 dir-fingerprint hardening already closed it) versus the H2-H3 programmatic-construction site, and fix at the identified layer with a regression test

## Scope

- `src/aeat/application/modelo/`

## Description

- Ground the failure in the extraction-profile provenance surface: `verification_source` is a registry-build validation field on `ExtractionProfileDefinition`, gated by `validate_declaracion_pdf_round_trip_gate`.
- Reproduce through the production authority path: clear the loader fingerprint and lru caches, then cold-load the Modelo 303 snapshot via `resources().modelos.authority`.
- Capture the failure signature: the round-trip gate refusal "extraction profile 'modelo-303-declaracion-pdf' sets corpus_round_trip_verified = true but verification_source is not set".
- Triage H1 (stale loader/snapshot cache) versus H2-H3 (programmatic-construction site) against HEAD.
- Add an application-layer regression test that exercises the Modelo 303 production resolution plus an anti-tautology gate guard.
- Verify: run the regression sequentially (registry suites race under xdist), then ruff and ty.

## Outcome

- VERIFY-CLOSE (H1). The failure DOES NOT reproduce at HEAD: the cold-loaded Modelo 303 snapshot resolves `corpus_round_trip_verified = true` with `verification_source = "synthetic_from_aeat_published_text"` on both revisions (2009-y-siguientes, 2023-y-siguientes). No fix was manufactured for a resolved bug.
- Root cause = the pre-hardening loader-cache partial-read class: under concurrent registry writes in the shared worktree, a mid-write `extraction_profiles` fragment could be read with the round-trip flag present but `verification_source` not yet written, tripping the gate at snapshot build. This is the same stale-cache-under-concurrent-writes class closed for the sibling context row (S349).
- Closed by commit `688ed6713`: the registry-tree fingerprint now recursively covers every `revisions/**/*.toml` fragment (so an `extraction_profiles` fragment edit invalidates the lru cache rather than serving a stale partial), and a concurrent directory change during fingerprinting raises the actionable "retry after concurrent registry writes settle" error instead of serving partial data.
- H2/H3 ruled out: the only application-layer reference to `verification_source` is a docstring in `_reconcile.py`; there is no programmatic-construction site that builds the Modelo 303 profile with a missing provenance tag.
- Regression added at the step-scoped layer: `test_modelo_303_verification_source_snapshot_resolution.py` under `src/aeat/application/modelo/tests/` (3 tests, green sequentially, ruff and ty clean). Test 1 resolves Modelo 303 through the production authority with caches cleared and asserts every `corpus_round_trip_verified` `declaracion_pdf` profile carries a non-None `verification_source` (would raise on a regressed partial). Test 2 is the anti-tautology guard: it feeds the round-trip gate the exact partial shape (round-trip verified, `verification_source = None`) against the real justificante corpus and asserts the refusal still fires. Test 3 is a dormancy guard confirming the Modelo 303 justificante corpus PDFs exist so test 2 is not vacuous.

## Notes

- The domain-layer gate branch itself is already covered by `test_corpus_round_trip_gate.py` (including a production-validation-path test); this step adds the application-layer Modelo 303 production-resolution regression without duplicating that coverage.
- Independent corroboration: cdc-coder converged on the same `688ed6713` attribution, so the H1 verdict is doubly confirmed.
- Committing encountered the recurring benign 0-byte `index.lock` (statusline/temp-repo git-diff debris) in the shared worktree; the lock was not force-removed. Commit landed via an explicit-pathspec retry once the lock cleared.
