# Registry, legal sources, and Python API

The Agencia Estatal de Administración Tributaria (AEAT) owns the official
modelo structure. API means application programming interface.

## Registry and legal-source lookup

Cadrumo's calculation registry preserves the AEAT structure it represents:
modelo identifiers, periods, sections, casillas, formulas, bindings,
classifications, and source references remain authority-named. A resolved
calculation revision records the registry revision it used so later review can
identify the exact rule set.

| Reference field | Meaning |
| --- | --- |
| Registry revision | Exact bundled rule revision used for the calculation |
| Formula or binding | Deterministic route from source values to a casilla |
| `legal_refs` | Legal provisions grounding a rule or finding |
| `source_refs` | Official manual or source material supporting the implementation |
| Evidence provenance | Local record, document, observation, or prior filed revision that supplied a value |

Use the generated [application command reference](../cli/app.rst) to look up
registry inspection, modelo description, formula, verification-report, and
audit surfaces. Use the {doc}`glossary </_generated/glossary>` for taxpayer-facing
definitions.

## Python public API lookup

The generated [Cadrumo package API](../api/cadrumo.rst) is the entry point for
Python lookup. Public consumers import from `cadrumo` and its documented public
facades. The generated package tree lists the supported adapters, application,
core, domain, entrypoint, and locale surfaces.

There is no `aeat` Python import compatibility package. Names containing
`aeat` inside the `cadrumo` package identify the external authority adapter or
authority-owned vocabulary, not a second product API.
