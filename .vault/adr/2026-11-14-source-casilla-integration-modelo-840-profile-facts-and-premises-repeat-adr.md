---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-11-14'
modified: '2026-11-14'
body_schema: 'body-v2'
body_hash: 'sha256:7a8024055089a333aefeaac569962e0805760cfe2df9325755c3ce3788738860'
related:
  - "[[2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-owner-deferral-adr]]"
  - "[[2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-lifecycle-grounding-research]]"
---

# `source-casilla-integration` adr: `Modelo 840 profile facts and the premises repeat layout` | (**status:** `accepted`)

## Problem Statement

The Modelo 840 export layout cites 65 producer keys that no runtime producer supplies:
`m840.actividad.municipio`, `m840.actividad.provincia_codigo`, the AEAT `administracion` and
`delegacion` codes, and the `elementos_tributarios.*` family. Exported, they would render blank.
The export therefore keeps the typed unsupplied-producer refusal (landed with tui `7fe252b77a`),
and `test_every_cited_producer_key_is_resolvable` is a known red with owner LIFECYCLE.

LIFECYCLE's discovery (status LIFECYCLE 09:40 and 09:55; RULINGS 08:33) found three gaps:

- No stored profile fact exists for any of the 65 keys.
- The keys need facts the profile schema does not hold: a structured fiscal address with
  municipality and province codes, the AEAT delegación and administración, and per-activity
  premises with their IAE Regla 14 surface classes and tax elements.
- The anexo "Relación de locales" layout repeats one key across premises slots, so the export
  generator needs repeat semantics.

Producers written now could only refuse, and PRIME ruled out always-refusing producers that
exist only to turn a test green.

This record states what would close the gap, for the operator to accept or defer.

## Considerations

- `2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-owner-deferral-adr`
  (accepted) holds two M840 source families, the declaration and activity family and the
  per-local row family, at `grounding_blocked`. It allows reopening one family only when five
  conditions hold: a durable encrypted carrier and identity; exact grain, zero, absent,
  correction and collision semantics; a law-selected semantic map excluding AEAT-reserved fields;
  resolver, provenance, persistence, replay and review; and independently grounded export
  evidence. This proposal is that reopening, scoped to both families. Its research is
  `2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-lifecycle-grounding-research`.
- Official grounding located by LIFECYCLE: the M840 record design (Orden HAC/2572/2003), the
  Modelo 840 form, and the IAE tariffs and instruction (RDLeg 1175/1990, including Regla 14 on
  surface classes).
- PLAN places Modelo 840 in phase 2, and no persona row exercises it, so no persona-table row
  moves.
- The profile schema declares sensitive taxpayer facts with provenance, effective dates and
  custody policy. Adding facts is a persisted-schema change under that contract, not a fixture
  change.
- A key with no stored fact keeps the typed refusal (RULINGS 04:56) and never takes a default.

## Considered options

### (a) Full feature: profile facts, premises repeat layout and producers

Add typed profile facts: the structured fiscal address with INE municipality and province codes;
the AEAT delegación and administración; and per-activity premises carrying their address,
Regla 14 surface classes (computable, total, rectified) and the tax elements the tariff names.
Give the export generator repeat semantics for the anexo premises slots, keyed by a durable
per-local identity. Write producers that read only those stored facts.

### (b) Header-only interim

Supply only the declaration-level keys a stored fact already covers and keep the refusal for the
rest. Rejected: no stored fact covers any of the 65 keys, so the interim would supply nothing.

### (c) Defer to phase 2 (recommended)

Keep the typed refusal and the known red with its owner and reason. Make no schema or layout
change now.

## Constraints

- Option (a) must meet all five reopening conditions of the 2026-08-25 deferral ADR for each
  family it opens. The premises family keeps its distinct Total, Rectificada and Computable
  values and its per-local identity, and never borrows a declaration fact.
- Facts are entered by the operator or acquired with provenance, never inferred from the IAE
  epigraph alone.
- The profile schema change carries effective dates, sensitivity and custody policy, and four
  locales of wording.
- The generator's repeat change is proven against the official design's slot positions through
  the real export builder.

## Implementation

If accepted: an L2 plan of about three hands, owned by LIFECYCLE.

1. The profile-schema facts, with typed records, custody and wizard or CLI entry.
2. The export generator's premises repeat semantics and regenerated M840 layouts.
3. The producers over the stored facts, the export round trip against the official design, and
   `test_every_cited_producer_key_is_resolvable` turned green with no refusing stubs.

The accepted 2026-08-25 ADR's reopening predicate is satisfied by this plan's proofs. It needs no
wording change: the reopening is the path it already describes. When this record is accepted, its
Implementation becomes the "explicitly authorized M840 slice" that ADR requires.

## Rationale

Producers need facts to read, and the facts need a persisted schema. No smaller change removes
the blank keys without either inventing values or writing refusing stubs, and both are ruled out.
The work is phase-2 scope with no persona row, so deferring loses no measured coverage now.

The author recommended deferral (option c) until phase 2.

## Decision

Accepted on 2026-11-14 with option (a), on the operator's approval of the proposed records
"if they do not diverge from delta keyed compacted registry definitions", as applied by PRIME
in RULINGS 2026-11-14 13:54. Conditions of the acceptance:

- The new facts belong to the profile schema, not the registry.
- Any Modelo 840 registry member the work adds is declared once, at its earliest edition. Later
  editions state only official differences and restate nothing.
- The premises repeat semantics regenerate only the Modelo 840 editions whose layout changes.
- `test_every_cited_producer_key_is_resolvable` clears only through real producers over stored
  facts, never through stubs or always-refusing producers.
- This authorizes the Modelo 840 slice only, as the explicitly authorized slice of the
  2026-08-25 deferral ADR. It does not start phase 2 in general.

Owner LIFECYCLE, after M322T and M322P, through an L2 plan built from the Implementation
section.

## Consequences

- If accepted: Modelo 840 can export with every cited key supplied from stored facts, the known
  red clears, and the two M840 source families reopen under the accepted deferral ADR's predicate.
- If deferred: the export keeps refusing with its typed code, the known red stays recorded with
  owner LIFECYCLE and this record as its reason, and no persona row changes.
- Reconsider when phase 2 starts, or when a persona with an IAE activity needs Modelo 840.
