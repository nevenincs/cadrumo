---
tags:
  - '#research'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:31830889ee88038171cb2d07742481f88a7ce8efd59717bc5cc08c5bdd0eb799'
related:
  - "[[2026-08-07-invoice-canonical-structure-iva-treatment-axis-adr]]"
---
# `invoice-canonical-structure` research: `Measured consumer set of the invoice IVA category, and the prorrata denominator trace`

Two questions, both answered by measurement rather than reading. First: does the
invoice-level IVA category conflate an operation-treatment axis with a rate-tier axis,
and would separating them dissolve the multi-rate problem? Second: does dropping
zero-cuota invoice lines from the Modelo 303 screen distort the prorrata deductible
percentage? The first grounds the sibling ADR of the same stem; the second was raised
there as an unquantified consequence and is settled here.

Every numeric claim below was produced by a read-only probe run against HEAD through the
production writer and the production helpers, not by reading the code and reasoning about
what it would do.

## Findings

### The complete production consumer set of the invoice IVA category is three, and all three are treatment-only

Enumerated by sweeping every non-test read of the field and classifying each by whether
it could distinguish one domestic rate tier from another.

- The decomposition contract reads only the Axis-A presence columns.
- The Modelo 349 clave derivation is keyed on a table holding no domestic entry at all,
  so a domestic invoice returns no clave regardless of tier.
- The retencion routing reads only the retencion role.

The category-to-tier reverse accessor `rate_kind_for_domestic_category` exists and is
exported, and has ZERO production call sites. Nothing anywhere reads a tier back off a
category.

### The three domestic rated members are measured indistinguishable at invoice level

A two-line invoice (1000.00 at 21 percent, 500.00 at 10 percent) was built through the
production writer and decomposed under each candidate category:

```
category=domestic_general  grounded=True  defects=[]  base=1500.00 cuota=260.00 total=1760.00 cash=1760.00
category=domestic_reduced  grounded=True  defects=[]  base=1500.00 cuota=260.00 total=1760.00 cash=1760.00
category=domestic_exempt   grounded=False defects=['cuota_contradicts_category']
category=<none>            grounded=False defects=['iva_treatment_undeclared']
```

The two rated members produce identical output; their Axis-A rows are identical, both
being emitted by one shared factory that varies only the tipo article cited. A wrong
TREATMENT is caught by an existing defect; a wrong TIER is caught by nothing. That
asymmetry is what the axis separation predicts.

### Modelo 303 derives the tier from the line, never from the invoice

The invoice-to-observation loop iterates the invoice's lines and classifies each from the
line's own rate slot. Measured on the same two-line invoice:

```
line0 rate=RATE_21 -> category=domestic_general  tier=general  applied=0.21 base=1000.00 cuota=210.00
line1 rate=RATE_10 -> category=domestic_reduced  tier=reduced  applied=0.1  base=500.00  cuota=50.00
```

The registry selectors that name `domestic_general` match this line-derived observation,
not the invoice field. A two-rate invoice therefore already aggregates correctly per tier
whatever its invoice-level category says.

### The writer already accepts multiple lines; only the category declines

Measured: the production writer accepted both lines and summed the totals
(`base_total=1500.00 iva_total=260.00 grand=1760.00`). An earlier sweep recorded that no
operator path could produce a two-line invoice; that is stale at HEAD. The multi-rate gap
is now confined to the category resolution alone.

### The axes are separable at the invoice, but the enum cannot be split

The tier-named members stay load-bearing on two other surfaces. A ledger transaction has
no lines, so its category is the only place its tier can ride; and the IVA ledger
observation's category is the token registry selectors match as strings. A split into a
treatment enum and a tier enum would break both. The finding is that on the INVOICE
surface the category functions as treatment only, not that the enum conflates two axes
and should be divided.

### Spanish law refutes the stronger premise that treatment is invoice-level single-valued

RD 1619/2012 art. 6.1.g requires the invoice to state "el tipo impositivo o tipos
impositivos, en su caso, aplicados a las operaciones" - plural tipos on one factura,
which is the legal form of "the tier belongs to the operation, not the document". That
supports the rate half of the hypothesis.

Art. 6.2 of the same article refutes the treatment half. It requires the base to be
stated separately per operation in three cases, only ONE of which is about rates:
operations exempt from IVA mixed with operations that are not (6.2.a); operations where
the destinatario is the sujeto pasivo mixed with operations where they are not (6.2.b);
and operations subject to different tipos (6.2.c). Spanish invoicing law explicitly
contemplates a single factura mixing exempt with rated supply, and reverse-charge with
ordinary supply. A single invoice-level treatment field cannot describe either. Verified
against the bundled corpus file `rd-1619-2012-art-6.html`.

