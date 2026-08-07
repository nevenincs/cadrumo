---
tags:
  - '#research'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4f092251c1822a3779216d8e83f46086e98bf54d506e0075053e626b5b154aa8'
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

### The bundled art. 94 excerpt does not ground the con-derecho set

Attempting to ground the previous finding legally, the bundled `ley-37-1992-art-94.html`
excerpt was found to carry apartado Uno points 1 through 5 and to stop there. It does not
carry the exempt-with-credit clause that would ground treating intra-community supplies
and exportaciones as operations originating the right to deduct. The codebase's
con-derecho set already classifies them that way and may well be right, but that
classification is NOT verifiable against the bundled corpus as it stands.

Recorded as a grounding gap, not as a claim that the classification is wrong. Art.
104.Dos IS bundled and states the ratio: the numerador takes operations "que originen el
derecho a la deducción", the denominador all operations "incluidas aquellas que no
originen el derecho a deducir". Which side an exempt intra-community supply falls on is
exactly what the missing art. 94 clause decides.

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
  `ley-37-1992-art-104.html` (art. 104.Dos), `ley-37-1992-art-94.html` (truncated).
