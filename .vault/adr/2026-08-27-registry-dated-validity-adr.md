---
tags:
  - '#adr'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:f40eda7c4e570b58954d6ea9a68e22a3e6ee4566746a7b4400061925cba46994'
related:
  - "[[2026-08-27-registry-dated-validity-research]]"
---

# `registry-dated-validity` adr: `dated citation windows replace whole-file-per-year copies, and a window is a grounding claim` | (**status:** `proposed`)

## Problem Statement

Registry corpora that sit outside a modelo revision are versioned by copying a
whole file per filing year. Admitting a year therefore costs a full duplicate of
content that does not vary, and the duplicate is made by mirroring a reviewed
year rather than by grounding the new one.

A decision is needed before code because the obvious remedy carries a hazard the
remedy itself creates. Collapsing per-year copies into dated rows requires
choosing a validity window for the surviving row, and a window that spans two
years asserts that the content is grounded for both. Where one of those years was
mirrored, widening the window launders a copy into a grounding claim, silently
and permanently. `2026-08-27-registry-dated-validity-research` measures exactly
that condition in the reference corpus.

The decision must therefore settle three things: the format, the honesty
invariant that makes the format safe, and how far the change reaches. On the last
point one boundary is hard and one is not. The exact-year pinning defect belongs
to a separate brief and must not be absorbed, because a format commit that
quietly alters refusal behaviour is unattributable. The live IVA grounding hole
is inside the reach, because measurement shows it is a filename artefact over
year-neutral content rather than missing evidence.

## Considerations

- The reference corpus's two years vary in citation metadata only, and in nothing
  normative; the year-variable surface the brief anticipated does not exist at
  HEAD (`2026-08-27-registry-dated-validity-research`).
- The older copy declares in its own header that it was mirrored from the
  reviewed year, and its year-dated citations were rewritten by substitution
  (`2026-08-27-registry-dated-validity-research`).
- The tree already carries a written ruling that a mirrored table is "a
  fabricated citation wearing a legal reference", enforced for two sibling
  corpora and not for this one
  (`2026-08-27-registry-dated-validity-research`).
- Three of the forty-two profiles carry no year-neutral citation, and at least
  one citation is a hard model invariant, so a blanket retraction refuses at load
  (`2026-08-27-registry-dated-validity-research`).
- The two IVA corpora are four supported years short and their gate is red at
  HEAD; that gate's remedy clause is grounding, and explicitly not copying
  (`2026-08-27-registry-dated-validity-research`).
- Neither IVA corpus contains a year-dated field; every citation resolves to a
  legal-catalogue provision effective before 2022 and repealed in none of the
  supported years, so their span is derivable rather than attested
  (`2026-08-27-registry-dated-validity-research`).
- `valid_from` is canonical only inside the modelo revision parameter subsystem,
  whose resolver, gap and overlap machinery does not reach these corpora; three
  other spellings exist elsewhere in the tree
  (`2026-08-27-registry-dated-validity-research`).
- An omissible window sorts as `date.min` and makes partial adoption fail
  silently, per `2026-08-04-profile-derived-selectors-research`.
- All three affected resolvers refuse an uncovered year with no fallback, which
  is the year-pinning behaviour a separate brief owns; the format choice can
  preserve or destroy it (`2026-08-27-registry-dated-validity-research`).
- `2026-08-14-registry-temporal-coverage-plan` will make an unsupported filing
  year a refusal, and owns no row for either problem here
  (`2026-08-27-registry-dated-validity-research`).

## Considered options

**Dated rows over the whole record, one window per year.** Mechanically closest
to the brief and to the revision-parameter idiom. Rejected: it dates content that
does not vary, so it preserves the duplication in row form rather than removing
it, and it offers no place to say that only part of a record is year-dated.

**Base file plus per-year overlay files.** Keeps a file per year but shrinks each
to its deltas. Rejected: it retains the per-year file as the unit, so a year
still costs a file; and an overlay whose base is invisible at the edit site is
the shape that produced the mirror in the first place.

**Undated normative body, dated citations, window required.** Chosen. The split
falls exactly where the measured variance falls, it makes the grounding claim
explicit and checkable at the only place a year genuinely enters, and a new year
costs citation rows alone.

**Collapse and widen the window across both years.** Rejected on honesty: it is
the laundering failure this record exists to prevent.

**Do nothing until the mirrored citations are re-grounded.** Rejected: the format
defect and the grounding defect are independent, and the format decision is what
prevents the next mirror. Grounding is sequenced after, not before.

