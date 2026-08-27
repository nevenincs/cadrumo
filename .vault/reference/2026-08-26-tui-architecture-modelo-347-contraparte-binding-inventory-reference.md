---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:4b879174c7660c65c7de6db8ebf46dbe5d013ecf8f4f7aedf504d63f16998eb5'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` reference: `modelo 347 contraparte binding inventory`

## Summary

Reading-only inventory for the deferred pieces of the modelo 347 contraparte
per-row binding family (S294 pieces 1, 3, 4). Every provision below is an
UNVERIFIED CANDIDATE, not a citation: none has been checked as a distinctive
`required_text` match, and none should be copied into a binding's
`legal_refs`/`source_citations` without that cross-check.

### Calc-grade revisions (checked via the loaded authority, not a directory listing)

`bundled_authority().modelo("347").revisions` shows both revisions with real
export layouts and casillas: `2011-2024` (39 casillas, closed historical
window, `valid_to = 2024-12-31`) and `2025-y-siguientes` (44 casillas, open,
`valid_to = None`). Both currently carry only 2 bindings each -- the thin
declarant-summary placeholder found earlier, zero contraparte row bindings.
The deferred registry-authoring work does NOT halve: both revisions need the
same buildout. A properly-paced pass should prioritize `2025-y-siguientes`
(the open filing window) and treat `2011-2024` as follow-on scope for
late/amended historical filings, stated explicitly rather than silently
dropped.

### Source read

`corpus/aeat_official/disenos_registro/modelo_347/files/01-347-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1431-2025-de-3-de-diciembre-332-kb.pdf.extracted.md`
(current diseño de registro, orden HAC/1431/2025). "TIPO DE REGISTRO 2:
REGISTRO DE DECLARADO" (the contraparte record) starts at line 222.

### Fields the per-row binding family needs, with diseño positions

- **NIF DEL DECLARADO** (positions 18-26, line 239): the counterparty's tax
  id. Text distinguishes resident-NIF, non-resident-with-NIF, and
  no-NIF-with-country-code (`XX` = ISO country code per Orden EHA/3496/2011
  Anexo II) shapes -- the existing `Modelo347ContraparteRow.nif` field may
  need this three-shape handling, not confirmed against the current model.
- **CLAVE OPERACIÓN** (position 82, line 336): single-letter code, closed set
  read directly from the diseño text: `A` adquisiciones >3.005,06 EUR, `B`
  entregas >3.005,06 EUR, `C` cobros por cuenta de terceros >300,51 EUR
  (different threshold from the general one), `D` adquisiciones al margen de
  actividad empresarial by entidades públicas/partidos/sindicatos/etc., `E`
  subvenciones/auxilios/ayudas by administraciones públicas (exclusive to
  that filer type), `F` ventas agencia viaje, `G` compras agencia de viajes.
  `Modelo347ContraparteRow.clave_operacion`'s existing `_M347_CLAVE_OPERACION`
  type declares `Literal["A".."I"]` (nine members) -- A-G confirmed present
  and matching in this pass; H and I were not located in the section read
  and remain unconfirmed, not contradicted.
- **IMPORTE ANUAL DE LAS OPERACIONES** (positions 83-98, line 372): signed
  (position 83 sign flag) + 15-digit unsigned amount (84-98). Explicitly
  EXCLUDES amounts covered by "el artículo 34.1 del Reglamento General de
  las actuaciones y los procedimientos de gestión e inspección tributaria"
  (RD 1065/2007 art. 34.1) -- a candidate exclusion provision worth checking
  against RD 1065/2007's real text before treating any operation as
  M347-declarable in an automated resolver.
- **Quarterly breakdown fields** (positions 136-247, six paired
  sign+amount blocks: 1T/2T/3T/4T operaciones plus percibido-por-transmisiones
  variants) -- these map to `Modelo347ContraparteRow.importe_Q1..Q4`, but the
  diseño's quarterly fields are paired with separate "PERCIBIDO POR
  TRANSMISIONES" sub-fields the current row model does not appear to carry;
  not confirmed whether that's a legitimate omission (inmueble-only) or a
  gap.
- Representante legal NIF and nombre casillas already exist
  (`contraparte.representante-legal-nif`, seen in the loaded snapshot) but
  their diseño-position mapping was not read in this pass.

### Candidate provisions with locators (UNVERIFIED, not cross-checked)

- `orden-hac-1431-2025` (the current orden modifying M347's diseño de
  registro for 2025 y siguientes) -- likely the correct primary `source_ref`
  for any 2025-y-siguientes contraparte binding, mirroring how the existing
  thin bindings already cite `orden-eha-3012-2008`/`rd-1065-2007:art-31`/
  `ley-58-2003:art-93` at the revision level.
- `rd-1065-2007:art-34-1` -- candidate for the IMPORTE ANUAL exclusion
  language quoted above; NOT yet checked against the bundled consolidated
  RD 1065/2007 text for a distinctive matching phrase.
