---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7a7fd597a6da7fd346be8d8e99cae953d99c63b01f11c879d1903aec5d54b5e9'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-24-registry-completeness-closure-W03-P05-S85]]"
  - "[[2026-08-25-registry-completeness-closure-s85-remediation-rereview-audit]]"
---

# `registry-completeness-closure` audit: `S85 final remediation independent re-review`

## Scope

Read-only final re-review of the four S85 remediation paths captured in mixed commit `96bb9e08a2`, with execution evidence in `538738ce3a`, against the prior remediation audit. The review is explicitly limited to `src/cadrumo/domain/calculations/registry/_authority.py`, its public facade, `dev/registry/filing_export_proof.py`, and its focused integration tests. The other 470 files in the mixed relocation commit are outside this audit and receive no S85 credit.

The review covers the diagnostic object's complete stored-object graph, its `object.__getattribute__` surface, normal and live canonical factory admission, strict-failure materialization refusal, static projection serialization, one-path classifier/provenance/residue ownership, tracking-metadata hygiene, dynamic current-corpus disposition, fabricated-input prohibition, and the uncredited Modelo 200/S22 predecessor boundary.

## Findings

### serialized-inspection-roundtrip | high | The immutable inspection payload cannot deserialize, corrupting the dynamic residue classification

The remediation serializes `RegistryRevisionInspection` through `model_dump_json()` in `derive_filing_revision_classifications`, then calls `RegistryRevisionInspection.model_validate_json()` in `_deserialize_static_revision`. This is not a valid strict round trip. A direct Modelo 100/2020 probe constructed its inspection successfully, serialized it, then received 153 validation errors while restoring it because JSON arrays are not accepted for the strict tuple-valued formula arguments.

The shared classifier catches this deserialization error before it reads a provenance manifest and emits `revision_validation_failed`. Its current live result is 66 selected revisions and zero materialized vectors, but the residue distribution is now six canonical-builder-missing, four generated-provenance-missing, one generated-provenance-invalid, and 55 revision-validation-failed. This contradicts the attested S85 result of 16, 41, seven, and two respectively. It also hides provenance/builder residue and gives the wrong responsible owner and reconsideration condition for ten builder candidates. The four focused tests pass because they do not run a successful current-corpus inspection JSON round trip or assert the current residue distribution.

### s85-final-remediation | low | verified: the prior runtime escape and classifier duplication are resolved

`UnvalidatedRegistryClassification` is a frozen slotted data object with only a strict-error string and a tuple of frozen filing-revision facts. Each fact contains identifiers, coordinates, layout identifiers, error text, and serialized layout/inspection JSON. It retains no authority, snapshot, model-definition, catalogue, validator, bound method, callable, or other runtime service. Direct `object.__getattribute__(classification, "_authority")` raises, and the focused recursive graph inspection finds neither a `ValidatedRegistryAuthority` nor a callable value.

Both canonical factory boundaries reject the diagnostic object: the normal factory checks for `ValidatedRegistryAuthority`, and the live-factory probe raised `TypeError` with its validated-authority refusal. The shared static classifier accepts the diagnostic wrapper only with `validated_authority=None`; it records `registry_validation_incomplete` after every otherwise-materializable candidate and the enrollment report independently refuses any non-empty materialized tuple when a strict error is present.

The normal and diagnostic entry points now pass the same immutable revision facts to one `_derive_static_filing_export_conformance_enrollment` body. Generated-provenance verification and every residue mapping are shared helpers. Exact searches found no retained legacy diagnostic loader, no parallel candidate/residue implementation, and no S85 or plan-tracking identifier in the reviewed production or test code.

The canonical vector and live-proof-entry tuples remain empty. No `ModeloDraft`, producer snapshot, taxpayer data, payload, or acceptance hash is fabricated. A layoutless/static refusal cannot deserialize a layout and so cannot reach candidate or evidence construction. S86 remains blocked by the plan's zero-success release rule. The mixed remediation commit changes no Modelo 200 generated input, output, map, profile, or provenance path; its predecessor conflict remains uncredited and owned by W04.P08.S22.

## Recommendations

- **REVISION REQUIRED - high:** replace the inspection JSON transport with an actual strict round-trip representation, or with a dedicated immutable primitive projection that the generated-provenance verifier can consume without reconstructing a strict Pydantic inspection model. Add a current-corpus assertion that each serialized successful fact restores successfully before provenance classification begins.
- **REVISION REQUIRED - high:** restore and assert the dynamic current-corpus distribution: 66 selected, zero materialized, 16 canonical-builder-missing, 41 generated-provenance-missing, seven generated-provenance-invalid, and two period-unrepresentable. The test must prove that a static successful revision does not become `revision_validation_failed` solely due to transport encoding.
- Preserve the resolved authority-capability boundary and the single shared classifier. Keep S85 and S86 unchecked; do not use Modelo 200 re-pinning or regeneration as remediation evidence.

## Verification receipt

- Vaultspec-RAG semantic discovery, whole-file review of all four S85 paths, exact scoped diff review, and exact-symbol sweeps completed. The mixed-commit scope was restricted to those four paths.
- `object.__getattribute__` escape, recursive stored-field graph, normal factory refusal, live factory refusal, and strict-failure materialization refusal were independently checked. The focused module passed all four integration tests in 223.00 seconds, but lacks the failing serialized-success/current-distribution coverage.
- Scoped Ruff passed for all four reviewed Python paths. The feature Vault check is clean except for two pre-existing missing-section warnings in the unrelated source-casilla predecessor audit.
- The independent enrollment probe confirmed 66 selected rows and zero materialized vectors, but reported six canonical-builder-missing, four generated-provenance-missing, one generated-provenance-invalid, and 55 revision-validation-failed. The direct Modelo 100/2020 inspection round-trip probe reproduced the strict JSON restoration failure.
