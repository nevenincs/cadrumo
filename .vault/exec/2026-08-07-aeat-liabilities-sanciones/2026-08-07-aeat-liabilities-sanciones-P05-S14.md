---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:e11239dc45642545a0f9211adfeb956e3ead63f69191d527ed3a0eaca0427715'
step_id: 'S14'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# BLOCKED on the same specimen: write walk_deudas_consulta mapping the real DOM to Deuda rows, verified by a parse test against the captured fixture with sensitive fields never committed to the repo

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`

## Description

- Decomposed the consulta surface far enough to specify the walker.
- Wrote no walker: the row's verification gate is a parse test against a
  captured fixture, and no populated capture exists.

## Outcome

**DEFERRED CARRY-FORWARD. `walk_deudas_consulta` does not exist.**

The row asks for a DOM-to-`Deuda` mapping verified against a captured fixture.
No populated listing was reachable, so there is no row DOM to map and no fixture
to verify against. A parser written now would encode a guessed table shape
behind a test asserting the guess — the precise failure the module's own
fail-closed comment was written to prevent.

What the discovery DID establish, and what the eventual author inherits:

- The consulta is a TWO-STEP surface. The endpoint renders a NIF form; the
  listing exists only behind its submission, so the read needs a POST. The guard
  already declares that allowance, scoped to the consulta path alone.
- The surface is served as **ISO-8859-15**. Decoding it as UTF-8 raises
  outright; decoding it as Latin-1 silently mangles the euro sign, which is the
  column the listing exists to report.
- A retrieval failure surfaces as an error line naming the NIF in the avisos
  region, not as an HTTP status.
- The zero-state is a bare form re-render: no table, no "no existen" message.
  A parser must not read that as a parse failure, nor a parse failure as a
  zero-state.

## Notes

The charset and error-shape findings live here because they have nowhere else to
live until the walker exists. An author who does not read this record will
decode the page wrong.

A sibling failure mode is worth stating: the notifications reader on this same
sede returned a clean `row_count 0` against a populated inbox because one column
label differed by the word "de", and an unresolvable date made every row
unclassifiable. When this walker is written, it must distinguish an empty
register from a parse that bound nothing, and refuse rather than return zero.
