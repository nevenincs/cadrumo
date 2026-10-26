---
tags:
  - '#research'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1b0aa0f96db4f55e3fec26797e4e5cd2ccdb317a96390c7b328de53decc8b303'
related: []
---

# `registry-edition-authoring` research: `registry mechanics audit`

How a casilla value travels from declaration to filed bytes, and which properties of that path
constrain an edition-relative authoring model. This records the mechanism and its load-bearing
properties; it is not a defect list, and several of the thin objects it describes are correct and
deliberately so.

The conclusion: the registry stores identity by containment, which is sound and works nearly
everywhere; it stops holding at four points where a value leaves the tree; and two independent
findings constrain what a delta model may assume about identity.

## Findings

### The mechanism

The registry is a directory tree. A casilla row states its own identifier, data type, whether it
is manual, computed or bound, and pointers to the legal texts grounding it and the wire slots it
feeds. It does not state its modelo or edition; the directory does.

The loader merges the fragments of each section into one edition object per revision folder
inside one modelo definition. Forty-four private validators and four public ones run over the
assembled whole, and only if all pass is the tree published as a validated authority. A filing
coordinate selects one snapshot, the only object holding modelo, edition, year and period at
once.

A value is produced by a binding fetching it from outside the registry, a formula computing it
from other casillas, or a person typing it. Export writes it into a fixed-width slot at a
declared offset, reading width, decimals, sign and padding off the slot declaration rather than
off the value.

### The governing rule, and that it is deliberate

An object carries an identity axis only where its position in the containing structure cannot
supply it. `RelationDefinition` demonstrates both halves: it carries a source modelo for a
cross-modelo edge and deliberately carries no target modelo, because the file already sits in the
target's directory. `ExportLayoutDefinition` states the same reasoning in its own docstring — the
modelo is deliberately not a field because the render path reads it from the selected snapshot.

This is normalisation and it is why 19,821 files do not each repeat the same two facts. Several
thin projections are explicitly defended in code as projections that must not become second
snapshots. Any account treating that thinness as neglect is wrong.

### Where containment stops supplying identity

Four points lose the containing structure.

The flatten in `application/filing/export.py` turns typed draft values into a mapping keyed by
casilla identifier with untyped values; `core/casilla_id.py` documents that the identifier
validates shape only. Binding resolution returns nine parallel maps and no resolved-binding type
exists, so a value's kind is encoded by which map it lands in. The facts layer is keyed on law
rather than form, so nothing states which casilla a fact feeds. The calculation result keeps
modelo and edition as bare strings used only for error messages.

Once in reverse: eight binding selector families restate the modelo or casilla their containing
directory already supplies, under two field spellings, with no validator comparing the declared
value against the containing path.

### Casilla is not the universal identity of a wire value

13,681 of 27,305 resolved export slots carry no casilla, of which 3,038 are money or decimal
amounts. At least 46 are unnumbered by AEAT itself: one modelo 200 record carries three
consecutive 17-byte money slots sharing one data type, one sign, one set of legal references and
the same official source, of which AEAT numbered one.

This constrains identity schemes keyed on casilla. A delta model may key **declarations** on
casilla lineage, but must not assume casilla addresses the wire.

The attribution of a further 2,319 casilla-less amounts to repeated detail rows is inferred and
not proven; no official design was opened for the modelos making up that bulk.

### An official column is read more narrowly than it is written

### An official column is read more narrowly than it is written

The generator derives a slot's required flag by exact string comparison against one value. A
census of the raw source cell across 32 generated editions found 15,566 fields: 14,675 silent,
860 stated in three casings, and 31 stating something an exact comparison cannot carry.

Traced through the shipped derivation records, only **ten** of those 31 are defects, and all ten
are the same one: a qualified requirement on a `header` slot shipping `required = false` —
`Obligatorio PI` six times and `OBLIGATORIO (persona fisica)` four times. A stated requirement is
silently downgraded.

The other twenty-one are not defects, for two different reasons.

Twelve read `OBLIGATORIO.` — the accepted word plus a full stop — and every one resolves to a
`literal` slot shipping `required = true`. A literal's requiredness is forced independently of
the string comparison, so the comparison missing the trailing stop changes nothing about what
ships.

Nine read `En blanco` and resolve to `filler` slots under the `filler-v1` derivation, with
lengths of 1,628, 1,186 and 1,149 bytes across three editions — trailing blank page regions, not
fields carrying a value. A filler renders as spaces and never consults the required flag.

So the collapse is narrower than the census alone suggests: three official states reduce to two,
and the observable harm is ten header slots. The distinguishing raw cell is preserved in the
shipped derivation records and discarded at generation, so representing the third state needs no
new evidence capture — only a field that can hold a string already in the package.

### Neighbouring questions already settled or in flight

Identifier grammars and their per-modelo declaration, the temporal identity model including a
typed axis for non-temporal scheme variants, the field taxonomy of owned, derived and attesting
values, wire type and scale derivation, and the rule that an edition declares whether its values
are derived or transcribed are all decided elsewhere and must be cited rather than restated.

A locale cascade already ships a base, override and exact model keyed on the same lineage field a
delta needs, with an explicit barrier for a repurposed concept. A separate decision explicitly
declined to generalise successor inheritance beyond a single modelo.

### Not investigated

Whether the absent-versus-zero distinction reaches a user-facing handoff was not tested by any
pass. Whether the generator's semantic-map join reads the materialised authority or raw
per-edition files was not established.

## Sources

- `src/cadrumo/domain/calculations/registry/` — loader, authority, schema and validators
- `src/cadrumo/application/filing/export.py` — the flatten to an untyped mapping
- `src/cadrumo/core/casilla_id.py` — identifier shape validation only
- `src/cadrumo/domain/calculations/registry/schema_surfaces.py` — the relation asymmetry
- `src/cadrumo/domain/calculations/registry/schema_exports.py` — the deliberate omission of modelo
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/export/_generation.provenance.json` — the
  shipped derivation records carrying each field's raw source cell
- The requirement-column census across 32 generated editions was measured by the generator lane
  working concurrently in the same worktree; the filler resolution was traced independently here
  from the shipped derivation records.
