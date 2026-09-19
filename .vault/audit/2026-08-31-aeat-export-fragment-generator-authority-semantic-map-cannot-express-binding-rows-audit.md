---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4ac1a35a1a71ed7e165b29ae894cbf9036ec19dc9753dc84aa186595684fd95d'
related: []
---

# `aeat-export-fragment-generator-authority` audit: the generator's input schema is narrower than the registry it generates into

## The finding

The semantic map cannot express a `binding_rows` repeat. The registry can:

| | `repeat` vocabulary |
|---|---|
| registry, `registry/schema_exports.py:645` | `Literal["binding_rows", "projection_rows"] \| None` |
| generator map, `dev/registry/pipeline/_semantic_map.py:300` | `Literal["projection_rows"] \| None` |

A generator whose input vocabulary is a strict subset of its output schema can
emit a structurally WRONG tree while every individual step reports success.

## What it costs, concretely

Modelo 347 is the declaration of operations with third parties. Its AEAT design
says, verbatim: *"1 y tantos registros del tipo 2 como declarados e inmuebles
tenga la declaracion"* -- the Tipo-2 declarado record repeats once per
counterparty. The committed export models exactly that:

    committed   repeat = 'binding_rows'
                kind = 'binding'   binding = 'modelo-347-contraparte-row-nif'
    fresh       (no repeat)
                kind = 'casilla'   casilla_id = 'contraparte.nif'

A single `casilla_id` carries ONE value. So regenerating modelo 347 today
produces a tree that can declare the FIRST counterparty and silently drops every
other one, on both `2011-2024` and `2025-y-siguientes`. That is a silent
under-declaration of exactly the class `no-silent-under-declaration` exists to
prevent, and it would reach a filer through an ordinary, well-intentioned
"regenerate the tree" action.

The shape is not unique to 347. `repeat = "binding_rows"` is live in modelo 131
and in modelo 190's perceptor record, so any modelo with a binding-row repeating
record is in the same position.

## What is NOT wrong

Worth stating, because each was suspected in turn and cleared on evidence:

- **The map was not mis-authored.** The term it needs does not exist in the
  format. No amount of careful authoring could have declared this.
- **The renderer is not at fault.** It faithfully renders what the map says, and
  it never sees the revision's bindings, so it cannot know a record should repeat.
- **The committed tree is CORRECT.** It agrees with the AEAT design and with the
  row bindings the revision declares in
  `347/revisions/2011-2024/bindings/0002-contraparte-clave.toml`
  (`modelo-347-contraparte-row-{nif,nombre,clave,importe,pais-codigo}`, each
  `aggregation = { op = "rows" }` over a `row_field` selector).
- **The gate works.** `test_committed_tree_is_reproducible_and_check_mode_refuses_only_for_its_named_reason`
  reds precisely because committed != fresh. It caught this.

## The dangerous repair

The gate's red says "committed export fragment(s) differ from a fresh render",
which reads like ordinary staleness. The obvious response -- regenerate and
commit -- is the one action that converts a caught defect into a shipped one. Any
fix must make that repair impossible to take by accident.

## Fix, in order

**A. Refuse (small, and the honest guard).** A target whose published export
declares `repeat = "binding_rows"` must not be renderable from a map that cannot
express it. The right home is `check_generated_export_tree`
(`dev/registry/pipeline/_tree_check.py:83`), the only place holding BOTH the
fresh candidate and the published tree; the renderer cannot host it, since its
inputs are the design, map, profiles and defects, with no binding visibility.
The refusal must name the schema gap, not report drift. Prove it bites.

**B. Then the capability.** Widen the map `repeat` to admit `binding_rows`, let
entries name a binding id instead of a `casilla_id`, teach the renderer to
materialise binding rows, and re-author the modelo 347 `2011` and `2025` maps
from the AEAT design plus the revision's bindings -- never from the committed
tree, which is the circularity the renderer admission gate exists to prevent.
Entries to convert sit at `mappings/modelo_347/2011/0003-declarado.toml` lines
68, 96, 124, 151 and 165.

**Widening the `Literal` alone is the worst move available:** it would let a map
claim a repeat the renderer still cannot materialise, turning a loud schema
refusal into a silent one.

## The generalisable lesson

When one component generates content for another, compare their VOCABULARIES, not
just their behaviour. A term present downstream and absent upstream is a silent
truncation waiting for someone to press regenerate, and no test of the generator
against itself can see it -- only a comparison against the schema it targets.

## Severity correction: this is already shipped, and it blocks its own repair

