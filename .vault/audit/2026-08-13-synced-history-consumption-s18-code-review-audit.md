---
tags:
  - '#audit'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1e6ce73caa8c52b82b326f53db7c0c65f140877746690394ed4725eee7c638e7'
related: []
---
---
---

# `synced-history-consumption` audit: `s18 code review`

## Scope

Independent review of current `P02.S18` implementation and its directly generated sequence evidence against the accepted synced-history decision, the measured census and classification references, the step execution record, and the current shared-tree diff. Peer-owned `P02.S35` paths and `src/cadrumo/_data/registry/aeat/legal/iva-dana-2024.toml` were read only to identify the declared external blocker.

## Findings

### classification-closure | high | The validator does not require every direct previous-filing carry to have a classification

The execution record claims at `.vault/exec/2026-08-08-synced-history-consumption/2026-08-08-synced-history-consumption-P02-S18.md:22` and `:29` that every direct `previous_filing` carry is covered and future unclassified bindings are rejected. The implementation at `src/cadrumo/domain/calculations/registry/_validate_dependency_sections.py:226` returns for every treatment other than `direct_annual_settlement`, and the surrounding validator iterates classifications rather than direct bindings. Removing the new Modelo 720 `factual_evidence` classification therefore leaves its three direct carries without treatment while bypassing this closure check. A missing relation-less settlement classification also has no classification object on which this helper can run. The mutation at `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_registry_constructs.py:895` only removes relation references from an existing classification; it does not delete a required classification or exercise `factual_evidence`. This contradicts the step's canonical fail-closed ownership claim and requires code and real mutation-test changes before approval.

Re-review status: RESOLVED IN CODE. The corrected validator now groups every direct `previous_filing` binding by the resolver's canonical `source_modelo` key, rejects missing classifications and `non_dependency`, and applies construct and legal-reference coverage to relation-less `factual_evidence` as well as `direct_annual_settlement`. The implementation is generic and contains no modelo-specific branch or duplicate authority. The real loaded Modelo 720 removal mutation at `src/cadrumo/domain/calculations/registry/tests/test_modelo_720_registry.py:70` proves the missing factual-evidence case. A test-evidence gap remains: no mutation currently proves the new `non_dependency` refusal or removal of a relation-less direct-settlement classification, even though both branches are correct by inspection.

Final re-review status: CLOSED. `src/cadrumo/domain/calculations/registry/tests/test_modelo_720_registry.py:107` now drives the loaded Modelo 720 revision through the real validator after changing its classification to `non_dependency`, and `src/cadrumo/domain/calculations/registry/tests/test_modelo_130_registry.py:196` removes the real relation-less direct-settlement classification and construct membership. Both refuse on the generic source-modelo completeness contract. No model id is embedded in the validator and no parallel classification lookup was introduced.

Final re-review: RESOLVED. The current test changes close the recorded gap with a real Modelo 130 removal mutation for the relation-less `direct_annual_settlement` branch and a real Modelo 720 `non_dependency` mutation, in addition to the factual-evidence removal mutation. The live loaded-authority probe accounts for all fifteen scoped carries: the twelve P02.S18 carries and the three committed Modelo 353 carries all have one canonical source-modelo classification, construct membership, and classification legal coverage. No duplicate or modelo-specific fallback authority was found.

### generated-sequence-proof | high | Eight required exact sequence checks remain unexecuted

The execution record accurately states at `.vault/exec/2026-08-08-synced-history-consumption/2026-08-08-synced-history-consumption-P02-S18.md:33` and `:53` that only six of fourteen regenerated sequences were checked and eight remain blocked by the peer-owned duplicate legal id. Those generated goldens are part of the declared S18 change surface, so regeneration without their exact `check --sequence` verification is not review-complete. This is an external shared-tree blocker, not authority to approve the step conditionally while the classification-closure defect above remains.

A current-tree recheck no longer reproduced that blocker for `modelo-130-manual-casilla`: it and the already-green `first-quarter-export-file` both returned clean. However, the sequence runner explicitly warns that a single-sequence pass does not verify either sequence because commands on a page share one in-process CLI tree, and requires the corresponding page-level gate. The remaining six deferred sequences and the required page-level gates remain unproven, so the execution record is stale and the generated-evidence gate is still open even though the earlier duplicate-id symptom may have moved.