### The prorrata percentage is operator-declared; the ledger rollup is only a detector

The consequence flagged in the sibling ADR - that dropping exempt observations shrinks the
prorrata denominator and inflates the deductible percentage - is REFUTED. Traced end to
end:

- `iva.prorrata-volumen-con-derecho` and `iva.prorrata-volumen-total` are both declared
  `input_kind = "manual"` in the Modelo 303 registry, on both the 2009 and 2023 revisions,
  and NO binding populates either. The only binding naming them reads them as source
  casillas.
- `iva.prorrata-porcentaje` is `input_kind = "computed"` from those two manual inputs.
- The ledger observation rollup feeds neither. When it disagrees with the declared
  casillas it emits a diagnostic whose own message states that the declared casillas
  retain the authority.

So the deductible percentage never came from observations, and losing observations could
not have inflated it. The money consequence hypothesised does not exist.

### What the skip actually broke was the detector, in the under-declaration direction

The rollup classifies repercutido observations into a con-derecho and a sin-derecho
bucket, and compares the result against the operator's declared volumes. Before the
zero-cuota lines were restored, every exempt and every zero-rated line was absent from
BOTH buckets, so the comparison ran over the rated operations only.

The consequence that matters is a false negative. An operator who under-declared their
exempt volume would have matched an equally understated ledger rollup, and the detector
would have stayed silent. Under-declared exempt volume shrinks the denominator, raises the
percentage, and over-deducts - so the safety net was blind in exactly the direction that
costs money. Restoring the lines closes that hole.

### New and live: restoring the lines routes an exempt-slot IC supply to the WRONG prorrata bucket

Raised by the same root cause the casilla 59/60 correction identified - the observation is
built from the rate slot, not the invoice category - but with a consequence that only
became reachable once the zero-cuota lines started flowing. Measured:

```
slot=EXEMPT -> category=domestic_exempt side=sin_derecho
slot=RATE_0 -> category=domestic_zero   side=con_derecho
slot=RATE_21-> category=domestic_general side=con_derecho

if the observation carried the INVOICE's own category instead:
category=intra_community_supply          side=con_derecho
category=export_third_country_zero_rated side=con_derecho
category=domestic_exempt                 side=sin_derecho
```

An intra-community supply or an export recorded on the EXEMPT slot now produces a
`domestic_exempt` observation and lands in the SIN-DERECHO bucket, while the codebase's
own con-derecho set classifies both of those categories as CON-DERECHO. The same
operation recorded on the RATE_0 slot lands con-derecho, so the bucket depends on which
slot the operator or the extractor picked rather than on what the operation is.

Scope and severity, stated precisely: this moves the ROLLUP, which is a detector, not the
declared percentage, which is manual. So it degrades the detector rather than mis-filing a
figure - it makes the comparison diverge for a taxpayer whose books are correct. It is
not an under-declaration. It is nevertheless the same fix as casilla 59/60: construct the
observation from the invoice's own category.

### CORPUS REFRESH TRIGGER: the bundled art. 94 excerpt is truncated, and its evidence gate cannot detect that

A standalone finding, not a footnote to the prorrata work. A live deduction-rights
classification rests on a bundled excerpt that cannot ground it, and the gate that is
supposed to catch exactly this passes.

**The excerpt stops mid-article.** `corpus/normatives/html/ley-37-1992-art-94.html`
carries the article heading, the apartado Uno chapeau, and points 1 through 5. Its final
bytes are, verbatim:

```
<p class="parrafo_2">5.º Los servicios prestados por agencias de viajes que estén exentos
del Impuesto en virtud de lo establecido en el artículo 143 de esta Ley.</p>
```

The file ends there - no further point, no subsequent apartado, and no closing markup.
That is a truncated fetch, not a curated excerpt that deliberately stopped.

**What is missing is the operative clause.** Point 1.º as bundled reads flatly "Las
entregas de bienes y prestaciones de servicios sujetas y no exentas", with no letras. The
exempt-with-credit provision - the one that decides whether an exportación or an entrega
intracomunitaria exenta originates the right to deduct - is absent. This research does NOT
state what the consolidated text says in its place: authoring the missing clause from
memory is the failure the grounding rule exists to prevent, and a wrong art. 94 would
mis-classify deduction rights rather than merely fail to ground them. The text must come
from a corpus refresh against BOE.