- The revision-level `legal_refs` already declared
  (`orden-eha-3012-2008:art-1`, `orden-eha-3012-2008:art-10`,
  `rd-1065-2007:art-31`, `ley-58-2003:art-93`) are plausible per-binding
  candidates too, since the existing thin declarant-summary bindings already
  cite them -- but that is precedent, not verification for a NEW binding's
  own `required_text`.

### What is explicitly NOT done here

No `required_text` phrase has been authored or verified against any corpus
file. No TOML binding has been written. No claim is made that any candidate
provision above is the correct or complete legal grounding -- a properly-paced
pass must open the actual bundled corpus files named here, confirm each
candidate against the CURRENT consolidated text (never the excerpt above),
and only then author `legal_refs`/`source_citations`.

### Open domain question: M347 has no ledger fail-closed guard, and no category grouping to build one from

`_m349_ledger_guard.py` (`src/cadrumo/application/modelo/_m349_ledger_guard.py`)
refuses M349 calculation when raw intracom ledger transactions exist but no
declarable operador row does, so a taxpayer with real intracom activity
cannot silently file a zero-row declaration. Its trigger condition is
`_M349_INTRACOM_LEDGER_CATEGORIES`, a closed three-member `IvaCategory`
set declared in that same file: `INTRA_COMMUNITY_SUPPLY`,
`INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`, `INTRA_COMMUNITY_TRIANGULATION`.

That pattern does not transfer to M347. Searched `domain/iva` for an
equivalent grouping (any M347-specific `IvaCategory` set, threshold-adjacent
constant, or classification helper) -- none exists. This is a real gap, not
an unbuilt afternoon of typing: M347's threshold applies across third-party
operations generally (the CLAVE OPERACIÓN closed set above spans several
distinct operation kinds -- adquisiciones, entregas, cobros por cuenta de
terceros, subvenciones públicas, agencia de viajes -- each per the diseño
text above), not one narrow reverse-charge classification the way M349's
intracom guard is. Picking a trigger set without resolving this is deciding,
by fiat, which ledger classifications legitimately should have produced a
contraparte row -- the same class of judgement the corpus-grounding rule
protects against, only smaller in scope. Per `no-silent-under-declaration`:
a guard built on a guessed trigger set either false-fires until operators
learn to ignore it, or silently fails to fire on the population it exists to
catch -- both outcomes defeat the guard's purpose.

