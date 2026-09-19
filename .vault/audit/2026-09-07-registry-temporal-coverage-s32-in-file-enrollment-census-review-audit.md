---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:edada4e7d452b80ed6e071395942e03eb3fc5cecd4b01f544e98702747fbb78d'
related:
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - "[[2026-08-24-registry-completeness-closure-adr]]"
  - "[[2026-08-28-registry-narrow-mechanism-widening-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-09-07-registry-temporal-coverage-enrolment-versus-declared-projection-research]]"
---
# `registry-temporal-coverage` audit: `S32 in-file enrolment census review`

## Scope

Review W01.P09.S32 against the accepted temporal-coverage, completeness-closure, and narrow-mechanism-widening decisions. The reviewed surface includes the consolidated Modelo 303 semantic-map census and test suite already landed in commit a16b0b8ffd7, the new yearless literal-enrolment detector, its source-digest pin contract, and its isolated mutation proofs.

## Findings

### s32-property-collapse | info | one discovered suite owns every authored M303 epoch

The live Modelo 303 suite discovers epochs from the mapping tree, resolves each through canonical temporal selection, requires a render profile and reviewed census expectation for every discovered epoch, and refuses an empty population. The former per-epoch census and test modules are absent. The authored semantic maps and render profiles remain evidence declarations, as required by the accepted year-scoped authority boundary; they are discovered inputs rather than a copied Python enrolment list.

### s32-yearless-enrolment-census | info | literal revision collections cannot remain silently partial

The new AST census scans module-level literal row collections under dev/registry/tests. It recognises tuple, list, set, dictionary-key, and constructor-row shapes whose first two literal fields are a canonical modelo and digit-led revision identity. Imported and computed collections are not counted a second time. The expected subjects come from compose_temporal_coverage revision summaries, so the detector reuses the canonical law-selected denominator instead of copying selection logic or a corpus tally.

Missing subjects may be accounted for only by TemporalEnrollmentExclusionPin. Each pin names the exact path, symbol, modelo, revision, source reference, source SHA-256, reason, and reconsideration condition. A source reissue, removed declaration, duplicate pin, now-enrolled subject, or unknown subject makes the audit red. No live exclusion pin is required after the generated-tree list was replaced by derivation.

Mutation proofs cover the former _GeneratedTree constructor shape in a yearless file, an exact missing pair, an exact altered pair reported as both missing and extra, imported-list non-duplication, digest reissue dormancy, and orphan-pin refusal. The live census is clean without a frozen revision or file count. Ruff is clean, strict BasedPyright reports zero diagnostics, and the focused property suite passes. The reviewed code introduces no cast, Any annotation, type ignore, Pyright ignore, matcher relaxation, fallback, or compatibility alias.

## Recommendations

Close W01.P09.S32. Preserve compose_temporal_coverage as the sole denominator and keep exclusions in ENROLLMENT_EXCLUSION_PINS rather than suppressing AST matches or narrowing the scan root.
