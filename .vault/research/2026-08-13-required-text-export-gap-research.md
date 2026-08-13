---
tags:
  - '#research'
  - '#required-text-export-gap'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:762ddb3f7356d158f57a57324d0b0abbeb49c46c6d54f867de1cb7409963346c'
related: []
---

# `required-text-export-gap` research: `required-text fields silently render blank on the fixed-width fichero-BOE export`

The fixed-width codec's numeric path refuses to render a required numeric
casilla with no value (`_render_absent_numeric` raises when `field.required`
and the value is absent). The text path has no equivalent guard: a required
`data_type = "text"` export field with an absent value renders as an empty
string, padded to blanks, and the write proceeds — a structurally valid,
correctly-digested fichero-BOE file carrying a missing mandatory fact. This
is silent under-declaration on the wire, the defect class every rule in this
repository exists to prevent, currently unguarded for text.

This research measures the real population (not the 98 figure taken on
trust), checks the bundled AEAT corpus for whether text carries the same
"no genuine blank" semantics numeric already established, and traces whether
the pre-write completeness gate already covers this population on a
different path. It grounds an ADR; it does not decide the fix and no
behaviour changes as a result of it.

## Findings

### The real population is 98, and it is not one population

A fresh stanza-level scan of every `export_layouts/*.toml` fragment
tree-wide (`data_type = "text"` AND `required = true` on
`[[...records.fields]]` stanzas) reproduces exactly 98, confirming the
relayed figure independently rather than trusting it. It decomposes by
`kind` (`domain.calculations._export_field_kind.CasillaFieldKind`) into four
structurally different populations, only two of which carry genuine
runtime absence risk:

| kind | count | distinct sources | absence risk |
| --- | --- | --- | --- |
| `literal` | 60 | n/a | NONE — `field.literal` is a compile-time TOML string, never absent |
| `casilla` | 20 | 12 casilla ids | REAL — value is `field_values.get(field.casilla_id)`, legitimately `None` when uncalculated or unsupplied |
| `header` | 12 | 2 producer keys | LOW — value is a `FilingProducerSnapshot` attribute (`presenter.tax_id`, `filing.result_disposition`) |
| `draft` | 6 | 2 draft attributes | LOW — value is a `ModeloDraft`/`Period` attribute (`filing_year`, `period_code`) |

Per modelo: `131` contributes 60 (50 literal, 8 header, 2 draft — zero
`casilla`-kind); `145` contributes 6 (2 literal, 4 casilla); `180`
contributes 32 (8 literal, 16 casilla, 4 header, 4 draft). Modelos `100` and
`720` declare `export_layouts` directories but use the `xml_dictionary`
format, not fixed-width — out of this codec's scope entirely, per
`modelo-export-mirrors-official-structure`'s own carve-out that an
`xml_dictionary` export legitimately omits an absent optional element.

`literal`-kind fields need no fix — `render_fixed_width_export_field`
(`src/cadrumo/domain/calculations/registry/_fixed_width_codec.py:187-188`)
substitutes `field.literal` before any absence check runs, so a literal
field's own `required = true` is a documentation marker, never a load-bearing
runtime guard. The genuinely at-risk population is the 20/12 `casilla`-kind
sites; `header`/`draft` are addressed separately below.

### The codec's refusal path is scoped to numeric, by construction

`render_fixed_width_export_field` (`_fixed_width_codec.py:180-196`) branches
on `_is_absent_numeric_slot`, which explicitly filters to
`_NUMERIC_DATA_TYPES = {"integer", "decimal", "money"}`
(`_fixed_width_codec.py:426-438`); `text` never enters that branch. Every
`text`-typed field falls through to `_require_allowed_value` (a no-op unless
`allowed_values` is declared) then `_render_typed_value` →
`_render_text(field, value)` (`_fixed_width_codec.py:387-394`), which returns
`""` unconditionally for `value is None` — no `field.required` check
anywhere on this path. This is confirmed by reading the code, not inferred
from behaviour.

### AEAT's diseño de registro states the same two-tier convention for text as for numeric, and the LAW itself states the default is content