The body above frames the gap as a REGENERATION hazard, true of modelo 347 whose
committed tree is correct. Measured across the corpus, that understates it.

**Modelo 184 is already wrong in committed content.** Its diseño prescribes *"1 y
tantos registros del tipo 2 como claves y subclaves declaradas ... por cada socio,
heredero, comunero o partícipe"*. Its shipped layout's `m184-socio` record carries
`repeat=None`, `binding_record=None` and **0 binding fields of 32**, against 19
declared `modelo-184-member-row-*` bindings. The tree as published can declare ONE
socio. Nobody has to regenerate anything for that to be true.

**And the schema gap blocks the fix.** Modelo 184's export IS a generated tree --
it carries `_generation.provenance.json` and is enrolled in `_GENERATED_TREES` --
so its layout may only change by regenerating from its semantic map. The map
cannot express `binding_rows`. Hand-editing the committed fragment is not an
escape either: the committed tree must equal a fresh render, so an edit reds the
reproducibility gate immediately.

So modelo 184 cannot be repaired at all until the generator can express the
repeat. What reads as an optional capability in the fix ordering above is in fact
the only route to correcting shipped content that under-declares.

Modelo 360 `2010-y-siguientes` sits in the same category on the evidence available
(5 refund-row bindings, 0 consumed across 235 fields), though its diseño extract
does not settle whether the block repeats or uses fixed slots, so the SHAPE of its
repair is open in a way modelo 184's is not.

Enrolled with reasons in
`registry/tests/test_row_bindings_are_consumed.py`, whose companion test reds if a
revision is repaired without its entry being removed.

### Closing the gap is a coordinated migration, not an incremental change

Two attempts established the real cost, and both corrections make the CODE change
smaller while making the SEQUENCING harder.

What the fix is NOT: the renderer does not materialise rows. It emits the record
DEFINITION, and the runtime already honours `repeat == "binding_rows"` in
`registry/export_parse.py`. The map's entry side is already capable too --
`SemanticMapEntry` carries `binding: BindingId | None` and `CasillaFieldKind`
already admits `BINDING`. So the code change is three small edits:

1. `SemanticMapRecord`: widen `repeat`, add `binding_record` and
   `row_field_casilla_ids`.
2. `_export_tree` line ~591: pass both through beside `repeat`.
3. `_provenance_manifest`: add the keys to `_SEMANTIC_MAP_RECORD_KEYS`.

Two constraints found by doing it, each of which refused the change correctly:

**The record must stay hashable.** `_export_tree` proves the joined records
attest exactly the supplied map by comparing two `frozenset`s, so a `Mapping`
field raises `unhashable type: 'dict'` across fifteen tests. The carrier must be
a sorted `tuple[tuple[str, CasillaId], ...]` normalised at the boundary, which
also keeps two maps declaring the same pairs in different order equal. The
renderer converts it back to the mapping the registry schema declares.

**Adding a key forces a normalisation version bump.** `_require_exact_keys`
refuses an unknown key with "review and version the normaliser", by design, and
every committed `_generation.provenance.json` carries
`EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION` and is refused on mismatch. So the
moment the keys are added, EVERY enrolled generated tree is invalid until
regenerated.

**The sequencing hazard, which is the reason this is not incremental.**
Regenerating is exactly what must not happen before the maps are re-authored: a
regeneration today ships modelo 347's truncation and leaves modelo 184's
unrepaired. The only safe order is

> widen schema + normaliser + version -> re-author the modelo 347, 184 and 360
> maps against their disenos -> regenerate every enrolled tree -> verify modelo
> 347 byte-equal to its committed tree, which is a correct oracle for that one.

That is one transaction across the generator, three authored maps and every
enrolled tree. Attempting it piecewise leaves the tree in a state where the
obvious next action ships a silent under-declaration.

### Correction: the schema blocker reported against Option B does not apply

This audit twice recorded that widening the semantic map to carry `binding_rows`
was blocked because `_require_exact_keys` refuses an unknown key, so adding
`binding_record` and `row_field_casilla_ids` would force a bump of the render
normalization version and invalidate every committed provenance manifest. That
costing is wrong, and the work was reverted twice on it.

Two facts settle it. The registry side already carries the shape: `_RECORD_KEYS`
in `_provenance_manifest.py` projects `repeat`, `binding_record` AND
`row_field_casilla_ids` today, so the loader/target schema needs no change at all
-- the gap is only in `_SEMANTIC_MAP_RECORD_KEYS`, the generator's INPUT schema,
which carries `sheet`, `record_identity`, `export_record_id`, `record_type`,
`required`, `repeat` and `discriminator`.

