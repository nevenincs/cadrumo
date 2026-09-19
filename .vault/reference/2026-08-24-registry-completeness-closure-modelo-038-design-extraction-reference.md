---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:dc3608be3b704d0db71c98260e960e38c031e6f85065630ce945fb1e5c0f3bb7'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` reference: `modelo 038 design extraction`

Modelo 038 has an official current fixed-position design and an active fichero
submission route, but its bundled two-page diagram is not trustworthy coordinate
input for the shipped parser. The registered revision must remain inspection-only
at the applicability grade. No export layout, semantic map, or filing-grade claim
is authorized by this finding.

## Summary

### Official source and filing route

AEAT's record-design index currently lists Modelo 038 and its `dr038_2024.pdf`
design. AEAT's Modelo 038 filing guidance requires the uploaded declaration file
to conform to the current record design, accepts the file for validation, and
allows a wholly correct file to be presented. The source is therefore neither
missing nor a web-form-only exception.

The original legal authority, Orden HAC/66/2002, approves the Modelo 038 logical
design and fixes a monthly declaration cycle. Orden HAC/646/2024 makes a narrow
change: type-2 IRUS occupies bytes 153-165 and bytes 166-250 are blank. It applies
that change first to the June 2024 declaration, filed in July 2024. The 2024
publication consequently cannot evidence the pre-June-2024 field arrangement of
the open `2002-y-siguientes` revision.

### Shipped design is real but not a trustworthy extraction

The registered source `enrolled-modelo-038-layout` points to the hash-pinned AEAT
PDF in `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_038/`.
Its manifest records SHA-256
`f2f713cd60b26548ab9fb57b457f28c5a7841423592f95debdf83a78d9e2f0fe` and 94,268
bytes. The extracted artifact has only the two visual pages: a position ruler with
free-floating labels. The geometry recovery returns mirrored labels and overlapping
field spans rather than a stable position/length/description table.

`test_cited_design_field_bounds_are_self_consistent.py` proves that this source
still produces the overlapping-field condition and that no export layout cites it.
The filing-capability worklist independently records Modelo 038 as blocked on
design extraction. Its aggregate assertion is intentionally red while the
fourteen-revision filing backlog exists; its Modelo 038 line is the expected
refusal, not a regression.

### Adjudication and exact owners

`038/2002-y-siguientes` is supported for registered-modelo inspection and monthly
applicability only. It is not fileable in Cadrumo. Retaining
`authority_grade = "applicability"` and no export layout is the correct boundary;
the official design must not be converted into guessed field coordinates.

`W02.P05.S43` in `registry-temporal-coverage` is the exact owner of the source-era
correction. It must retain the 2024 design only from the June 2024 declaration,
obtain a hash-pinned earlier official design before it asserts 2002-to-May-2024
coverage, and split the revision or source binding through the validated temporal
authority. It cannot promote the grade, author a layout, infer the earlier layout,
or retain a fallback.

`W04.P07.S96` in `aeat-export-fragment-generator-authority` is the separate exact
owner of trusted-layout acquisition. Only after the source era is exact, it may
derive a complete non-overlapping coordinate intermediate from a hash-pinned
official design and then pass the existing reviewed semantic-map, render-profile,
canonical-generator, provenance, and production emitted-byte proof gates. It may
not guess coordinates or add a parallel writer.

Reconsider fileability only after all of these are true:

1. `W02.P05.S43` closes with a validated historical design for the earlier window
   and the 2024 design scoped from June 2024.
2. `W04.P07.S96` derives a complete, non-overlapping coordinate intermediate with
   source-hash and applicability validation; a parser workaround alone is
   insufficient.
3. A reviewed semantic map, render profile, generated-tree proof, and production
   emitted-byte test satisfy the established export-generator authority.

## Sources

- AEAT record-design index, retrieved 2026-08-24: https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-01-99.html
- AEAT Modelo 038 filing guidance, retrieved 2026-08-24: https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/declaraciones-informativas-ayuda-tecnica/modelos-038-180/modelo-038.html
- AEAT Modelo 038 current design, retrieved 2026-08-24: https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_01_99/archivos/dr038_2024.pdf
- BOE-A-2002-1041, Orden HAC/66/2002, arts. 1, 2 and 6: https://www.boe.es/buscar/doc.php?id=BOE-A-2002-1041
- BOE-A-2024-13049, Orden HAC/646/2024, art. 1 and final provision: https://www.boe.es/buscar/doc.php?id=BOE-A-2024-13049
- `src/cadrumo/_data/registry/aeat/legal/modelo-038.toml`
- `src/cadrumo/_data/registry/aeat/modelos/038/revisions/2002-y-siguientes/revision.toml`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_038/manifest.json`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_038/files/01-038-diseno-de-registro-actualizado-28-06-2024.pdf.extracted.json`
- `src/cadrumo/domain/calculations/registry/tests/test_cited_design_field_bounds_are_self_consistent.py`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`
- `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md` (`W02.P05.S43`)
- `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md` (`W04.P07.S96`)
