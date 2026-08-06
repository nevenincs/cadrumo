---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-07-01'
modified: '2026-07-31'
body_hash: 'sha256:200284141124e3a2a6d4a4554badbf330731a31f34770fffb8896c7f30918ae1'
related:
  - "[[2026-07-01-modelo-verify-nonzero-guards-audit]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# M123 RIRPF exoneration corpus deferral resolution

This record resolves the documented deferral `DFR-M123-RIRPF-EXONERATION-CORPUS`,
cross-referenced from `2026-07-01-modelo-verify-nonzero-guards-audit.md`
finding `m123-art-75-exoneration-list-not-bundled`. The audit found the M123
retenciones-capital-mobiliario `06->09` ADVISORY guard
(`modelo-123-2024-base-total-implica-retenciones-total`) grounded against
`rd-439-2007:art-90` and `ley-35-2006:art-101`, while the type-based
retention-exoneration list in RIRPF art. 75 was not bundled in the legal
corpus.

## Description

- Verified RD 439/2007 art. 75 against the BOE consolidated text for
  `BOE-A-2007-6820`. The current BOE consolidated document is updated through
  2026-02-28; the article 75 wording bundled here matches the article 75 block
  whose relevant amendment version has been in force since 2023-04-25.
- Bundled `src/aeat/_data/corpus/normatives/html/rd-439-2007-art-75.html`
  with the full article 75 text and the `#a75` anchor used by the legal entry.
- Added `[legal."rd-439-2007:art-75"]` in
  `src/aeat/_data/registry/aeat/legal/irpf.toml`, with `corpus_ref`,
  `document_id`, `article`, `permalink`, and `required_text` pinned to the
  article title, apartado 3 opening clause, capital-mobiliario-adjacent
  exception clauses, and the explicit carve-back clause for retained capital
  income.
- Kept the M123 guard unchanged as an ADVISORY aggregate `implies_nonzero`
  predicate. The guard's `legal_refs` now include `rd-439-2007:art-75`
  alongside `rd-439-2007:art-90` and `ley-35-2006:art-101`.
- Updated the focused tests to assert the shipped predicate and emitted
  advisory findings carry `rd-439-2007:art-75` from the loaded registry
  predicate.
- Updated the audit closeout language to point to this exec record. The broader
  registry legal/referential/M123 selection named by the audit was rerun below.

## Outcome

The M123 deferral is closed for this slice. The bundled corpus now contains
the BOE article 75 evidence needed by the legal catalogue, and the M123
verification guard cites that legal reference from the real registry source.
The closeout does not rely on the false shortcut that only letras b) and c)
touch capital mobiliario; it relies on the art. 75.3 obligation boundary:
non-withheld classes are outside a positive M123 withholding-base declaration,
and carve-back/payment-on-account cases remain inside the existing positive
base guard.

## Files

- `src/aeat/_data/corpus/normatives/html/rd-439-2007-art-75.html`
- `src/aeat/_data/registry/aeat/legal/irpf.toml`
- `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/verification_expectations/0002-verification_predicates.toml`
- `src/aeat/domain/calculations/registry/tests/test_modelo_123_registry.py`
- `src/aeat/application/modelo/tests/test_verification_m123_advisory.py`
- `.vault/audit/2026-07-01-modelo-verify-nonzero-guards-audit.md`

## Verification

- `uvx vaultspec-rag search "M123 RD 439 2007 art 75 retention exoneration capital mobiliario modelo 123 verification guard" --type code`
- BOE consolidated `BOE-A-2007-6820`, article 75 (`#a75`)
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/tests/test_modelo_123_registry.py::test_m123_2024_carries_base_total_implies_retenciones_total_advisory src/aeat/application/modelo/tests/test_verification_m123_advisory.py` - 5 passed.
- `uv run --no-sync pytest -q -k "legal or referential or modelo_123" src/aeat/domain/calculations/registry/tests` - 352 passed, 3363 deselected.
