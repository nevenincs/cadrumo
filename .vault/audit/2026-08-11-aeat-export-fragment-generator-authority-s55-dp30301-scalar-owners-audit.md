---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:30e734e2b70b582fb63c37eb9c103b79c1b33128cdf274cbce6d8d983a85691d'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S55 DP30301 scalar-owner review`

## Scope

Formally reviewed `W04.P07.S55` against the accepted generator-authority ADR, the accepted M303 semantic-home and DP30301 scalar-ownership decision, the completed S54, S56, and S58 review outcomes, and the live shared-worktree implementation. The review covered the closed core `FilingProducerKey`, canonical IVA profile construction, durable filing-instance evidence, supplier-regime and prorrata-transition arrivals, the immutable `M303FilingFacts` and `FilingProducerSnapshot`, internal export assembly, and the calculation-revision evidence path.

A structural census parsed the five real official DP30301 binaries. The 2023, 2024-early, 2024-late, and 2025 designs each expose the fourteen A16-A29 identification scalars at offsets 109 through 129; the 2026 design exposes those fields plus A30 at offset 130. The core enum contains exactly fourteen unique M303 scalar producer identities for A16-A28 and A30. A29 is correctly absent from `FilingProducerKey`: it remains the annual-volume result derived from canonical annual operations and official endpoint 88. An AST census found every exact M303 producer token literal only in `core/_filing_producer_key.py`; no duplicate raw producer identity was found. The source-grounded Nota 5 foral projection and Nota 6 period-applicability branches are renderer translations of typed facts, not alternate persisted owners.

Focused real-behavior validation produced 149 passing tests across producer snapshots, arrivals, the prorrata register, filing-evidence validation, calculation-revision identity, and taxpayer-profile behavior. A separate current deadline/profile plus arrival lane produced 16 passes and two failures, and the five-epoch exonerado endpoint lane produced five passes and one failure. Scoped Ruff passed, and basedpyright reported zero errors, warnings, or notes. Direct production-model validation proved both omission defects below: deleting `redeme_enrolled` or `insolvency` from otherwise complete payloads is accepted, the omitted field is absent from `model_fields_set`, and Pydantic supplies `False` or `None` respectively.

## Findings

### a17-required-owner | high | REDEME omission silently becomes a negative filing fact

- [ ] `ModeloIVAProfile.redeme_enrolled` remains `bool = False` in `domain/deadlines/_models.py`. Although `taxpayer_profile_from_mapping` now requires the canonical path, direct construction and every other typed deserialization boundary can omit it and receive `False`. The filing producer then renders A17 as `2` NO. This makes an omitted authority indistinguishable from an explicitly evidenced negative and violates S55's required explicit profile owner and no-default contract.

### a24-a26-required-owner | high | Omitted insolvency evidence silently becomes an explicit no-concurso projection

- [ ] `M303FilingInstanceEvidence.insolvency` remains `M303InsolvencyFilingFact | None = None` in `domain/modelos/_calculation_revision.py`. Omitting the field therefore validates as `None`, participates in the revision payload as the defaulted absence, and later renders A24 as `2` while A25-A26 are blank. The durable evidence boundary cannot distinguish an explicit no-insolvency declaration from an omitted fact, contrary to the accepted requirement for complete explicit filing-instance evidence and no inferred false value.

### deadline-profile-redeme-fixture | medium | The current mapping projection proof omits the newly required A17 path

- [ ] `TestTaxpayerProfile.test_mapping_projection_preserves_enrollment_and_schedule_facts` fails because its otherwise current IVA mapping omits `iva.redeme_enrolled`. Its expected `ModeloIVAProfile` also relies on the production default. The test must supply and assert an explicit value so the profile boundary proves the A17 owner rather than normalising omission.

### deadline-profile-scope-fixture | medium | An unrelated pagadores fixture now enters incomplete IVA profile construction

- [ ] `TestTaxpayerProfile.test_mapping_projection_reads_pagadores_axes` supplies `iva.regime` while testing only IRPF pagadores facts. That key now activates canonical IVA profile construction, but the fixture omits the required M303 composition and scalar facts, so the focused deadline lane is red. Remove the unrelated IVA trigger or make the fixture a complete current-schema IVA profile; do not weaken the production refusal.

### a28-endpoint-census | medium | The exonerado endpoint gate rejects the legitimate A28 scalar producer

