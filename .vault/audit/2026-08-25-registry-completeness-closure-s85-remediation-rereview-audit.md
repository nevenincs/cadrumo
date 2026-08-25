---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d0318ceecea5f0f787bd7733e14b3adad1c80ad67e011a78e4d2c5048d479f43'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-24-registry-completeness-closure-W03-P05-S85]]"
  - "[[2026-08-25-registry-completeness-closure-s85-independent-classification-review-audit]]"
---

# `registry-completeness-closure` audit: `S85 remediation independent re-review`

## Scope

Read-only re-review of remediation commit `07a99c8e12` against the prior independent classification review. The reviewed surface is the diagnostic classifier in `src/cadrumo/domain/calculations/registry/_authority.py`, its public registry exports, the dynamic enrollment and canonical/live proof factories in `dev/registry/filing_export_proof.py`, its three focused integration tests, the closure plan row, and the S85 execution record. Later shared-worktree commits and any subsequent remediation are explicitly outside this review.

The prior plan-metadata finding is resolved: exact source-and-test searches find no S85 or W03.P05 tracking identifiers in the reviewed production or test files. The remediation also retains the dynamic law-selected denominator, empty canonical live-entry/vector tuples, typed residues, and the diagnostic enrollment postcondition that a recorded full-registry error has an empty materialized-vector tuple. The execution record's measured clean-load observation remains 66 filing-grade revisions with zero materialized vectors: 16 canonical-builder-missing, 41 generated-provenance-missing, seven generated-provenance-invalid, and two period-unrepresentable. It does not credit the concurrent Modelo 200 re-pin and continues to route that predecessor conflict to W04.P08.S22. S86 remains blocked by the plan and by zero successful enrollment.

## Findings

### diagnostic-capability-runtime-escape | high | The diagnostic wrapper still discloses a fully usable filing authority

`UnvalidatedRegistryClassification` stores a real `ValidatedRegistryAuthority` in its `_authority` slot. Its `__getattribute__` and `__dir__` overrides hide that slot only from ordinary attribute access; they do not remove the capability. A read-only probe in an isolated checkout of `07a99c8e12` constructed the classifier with a forced `RegistryValidationError`, obtained `object.__getattribute__(classification, "_authority")`, and successfully called `snapshot("100", filing_year=2020, period="0A", grade=FILING)`. It returned `ValidatedRegistryAuthority 2020`.

That hidden authority also passes the `isinstance(ValidatedRegistryAuthority)` checks in the canonical and live factory constructors. Consequently the new public wrapper is structurally distinct only at the surface level, not at the capability level: a caller can create a filing-grade runtime projection from a diagnostic load that did not complete whole-registry validation, or hand the recovered object to normal proof construction. The factory accepts any caller-supplied `RegistryValidationError`; it does not establish that strict loading actually failed before constructing this unvalidated authority. The regression test checks `dir()` and `hasattr()` but does not exercise this direct escape.

### duplicated-diagnostic-enrollment | medium | The diagnostic path redeclares the provenance and residue classifier rather than using one canonical verifier

`derive_filing_export_conformance_enrollment` and `derive_diagnostic_filing_export_conformance_enrollment` independently implement generated-manifest loading, identity validation, generated-source verification, period conversion, public-probe construction, candidate assembly, producer-key checking, canonical-builder checking, and residue construction. `_modelo_validation_residue` and `_diagnostic_revision_residue` also separately map validation-failure cases after rechecking generated provenance.

The common pieces happen to agree on the current zero-success corpus, but they are independently editable outcome logic. A change in provenance, layout, period, probe, or builder policy can therefore classify the same selected revision differently depending on whether the whole-registry load succeeds. That violates the requested single canonical verifier/no-redeclaration boundary and makes the diagnostic denominator less auditable.

## Recommendations

- **REVISION REQUIRED - high:** make the diagnostic result a genuine static data projection. Do not retain a `ValidatedRegistryAuthority`, its bound methods, snapshots, model definitions, catalogues, validators, or an equivalent recoverable reference in the published diagnostic object. Bind construction to an actual captured strict-load failure, and add a regression which attempts the current slot/introspection escape and proves no filing snapshot, canonical authority, or live authority can be recovered.
- **REVISION REQUIRED - medium:** factor the manifest/provenance/period/probe/candidate/builder residue decisions into one canonical verifier that consumes either a validated law-selected projection or an explicitly refusal-only diagnostic projection. Keep strict failure as the sole diagnostic difference: it must always force a typed non-success and never materialize a vector.
- Re-run the isolated three-test integration module, scoped Ruff, and the feature Vault check after the repairs. Keep S85 and S86 unchecked; do not use Modelo 200 re-pinning or regeneration as remediation evidence.

## Verification receipt

- Vaultspec-RAG semantic discovery, whole-file/diff review of the relevant authority, enrollment, factory, and test modules, and exact-symbol searches completed.
- Exact tracking-metadata search found no `S85`, `W03.P05`, or vault-plan path reference in the reviewed production and test files. Exact authority search found only the new diagnostic loader/capability and no retained legacy diagnostic loader.
- The canonical and live factory constructors reject the wrapper object directly, and the diagnostic enrollment returns an empty materialized-vector tuple; neither fact prevents recovery of the hidden real authority described above.
- Scoped Ruff passed for all four reviewed Python files. The feature Vault check is clean except for two pre-existing body-section warnings in the unrelated source-casilla predecessor audit.
- The shared-worktree integration command was collection-blocked by concurrent authentication WIP at `config.py` because `BucketPointer` was missing. The attributable isolated checkout of `07a99c8e12` passed `dev/registry/tests/test_filing_export_two_channel_proof.py`: three passed in 197.98 seconds, with two upstream `openpyxl` print-area warnings. This green test does not cover the direct slot/introspection escape above.