Final re-review: RESOLVED. The current evidence records all fourteen exact sequence checks clean and the required Modelo 130, quickstart, review-calculation-values, and first-quarter page gates clean. The broader IRPF-lifecycle page is red only for the unrelated overview action-schema and notice drift, not for an S18 contract or generated artifact. The fourteen JSON artifacts are generated output and their contracts no longer duplicate the seeded invoice-evidence setup; `autonomo-irpf-2026` remains the canonical seed. No generated artifact was hand-authored in this review.

### m720-baseline-boundary | medium | The two-bucket test does not prove work-unit isolation or full provenance survival

The new test at `src/cadrumo/application/calculations/tests/test_modelo_720_prior_year_baseline_fidelity.py:597` uses real encrypted repositories and correctly proves taxpayer-bucket isolation, 2023-to-2024 annual source selection, all three numerical baseline values, unresolved behavior in the empty bucket, and survival of the registry treatment. It does not construct distinct work units, so it cannot prove the requested cross-workunit boundary or the intended same-taxpayer behavior between work units. It also asserts only `dependency_treatment` and a binding id parsed from `source_ref`; it does not prove that persisted capture provenance (`app_filing`, capture time, stamped source revision) survives the resolver projection. `PreviousFilingSourceResolver` currently projects `source_kind="previous_filing"` and an encoded string while omitting the richer source coordinates supported by `CalculationSourceProvenance`. The test is valid repository-and-binding fidelity, not complete evidence for the stronger work-unit and provenance requirement. Its numeric assertions prove exact baseline-copy behavior from stored values, not an independently grounded Modelo 720 calculation oracle; the module correctly identifies M720 as a non-calculation informative model.

Final re-review status: CLOSED FOR THE REQUIRED M720 CONTRACT. `src/cadrumo/application/calculations/tests/test_modelo_720_prior_year_baseline_fidelity.py:667` creates two real persisted work units in one encrypted taxpayer bucket, resolves both through the production bucket source mesh, proves the 2024 work unit receives exact `60000.00`, `55000.00`, and `0.00` prior-year baselines, and proves the 2025 work unit remains unresolved because the required 2024 source coordinate is absent. The distinct work-unit ids, shared bucket id, annual periods, and law-resolved revision objects make the coordinate discrimination real rather than a hand-built resolver call. Treatment survives both mesh provenance and the production application-to-domain source-ref projector. The baseline observation projection preserves exact filing coordinates, registry-owned legal and source references, and the correct no-formula provenance for an informative modelo. The separate two-bucket test retains taxpayer isolation. The tests import production implementations, use real encrypted repositories, and contain no fake, stub, patch, monkeypatch, or mirrored resolver logic. The exact figures are scenario inputs testing copy and routing fidelity; they are not presented as an external AEAT calculation oracle, which is correct because Modelo 720 has no calculation formula.

## Recommendations

The first recommendation is satisfied by the corrected generic validator. The remaining mutation coverage, generated-evidence, and M720 boundary recommendations stay open.

Final status: the validator, mutation coverage, and M720 boundary recommendations are satisfied. Only the generated-evidence recommendation remains open.

- Make the registry validator iterate every direct `previous_filing` binding and require exactly one source-modelo classification regardless of treatment. Apply construct-membership and binding legal-reference coverage checks to both `direct_annual_settlement` and `factual_evidence` classifications.
- Add real mutation tests that remove the Modelo 720 classification and a relation-less settlement classification, and prove both mutations fail registry validation. Include factual-evidence construct-membership and legal-reference removal mutations.
- Refresh the execution record against current-tree evidence, run the runner-required page-level gates for every affected page, and account for all fourteen regenerated sequences. Do not approve `P02.S18` until the complete generated surface is current and green.
- Extend the M720 boundary proof through distinct real work units in one taxpayer bucket plus a second taxpayer bucket, asserting the intended same-taxpayer work-unit behavior and cross-taxpayer refusal. Preserve and assert capture source kind, source year and period, stamped revision, capture time or fingerprint, and legal and source references through the production source-mesh provenance projection; do not treat an encoded `source_ref` suffix as full provenance.

## Final verdict

PASS for P02.S18 review closure. There are no open critical or high findings. The M720 item remains a non-blocking medium observation about a broader persistence/provenance boundary; it neither contradicts the fifteen carry-treatment declarations nor invalidates the P02.S18 registry or generated-sequence gates.