**The evidence gate cannot catch it.** The registry legal entry
`[legal."ley-37-1992:art-94"]` declares exactly one `required_text`:

```
required_text = ["operaciones cuya realización origina el derecho a la deducción"]
```

That string is the article TITLE, and the title survives truncation - it is the first line
of the bundled file. So the cross-check confirms that something is present, never that the
binding provision is present, and deleting the entire article body would not red the gate.
The entry is nevertheless stamped `review_status = "reviewed"`, `reviewed_by = "operator"`,
`reviewed_at = 2026-05-21`, which makes it read as verified.

**Reach.** The entry is not dormant: `ley-37-1992:art-94` is cited across the Modelo 390
formulas, constructs, bindings, casillas, completeness manifest and export layouts, and the
codebase's own con-derecho set - the classification this article governs - is what routes
volume between the prorrata numerator and denominator.

**It is a class, not an instance.** The sweep this research flagged as unrun was run by the
team lead; the numbers below are their measurement, and two rows were spot-checked
independently here before being recorded.

Of 599 legal entries carrying both a `required_text` and a readable corpus file, 67 have
every required phrase falling inside the excerpt's opening heading. That raw figure
over-reports: some are genuine one-line dispositions where the heading IS the provision
(`orden-hac-1526-2024:df-unica` is "Entrada en vigor" and has nothing further to check),
and counting those as defects would be its own over-claim. The meaningful cut is entries
whose BODY the gate never touches: **32 entries carry a body over 1200 characters that no
required phrase reaches, and all 32 are stamped `review_status = "reviewed"`.**

The largest:

```
orden-eha-3127-2009:art-1    176,330 chars   reviewed
ley-37-1992:art-20            30,207 chars   reviewed
ley-27-2014:art-18            24,764 chars   reviewed
rd-1065-2007:art-42-ter        9,603 chars   reviewed
rd-1065-2007:art-3             9,552 chars   reviewed
```

Spot-checked here rather than taken on report. `ley-37-1992:art-20` requires
`["Exenciones en operaciones interiores", "Estaran exentas de este impuesto las siguientes
operaciones"]` - the title plus the chapeau that INTRODUCES the enumeration, so which
operations are actually exempt is never checked, across a 35KB file.
`orden-eha-3127-2009:art-1` requires three title-region phrases against a 445KB file. Both
carry the operator review stamp.

`ley-37-1992:art-20` matters directly to this session's work: it is the LIVA exemptions
article, it grounds the exempt classification that the component table and the con-derecho
set both rest on, and its operative content is unverified by construction.

**Two claims, deliberately kept apart.** ESTABLISHED: for these 32 entries the evidence
gate confirms a heading is present and nothing more. NOT ESTABLISHED: that any of those 32
files is actually truncated. Only `ley-37-1992-art-94.html` is confirmed truncated, because
its tail was read - and at 1,627 bytes it is two orders of magnitude smaller than the
articles above. The finding is that a truncation or corruption in any of the 32 would pass
the gate exactly as art. 94's did: silently, under a reviewed stamp. Establishing that any
of them IS truncated needs 32 more tail-reads and has not been done.

**Actions, none of them authoring legal text.** Refresh the art. 94 excerpt from the BOE
consolidated article. Require `required_text` to quote a phrase from the OPERATIVE
provision rather than the heading - now a rule about 32 entries, and mechanically checkable
by the sweep above, which is near enough to be the gate itself. Neither correction should
be authored by an agent: requoting means choosing which phrase is operative, and choosing
wrongly on an article nobody has re-read from BOE leaves the entry looking better-grounded
while checking something equally incidental. Both belong in the operator corpus refresh.

### The bank-transaction path already does what the invoice path should, and the gap costs a reverse-charge entry

Checked because a landed test docstring asserts the routing fix should follow "the way the
bank-transaction path already does". The premise is correct, and comparing the two paths
surfaces a second divergence nobody had costed.

The bank path prefers the DECLARED category and falls back to rate derivation only when
none is declared - `effective_category = explicit_category`, else
`domestic_categories_by_rate_kind()[rate_kind]` - and it guards the declared branch twice
(a category impossible on that invoice kind, and a non-zero rate on a zero-cuota category).
It then RECOMPUTES the flow from the effective category through
`derive_flow_for_classification`. The invoice-line path does only the fallback, and fixes
the flow from the invoice kind alone.

So the fix template exists, is live, and already carries the guards worth having.

The second divergence is the cost. Measured, on the realistic shape - a supplier under
inversion del sujeto pasivo charges no cuota, so the received invoice carries a base and a
zero cuota:

```
invoice line slot=RATE_0 -> category=domestic_zero   flow=soportado  cuota=0
invoice line slot=EXEMPT -> category=domestic_exempt flow=soportado  cuota=0

Axis-A for DOMESTIC_REVERSE_CHARGE / RECEIVED: cuota=required, settlement=inversion_sujeto_pasivo
correct flow:                                   inversion_sujeto_pasivo
bank path, same category declared:              inversion_sujeto_pasivo
```

A received reverse-charge invoice recorded in the CATALOGUE therefore cannot produce the
self-assessed devengada entry at all: the path never reads the invoice's category and never
recomputes the flow, so the operation lands as an ordinary zero-cuota purchase. The Axis-A
row calls this pair "two entries, one cuota"; the invoice path produces neither.

Direction, stated honestly. For a taxpayer deducting in full the two missing entries offset
and the net cuota is unchanged, so this is not always money. For a prorrata or partially
deductible taxpayer the devengada side is owed in full while the soportada side is only
partly recoverable, so the omission is a real underpayment. In both cases the declaration
is wrong on its face, and the same operation recorded as a BANK ROW with its category
declared is handled correctly - so two records of one operation disagree.

This is the third consequence of one root cause. Constructing the invoice observation from
the invoice's own category closes casillas 59/60, the prorrata bucket misrouting, and this.

### The reverse-charge case is reachable by two paths, and one got more frequent this week

The reachability question this research left open was answered by the team lead and
re-verified here on all three points.

**The CLI does not narrow the choice.** The catalogue `--iva-category` option is typed
`IvaCategory | None` over the full enum, so an operator can attach any category, including
a reverse-charge one, to a catalogue invoice.

**The structured confirm path now carries it.** A test at HEAD asserts that a Facturae tax
category reaches a real catalogue invoice as `DOMESTIC_REVERSE_CHARGE`. That test exists
because the category used to be DROPPED at the confirm boundary and was recently fixed.

These two paths bound the population from BELOW, not above. Neither
`_llm_classification.py` nor the manual ledger edit paths were audited by anyone in this
thread, so "reachable by two paths" is a floor on how often a catalogue invoice carries a
reverse-charge category, never a census of it. The finding needs only the floor - one
reachable path makes it live - but a reader should not read two as the total.

The sequencing point is worth stating plainly: closing the dropped-category hole is what
populated the field, so the population of reverse-charge catalogue invoices went from
approximately none to however many such documents are confirmed. The earlier fix did not
cause the defect recorded above - it removed the accident that was masking it.

**Scope correction, and it decides how the fix must be written.**
`_RECIPIENT_ONLY_REVERSE_CHARGE_CATEGORIES` holds ONLY the two intra-community acquisition
categories; `DOMESTIC_REVERSE_CHARGE` is deliberately absent, and the frozenset's own
docstring gives the reason: an intra-community acquisition self-assesses on either
direction because its supply counterpart is not located in Spain, whereas domestic reverse
charge resolves BY DIRECTION because both sides are Spanish and the form asks for them
separately.

So the frozenset is correct, not deficient - but a fix keying on it would miss the domestic
case, which is exactly the case the defect above is about. The correct construction is the
one the bank path already uses: call `derive_flow_for_classification` with the effective
category and the invoice direction, which routes both families correctly, rather than
testing membership of the frozenset.

### UPDATE: the supplier half of the reverse-charge gap is closed; the recipient half is not

The tree moved while the finding above was being written. Re-verified at HEAD.

**A fourth flow member now exists.** `IvaFlowDirection` carries `operacion_con_inversion`
alongside `repercutido`, `soportado` and `inversion_sujeto_pasivo`, and
`derive_flow_for_classification` now splits the domestic reverse-charge category by
direction into two different members:

```
DOMESTIC_REVERSE_CHARGE issued   -> operacion_con_inversion
DOMESTIC_REVERSE_CHARGE received -> inversion_sujeto_pasivo
```

The received-side value is unchanged, so the measurement recorded above stands; it was
incomplete rather than wrong. A peer landed a declared-category flow map on the projection,
which routes the SUPPLIER side to `modelo-303-casilla-122-inversion-sujeto-pasivo-base`.
That half of the gap is closed.

**Why the supplier half could be closed and the recipient half cannot, structurally.** The
supplier-side base binding selects `rate_kinds = ["general", "reduced", "super_reduced",
"zero", "exempt"]` - it ADMITS the zero and exempt tiers, which is exactly why routing a
base into it works for a document carrying no cuota. Every recipient-side binding selects
only the three rated tiers.

