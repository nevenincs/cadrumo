---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:80bd0f7c1f396383a841a9ecfcd8f95d92a9b92383077f8977fb686b788eb179'
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