**Open question, not a recommendation:** what IS the correct trigger
population for M347's contraparte threshold -- is it a registry-declared
fact (a per-binding selector predicate already scoped to M347-relevant
`IvaCategory` members, once the row-producer binding family from the
sections above exists), or a new `domain/iva` classification analogous to
M349's? Locators for whoever picks this up: `_m349_ledger_guard.py`
(the pattern that does not transfer), `domain/iva` (searched, empty of an
M347 answer), and the CLAVE OPERACIÓN field inventory above (the candidate
operation-kind boundary a grouping would need to cover, itself still
unverified against RD 1065/2007's consolidated text).

## Open finding: the row model cannot represent per-quarter transmisiones amounts

Confirmed against the tree while scoping this inventory:
`Modelo347ContraparteRow` (`src/cadrumo/domain/modelos/_row_models.py:620-623`)
declares only `importe_Q1..Q4`, so the diseño's paired "PERCIBIDO POR
TRANSMISIONES" sub-fields have no representation in the row shape at all.

The full finding, its consequence and the open legitimacy question live in
`2026-08-26-tui-architecture-modelo-347-contraparte-quarterly-transmisiones-representation-gap-audit`.
It is recorded there rather than here because it is a different class of problem
from this document's subject: the binding family is unbuilt capability, visible
and tracked, while an amount the model cannot represent is invisible from every
operator-facing surface.

## CLAVE OPERACIÓN classification, grounded against RD 1065/2007 and RD 1619/2012

Cross-checked the diseño de registro's CLAVE OPERACIÓN table against three
bundled diseño files spanning different orden years (`01-347-...orden-hac-
1431-2025...`, `04-347-...orden-eha-3378-2011...`, and the 2010 diseño) and
against the bundled consolidated RD 1065/2007 and RD 1619/2012 texts. This
answers both the binding-family classification question and the ledger
fail-closed guard's open trigger-population question from the same
evidence, as instructed.

**H and I do not exist in any M347 diseño de registro checked.** The
CLAVE OPERACIÓN table in the current (`orden-hac-1431-2025`, 2025-y-
siguientes) diseño runs A through G only (position 82, single alphabetic
character); the 2011 diseño (`orden-eha-3378-2011`) and the 2010 diseño show
the same A-G set. `Modelo347ContraparteRow`'s `_M347_CLAVE_OPERACION =
Literal["A", "B", "C", "D", "E", "F", "G", "H", "I"]`
(`src/cadrumo/domain/modelos/_row_models.py:595`) claims two members, H and
I, that no checked diseño declares. This is now a confirmed finding, not an
unconfirmed gap: the type over-declares its own domain by two members.

| Clave | Diseño description (2025-y-siguientes) | Observable fact / grounding |
| --- | --- | --- |
| A | Adquisiciones de bienes y servicios >3.005,06 EUR | Acquisitions side of the general threshold. RD 1065/2007 art. 31.1 (threshold establishment) + art. 33.1 ("se computarán de forma separada las entregas y las adquisiciones"). |
| B | Entregas de bienes y prestaciones de servicios >3.005,06 EUR | Supply/delivery side of the same general threshold, same arts. as A. |
| C | Cobros por cuenta de terceros >300,51 EUR | A DIFFERENT threshold (300,51, not 3.005,06). RD 1065/2007 art. 31.3 ("las sociedades, asociaciones, colegios profesionales u otras entidades que... realicen la de cobro, por cuenta de sus socios, asociados o colegiados, de honorarios profesionales o de derechos derivados de la propiedad intelectual... u otros, estarán obligados a incluir estos rendimientos") + art. 33.4 (the 300,51 EUR figure, explicitly cross-referencing "los obligados tributarios a que se refiere el artículo 31.3"). |
| D | Adquisiciones al margen de actividad empresarial/profesional by entidades públicas, partidos, sindicatos, asociaciones empresariales, Ley 49/1960 (propiedad horizontal) entities, art. 20.Tres Ley 37/1992 social entities, >3.005,06 EUR | RD 1065/2007 art. 33.3, near-verbatim match down to the >3.005,06 EUR figure and the same enumerated filer types. |
| E | Subvenciones, auxilios y ayudas satisfechos por Administraciones Públicas | RD 1065/2007 art. 31.2 ("Las entidades integradas en las distintas Administraciones públicas deberán incluir... las subvenciones, auxilios o ayudas que concedan") + art. 33.3 final paragraph. **Legal evolution found, not a contradiction**: the 2011 diseño requires this only ">3.005,06 euros", the current 2025 diseño states "cualquiera que sea su importe" (no threshold) -- both diseños are internally consistent with their own orden year; neither is wrong, the underlying rule changed. Any binding grounding this clave for the 2025-y-siguientes revision must NOT reuse the 2011 threshold language. |
| F | Ventas agencia de viajes (mediación en nombre y por cuenta ajena) | RD 1619/2012 (facturación) disposición adicional cuarta, verified present in the bundled text with the exact service-type enumeration (transporte de viajeros, hostelería, restauración, etc.) the diseño's cross-reference names. NOT RD 1065/2007 -- a genuinely different governing regulation, correctly so per the diseño's own cross-reference. The 2011 diseño cites the OLDER RD 1496/2003 for the same clave; not checked in the bundled corpus in this pass. |
| G | Compras agencia de viajes (transporte de viajeros y equipajes por vía aérea) | Same disposición adicional cuarta, apartado 3 (the diseño's own text names "apartado 3 de la citada disposición adicional cuarta" for this clave specifically); RD 1619/2012 as above. |
| H, I | Not found in any checked diseño | **Unconfirmed as real claves.** Either an older or newer orden year not in the bundled corpus declares them (not ruled out -- only three of the corpus's several M347 diseño files were checked for this table), or the row model's type is simply wrong and should be `Literal["A".."G"]`. This is now the actionable question for whoever resolves the type: check the REMAINING bundled M347 diseño files (`02-347-...2008-2009...`, `05-347-...` through however many exist) for H/I before narrowing the type, since only three of the available files were read in this pass. |

### This also answers the ledger guard's open trigger-population question

The classification above IS the trigger population the deferred M347
ledger fail-closed guard needs, and it resolves why no `domain/iva`
grouping could mirror M349's: M347's clave set is not one `IvaCategory`
classification the way M349's intracom set is. Claves A/B key on the
general >3.005,06 threshold (any IVA-relevant supply/acquisition), C keys
on a completely different professional-fees-collection fact with its own
300,51 threshold, D/E key on the FILER's own type (entidades públicas, etc.)
rather than on any transaction classification, and F/G key on a mediación
fact under an entirely different regulation (RD 1619/2012) that has nothing
to do with IVA category at all. A single `domain/iva` `IvaCategory` grouping
cannot express this population -- the guard's trigger condition would need
to be built from a COMBINATION of transaction facts (amount vs. threshold,
filer type, mediación-agency-viajes flag) that do not currently exist as
one classification anywhere in this codebase. Whoever builds the binding
family answers this by construction: each binding's selector already has to
express which fact identifies each clave, and the guard's trigger condition
is then "any of those facts present with no corresponding contraparte row"
-- the same shape as M349's guard, built from the SAME facts the bindings
already need, not invented separately.

### What is still not done

RD 1065/2007 art. 33/34's FULL text for the "declaración desglosada
trimestralmente" language (the quarterly split itself, distinct from the
transmisiones sub-field already grounded above) was read but not
independently cross-checked against the diseño's exact quarterly field
positions field-by-field. The remaining M347 diseño files in the bundled
corpus (years between 2010 and 2025 not yet opened) were not checked for
H/I or for any clave added/removed across intervening orden years. No
binding TOML has been written; no `_InvoiceGrouping` extension has been
made to `invoice_bindings.py`.