**Migrate categories only and defer the two IVA corpora.** Rejected by the
operator, and the rejection is correct on the evidence. The deferral rested on
treating the IVA four-year shortfall as missing evidence needing per-year
grounding. It is not: neither corpus carries a year-dated field, and every cited
provision resolves to a legal-catalogue entry effective before 2022 and repealed
in none of the supported years. Deferring would have left two corpora per-year
and red while the very migration that makes them honest was available.

## Constraints

No frontier dependency; the mechanism is TOML parsing, a date comparison and a
derived key set over surfaces this tree already owns.

Two parent surfaces bear on stability. The revision-parameter temporal machinery
is mature but deliberately not reused, so nothing here inherits its maturity or
its bugs. The supported-filing-years declaration is a stable single-file
authority, but the enforcement that reads it is mid-campaign in
`2026-08-14-registry-temporal-coverage-plan`; this record therefore consumes the
declaration and does not depend on the enforcement flip.

The blocking constraint is external and named: three profiles cannot be collapsed
honestly without the 2024 Manual práctico text. That text is not bundled. The
implementation below carries an explicit disposition for the case where it cannot
be obtained, so the constraint cannot silently become a mirror.

The dormant `valid_at` channel that `2026-08-04-profile-derived-selectors-research`
requires a temporal design to adopt or retire sits on the binding-selector
surface, not on this corpus surface. It is deliberately untouched, named here so a
reader does not read the omission as an oversight.

## Implementation

**One undated file per corpus.** The year-named files are replaced by a single
undated file. The normative body is declared once with no temporal fields at all:
the profile, its kind, its ratios, its multiplier and its caps. Nothing that does
not vary carries a date.

**Every citation carries a required, closed window.** Citations gain
`valid_from` and `valid_to`, adopting the tree's majority spelling. Both are
required and both are closed; there is no default, no open end and no absent
form. A year-neutral statutory citation states the span it is asserted over
explicitly rather than omitting the field, which is what keeps a later undated
addition from resolving as effective from `date.min`.

**A window is a grounding claim, and two gates enforce it.** The claim is checked
on whichever axis the citation supplies, and every citation supplies at least one.

A citation whose `reference` or `url` names a filing year may not carry a window
reaching outside that year. This is machine-checkable from the citation's own two
fields, it fires on exactly the act that produced the mirror in the categories
corpus, and it makes widening-over-a-mirror impossible rather than discouraged.

A citation naming a legal-catalogue provision may not carry a window reaching
outside that provision's own `effective_from` / `effective_until`. This is the
axis the IVA corpora supply, since they carry no year-dated text at all, and it
is the stronger of the two: it derives the permissible span from the legal
catalogue rather than accepting an author's assertion, and it fails closed on a
provision that was repealed or took effect mid-window.

Both gates are proven by breaking them: widen one year-dated citation past its
named year, and widen one provision-cited window past the catalogue's effective
date; observe each red; restore.

**Covered years are derived; refusal is unchanged.** The loader derives the
covered year set as the union of the citation windows, and the resolver continues
to refuse an uncovered year with no adjacent-year fallback and no widening. The
exact-year semantics are preserved deliberately and byte-for-byte in effect, so
the pinning defect stays exactly where it is and remains attributable to the brief
that owns it.

**The mirrored citations are not carried forward.** The forty-one year-dated 2024
citations were produced by substitution and are dropped rather than re-windowed.
Thirty-nine profiles retain their statutory `ley_irpf` and `reglamento_irpf`
grounding for 2024, which is the stronger authority and is genuinely
year-invariant. The three profiles that would be left with no citation are
grounded against the 2024 Manual práctico in the same change. If that text cannot
be obtained, 2024 is withdrawn from the corpus and resolves as a refusal; the gap
is then visible at the boundary instead of papered over by a copy.

**One shared mechanism replaces three copied loaders.** The window resolution and
coverage derivation land in a single canonical defining module consumed directly
by each corpus loader, with no re-export, facade or package-namespace binding. The
year-keyed resource repositories that wrap these loaders are updated in the same
commit, since the year is a cache key in a second place.

**Atomicity.** The format change, the loader, the gate, every consumer, every
fixture and every test land in one explicit-path commit, with the old per-year
shape and its tests deleted outright rather than bridged.

**Scope.** All three Tier-1 corpora are migrated: `aeat/categories/profiles`,
`aeat/iva/catalogues` and `aeat/iva/place_of_supply`. Categories lands first as
the reference implementation, because it is the corpus with genuinely year-dated
content and therefore exercises both gates; the two IVA corpora follow onto that
pattern.

