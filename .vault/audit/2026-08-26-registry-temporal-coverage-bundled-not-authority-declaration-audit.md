---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:d7e871f5e228bdea9eb1974389adc4a7980f3d8ced1f6d1ad5c72950731560b1'
related:
  - "[[2026-08-26-registry-temporal-coverage-modelo-200-split-coherence-audit]]"
---

# `registry-temporal-coverage` audit: `Bundled corpus that is deliberately not an authority`

## Scope

The registry has no way to declare that a bundled corpus file is deliberately
NOT a registered or machine-readable authority. Three separate gate families now
want that one concept, and each currently expresses it by contradicting another
gate. Opened after the modelo 184 parseability contradiction was measured and
found to have no existing marker, and after unregistering the modelo 036
provisional draft moved a failure from one gate to its opposite.

## Findings

### m184-parseability-contradiction | high | two adjudicated contracts are mutually exclusive, 9 failures

The modelo 184 regression pins, for the four raw BOE ordenes: `kind` is
`record_design`, `record_design_epoch` is None, and the parse REFUSES, asserted
with `pytest.raises` on `first field starts at position N`. Its docstring states
the ruling: a raw BOE design is provenance, not a surrogate for a later AEAT
map, and the parser refusal is intentional and load-bearing.

Against that, `test_registered_record_design_sources_are_discovered_and_parseable`
takes EVERY source whose `kind` is `record_design` and requires it to parse, and
`test_record_design_pdf_corpus_is_discovered_and_parseable` does the same. The
export-layout coverage gate's design-sheet enumerator calls the extractor on
every declared design with no refusal tolerance, which is 7 of the 9.

Neither side can pass while the other does. Every escape was checked and closed:
there is no exclusion or allowlist in the parseability module at all, so the
stale-allowlist move does not apply; `kind` reclassification to `form_spec` has
precedent but is blocked because the m184 contract pins `kind` to
`record_design`; and skipping epoch-less designs over-skips, because the pending
map conflates provenance-that-never-parses with a design whose epoch is merely
unassigned. Two semantic vault searches found no ruling.

### m036-provisional-moves-the-failure | medium | correcting one gate fed the opposite gate

The non-ejercicio gate rules that modelo 036's provisional 2025 design is a
superseded draft which governs no window, and that being bundled WITHOUT being
registered is the right outcome. A blanket registration sweep enrolled it
anyway. Unregistering it cleared two failures and added one entry to the
bundled-design registration gate, which requires every bundled design file to be
registered.

That gate declares itself a worklist, red by design when a gap exists, and it
was already red for a second file. So this is not a regression. It is the same
missing concept surfacing a third time: the worklist has no way to record a file
that is deliberately unregistered, so a correctly-unregistered draft keeps it
red permanently.

### m165-layout-gap-is-the-same-question | medium | previously escalated separately

Modelo 165's revision `2023-2025` has no layout authority, and no precedent
exists for a design-less era: 1,717 of 1,720 coverage ledgers satisfy the layout
tier and none does so without citing a record-design source. That is the same
shape as the two above -- an authority that cannot serve as a machine design --
and was escalated on its own terms before the pattern was visible.

### orphan-inventory | low | a repoint stranded a file nothing references

The modelo 200 2025 design moved from `.xlsx` to `.xls`. The `.xlsx` remains in
the corpus, registered by nothing, and is the bundled-design worklist's other
entry. Deleting bundled corpus is destructive and was not done.

## Recommendations

Rule once on where "bundled corpus that is deliberately not a registered or
parseable authority" is declared, and let all three families read it. The
declaration belongs in registry data rather than in test-local constants,
because three independent gates need to agree about the same files. This is the
decision a follow-on ADR must make; it is not taken here.

Whatever shape it takes must distinguish two things the pending-epoch map
currently conflates: a source that will never be a machine design, and a design
whose selection window is merely not yet assigned. Collapsing them would let a
genuinely unfinished design hide behind the same marker.

Do not resolve any of these by relaxing an assertion. The parseability gates and
the m184 refusal each carry a stated contract, and the coverage enumerator's own
docstring records that requiring completeness there once silently emptied a
population and proved nothing.

Until the ruling lands, the modelo 184 nine and the modelo 036 worklist entry
stay red and attributed rather than worked around.
