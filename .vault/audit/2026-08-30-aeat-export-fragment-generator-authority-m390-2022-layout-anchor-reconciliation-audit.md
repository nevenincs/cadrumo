---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:4dda89e9eae9b055a55d450ecb00984c2747ab4f4a9fa97621aa6ca94d312e38'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace aeat-export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `aeat-export-fragment-generator-authority` audit: `Modelo 390 2022 layout-to-anchor reconciliation`

## Scope

The committed Modelo 390 2022 fixed-width export layout, reconciled field-by-field against the parser anchors of the hash-pinned official design `aeat-dr-390-2022` (sha256 `7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe`).

Layout read from the fourteen committed fragments under `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/export_layouts/`. Anchors read through `load_record_design_intermediate` via the census helper in `dev/registry/tests/test_m390_2022_numbered_anchor_census.py`, whose own gate is green at 537 anchors. Matching is by `(record, offset)`. No production code was modified.

## Findings

### the committed layout covers 403 of the 537 numbered-page anchors | `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/export_layouts/`

Per-page, layout fields against design anchors:

| record | layout | design | gap |
|---|---|---|---|
| `modelo-390-page-01` | 68 | 74 | -6 |
| `modelo-390-page-02` | 91 | 92 | -1 |
| `modelo-390-page-03` | 96 | 97 | -1 |
| `modelo-390-page-04` | 18 | 19 | -1 |
| `modelo-390-page-05` | 6 | 97 | **-91** |
| `modelo-390-page-06` | 48 | 49 | -1 |
| `modelo-390-page-07` | 16 | 48 | **-32** |
| `modelo-390-page-08` | 60 | 61 | -1 |

403 of 537, a shortfall of 134. `modelo-390-envelope-header` (11 fields) and `modelo-390-envelope-footer` (1) are the separately governed auxiliary header and are excluded from the numbered-page count.

What is lost: S79 has been scoped as authoring 537 owners from nothing. It is not. Three quarters of the anchors already carry a reviewed owner, offset, length, `data_type`, `legal_refs` and `source_refs` in the committed layout, and that layout is also what a generated tree must reproduce byte-for-byte. Scoping the row as blank-page authoring invites inventing owners that already have a reviewed answer.

### the shortfall is concentrated on pages 5 and 7, and part of it is a reasoned deferral with a named blocker | `export_layouts/0011-export-layouts-complementaria-blank.toml`

The uniform -1 on pages 1, 2, 3, 4, 6 and 8 is the *indicador de página complementaria* at offset 12, length 1, authored as `kind = "filler"` because the official design declares that contenido `En blanco`.

Pages 5 and 7 declare the SAME offset as a real operator datum -- `Blanco (No complementaria) o "C" (Complementaria)` -- and were deliberately left unauthored. The fragment's own comment records why: no carrier in this registry emits `"C"`, because `data_type = "boolean"` renders the canonical `"X"` and blank only, so authoring it with what was available would put wrong bytes on the wire.

That accounts for one anchor on each of pages 5 and 7. The remaining 90 on page 5 and 31 on page 7 are not explained by that comment and have no prior adjudication.

### box numbers do not resolve by label, and one measurement in this session was wrong because of it | `export_layouts/0002-export-layouts.toml:805`

Casilla ids are semantically renamed relative to the official box labels. Box [64] `Suma de deducciones` is `iva.anual.cuota-deducible-total` at offset 183; a search for `suma-deducciones` finds only the `regimen-simplificado` and `sector-diferenciado-N` variants and reports a registry gap that does not exist. An earlier tick of this session recorded exactly that false gap before the layout was read.

Anchors must be matched to owners by `(record, offset)` against the committed layout, never by searching the official label.

## Recommendations

1. Re-scope S79 in the plan row from author-537 to transcribe-403-and-adjudicate-134, naming pages 5 and 7 as the adjudication surface. The row's current wording overstates the work and hides where the real decisions are.

2. Author the `dev/registry/mappings/modelo_390/2022/` semantic map by transcribing the committed layout keyed on `(record, offset)`, so every transcribed owner is traceable to a reviewed field rather than re-derived. `validate_semantic_map` runs `_validate_exact_bijection`, so the map only validates once all 537 anchors are covered -- the 134 must be resolved before the map can land at all.

3. Open the complementaria carrier question as its own row rather than folding it into S79: emitting `"C"` needs a carrier `data_type` that can render it, and no existing one can. Until that is decided, pages 5 and 7 cannot close, so it gates the row rather than being a detail inside it.

4. Feed this page-design read back to the twelve UNCLASSIFIED entries in `2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit` (three casillas across four revisions, both fields 17 wide, policy unset). That audit deferred them explicitly pending "the 390 page design read", which this reconciliation now supplies.

5. Do not treat the 403 as verified merely because they are committed. They are a prior adjudication, and the generated tree must still reproduce them through `check_generated_export_tree`; a transcription that agrees with a wrong layout is still wrong.