**The IVA corpora migrate to a derived multi-year span, not a copied one.** Their
content is year-neutral throughout, so the collapse drops nothing and retracts
nothing. Each citation's window is authored from the cited provision's own
effective window in the legal catalogue and checked against it, which makes a
2022-2026 span a derived fact. The covered-year set then derives from those
windows, and `test_year_coverage_matches_supported_filing_years` goes green
because the grounding genuinely spans the supported window -- not because a table
was copied into four new filenames. Where a cited provision does not in fact span
the window, the gate refuses and that citation's true span stands; the corpus
then covers less than the supported window and the year-coverage gate stays red,
which is the correct and visible outcome.

**Corpora ruled permanently out.** `authorization.d` is excluded structurally, not
provisionally: its year sets are discontiguous and a span cannot express them
without either admitting a year wrongly or costing more rows than the array it
replaces. `m303_orden_anual` is excluded as already conforming, being
generator-owned per-ejercicio rows reached by a different route. Modelo revision
directories remain out of scope, since a revision is an orden's applicability
span.

**Spelling.** `valid_from` and `valid_to` are adopted. The `applies_from`,
`effective_from` and `renta_years` populations are not swept; each sits behind its
own validated schema and gates, and unifying them is a larger relocation than this
corpus work.

## Rationale

The measured variance decides the shape. Splitting undated body from dated
citation is not a design preference imposed on the data; it is where the diff
already falls, at one hundred percent invariant body against eighty-two lines of
citation metadata. Every alternative dates content that does not vary, and paying
that cost buys nothing because no consumer varies it.

The knockout criterion is the honesty invariant. Two options collapse the
duplication competently; only this one makes the resulting window a checkable
claim. Without the invariant, the migration's own output is indistinguishable from
the defect it removes, and is worse, because a widened window reads as a
deliberate multi-year grounding assertion where two files at least read as two
files. The tree's existing never-mirror ruling states the principle; this record
supplies the first mechanism that enforces it.

Requiring the window rather than defaulting it is the direct application of the
silent-partial-adoption hazard recorded in
`2026-08-04-profile-derived-selectors-research`. That document rejected
effective-dating for taxpayer facts on grounds that do not transfer here, since
its objection was a duplicated time axis and registry regulatory data has none;
what transfers is its warning, and requiring the field discharges it.

Preserving the exact-year refusal exactly is what keeps the blast radius
attributable. An omissible `valid_to` would have quietly changed pinning
behaviour inside a format commit, which is the coupling the brief forbids.

Including the IVA corpora follows from the same principle rather than from
appetite. Their gate's remedy clause rules out closing the red by copying, and
this migration does not copy: it replaces a filename-borne year claim with a
window derived from the legal catalogue and checked against it. The corpora most
at risk of being closed by a future mirror are precisely the ones that most need
the gate installed, and installing it while migrating them is cheaper and safer
than leaving them per-year with a standing red and an obvious wrong fix.

## Consequences

A new filing year for the migrated corpus costs its year-dated citation rows and
nothing else, and the cost is proportional to what genuinely changed.

The honesty invariant will refuse work that today succeeds. Adding a year by
copying is no longer possible, so the cheap path is closed and the remaining path
is to read the year's source. That is the intended trade and it will feel like
friction at the moment a year is admitted.

Grounding for filing year 2024 is reduced on paper for thirty-nine profiles,
because forty-one citations that appeared to support it are withdrawn. Nothing is
actually lost: those citations never carried evidence. The statutory citations
that remain are the load-bearing ones.

The three ungrounded profiles are a real, bounded external dependency. If the 2024
text cannot be obtained, the corpus loses a filing year it currently appears to
serve, and the loss becomes visible at a refusal boundary. That is the correct
failure, and it will look like a regression to anyone reading only the coverage
count.

The IVA year-coverage gate is expected to go green, and that is the outcome most
likely to be misread. It goes green because the covered years derive from
provision-checked windows over content that was always year-neutral, not because
coverage was manufactured. Anyone reviewing the diff will see one red test turn
green beside a corpus that lost two-thirds of its filenames, which is exactly the
shape a mirror would also produce; the provision-window gate is what distinguishes
them, and it has to be read as part of the same change.

If any cited provision turns out not to span the supported window, the gate
refuses the wide window and the corpus covers less than the declared years. The
red then persists for a real reason. That is a success of the design and will
look like a failure of the migration.

Collapsing three copied loaders into one shared mechanism removes a duplication
the brief did not name, and gives the deferred corpora something to migrate onto
rather than a pattern to re-derive.

The tree keeps four validity spellings. This record adds no fifth and unifies
none; a reader encountering `applies_from` or `effective_from` still has to know
which subsystem they are in.
