---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:bc0a6a0714c15684424add186f960694d2230db41f93a7fd32be1fd197247554'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `s78 m390 envelope`

## Scope

Independent review of the S78 official-source epoch bindings, parser-owned page-zero classification, typed byte composition, source and revision admission, and dedicated real-workbook gates.

## Findings

### s78-m390-envelope | critical | target binding needs parent adjudication

The reviewer found that the typed 2022, 2023, 2024 and 2025-y-siguientes source bindings are intentionally future generation targets, whereas the currently loaded registry still selects the unreviewed `2010-y-siguientes` revision. The implementation refuses that live revision rather than treating it as admitted. This follows the execution direction not to fabricate copied revision authority, but it requires the parent to confirm that the target contract is the correct pre-authoring boundary before the step can close.

### s78-m390-envelope | high | product identity canonical home needs parent adjudication

The reviewer found that the existing evidence-bearing `M303ProductSoftwareIdentity` type has an M303-specific name and documentation while the M390 header needs the same explicit four-byte program and nine-byte developer identity. The implementation reuses that typed authority to avoid a duplicate model, but the parent must decide whether a neutral canonical home is required before closure.

### s78-m390-envelope | low | format check requires completion

The independent review found two files that need the formatter. The static lint gate passed; run the formatter check and record the result before closure.

### s78-m390-envelope | low | format check resolved

The two reported files were formatted and the scoped formatter check passed.

### s78-m390-prospective-target | critical | resolved by approved adjudication

The approved boundary is a prospective typed generation target, not a claim about current registry selection. Each target reuses `ExportFragmentTarget` and binds exactly one source reference, SHA-256, design epoch, and filing-year window. Generation verifies that source against the catalogue and resolved official binary before the typed header is accepted. The existing selected-snapshot admission validator is unchanged and still refuses an intermediate source absent from the candidate or final revision source membership.

### s78-product-identity | high | resolved by canonical core generalization

The M303-named product/software classes were atomically replaced by `AeatProgramIdentifier`, `AeatProductSoftwareEvidence`, and `AeatProductSoftwareIdentity` in the core identity authority. Every consumer and test imports the generic authority, and the former names have neither aliases nor re-exports.

### s78-m390-anchor-contract | low | resolved by exact-anchor hardening

The parser, intermediate, and rendering boundary now retain and verify all thirteen source rows, workbook cells, ordinals, positions, widths, literals, and the terminal byte extent. A mutation test proves a shifted source row refuses before emission; no path writes or derives a fixed-record total for page zero.

### s78-final-independent-review | low | clean

The final independent review found no critical, high, medium, or low S78 issue. Its scoped run was blocked only at `bundled_authority()` by concurrent annual-Orden validation work before the selected-snapshot negative test could execute. The reviewer confirmed that the four prospective targets re-resolve their exact source authority, the parser and renderer retain all thirteen anchors through byte 328 without a declared total, the generic identity leaves no old runtime aliases, and no Modelo 390 revision membership or snapshot admission code changed.

## Recommendations

- Keep target admission prospective until the relayout revision-authoring work supplies reviewed M390 revision source membership, semantic maps, render profiles, and complete tree generation.
- Re-review the resolved prospective target and canonical identity boundaries after the full focused gate.