Checked twice, not reasoned out: first in AEAT's own technical PDF extract
(`src/cadrumo/_data/corpus/aeat_official/disenos_registro/`), then
cross-checked against the actual BOE-published consolidated Order text
(`src/cadrumo/_data/corpus/normatives/html/`), per this repository's own
"distrust the bundled corpus on numbers, cross-check the live BOE/AEAT
text" discipline. Both carry the identical rule pair:

```
* Los campos numéricos que no tengan contenido se rellenarán a ceros.
* Los campos alfanuméricos/alfabéticos que no tengan contenido se rellenarán a blancos.
```

(AEAT PDF:
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf.extracted.md:181-182`,
restated at `:547-548`. Same pair, same wording, in the BOE-published Order
itself: `src/cadrumo/_data/corpus/normatives/html/orden-hap-1732-2014.html.extracted.md:149-150`,
restated five more times across the document's several modelo annexes at
`:588-589,809-810,923-924,1275-1276`.)

**The BOE text carries a stronger, more direct statement the AEAT PDF
extract does not quote on its own** — the sentence immediately preceding
the rule pair, at `orden-hap-1732-2014.html.extracted.md:40` (and restated
at `:833`):

> Todos los campos tendrán contenido, **a no ser que se especifique lo
> contrario en la descripción del campo**. Si no lo tuvieran, los campos
> numéricos se rellenarán a ceros y tanto los alfanuméricos como los
> alfabéticos a blancos.

("All fields will carry content, unless otherwise specified in the field's
own description. If they lack content, numeric fields are filled with
zeros and alphanumeric/alphabetic fields with blanks.") This is the actual
legal default, published in the Boletín Oficial del Estado, not a
convenience convention `_render_absent_numeric`'s docstring paraphrased:
content is the baseline for EVERY field, an exception exists ONLY where a
field's own description states one, and the zero/blank fill rule applies
ONLY inside that exception — never as a substitute for a field with no
stated exception and no content. This is the exact mechanism the worked
example below demonstrates field-by-field (`NIF DEL REPRESENTANTE LEGAL`
states its own exception explicitly; `NIF DEL PERCEPTOR` does not), now
shown to be the general rule the field-level examples instantiate, not an
inference from them.

The text half is not a silent gap in AEAT's own spec — it is stated,
general, and unconditional in exactly the same place, in the same
document, as the numeric rule `_render_absent_numeric`'s docstring already
cites. Rendering blanks for a REQUIRED field's absence — one whose own
description states no exception — produces a byte-valid file that
contradicts this baseline rule directly, not a legitimate use of the fill
convention. The same defect the numeric fix already named has identical
legal grounding for the text half, and that grounding is now the stronger
of the two claims: a direct legal quotation, not an inference from a
worked example.

### A worked example: Modelo 145's own "Uso" column distinguishes unconditionally-required from conditionally-blank

Modelo 145's diseño uses an explicit `Uso` column
(`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_145/files/dr145v20.pdf.extracted.md:7-14`):

```
NºPosic. Lon Tipo Descripción         Validación Contenido  Uso
3        11  9   An 1. NIF                                 obligatorio
4        20  40  An 1. Primer apellido                      obligatorio
5        60  40  An 1. Segundo apellido                      obligatorio
6        100 40  An 1. Nombre                                obligatorio
7        140 4   Num 1. Año de nacimiento                     obligatorio
8        144 1   An 1. Situación familiar. [1][2][3]     "1" o "2" o "3" o blanco
```

Fields 3-7 (`perceptor.nif`, `.primer-apellido`, `.segundo-apellido`,
`.nombre`, `.anio-nacimiento`) are `obligatorio` with NO stated content
alternative. Field 8 is the direct contrast: its `Uso` cell states the
blank is one of the field's own VALID values ("o blanco"). AEAT's own
document distinguishes the two cases in the same column; our registry's
`required = true` on fields 3-6 (all `casilla`-kind, `data_type = "text"`)
matches AEAT's `obligatorio` classification exactly, confirmed at the
casilla-schema layer too — `perceptor.nif`'s own `CasillaDefinition`
declares `required = true`
(`src/cadrumo/_data/registry/aeat/modelos/145/revisions/2012-01-31-y-siguientes/casillas/ccomunicacion.pagina-complementaria__cacuse-recibo.tipo-firma.toml`,
stanza `id = "perceptor.nif"`). Field 7 (`año de nacimiento`) is `Num`
(numeric) and is ALREADY covered by the existing numeric refusal fix, since
its casilla type differs from the four text fields beside it.

### Modelo 180's diseño distinguishes unconditional-required from conditional-blank the same way, in prose rather than a column

Modelo 180's diseño has no `Uso` column; the same distinction is stated in
each field's own description
(`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf.extracted.md`):
`NIF DEL PERCEPTOR` (position 18-26, `:215-228`) is described
unconditionally — "si el declarado dispone de NIF... se consignará" (how to
fill it, not whether to). The immediately following field, `NIF DEL
REPRESENTANTE LEGAL` (27-35, `:246-253`), is explicitly conditional and
states its OWN blank rule: "si el declarado es menor de 14 años se
consignará... **en cualquier otro caso el contenido de este campo se
rellenará a espacios**." AEAT states the conditional-blank exception
per-field when it applies and is silent when it does not — `NIF DEL
PERCEPTOR` carries no such exception, matching `perc.nif`'s registry
`required = true`.

### Adjacent, unverified finding: two of the 12 `casilla`-kind fields may carry the wrong `data_type`

Modelo 180's diseño declares position 76-77 (`CÓDIGO PROVINCIA`, our
`perc.provincia`) and position 78 (`MODALIDAD`, our `perc.modalidad`) as
`Numérico`
(`...noviembre-251-kb-pdf.pdf.extracted.md:272,306`), while both casillas'
export fields declare `data_type = "text"` in our registry. If AEAT
genuinely treats these as numeric-typed positions, they are simultaneously
mistyped (should route through the numeric branch, already refusal-guarded)
AND part of the 20-site text population this research measured. Not
verified further — named so it is not lost, and because it demonstrates the
same "declared shape does not match AEAT's own classification" risk this
whole research is about, one layer up from the required/absent question.
Needs its own per-field corpus check across all 20 `casilla`-kind sites
before any fix lands, not assumed from these two.

### The completeness gate does not cover this population, and the gap is scope, not ordering

`export_draft` (`src/cadrumo/application/filing/_export.py:546-663`) calls
`_render_export_layout` (the codec entry point) at line 611, BEFORE
`assert_export_mirrors_manifest` at line 633-642 — so even if the manifest
covered this population, reordering would not be the fix; the render call
happens first regardless.

More fundamentally, `assert_export_mirrors_manifest`'s required set is
"every casilla that is a calculation RESULT (declares a formula) OR is
schema-required, that the completeness manifest LISTS"
(`src/cadrumo/application/filing/_export_parity.py:14-17`) — an AND across
three conditions, and the manifest's own scope is documented as the
modelo's "calculation closure": formula targets, formula-referenced
casillas, formula/binding endpoints, verification-expectation operands,
explicitly excluding "pure accounting-statement data-entry fields that feed
no calculation" (`CasillaCompletenessManifestEntry` docstring,
`src/cadrumo/domain/calculations/registry/_schema_surfaces.py:460-473`).

Confirmed empirically, not just from the docstring: Modelo 180's actual
completeness manifest
(`src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/completeness_manifest/0001-completeness_manifest.toml`)
lists exactly three casillas — `decl.total-perceptores`, `decl.base-total`,
`decl.retenciones-total` — the declarante-level summary figures, and NONE
of the eight per-perceptor identity fields. Modelo 145 has no
`completeness_manifest` fragment for its revision at all, so
`export_draft`'s own guard (`if subview.completeness_manifest is not None:
...`) skips the gate call entirely for that modelo — confirmed by directory
listing, no `completeness_manifest/` directory exists under
`145/revisions/2012-01-31-y-siguientes/`.

**This is not an ordering defect.** The manifest was built to police
calculation integrity, not identity-field presence, and it does that job
correctly within its stated scope. A perceptor's NIF feeds no formula, so
by the manifest's own design it was never going to be listed — closing the
ordering gap would not close this one.

### `header`/`draft`-kind sites are low-risk but structurally reachable through the same guard

The two `header`-kind sources (`presenter.tax_id`, `filing.result_disposition`)
resolve through `_filing_producer_values`
(`src/cadrumo/application/filing/_export.py:362-372`) as
`str(snapshot.presenter.tax_id)` and
`snapshot.elections.result_disposition.value` — a `str()` coercion of a
presumably-non-optional attribute and a `StrEnum.value` access, neither of
which can yield `None` without an upstream typing gap this research did not
trace further. The two `draft`-kind sources (`filing_year`, `period_code`)
are `ModeloDraft`/`Period` attributes, similarly expected non-optional. Not
zero-risk by proof, but far lower confidence of a live defect than the
`casilla`-kind population, and any fix to the text-rendering path would
cover them for free — the same code path renders every kind once `kind not
in {"literal", "filler"}`.

## Proposal shape (not a decision)

The evidence favors mirroring the numeric fix's own shape rather than
extending the completeness manifest's scope, and the cost difference between
the two is the material question an ADR must settle:

- **Narrow fix — mirror `_render_absent_numeric`.** Add the equivalent
  guard to the text-rendering path: a required `text` field with an absent
  value raises `RegistryValidationError` naming the field, exactly
  parallel to `_render_absent_numeric`'s existing shape
  (`_fixed_width_codec.py:441-461`). Estimated cost: a small, localised
  change to `_fixed_width_codec.py` (one new absence-check function or a
  guard inside `_render_text`), one new test mirroring
  `test_required_numeric_slot_absent_still_refuses` for text, and a
  per-field corpus verification pass across all 12 distinct `casilla`-kind
  ids (plus the 2 `header` and 2 `draft` sources) before landing, per this
  repository's own grounding discipline — every regulatory behaviour this
  codec encodes is corpus-cited, and this fix would be too. Risk: LOW — a
  currently-silent path becomes a refusal, the same direction and shape
  already accepted for numeric, on a codec covering only 3 modelos today
  (`131`, `145`, `180`).
- **Broad fix — widen the completeness manifest's scope.** Extend the
  manifest (or a sibling gate) to also enumerate schema-required
  identity/data-entry casillas, so the pre-write aggregate-error gate
  catches this population too, rather than the codec refusing on the first
  missing field it encounters. Estimated cost: materially larger — a schema
  and build-validator change, and an authoring decision for every modelo's
  `completeness_manifest` TOML about which non-calculation casillas join
  it, which the manifest's own docstring currently keeps out by design.
  Risk of conflating two conceptually different "required" axes
  (calculation-integrity vs. data-completeness) the manifest deliberately
  separates today.

Not addressed by either option, and worth its own line in the ADR: the
`perc.provincia`/`perc.modalidad` data-type mismatch finding above, and
whether the same text-absence guard should also apply to the `xml_dictionary`
export path for modelos `100`/`720` — `modelo-export-mirrors-official-structure`
states that format's absence semantics are already legitimate ("omits an
absent casilla as a legitimately absent optional element"), but that rule
was written before this research and was not re-verified against a
`required = true` case in the `xml_dictionary` codec specifically.

## Sources

- `src/cadrumo/domain/calculations/registry/_fixed_width_codec.py:180-196,387-394,426-461`
- `src/cadrumo/domain/calculations/registry/tests/test_fixed_width_codec.py:421` (the numeric precedent this research mirrors)
- `src/cadrumo/domain/calculations/_export_field_kind.py:16-43`
- `src/cadrumo/application/filing/_export.py:362-372,546-663`
- `src/cadrumo/application/filing/_export_parity.py:14-17`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:460-473,811-834`
- `src/cadrumo/_data/registry/aeat/modelos/145/revisions/2012-01-31-y-siguientes/export_layouts/0001-export_layouts.toml`
- `src/cadrumo/_data/registry/aeat/modelos/145/revisions/2012-01-31-y-siguientes/casillas/ccomunicacion.pagina-complementaria__cacuse-recibo.tipo-firma.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/export_layouts/0001-0002-modelo-180-perceptor.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/completeness_manifest/0001-completeness_manifest.toml`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_145/files/dr145v20.pdf.extracted.md:7-14`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-251-kb-pdf.pdf.extracted.md:181-182,215-253,272,306,547-548`
- `src/cadrumo/_data/corpus/normatives/html/orden-hap-1732-2014.html.extracted.md:40,149-150,588-589,809-810,833,923-924,1275-1276` (BOE-published Order text, cross-checked against the AEAT PDF extract above per the numeric-value distrust discipline)
