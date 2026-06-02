# aeat

`aeat` is a local-first command-line tool for preparing your Spanish tax forms.
It takes the records you keep and works out the figures for each *modelo* (a
Spanish tax form). It checks them against the form's rules and exports a file
ready to submit to the Agencia Estatal de Administración Tributaria (AEAT). It's for
*autónomos* (self-employed filers) and small businesses who file their own taxes,
and for the people who help them. The [glossary](glossary.md) explains the
Spanish terms used throughout these docs.

> **Disclaimer.** `aeat` is a software utility, not a tax advisor. It gives no
> tax, legal, accounting, or financial advice, creates no advisory
> relationship, and is not affiliated with, endorsed by, or connected to the
> AEAT.
>
> Nothing `aeat` produces is advice or a guarantee. No calculation, draft,
> verification, or export assures you that a figure, form, or filing is correct,
> complete, or compliant with current law. You alone are responsible for the
> accuracy, completeness, and legality of every figure you enter and every
> declaration you file, and you should review every output before you rely on
> it.
>
> `aeat` never files. It does not submit to the AEAT and cannot file for you.
> You file yourself, through official channels, and bear sole responsibility for
> that filing. Because tax law changes and depends on your circumstances,
> consult a qualified professional such as an asesor fiscal or gestor for advice
> on your situation.
>
> `aeat` is provided "as is", without warranty of any kind, under the Apache
> License 2.0. The authors accept no liability for any loss, penalty, interest,
> or other damage arising from its use. Read the [full disclaimer](disclaimer.md)
> before you rely on `aeat`.

## Choose your path

Pick the route that matches what you want to do:

- **Install and produce your first export.** [Get started](getting-started.md)
  takes you from install to a first exported modelo file in a few commands. It's
  the fastest route to one real result.
- **Learn the whole workflow.** The [tutorial](tutorials/index.md) is a guided,
  end-to-end lesson. It loads a sample set of transactions, classifies them, and
  builds, checks, and exports a modelo from start to finish.
- **Do one specific task.** The [how-to guides](how-to/index.md) are short
  recipes for single goals, such as importing your records, classifying
  transactions, recalculating a modelo, checking a draft against a justificante,
  and exporting a file.
- **Look up a command or term.** The [command-line reference](cli/index.rst)
  lists every command and option, and the [glossary](glossary.md) explains the
  Spanish tax terms.
- **Understand how it works.** The [explanation](explanation/index.md) covers
  how each figure traces to the law behind it and why `aeat` never submits your
  filing.

## Project and reference material

- The [architecture overview](architecture.md) describes how the code is
  organized.
- The [authoring guide](authoring-guide.md) is for contributors who change the
  documentation.
- The [API reference](api/aeat.rst) documents the application programming
  interface (API), generated from the source.

## Getting help

Report bugs and ask questions on the
[issue tracker](https://github.com/wgergely/aeat/issues). Every command carries
its own `--help`. The [full disclaimer](disclaimer.md) covers the limits of what
`aeat` does.

```{toctree}
:hidden:
:caption: Where to start

getting-started
tutorials/index
```

```{toctree}
:hidden:
:caption: Everyday use

how-to/index
cli/index
glossary
```

```{toctree}
:hidden:
:caption: How it works

explanation/index
```

```{toctree}
:hidden:
:caption: Project

disclaimer
architecture
authoring-guide
api/aeat
```
