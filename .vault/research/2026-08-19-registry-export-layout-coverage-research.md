---
tags:
  - '#research'
  - '#registry-export-layout-coverage'
date: '2026-08-19'
modified: '2026-08-19'
body_schema: 'body-v1'
body_hash: 'sha256:f03f00675277348f0cd820d4164f84b0c699d96421c102cabbafa1b0a79ded85'
related: []
---

# `registry-export-layout-coverage` research: fichero filing routes vs export layouts

## Question

Seventeen registry revisions carry no export layout. Two claims had been treated as settled
and neither had been tested against AEAT:

1. Which modelos can actually be filed **by fichero** (a generated file), as opposed to only
   through a web form?
2. Where AEAT publishes a record design and we have no layout, **what is the cause** — a
   missing document, or a deliberate scope decision?

The consequence matters: a modelo with no fichero route must NOT get an export layout, because
there is nothing to submit the bytes to. Assuming that without evidence is how a real
capability gap gets mislabelled "impossible", and how an impossible one gets mislabelled "todo".

## Method

Enumerated AEAT's own record-design index — the five current range pages under
`sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/` (`modelos-01-99`, `100-199`,
`200-299`, `300-399`, `resto-modelos`). Each publishes anchors of the form
`NNN - <edition> (size - format)` linking into `/static_files/Sede/Disenyo_registro/`.
Parsing those anchors is reliable; free-text regex over the page is NOT — an early pass
reported modelos 200 and 303 as absent when their designs are bundled and hash-pinned, a
false negative caused by matching prose rather than the link structure.

Cross-referenced the result against the bundled registry: which modelos declare a
`kind = "record_design"` source, and at what `authority_grade`.

## Findings

**AEAT publishes a record design for 118 modelos.**

**15 of the 17 gap revisions have a published AEAT design, and every one of those 15 is
ALREADY BUNDLED in this registry.** There is no acquisition gap:

| modelo | AEAT publishes DR | bundled here | grade |
|---|---|---|---|
| 036, 038, 182, 185, 187, 188, 194, 220, 222, 763, 840 | yes | yes | **applicability** |
| 200, 296, 303 | yes | yes | filing |
| **136** | **NO** | no | **filing** |
| **721** | **NO** | no | **filing** |

### Answer to question 2
The cause is **not** missing documents. Every modelo except 136 and 721 has its design
acquired. Those 15 have no export layout because the registry declares them at
**`applicability` grade** — a deliberate scope decision that this application answers *when
the modelo is due and to whom it applies* and does not itself file it. The export-layout
refusal is scoped to `filing` grade precisely so an applicability-grade revision is not
refused for a claim it never made. Modelo 182 is the documented worked case: the donativos
declaration is filed by the entity RECEIVING the donation, so this application's taxpayer is
the subject of the declaration and not its filer.

### Answer to question 1, and the real anomaly
**136 and 721 are the only two modelos in the gap set with no AEAT record design at all**,
confirming the claim in `_validate_export_exemption.py` against AEAT's own index rather than
against our bundled corpus. For 721 the only layout artefact is its approving BOE orden's
anexo — a printable form, not a positional design a fixed-width writer could be authored from.

**But both declare `authority_grade = "filing"`:**

- **136** — Gravamen especial sobre los premios de determinadas loterías y apuestas
  (autoliquidación)
- **721** — Monedas virtuales situadas en el extranjero (informativa anual)

A revision claiming the filing rung asserts it can back a filing draft *and its export*. If
AEAT publishes no fichero design for the modelo, that export cannot exist by any amount of
authoring, so the claim is unbackable in principle rather than merely unbuilt. AEAT's own M721
guidance describes submission through the web form on the Sede, not by file.

## Open question for the operator

Is `filing` the intended rung for 136 and 721? Two readings, and the registry cannot choose
between them:

- **They are web-form-only.** Then `filing` overstates the reach and the honest rung is
  `applicability`, with the export family resolved as not-applicable on the grounds that AEAT
  publishes no positional design.
- **A fichero route exists that this survey missed** (a different AEAT surface, or a design
  published outside the record-design index). Then the gap is acquisition after all and the
  document must be fetched.

The validator explicitly forbids picking the rung from present content — "DO NOT pick the rung
by looking at which families this revision currently has" — so this is an intent decision, not
a derivation.

## What this changes

The framing "12 applicability-grade revisions would regress the registry if given layouts" is
correct but was stated without evidence about fichero availability. The evidence now exists:
AEAT DOES publish designs for those 12, they ARE bundled, and the reason they carry no layout
is the grade decision, not absence of a document. That is a stronger and more honest basis for
leaving them alone — and it means promoting any of them to filing grade is a live option that
would require authoring a layout, not an impossibility.

## Sources

- AEAT record-design index: `sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos.html`
  and its five range pages (retrieved 2026-08-19)
- `src/cadrumo/domain/calculations/registry/_validate_export_exemption.py`
  (`modelo_publishes_a_record_design`, and the grade/design double scoping)
- Bundled registry source catalogue (`kind = "record_design"` entries)
