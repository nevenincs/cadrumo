---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:90cbf0e08989919495fb4b7543121c01f35560907cf8053732fc9006b5bb846b'
step_id: 'S36'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec `W03-P04-S36`: Ground the tipo-de-actividad code-set granularity

## Scope

- `.vault/exec/2026-08-07-calculation-chain-integrity/2026-08-07-calculation-chain-integrity-W03-P04-S36.md`

## Summary

Report only; nothing changed. The answer is COARSER, decisively, and the code
table behind the M036 field is additionally not bundled. Both halves matter and
they are separate facts.

The M036 diseño de registro carries the field. Page 4 position 76 declares
`Actividad. Tipo de actividad. [403]` as three alphanumeric characters whose
values come from a `Tabla`. Its neighbours in the same sheet enumerate their
code sets inline, so the omission is legible rather than incidental: the IVA
régimen especial field beside it spells out `1 - incluido/2- excluido/3-
renuncia/4-revocacion/5-baja`. The IRPF section repeats the field per activity
slot at `[613]` and `[614]`, also three characters, also table-sourced. The table
itself is absent from the corpus, so the M036 value set cannot be read from what
is bundled.

The only bundled enumeration of a tipo-de-actividad set is the Modelo 840 IAE
declaration, which lists exactly three values: Empresarial, Profesional,
Artística.

That set cannot select an art. 95 rate. It carries no agrícola or ganadera
value, no forestal value, and nothing approaching the engorde de porcino y
avicultura carve-out that art. 95.4.1.º fixes at 1 per cent against the 2 per
cent of art. 95.4.2.º. It resolves only professional against everything else,
which is one boundary out of the four the rate partition needs.

The coarseness has a cause that also predicts it will not be fixed by finding a
better IAE-derived field: agricultural activities are largely IAE-exempt, so an
IAE-rooted tipo vocabulary has no reason to carry an agrarian value. That is the
same fact that makes the profile `iae_epigraph` systematically empty for the
filers a sectoral screen must identify, recorded earlier in the advisory module.
One structural cause, two placements refuted.

No classification of codes into art. 95 partitions was performed. Doing so
without a bundled authoritative source is the fabricated-grounding failure the
governing constraint names, and it would sit underneath a rate screen where
nothing downstream could detect it.

## Consequences for the build

The join alone is not sufficient. A grounded code-to-partition mapping is
required in the registry with its own legal_refs, which is an addition to the
`W03.P05` scope rather than a detail of it.

A corpus refresh is required before that mapping can be authored, since the
M036 `Tabla` is referenced by the diseño and not bundled. If the refreshed table
proves to match the IAE triple, the mapping cannot be built from it at all and a
different source axis is needed for the agrarian and forestal splits.
