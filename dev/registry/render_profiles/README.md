# Render profiles — authored numeric-representation review

One TOML fragment set per (modelo, design epoch), consumed by
`dev.registry.pipeline._render_profile`. Every file is AUTHORED evidence, not
generator output: each rule carries a hand-written `[.evidence]` block with its
decision id and justification.

## File schema

`NNNN-<topic>[-<NNN>].toml` — `NNNN` is the global ordinal in the directory
(the load order); the optional `NNN` is the per-topic counter; `fragment_id`
inside the file matches the filename stem.

## Topic vocabulary (closed)

- `numeric-representation` — reviewed numeric-representation policy for fields
  without a width-17 rule family (formerly spelled `reviewed-numerics`,
  `blank-numeric`, `unstated-numerics`).
- `singletons` — singleton-field numeric rules (formerly `singleton-numerics`).
- `width17-num` — width-17 rules for `Num`-type fields.
- `width17-n` — width-17 rules for `N`-type fields (n-prefix negative sign
  policy). Deliberately distinct from `width17-num`: the two populations carry
  different sign policies and are never the same topic.
- `identifier-digits` — identifier digit-width policy (modelo 210).

A new topic stem is a change to this vocabulary: add it here in the same
change as its first use.

## Which fields a profile may govern

A profile exists to state a wire fact the official design left unstated, so the
pipeline enumerates an ELIGIBLE set and demands the profile cover it exactly.
Coverage is checked in both directions: a rule for a field outside the set is
refused as unknown, and a field inside the set with no rule is refused as
missing. Both refusals name the anchor, so a coverage error tells you which way
it went.

For a workbook design, eligibility turns on whether the field's content cell is
blank. A blank cell means the design said nothing about representation and the
field is yours to rule on. A non-blank cell means the design stated the fact and
the pipeline takes it from there instead.

**A footnote reference is a non-blank cell.** A content cell reading only
`Nota 4.` excludes the field from profile authority exactly as a genuine format
statement would, even though the note it points at usually says something about
applicability rather than about how the value is written. If you find an amount
you expected to govern reported as unknown, check its content cell before
assuming the anchor is wrong: the field is outside your reach, and the
representation is being taken from the note.

This is not hypothetical. One monetary field in a revision currently in force is
emitted unscaled beside five identical siblings that emit cents, because its
content cell holds a bare footnote reference. Across the corpus 183 numeric
fields sat in that position when it was measured on 2026-09-02; almost all still
render correctly, because the generator derives a sound representation from the
design's type column, so the population is a migration surface rather than a
defect list. That count carries no standing command: deciding which fields are
numeric needs predicates private to the pipeline module, and a screen importing
them across that boundary was written, run once and deleted rather than shipped
as a boundary violation. Treat the figure as a dated measurement, not a live
number.
