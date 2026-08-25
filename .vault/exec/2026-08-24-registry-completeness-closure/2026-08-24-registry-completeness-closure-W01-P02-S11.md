---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d2ce0211a2ab36a7d285244c148f920511151ddf98e18072986cee8e1aaae705'
step_id: 'S11'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - '[[2026-08-24-registry-completeness-closure-s11-independent-post-review-audit]]'
---
# Prove complete, refused, stale-evidence, below-filing-grade, and cross-limb disagreement outcomes with mutation tests

## Scope

- `src/cadrumo/application/registry/tests/`
- `dev/registry/conformance/tests/`
- `.vault/exec/2026-08-24-registry-completeness-closure/`

## Description

- Preserve commit `7834c289ac` as the real descriptor/path-identity symlink-substitution regression; it remains independent of closure completeness.
- Reconcile the original five-outcome action against successor S69 and independently reviewed S72 evidence, using only the loaded authority, canonical source census, live filing-proof port, and existing closure composers.
- Retain the canonical Modelo 036 `2025-02-03-y-siguientes` complete row: law-selected temporal coverage is validated, the revision-scoped manual census evidence satisfies source connectivity, and the below-filing export limb is `not_applicable` with no proof, refusal, producer, or layout claim.
- Retain distinct real refused, stale-evidence, grade-participation, and cross-limb cases. The Modelo 151 live production emission remains refused on its unmeasured canonical source limb; Modelo 100 catalogue-byte drift is stale evidence; inverse Modelo 036 and Modelo 100 participation mutations reject; and divergent Modelo 303 law selection produces a cross-limb disagreement.
- Keep the mutation bites real: remove or pending the exact loaded Modelo 036 census entry and compose the existing three limbs; mutate loaded authority data before the existing composer; and validate inverted filing participation on rows obtained from the real report. Do not create a second selector, census, proof authority, export writer, or closure join.

## Outcome

The five named outcomes are now proven by real composed authority evidence and reproduce through the focused outcome corpus:

- **Complete:** bundled Modelo 036 `2025-02-03-y-siguientes` is a genuine satisfied row through `load_registry_closure_report`: temporal coverage is `validated`, source connectivity is `satisfied` from `source-domain-to-casilla-connectivity:censo.modelo-036-profile-status`, and filing export is a filing-only `not_applicable` limb. The whole report remains release-ineligible because other rows still refuse.
- **Refused:** live Modelo 151 canonical generation and production `export_draft` emission satisfies its filing limb, but the canonical census declares no scoped source evidence, so the same loaded report returns the row as `unmeasured` and predicate-refused.
- **Stale evidence:** mutating the loaded Modelo 100 official layout-source digest before calling the loader returns a filing `stale_evidence` refusal.
- **Below-filing grade:** the M036 completed row and a filing-grade M100 row reject both inverse filing-participation mutations. Below-filing revisions cannot claim filing evidence, and filing-grade revisions cannot opt out.
- **Cross-limb disagreement:** mutating the loaded Modelo 303 authority revision selection causes temporal `selected_revision_mismatch` and filing `cross_limb_disagreement` through the existing report loader.

The M036 entry-removal mutation reopens the same row as source `unmeasured`; replacing its terminal manual disposition with a bounded pending disposition reopens it as `unreviewed_evidence`. These tests exercise the canonical compositional path and fail when the applicable guard is weakened; they are not synthetic complete/refused report fixtures. S72 was independently approved in `e88b06f6c9` after its real row, source mutations, outcome corpus, and no-redeclaration audit were reviewed.

Vaultspec-RAG followed by exact-symbol search found one temporal composer, one source-connectivity composer and census contract, one filing-export composer and proof protocol, one live filing-proof implementation, and one dev-side report join. The tests call those homes only. No code or authority redeclaration was introduced by this reconciliation.

## Notes

The campaign still does not claim a wholly complete or release-eligible registry. S11 is closed only because its five named outcome categories, including the formerly missing positive complete row, are now proven through real current evidence; the broader release predicate remains blocked by visible refused rows.
