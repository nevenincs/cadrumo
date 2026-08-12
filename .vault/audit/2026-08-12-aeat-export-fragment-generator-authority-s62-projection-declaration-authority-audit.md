---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:c5916e8357bb077523d73c0b798baec97a88a34ba50e450ff9b5ef1ce29c1de3'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S62 Projection Declaration Authority Audit`

## Scope

Audited the revision-owned typed projection declaration authority that breaks the S19/S20 bootstrap cycle across the five explicit Modelo 303 revisions. The audit covered schema, loader, evidence, completeness, classifier integration, semantic-map admission, generated-layout bijection, and deletion of layout and `casilla.export_refs` admission.

## Findings

### declaration-completeness | high | an empty matrix initially bypassed validation

The first candidate checked missing projection-only casillas only when at least one declaration existed. Removing all 108 declarations from real Modelo 303/2025 therefore passed validation. Completeness is now unconditional whenever projection-only casillas exist; deleting the full matrix refuses both `RegistryValidator` and snapshot construction, while a real layoutless revision without projection-only casillas remains valid.

### projection-declaration-home | low | five revisions carry one exact typed declaration matrix

Each selected revision carries 108 declarations: 25 prorrata, 36 differentiated-deduction, 4 simplified activities, 2 simplified facts, 28 simplified modules, 12 exonerado activities, and one slotless operaciones-terceros marker. The 540 declarations cover all seven `FilingProjectionRef` variants with revision-scoped legal and source evidence.

### downstream-bijection | low | maps and layouts consume declarations without seed authority

Semantic maps admit projection references only from the selected revision's declaration index. Generated layouts must realize the complete declaration set exactly once. Numbered declarations match projection-only casillas, the sole official-box classifier reports them addressed, and neither layout membership nor `casilla.export_refs` admits projection semantics. Formal review approved the final candidate with zero unresolved critical, high, or medium findings.

## Recommendations

Treat the revision declaration index as the only pre-generation projection authority. Full or partial declaration deletion, duplicate declarations, cross-revision evidence, seed layouts, export-ref admission, inferred identities, and non-bijective generated layouts must continue to refuse.