- [ ] `test_exonerado_endpoints_are_unique_canonical_manual_homes_without_parallel_producers` still asserts that no `FilingProducerKey` may contain `exoner` or `390`. That pre-S55 invariant now rejects the required A28 applicability producer `m303.exonerado_390_applicable`, even though the numbered annual-summary endpoints correctly remain non-producer canonical casillas. Narrow the gate to forbid producer duplication of the numbered endpoint values while explicitly admitting the single A28 applicability key.

### a17-required-owner-resolution | high | Required REDEME ownership closes the omission path

- [x] Resolved on re-review. `ModeloIVAProfile.redeme_enrolled` has no default and `model_fields["redeme_enrolled"].is_required()` is true. Direct validation of an otherwise complete payload with the field deleted raises `ValidationError`; explicit `False` remains accepted and projects the intended negative fact. All direct constructors now state the value.

### a24-a26-required-owner-resolution | high | Required nullable insolvency evidence distinguishes omission from explicit no

- [x] Resolved on re-review. `M303FilingInstanceEvidence.insolvency` is required nullable with no default and `model_fields["insolvency"].is_required()` is true. Direct validation refuses a deleted field, while an explicitly supplied `None` validates and preserves the typed negative declaration. Populated atomic date/subtype evidence remains revision-identity-bearing.

### deadline-profile-redeme-fixture-resolution | medium | The profile mapping proof now supplies and asserts A17 explicitly

- [x] Resolved on re-review. The current IVA mapping fixture supplies `iva.redeme_enrolled` and its expected `ModeloIVAProfile` asserts `redeme_enrolled=False`; it no longer relies on a model default.

### deadline-profile-scope-fixture-resolution | medium | The pagadores proof no longer creates an unrelated incomplete IVA block

- [x] Resolved on re-review. The IRPF-only pagadores fixture removes its unrelated `iva.regime` key, so it proves only the axes under test and no longer weakens or accidentally exercises M303 profile completeness.

### a28-endpoint-census-resolution | medium | The endpoint census admits exactly the sole A28 applicability producer

- [x] Resolved on re-review. The five-epoch endpoint census now requires the exonerado-related producer-token set to equal exactly `{m303.exonerado_390_applicable}`. Numbered endpoint values remain canonical casillas with no parallel scalar producer, while A28 keeps its required snapshot-backed applicability key.
No additional duplicate owner, raw producer token, placeholder, fallback representation, or A29 producer was found in the reviewed production surface.

## Recommendations

- Make `ModeloIVAProfile.redeme_enrolled` required at the model boundary and add a structural omission-refusal proof, while retaining the mapping ingress requirement.
- Make `M303FilingInstanceEvidence.insolvency` a required nullable field so explicit `None` remains the typed negative decision but omission refuses; prove both explicit-none and atomic populated evidence through revision identity and export projection.
- Repair the three stale focused tests without relaxing current production refusal or reclassifying A28's applicability key as an endpoint value owner.
- Re-run the five focused lanes, Ruff, basedpyright, and the five-binary structural census after remediation.

Final verdict: **not approved**. A29 classification, enum singularity, arrival ownership, and the five-design official census are correct, but the two high-severity omission defaults violate S55's explicit canonical-owner and no-fallback acceptance, and three focused gates remain red.
## Re-review outcome

Verdict: **approved**. All five original findings are resolved and no new S55 blocker was found.

Independent bounded reruns produced 166 passing focused tests across the producer snapshot, arrivals, prorrata register, filing-evidence validation, calculation-revision identity, taxpayer-profile mapping, and five-epoch exonerado endpoint census. The full real CLI quickfile integration produced 11 passing tests. Direct runtime proofs confirm both formerly defaulted fields are required, omission raises validation, and explicit nullable insolvency `None` remains valid. The structural census again parsed all five official DP30301 binaries, confirmed fourteen A16-A29 fields for the four pre-2026 designs and fifteen A16-A30 fields for 2026, confirmed exactly fourteen unique typed M303 producer keys, confirmed A29 remains absent, and confirmed every exact producer-token literal has only the core enum as its production home. Supplied remediation static evidence reports Ruff clean on all changed paths and basedpyright at zero for the core slice.

Final verdict: **approved**. S55 now satisfies the explicit typed canonical-owner, no-default, no-raw-key, no-placeholder, no-fallback, and no-duplicate-owner acceptance within this reviewed boundary.
