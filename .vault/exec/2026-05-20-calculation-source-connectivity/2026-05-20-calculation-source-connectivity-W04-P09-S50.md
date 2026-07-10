---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S50'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S50 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Persist source refs and fingerprints on calculation revisions and ## Scope

- `src/aeat/domain/modelos/_calculation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Persist source refs and fingerprints on calculation revisions

## Scope

- `src/aeat/domain/modelos/_calculation.py`

## Description

- Add the compact `CalculationSourceRef` domain model (source_kind, typed binding_source, source_ref, fingerprint) to the calculation-revision module; the plan scoped file `_calculation.py` is the current `_calculation_revision.py`.
- Add an additive `source_provenance` tuple field on `CalculationRevision`, defaulting to empty for backward compatibility.
- Keep `source_provenance` OUT of `derive_calculation_revision_id`, mirroring `ledger_filing_snapshot` / `ledger_filing_evidence`, so the content-addressed id is unaffected.
- Deliberately omit `legal_refs` / `source_refs` from the ref model; per-casilla grounding stays on the revision observations.
- Export `CalculationSourceRef` from the calculation-revision `__all__` and the `domain.modelos` package facade.
- Map application `CalculationSourceProvenance` to the domain `CalculationSourceRef` at the persist boundary and thread `source_provenance` through `persist_calculation_revision`, `calculate_modelo_revision`, and the bucket-aggregation calculate path.

## Outcome

Every ledger/invoice/carry resolver that contributes to a calculation now leaves a persisted resolver-to-source-object-to-fingerprint trace on the revision. Verified the id is invariant to `source_provenance` (identical ids with and without the field) and that the field survives the encrypted repository roundtrip.

## Notes

The domain model imports `BindingSourceKind` from `core.aggregation` (domain-to-core is legal); it never imports the application-layer provenance model. The strict `min_length` constraints on `source_kind` / `source_ref` are what the S53 anti-tautology proof bites on.
