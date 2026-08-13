---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:d3b134777ba79f6463616aa7a00062e925fe80dd284f781bdf2bb11fa3ce4161'
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

**Third control, and the one that closes the question (2026-08-13).** The first
probe snapshotted the page 1.5 seconds after submitting, which was too fast to
rule out an AJAX-rendered listing — this sede's expedientes walker retries
`content()` eight times precisely because AEAT's AJAX races the snapshot, so the
method was genuinely open to that objection.

Re-run with the objection taken seriously: poll for a `table` element once a
second for twenty seconds, then wait for `networkidle`, with every request
traced. Result: no table at any point, `networkidle` reached, and the only
request to the consulta endpoint after submission is the form POST itself. The
remaining traffic is stylesheets, a sprite, a framework bundle and Google Tag
Manager. **There is no data call.** The page AEAT returns is complete when it
arrives and contains no listing.

Three independent controls now agree that the register is empty for this
taxpayer rather than unreachable: an invalid NIF draws AEAT's retrieval error so
the form processes; the notifications surface renders three populated tables in
the same session so the session and browser can render rows; and no late render
or background fetch exists to be waited for. The investigation is exhausted, not
abandoned.
