---
tags:
  - '#audit'
  - '#registry-legal-grounding-windows'
date: '2026-08-27'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:803c49e0bfe963d5ed5b2348bef2e34802a5b89f3d332c233ce3b377b0eef745'
related: []
---

# `registry-legal-grounding-windows` audit: `ninety autonomic scale tables cite the article that delegates the rate, not the one that sets it`

## Scope

## Findings

## Recommendations

## Finding

Ninety Modelo 100 autonomic-scale bracket tables -- 15 Comunidades Autónomas
across filing years 2020 to 2025 -- declare exactly one legal reference:

    legal_refs = ["ley-35-2006:art-74"]

LIRPF art. 74 sets no rate. The bundled consolidated text says the base is
taxed at "los tipos de la escala autonómica del Impuesto que, conforme a lo
previsto en la Ley 22/2009 ... hayan sido aprobadas por la Comunidad
Autónoma". The catalogue's own note agrees: "The article delegates the scale
to the Comunidad Autónoma under Ley 22/2009."

So every marginal rate a resident of those fifteen regions is taxed at is
grounded on the article that DELEGATES the rate, not on the regional norm that
establishes it. `aeat-calculation-grounding` addresses this directly: "Citing
the general framework article alone is insufficient when a more specific
provision ... actually fixes the number. A value whose binding provision is not
in the schema is ungrounded and MUST NOT ship."

Affected: andalucia, aragon, asturias, baleares, canarias, cantabria,
castilla-la-mancha, castilla-y-leon, cataluna, comunidad-valenciana,
extremadura, galicia, la-rioja, madrid, murcia -- 15 per year, 6 years.

## What is NOT wrong, stated precisely

The NUMBERS are cross-checked. All ninety carry `source_citations` with a
`required_text` assertion against the bundled AEAT Renta manual for the year
(e.g. "Comunidad Autónoma de Andalucía", "escala autonómica"). This is not a
population of unverified figures, and nothing here says a rate is wrong.

The defect is in the legal chain: `legal_refs` names a provision that cannot
establish the value it is attached to. That matters because the legal_refs are
what travel to the operator as the value's authority, and an operator who
follows art. 74 to check a rate finds an article that points somewhere else.

## Precedent for the fix already exists

`legal/irpf-autonomica-madrid.toml` catalogues a real autonomic authority --
Madrid's Decreto Legislativo 1/2010, with `authority = "autonomous_community"`
and a corpus_ref. It grounds a deducción and the regional mínimo por
descendientes, not the scale. So the shape of the correct entry is established;
what is missing is one per region per applicable year for the scale itself.

## Not repaired here

Grounding these needs the consolidated regional norm for each of fifteen
Comunidades across six years, sourced from official text. Inventing the
citations, or reusing Madrid's DL 1/2010 as a template with other regions'
identifiers guessed, would manufacture exactly the fabricated grounding
`aeat-calculation-grounding` forbids: "Do not invent legal behavior."

## Status

Open. Ninety values, verified figures, wrong establishing provision.
