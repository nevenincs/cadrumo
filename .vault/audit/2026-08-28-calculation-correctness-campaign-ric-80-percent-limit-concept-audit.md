---
tags:
  - '#audit'
  - '#calculation-correctness-campaign'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:5566f4fde7877640e4bf55fc8871d5a4b657438265af992878711a32dfb987db'
related: []
---

# `calculation-correctness-campaign` audit: `The RIC 80 percent parameter is named a reduccion but art 27.15 limits a deduccion en la cuota`

## Finding

`renta-2025-ric-reduccion-rate-maximo` carries the value `80` and cites
`ley-19-1994:art-27`. The **value is correct and is stated in the bundled
corpus.** What is wrong is the concept the parameter's name and its
`required_text` attach it to.

Art. 27 establishes two different Reserva para Inversiones en Canarias regimes,
and the parameter names the wrong one:

- **§27.1, Impuesto sobre Sociedades** — *"tendrán derecho a la **reducción en la
  base imponible** de las cantidades que… destinen de sus beneficios a la reserva
  para inversiones"*. This is the **reducción** regime, and its own ceiling is the
  90 % figure that appears elsewhere in the law.
- **§27.15, IRPF** — the regime this Modelo 100 parameter actually serves:

  > Los contribuyentes del Impuesto sobre la Renta de las Personas Físicas que
  > determinen sus rendimientos netos mediante el método de estimación directa
  > tendrán derecho a una **deducción en la cuota íntegra** por los rendimientos
  > netos de explotación que se destinen a la reserva para inversiones… La
  > deducción se calculará aplicando el tipo medio de gravamen a las dotaciones
  > anuales a la reserva y tendrá como límite el **ochenta por ciento de la parte
  > de la cuota íntegra** que proporcionalmente corresponda a la cuantía de los
  > rendimientos netos de explotación que provengan de establecimientos situados
  > en Canarias.

So for IRPF the 80 % is a ceiling on a **deducción en la cuota íntegra** — and
specifically on *the part of the cuota íntegra proportionally attributable to
Canarian rendimientos netos*. It is not a ceiling on a reducción, and it is not
80 % of the rendimiento neto.

The parameter is named `ric-**reduccion**-rate-maximo` and its cross-check reads:

```toml
required_text = ["Reserva para Inversiones en Canarias", "rendimiento neto"]
```

Both phrases occur in §27.15, so the evidence gate passes — while pinning neither
the number nor the limited quantity. A reader taking the name and `required_text`
at face value would conclude the cap applies to the rendimiento neto or to a
base-side reducción. Both readings are wrong, and they are wrong in a way that
changes the arithmetic: a reducción acts on the base, a deducción on the cuota,
and the §27.15 denominator is a *proportional share* of the cuota íntegra rather
than any whole quantity.

## Why this has no live consequence today

The parameter is **unconsumed** — no formula reads it (recorded previously as the
RIC entry in the unreachable-rung set). So nothing currently computes a wrong
figure from the mislabelled concept.

That is precisely why it is worth recording now rather than after it is wired: the
name is the specification a future implementer will read. Wiring
`ric-reduccion-rate-maximo` as a base-side reducción cap would be a faithful
implementation of the name and a wrong implementation of the law.

## A method note this finding produced

The corpus states the ceiling as **"ochenta por ciento"**, spelled in words. A
first pass regexing `80 por ciento` / `80 %` matched nothing and would have
supported the false conclusion that the corpus is silent on the figure. The
standing rule — *a number spelled in words is still grounded; compare Decimals,
never string-match Spanish legal numbers* — applies to the **corpus side** of the
comparison too, not only to the parameter side.

Relatedly, the per-article extract `ley-19-1994-art-27.html` is 1.607 characters
and carries only §§1, 4 and 15 — a deliberate excerpt, not the whole article. That
is adequate here because §15 is present verbatim, but a sweep that treats a
per-article file as the complete article will draw false negatives from the
paragraphs the excerpt omits. The full `ley-19-1994.html` (294.215 characters) is
the fallback.

## Remediation — owner's decision, not taken here

Rename to say what §27.15 limits — a deducción en la cuota íntegra, capped at a
proportional share — and replace the `required_text` with a phrase carrying the
distinguishing words (`deducción en la cuota íntegra`, `ochenta por ciento`) so
the cross-check can discriminate. Do **not** wire the parameter into a formula on
the strength of its current name.

A rename is not a mechanical edit here: the name states a tax-treatment fact, so
per the standing rule this is a tax review, not a text substitution. The value
itself is correct and must not change.

No production code, registry data or test was changed by this audit.
