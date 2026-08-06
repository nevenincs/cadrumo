---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:d1037197de6aabf1e9b6db92b54ff13ce28620186f7d167abedc0c598f2e5c53'
step_id: 'S04'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Discover the authenticated consulta URL and DOM for mis datos censales against a live session and record the selectors

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede`

## Description

- Analyse the captured authenticated consulta page and record its DOM shape.
- Record the consulta route as registry data rather than a code literal.
- Enumerate the modification surfaces the consulta page links, and record them as
  declared canaries for the no-write proof.
- Encode the discovered selectors and label set into the reader's parser.
- Sanitise the capture into a committable fixture so the selectors stay pinned to
  real markup.

## Outcome

The consulta route is `MdcAcceso` under the `BUGC-JDIT` application, reached with
`nifRepresentado`, `E_HNR` and `EJERCICIO` query parameters. It is a read view:
its page title is "Mis Datos Censales" and its heading "Consulta de Datos
Identificativos y Censales".

Data lives in `table.celdasConBorde`. The reliable section discriminator is the
`title` attribute AEAT stamps on every data table, not the `<th>` heading, which
renders only on the first table of each group. Three groups exist: "Datos
Identificativos del Contribuyente", "Domicilio Fiscal" and "Domicilio de
Notificación".

The page uses TWO different table shapes, which is the finding that most shaped
the parser. The identity table is row-wise: each row carries a label cell and its
value cell. Both address groups are columnar and split across several tables
each: a row of labels followed by a row of values, aligned positionally, preceded
by a hidden spacer row. A parser written for either shape alone silently drops the
other group entirely. In both shapes a label cell is discriminated by its content
being wrapped in `<b>`; the `notrad` attribute is NOT a usable discriminator,
because several value cells carry the same `notrad` value as labels.

Forty-four labels were recorded across the three groups. Blank values arrive as a
non-breaking space rather than an empty cell, so absence and empty string must be
distinguished at parse time. Values carry trailing padding. Dates render as
`DD/MM/YYYY`. The two electronic-notification fields render as Spanish yes/no
prose rather than booleans.

The page links a further consulta surface for economic activities, noted as a
future source and deliberately not followed in this step.

Four modification surfaces are reachable from the consulta page, which is the
material safety finding: two domicilio-change buttons whose scripts build
relative `ModifDomiDual` and `ModifDomiNotif` targets, the Modelo 036 filing tool
under a `BU36-` application as a `.zul` document, and an "Otras Modificaciones
Censales" link to a procedure launcher under the `procedimientoini` path. None of
the four contains the token an earlier draft of the proof forbade, which is why
the landing guard keys on path prefixes instead. All four are recorded as declared
canaries in the shared AEAT literal fixtures rather than as literals in a test.

Closing measurement at `3f16615f6b`: the parser resolves all 44 labels against the
sanitised capture, and a coverage test asserts that every `<b>`-wrapped label
rendered on the page maps to a model field, so a future AEAT addition cannot be
silently dropped.

## Notes

The live half of this Step was NOT performed by the executor who wrote this
record. The coordinator authenticated through Cl@ve and captured the
authenticated page, and a peer agent performed the live probing. The executing
agent was dispatched against that capture with an explicit instruction not to
open a live session, and owns the DOM and selector analysis, the route and canary
declarations, and the fixture. The record is written this way because a claim of
live discovery would mislead the reader this document exists for.

The raw capture carried a live AEAT session token in a hidden form field, and the
executor's sanitisation pass did not remove it. That pass was scoped to personal
values as briefed: it enumerated and replaced 19 tokens, verified zero residue,
confirmed tag-count fidelity, and swept for email addresses, IBANs, telephone
numbers, tax-identifier shapes and dates. All of it passed, and none of it was
looking for a credential, so the token survived every check. A peer agent
substituted it before the fixture was committed and landed a hygiene gate that
refuses credential-shaped values by SHAPE rather than by field name — the field
name here was opaque markup noise and matched none of the obvious keywords. The
committed fixture is clean and was confirmed to be within that gate's scope
rather than trusted on a passing run.

The raw capture retained on disk still contains the live token. It is excluded
from version control, and rotation was referred to the operator as their
decision.