And the convention for adding to that input schema is documented inside
`_normalise_semantic_map_record` itself: "Adding an optional semantic-map field
must not invalidate every existing generated tree whose authored meaning did not
use it. A present rule is attested; absence retains the previous canonical
representation." `discriminator` is already implemented that way -- projected only
when non-None -- and `normalised_loader_semantics` does the same for
`auxiliary_envelope_header`. `semantic_map_digest` hashes no version field, so a
conditionally-projected optional key changes the digest of exactly those maps that
declare it and no others.

So the migration adds optional keys to `_SEMANTIC_MAP_RECORD_KEYS`, projects them
only when declared, and leaves every existing manifest byte-identical. What
remains is real but ordinary: widen the semantic-map model, pass the values
through the renderer, re-author the m347, m184 and m360 maps, and verify m347
renders byte-equal to its committed tree.

The mis-costing came from stopping at the `_require_exact_keys` refusal without
reading how the same function already admits optional additions a few lines below.
A refusal encountered mid-change is a question about the convention, not proof
that no convention exists.

### m347 needs more than row bindings: its tree subdivides a design slot

Option B's row-binding work is necessary for m347 but not sufficient, and the
extra requirement is a different capability.

The committed m347 2011-2024 declarado record carries 28 fields against 27
semantic-map entries. The surplus is a subdivision: AEAT's design ordinal 9 is a
single slot at offset 77 of length 4, and its own prose reads "Campo numérico de
dos posiciones. En el caso de residentes o de no residentes...". The committed
tree renders that one slot as two 2-byte fields -- `f009a` at 77 carrying casilla
`contraparte.provincia-codigo`, and `f009b` at 79 carrying binding
`modelo-347-contraparte-row-pais-codigo` -- which exactly tile the four bytes. The
map holds one entry for ordinal 9, carrying `contraparte.pais-codigo`, so it can
name one of the two halves and not both.

A first reading of the corpus suggested the capability already existed: 101
entry pairs across the mappings share a non-null `(record_identity, ordinal)`, m232
2016 DR23202 ordinals 36-45 among them, and m232 is an enrolled byte-equal tree.
That reading is wrong. Those m232 pairs carry DIFFERENT `source_row` and
`source_cell` values -- 41/A41 against 83/A83 for ordinal 36 -- so they are two
distinct design rows whose printed ordinals repeat across sections, not one slot
divided. No map in the corpus subdivides a single design field.

So the sequence for m347 is: convert the eight ordinal-anchored casilla entries to
bindings (mechanical, the ids are in the committed tree), and then either give the
map a way to express a grounded subdivision of one design slot, or accept that
this committed tree is not reproducible from its own authored map. The second is
the more serious possibility and should be settled before more of the tree is
re-authored: m347 was enrolled late, after publication, precisely so that nothing
compared its committed bytes against a fresh render -- a subdivision no map can
express is what that gap would look like from here.

Do not hand-author an `f009a`/`f009b` pair to close the byte diff. The halves'
widths come from prose about residents and non-residents, not from a declared
geometry, so authoring them into a map would be inventing a slot division the
generator has no evidence for.

### The export-tree lifecycle has no operator surface at all, not just no publish

An earlier note here recorded that `publish_validated_generated_export_tree` has no
caller outside its own module, the pipeline re-export, and
`test_generated_tree_publication.py`. The same is true of the other entry point.
`check_generated_export_tree` is referenced only by the pipeline re-export and two
test modules, `test_generated_export_trees.py` and
`test_m303_generated_envelope_proof.py`. No CLI verb, `__main__`, script or
console entry point drives either one.

So the generated export-tree pipeline -- record designs, semantic maps, render
profiles, provenance manifests, check mode and publish mode -- is reachable only
from pytest. An operator cannot check a committed tree against a fresh render, and
cannot publish a rendered one, without writing Python against the private pipeline
modules. This is not a general property of `dev/`: `dev/registry/aeip/` ships both
`cli.py` and `__main__.py`, and `dev/locales`, `dev/identity` and `dev/docs` each
have their own entry points, so the convention exists and the export pipeline is
the exception.

That reframes the standing publication question. It is not "add a publish verb to
an otherwise complete tool"; it is that the authority which the project relies on
to keep generated registry content honest is exercised only as a test fixture. The
authority itself is sound -- check mode validates a candidate through the real
loader and refuses on unreviewed schema keys at every projection level -- but
nothing outside the test suite can invoke it, which is why two enrolled trees have
sat owed with no way to satisfy them and why a map change that alters output
currently has no path into a committed tree.
