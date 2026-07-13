# Tutorials

This page covers the guided lessons: two lifecycle tutorials that carry one
example taxpayer through a complete filing year, each demonstrating a whole
pipeline end to end. Both follow the same persona - Ana García López, a
consultant who started her activity on January 1, 2026 - and the same
continuous ledger, so you can run them in either order or interleave them
the way a real year does.

Every command is real and runs locally. Cadrumo (the `aeat` command)
prepares and exports filing files; it never submits anything to AEAT - you
upload each exported file yourself at the AEAT portal.

::::{grid} 1 2 2 2
:gutter: 3

:::{grid-item-card} The income-tax year
:link: irpf-lifecycle
:link-type: doc

Four quarterly Modelo 130 instalments, each building on the ones before it,
closing with the annual Modelo 100 Renta declaration that gathers the whole
year.
:::

:::{grid-item-card} The IVA year
:link: iva-lifecycle
:link-type: doc

The opening credit balance, four quarterly Modelo 303 returns with the IVA
credit carrying between them, an optional Modelo 349 branch, and the annual
Modelo 390 summary.
:::

::::

If you want the shortest possible path - one modelo, one period, copy-paste
commands - use the [Quickstart](../how-to/quickstart.md) instead; the
tutorials are the narrated year, the quickstart is the five-minute recipe.

```{toctree}
:hidden:

irpf-lifecycle
iva-lifecycle
```
