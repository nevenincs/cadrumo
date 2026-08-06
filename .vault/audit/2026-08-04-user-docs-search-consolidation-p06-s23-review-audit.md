---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:5dbc3e7ff5a63621528373078d8e9c1fec2023c05a6712bb6e67e72c40a6d141'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `P06 deterministic enrollment follow-up`

## Scope

Audit the landed P06 deterministic-enrollment slices against the accepted search ADR and the current P06 plan: `088e3255a8`, `77c2e8ea49`, `18a777cc44`, `a4281864a9e31438ccc9b536657cb89d7576020f`, `21436e572dce4ae84de9358fd990d8af30593aa4`, `3fb2c90cae363b464daab7ef0efcf99f0be43d7f`, `a294ac35ed`, and `ea5e441d7c`. The review is read-only and deliberately excludes tests, builds, Pagefind compilation, deployment, and live probes.

## Findings

### deterministic-census | low | Separate census preserves the existing relevance metric

`CasillaCoverageCensus` measures projected, exact-target, definition, locale, and sparse relevance axes over the same projected identity set. The existing four-kind `CoverageReport` join remains semantically unchanged. The census explicitly refuses to claim Pagefind or generated-site parity, which is the correct boundary.

### definition-projection | low | Registry-backed definition metadata stays on the canonical projection

The casilla projection carries localized help, data type, input kind, requiredness, binding, and formula identity into the unified metadata. The generated reference surface renders those fields with Spanish fallback. It does not invent a formula expression because the projection does not own the revision formula table.

### resolver-fail-closed | low | File-level representative casilla fallback is removed

The resolver now maps a registry TOML hit only when its source line span identifies exactly one casilla and exactly one current projected record. Invalid, unreadable, ambiguous, model-only, and non-TOML Diseño hits become typed dropped hits instead of selecting `records[0]`. This is safer, but its effect on the committed sweep remains unmeasured until the planned re-sweep/gate.

### structured-pagefind-result | high, corrected | Structured exact matches initially read the wrong Pagefind URL surface

The JavaScript controller initially read `result.url` after awaiting `result.data()`, while the existing `dataToCards` path takes the URL from `data.url`; valid exact matches could therefore be discarded. `21436e572dce4ae84de9358fd990d8af30593aa4` now uses `item.data.url`. A fresh focused formal review returned PASS with no findings. The real built index, filter behavior, target destination, and M130/casilla-15 reader result remain unverified.

### unquoted-casilla-header | high, corrected | Source-section parsing initially rejected real unquoted registry headers

The casilla section parser initially accepted only `[[revisions."...".casillas]]`, while real registry fragments also use unquoted headers such as `[[revisions.2009-y-siguientes.casillas]]`; the reviewer found 536 such headers. `3fb2c90cae363b464daab7ef0efcf99f0be43d7f` now accepts both valid forms while preserving individual-section matching and no-representative fallback. A fresh focused formal review returned PASS with no findings. The post-change sweep remains unrun.

### census-invariants | corrected | The coverage value object now enforces its measurement invariants

The initial census validated surface names but did not enforce `covered <= total`, uniqueness/order of surface entries, or consistency between the covered ids and the declared total. Commit `a294ac35ed` adds strict Pydantic validators for bounded counts, exact uncovered partitioning, unique sorted ids, canonical five-surface order, and one shared projected denominator. A fresh formal review returned PASS with no CRITICAL, HIGH, MEDIUM, or LOW findings. Runtime/Pagefind parity remains outside this model contract.

### source-compatibility | medium | Existing resolution expectations need reconciliation

The new fail-closed resolver deliberately drops model-only Diseño workbook/PDF hits without an individual locator, while existing resolution expectations still describe those hits as resolvable. P06.S24 must reconcile the expectation with the intended evidence boundary rather than silently restoring a representative fallback.

### definition-whitespace | corrected | Whitespace-only localized values now fall back consistently

The projection previously accepted whitespace-only localized labels or help as authored, while the census treated equivalent content as missing. Commit `ea5e441d7c` strips localized Spanish and non-Spanish values before deciding whether to use them, preserving non-empty values and the existing Spanish fallback. The focused formal review inspected the full file and exact diff and returned PASS with no findings. Runtime locale/detail parity remains a P06.S24 gate.

### review-revalidation | corrected | All landed P06 corrections now have focused formal review results

The original formal review identified the two high findings above. Focused fresh reviews now return PASS with no findings for the corrected structured Pagefind path (`21436e572dce4ae84de9358fd990d8af30593aa4`), registry-header resolver (`3fb2c90cae363b464daab7ef0efcf99f0be43d7f`), and localization fallback (`ea5e441d7c`). This clears the source-level review boundary for P06.S21-S23; P06.S24 still owns runtime, built-index, and target-coverage acceptance.

### coverage-review | low | Census invariant correction formally passes

The replacement reviewer inspected `a294ac35ed` against the P06 plan and grounding documents and reported no findings. The review covered only the census value-object correction; it did not authorize closure of the browser/Pagefind, re-sweep, legal, Rung 2, or deployment work.

## Recommendations

- The focused P06.S21-S23 corrections are landed and each has a focused formal PASS; close their step rows and move to P06.S24 runtime/target gates.
- Execute P06.S24 with real-behaviour gates for the projection census, M130/casilla-15 structured search, locale/detail output, and target resolvability before closing P06.
- Re-run the build-time sweep after the resolver change and compare relevance coverage and dropped-hit counts; do not interpret the old `22/6,359` report as current after the new fail-closed rule.
- Reconcile the existing Diseño workbook/PDF expectations and locale behavior in that gate; the census invariants are now formally reviewed. No test execution is authorized yet.
