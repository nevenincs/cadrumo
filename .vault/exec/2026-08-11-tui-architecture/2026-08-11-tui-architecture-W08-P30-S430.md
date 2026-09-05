---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:7cf95b07806352168a07840a1bd10669f7ccc446b589389122010f10d7f71c09'
step_id: 'S430'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Label every remaining M200/2024 casilla whose official text is pinned by digest. 116 casillas beyond 00067 carry an adjudication whose official_label_sha256 matches a cell in the shipped record design; those are grounded and derivable now, while the 79 with no adjudication and the 3 whose pin matches no cell need adjudication first. Spanish is the pinned cell verbatim; the other locales compose segment-by-segment from a glossary mined out of the label pairs the catalogues already ship, so a phrase translated once reads the same everywhere it recurs.

## Scope

- `src/cadrumo/locales/*/modelo/schema/200.yml`

## Changes

116 casillas labelled in all four locales. Unlabelled M200/2024 casillas fall
from 198 to 82 in es and en, 201 to 85 in ca, 223 to 107 in hu -- each down by
exactly 116, so the batch landed whole in every catalogue. The ca and hu figures
started higher than es and en and still do; that gap is older than this work.

Spanish is not composed. It is the record-design cell whose sha256 equals the
adjudication's pin, taken verbatim, for the reason S429 sets out: casilla
numbers repeat across record pages, so text chosen by searching for the number
can be real, official, correctly formatted, and the wrong box.

The other three locales are composed segment-by-segment. These labels are
hierarchical paths, and the segments repeat hard: 116 labels are built from 103
distinct segments, one of which ("Deducc. para incentivar determ.actividades")
appears in 57 of them. 51 of the 103 were already translated somewhere in the
3140 label pairs the catalogues ship that align segment-for-segment, so those
were mined rather than re-authored. Reuse is the point rather than an economy:
a segment translated once reads identically everywhere it recurs, while a
segment retranslated per label drifts, and the drift stays invisible until two
rows of the same table disagree about what one official phrase means.

52 segments had no existing translation and were authored. Event names under the
"acontecimientos de excepcional interes publico" programme -- Primavera Sound,
South Summit, Manifesta 15 -- are proper names of real events and are carried
rather than translated; the framing around them is translated normally.

Teeth on a batch member rather than the casilla already proven, and a near-miss
rather than nonsense: 00093's own official cell with "Aumentos" changed to
"Disminuciones", one word, from the same document, describing the sibling row
that really exists. The digest gate rejected it. Restored by copy.

The digest gate now covers 117 casillas with zero mismatches -- every casilla
that has both a pin and a shipped label.

## Notes

The runtime localization gate still fails, on the 82 casillas that remain
unlabelled. Of those, 79 have no adjudication entry and 3 carry a pin matching
no cell in the shipped record design; both groups need adjudication before a
label can be grounded, so none of them is derivable the way these 116 were.

test_codebase_to_locale_parity still fails but improved by exactly 117, from
"missing 345 codebase keys" to "missing 228" -- the 116 here plus 00067. The
remaining 228 are pre-existing and unrelated.

test_translated_values_differ_from_canonical_source_unless_allowlisted still
fails on tui.aeat_sync.* and tui.home.* keys. None of them is a casilla label
and none was touched here.
