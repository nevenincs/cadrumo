---
tags:
  - '#research'
  - '#iva-exemption-article'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `iva-exemption-article` research: `IvaExemptionArticle discriminator for domestic_exempt subenumeration (S354)`

## Problem statement

Plan Step W09.P41.S354 (R9-TOMAS-HIGH) flags that the
`IvaCategory.DOMESTIC_EXEMPT` value collapses all Ley 37/1992 Art. 20
("exenciones interiores") cases into a single bucket. The Art. 20
sub-articles have materially different downstream-deduction
implications: Art. 20.Uno.26 (servicios artísticos) operates "con
plena prorrata" (full deduction right preserved); Art. 20.Uno.8
(enseñanza) operates "sin prorrata" (no deduction right);
Art. 20.Uno.14 (sanitarios) and others fall along the spectrum.

Today every domestic-exempt transaction maps onto the same
`DOMESTIC_EXEMPT` IvaCategory regardless of sub-article, so the
calculation chain cannot distinguish whether the underlying
deduction right survives. That blocks correct Modelo 303 casilla-61
(operaciones exentas interiores con derecho a deducción) reporting
(S355) and silently understates the recoverable IVA for artistas
operating under 20.Uno.26.

## Existing surface

The `IvaCategory` StrEnum lives at `src/aeat/domain/iva/_schema.py`
(grep evidence: `IvaCategory.DOMESTIC_EXEMPT` referenced across
`src/aeat/domain/iva/_classification.py:558,610`,
`src/aeat/domain/iva/_invoice_classification.py:122`, and four test
files). Classification routes a transaction to `DOMESTIC_EXEMPT` via
two paths: `IvaRate.EXEMPT` → `DOMESTIC_EXEMPT` (line 558 of
`_classification.py`), and immovable-property classification rule
R04 (line 610 + test_classification.py:295-306).

The persisted `IvaInvoiceClassification` record carries
`category: IvaCategory`. No sub-article field exists on the record
or on the upstream Transaction.

The Modelo 303 registry under
`src/aeat/_data/registry/aeat/modelos/303/revisions/.../casillas/`
includes casilla 60 (exportaciones, OSS) but does NOT include
casilla 61 — the operator surface has no place to route
"interiores con derecho a deducción" operations.

## Design space

Two options the plan row names plus a third worth considering:

### Option A: add `IvaExemptionArticle` discriminator field on Transaction

A new optional `exemption_article: IvaExemptionArticle | None` field
on the transaction model. The discriminator is a closed StrEnum naming
each Art. 20 sub-article slot the codebase needs to distinguish
(initially: `ART_20_UNO_8` enseñanza, `ART_20_UNO_14` sanitarios,
`ART_20_UNO_26` artistas, plus a `ART_20_OTHER` catch-all).
Classification rules that route to `DOMESTIC_EXEMPT` additionally
stamp the discriminator based on transaction context (counterparty
type, service description, etc.).

Pro: additive; existing call sites unchanged; discriminator absence
means "exempt but article unknown" which preserves today's behaviour.
Con: classification rules need extension to populate the
discriminator; some sub-articles cannot be inferred from transaction
shape alone and require operator declaration.

### Option B: replace single `DOMESTIC_EXEMPT` with article-tagged variants

Split `DOMESTIC_EXEMPT` into `DOMESTIC_EXEMPT_ART_20_UNO_8`,
`DOMESTIC_EXEMPT_ART_20_UNO_26`, etc.

Pro: type-system enforces the sub-article distinction at every call
site.
Con: invasive — every existing reference to `DOMESTIC_EXEMPT` must
either pick a sub-article or be replaced by an enumeration. The
many tests that build a DOMESTIC_EXEMPT transaction without caring
about the sub-article all break.

### Option C: keep `DOMESTIC_EXEMPT` + add separate `exemption_basis`
mapping on the registry / domain calculation layer

Leave the IvaCategory enum unchanged. Add a separate
`exemption_basis` Pydantic record that classification stamps
alongside the category, carrying the article reference plus the
deduction-right flag derived from it. M303 casilla 61 then routes
on `exemption_basis.deducible_right`, not on the category itself.

Pro: most decoupled — the discriminator lives in the routing layer,
not the category enum. Existing IvaCategory consumers see no change.
Con: introduces a second classification-axis the consumers must
also read; risk of drift between the two axes.

## Recommendation

Option A. The discriminator is additive (defaults to `None` so
existing code paths see the same behaviour) and the
deduction-right routing for M303 casilla 61 reads cleanly from the
discriminator value: a tiny mapping
`{ART_20_UNO_26 → casilla_61, ART_20_UNO_8 → casilla_60_only, ...}`
implements the regulatory routing without spreading the rule across
the calculation engine.

Option B's call-site sweep is too invasive for the value gained.
Option C's two-axis classification is harder to reason about than
one enum + one optional discriminator.

The follow-up ADR scopes the closed `IvaExemptionArticle` enum
membership (which sub-articles to enumerate explicitly vs collapse
under `ART_20_OTHER`), the classification-rule extension (which
transaction features map to which discriminator value), and the
casilla-61 routing in the M303 registry.

## Blocked by

The casilla-61 authoring (S355) cannot land until either Option A's
discriminator OR a casilla-61 routing exists. The two Steps land in
order: S354 (discriminator + classification) → S355 (casilla 61
binding via the discriminator).

## Source

Plan Step W09.P41.S354 in
`[[2026-05-26-cross-domain-continuity-plan]]`. Persona testimonial:
R9-TOMAS-HIGH (artista plena con prorrata under Art. 20.Uno.26
losing deductible operations from M303 reporting).