**A refinement to the "no recipient-side base binding" reading, because it differs by
family.** Enumerating every binding whose `flow_direction` is `inversion_sujeto_pasivo`:

```
modelo-303-iva-autorepercutido-interior-devengado-cuota          domestic
modelo-303-iva-autorepercutido-interior-deducible-cuota          domestic
modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota  intracom
modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota  intracom
modelo-303-iva-autorepercutido-intracomunitaria-devengado-base   intracom
```

The DOMESTIC recipient side has cuota bindings only and no base binding at all. The
INTRA-COMMUNITY recipient side does have a base binding - but it is gated on the three
rated tiers, so an exempt-slot or zero-slot line misses it anyway. The conclusion that such
a line reaches nothing holds for both families; the reason differs, but - see below - the
remedy does not.

**The rate-kind asymmetry is deliberate, and it mirrors the component table per side.**
Reading the Axis-A rows by (category, KIND) rather than by category settles it:

```
domestic_reverse_charge                            issued   base=required cuota=zero_by_law
domestic_reverse_charge                            received base=required cuota=required
intra_community_acquisition_reverse_charge         issued   does_not_arise
intra_community_acquisition_reverse_charge         received base=required cuota=required
intra_community_service_acquisition_reverse_charge issued   does_not_arise
intra_community_service_acquisition_reverse_charge received base=required cuota=required
```

Every RECIPIENT-side row requires a cuota. The single cuota-less row is the domestic
SUPPLIER side - and that is precisely the side casilla 122's binding serves, which is
precisely the binding that admits `zero` and `exempt`. The registry's admitted rate kinds
track the component table's cuota column exactly: cuota-zero-by-law admits the cuota-less
tiers, cuota-required refuses them. The asymmetry noted above is not an accident to be
patched.

**So widening the intra-community recipient base binding to admit the cuota-less tiers is
NOT a candidate remedy, and this research withdraws it as one.** No recipient-side pair is
ever legitimately cuota-less, so a cuota-less line in any of the three is an INCOMPLETE
RECORD, not a zero-rated operation. Admitting those tiers would declare a base with no
matching cuota for an operation the law says always bears one - an internally inconsistent
return in which the incomplete record hides behind a partially populated one. That is worse
than the current silence, because a half-populated return reads as answered while a blank
one does not.

That collapses the two families back together. The remedy is the same for both and it is
not a registry change: complete the record - state the rate the supply bore and keep the
cuota at zero where none was charged - which is what the operator advisory on this path
already asks for. The advisory is the remedy, not a placeholder for one.

Whether the domestic recipient side SHOULD have a base binding is a registry and AEAT
question this research does not rule on: casilla 122 is the supplier's base, and where the
recipient's base belongs on the form is not settled here.

**The blocker is unchanged and is the same one this whole document is about.** The rate
slot is not the operation's treatment, so the record arrives at the binding layer carrying
the wrong category and, for a cuota-less document, a tier no recipient-side binding admits.

## Sources

- `src/cadrumo/domain/invoices/_decomposition.py` - the decomposition contract and its
  defect set.
- `src/cadrumo/domain/iva/_components.py` - the Axis-A component table and the shared
  domestic-rated factory.
- `src/cadrumo/domain/iva/_invoice_classification.py` - the line-to-observation helper
  that classifies from the rate slot.
- `src/cadrumo/domain/iva/_classification.py` - the tier-to-category map and its unused
  reverse accessor.
- `src/cadrumo/application/aggregation/_modelo_bindings.py` - the invoice IVA screen loop.
- `src/cadrumo/application/aggregation/_invoice_retencion.py` and
  `src/cadrumo/application/invoices/_source_resolver.py` - the other two invoice-level
  consumers.
- `src/cadrumo/application/calculations/_prorrata_regularizacion.py` - the con-derecho set,
  the volume-side classifier, and the divergence diagnostic.
- Modelo 303 registry, revisions `2009-y-siguientes` and `2023-y-siguientes`: casilla
  definitions for the prorrata volumes and percentage; bindings for casillas 59 and 60.
- Bundled corpus `rd-1619-2012-art-6.html` (arts. 6.1.g and 6.2.a/b/c),
  `ley-37-1992-art-104.html` (art. 104.Dos), `ley-37-1992-art-94.html` (truncated after
  apartado Uno point 5).
- `src/cadrumo/_data/registry/aeat/legal/iva.toml` - the `ley-37-1992:art-94` legal entry,
  its title-only `required_text`, and its operator review stamp.
