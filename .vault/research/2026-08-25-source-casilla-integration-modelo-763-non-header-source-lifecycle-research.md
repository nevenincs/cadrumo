---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ccf2aa35836ae05281600702d7d0b46e5390e6571c2b4316ff1637d4d2506d2b'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-24-registry-completeness-closure-modelo-763-design-era-and-filing-boundary-reference]]'
---

# `source-casilla-integration` research: `modelo 763 non header source lifecycle`

The question is whether the now period-aware Modelo 763 filing surface exposes
an already governed, authoritative lifecycle for a non-header value.  The
evidence establishes three exact AEAT target-design eras and a real set of
money, territory, and payment destinations.  It does not establish an ingress
fact, its native grain, provenance or absence semantics, a secure owner, or a
destination map for any one of those values.

## Findings

### The primary record authority is period-bounded, not an acquisition source

The official AEAT corpus has three immutable record-design artefacts: the
2012 design for 2T/3T 2012 and 2013--2014, SHA-256
`b9da58969e0a5cbea00c2f0780c3cbdc8fba3c5b9fc26d17042f8f277278d2fd`; the
2015 design through 3T 2018, SHA-256
`124c40d7cdadced45e21a2b6b01bb9d76d30e78551ae7316508c14ceaec4f62e`; and
the design for 4T 2018 onward, SHA-256
`590db67f074251ad1ddfcbebfffbf8d58f6157848b62661fadc334bc5e7af5d4`.
The AEAT catalogue identifies the last as "2018 4T y siguientes".  The 2015
BOE amendment replaces the Modelo 763 annex for periods beginning on
1 January 2015, and the 2018 BOE amendment applies its replacement to 4T 2018
and later.  These sources establish which record description is a filing
destination for each selected period; none names a Cadrumo acquisition channel
or a source-owner lifecycle.

### The designs show non-header filing values but leave the source tuple open

Across the three record designs, fields include gross and net gaming income,
prizes paid, rates and cuotas; the later designs also name territorial
amounts played by residents.  The 2015 design names the autoliquidation result,
payment form, and IBAN.  That is sufficient to show that non-header filing
facts exist on the official target surface.  It is not sufficient to identify
whether a value is a per-game, per-bet, per-player-territory, per-declarant
quarter, or derived aggregate source fact, nor which value source supplies it.

The declared numeric positions must therefore remain destinations, not
evidence of a connected fact.  In particular, an AEAT record position, an
export application link, a payment consequence, or the legal presentation
procedure cannot be used as the missing source identity, acquisition
provenance, absence policy, encrypted owner, or canonical destination mapping.

### Current M763 declarations distinguish the scheduling header from a value lifecycle

Each of the six selected revisions is `authority_grade = "applicability"` and
declares exactly the informational `decl.ejercicio` and `decl.periodo` header
casillas.  Their constructs retain static-layout parity anchors but no
non-header casilla, binding, formula, or export layout.  The period-aware
registry test couples each selector to only its exact design era and explicitly
refuses the unevidenced 2011, 2012-1T, and 2012-4T coordinates.

There is no declared Modelo 763 manual non-header casilla path.  That absence
does not recast the official design values as manual values; it only prevents
this research from treating the two informational filing headers as a source
domain.  Likewise, an exact search found no Modelo 763 entry in the canonical
source-connectivity census or discovery inventory and no Modelo 763
calculation, filing producer, or filing-application implementation.

### Candidate information that remains unestablished

No bounded candidate can yet state all of: the authoritative source fact,
native grain and durable identity; period and territorial semantics; complete
value, derivation, sign, rounding, and absence policy; an encrypted
non-lossy owner with capture provenance; and a particular reviewed non-header
destination for one exact era.  A later source-connectivity assessment would
need those facts before it can distinguish a genuinely independent operator
ledger or other source from a duplicate, a manual-by-design value, or a
derived filing aggregate.  The present evidence therefore leaves no
model-scoped normative alternative for an ADR to settle.

## Sources

- https://www.boe.es/buscar/act.php?id=BOE-A-2011-11704
- https://www.boe.es/buscar/doc.php?id=BOE-A-2014-13180
- https://www.boe.es/buscar/doc.php?id=BOE-A-2018-17602
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/resto-modelos.html
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_763/manifest.json:1`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_763/files/02-763-orden-eha-1881-2011-ejercicios-2t-3t-2012-2013-y-2014.pdf.extracted.md:20`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_763/files/03-763-ejercicios-2015-a-2018-hasta-3t.xlsx.extracted.md:18`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_763/files/03-763-ejercicios-2015-a-2018-hasta-3t.xlsx.extracted.md:74`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_763/files/01-763-desde-2018-4t-y-siguientes-actualizado-en-2023.xlsx.extracted.md:18`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_763/files/01-763-desde-2018-4t-y-siguientes-actualizado-en-2023.xlsx.extracted.md:129`
- `src/cadrumo/_data/registry/aeat/legal/modelo-763.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2012-2t-3t/casillas/cdecl.ejercicio__cdecl.periodo.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2015-2017/revision.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2018-4t/revision.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2019-y-siguientes/revision.toml:1`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_490_604_763_registry.py:111`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:158`
- `src/cadrumo/_data/source_connectivity/census.toml:1`
