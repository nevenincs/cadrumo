---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f5884e33f9c0407ac663656ce39d4135c85a331a57952576d14e43ef134f74b1'
related:
  - "[[2026-08-14-registry-campaign-sequencing-row-field-data-type-authority-audit]]"
---

# `registry-campaign-sequencing` audit: `Five data_type vocabularies, one canonical, one true duplicate, one outlier`

## Scope

Five sites in the registry package declare a closed vocabulary for a field named
`data_type`. They were found while looking for a symbol to reference rather than
duplicate, and recorded rather than converged, because converging them inside an
unrelated schema migration is the scope creep this campaign has spent its time
catching elsewhere.

The population was measured rather than counted by eye, including whether the
five agree. They do not, and what the disagreement turns out to be is more useful
than the duplication that prompted the look.

## Findings

### four-are-a-coherent-hierarchy | low | Most of the divergence is legitimate narrowing, not drift

Four of the five are nested, each a narrowing of the one above for a surface that
genuinely admits fewer types:

- casilla, 19 members, exactly the runtime scalar taxonomy
- export field, 6 members, a strict subset
- binding export, 6 members
- manual input, 5 members, a strict subset of export

A casilla may hold a NIF or an IBAN; a manual input may not. That is a real
distinction and the narrowing records it. Nothing here needs fixing, and a sweep
that collapsed them into one vocabulary would remove information rather than
duplication.

The measurement is worth keeping for that reason alone: the obvious reading of
"five copies of the same Literal" was wrong, and acting on it would have widened
what several surfaces accept.

### one-true-duplicate | medium | Two sites declare identical vocabularies for the same concept

The export-field vocabulary and the binding-export vocabulary are **member-for-member
identical**. One is inline on the export-field model; the other is a named alias in
the binding-selector module.

This is the only genuine duplication of the five, and it is the pair a convergence
sweep should take. The named alias is the better home for a binding selector's
type, and the inline copy is the one to retire — but that is a change to the export
schema and does not belong inside a binding migration.

Detail worth carrying: the inline copy is what a search for the vocabulary by
LOCATION finds, and the named alias is what a search by CONCEPT finds. The first
search would have produced a third copy.

### parameter-is-not-a-narrowing | medium | One vocabulary is a peer of the taxonomy rather than a narrowing of it

The PARAMETER vocabulary is **not** a subset. It carries `bracket_table` and
`keyed_bracket_table`, and both are refused by the runtime scalar classifier:

```
bracket_table        -> refused
keyed_bracket_table  -> refused
text                 -> family 'str'
```

So a parameter's `data_type` is not the same axis as every other `data_type` in
the package. Four of the sites name a scalar type; this one also names a table
shape.

On inspection that is not a defect but a correct modelling choice, and an earlier
draft of this finding named it wrongly. The declaring model is
`ParameterDefinition`, not a formula: a registry PARAMETER may legitimately be a
bracket table, because an IRPF rate scale is a table rather than a scalar. So the
vocabulary is a peer of the casilla taxonomy, not a drifted copy of it.

What remains true, and is the finding: one field NAME carries two axes across the
package, and nothing records which surfaces mean which.

It is the same defect class as a revision id asserting a window its selector
closes: one name, two meanings, with the distinction living in whoever last read
the code.

### no-derivation-and-no-containment-check | medium | The hierarchy is maintained by hand and nothing enforces it

None of the four narrower vocabularies is derived from the canonical taxonomy, and
nothing asserts containment. A scalar type added to the taxonomy does not reach
them, and a member added to one of them is not checked against it. The nesting
that holds today holds by hand.

The one member set outside the taxonomy is the parameter pair above. Nothing
would have reported it, which is why it took a manual comparison to find.

## Recommendations

Retire the inline export-field copy in favour of the named binding-selector alias,
as a change owned by the export schema rather than by a binding migration. That is
the only member-identical pair and the only unambiguous convergence.

Leave the casilla, export and manual-input narrowings alone. They encode real
distinctions between surfaces and collapsing them would widen what each accepts.

Derive the narrower vocabularies from the canonical taxonomy, or add a containment
check that fails when one admits a member the taxonomy does not. Either turns a
hand-maintained relationship into an enforced one; the check is the cheaper of the
two and would have surfaced the formula pair on the day it was introduced.

Decide separately whether a parameter's `data_type` should keep that name. It
legitimately spans scalars and table shapes, so it is a different axis from the
other four, and a distinct name would stop a reader assuming otherwise. That is a
naming ruling rather than a mechanical change, and it needs whoever owns the
parameter schema.
