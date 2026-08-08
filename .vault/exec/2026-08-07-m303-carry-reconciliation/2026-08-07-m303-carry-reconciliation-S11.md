---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:391961411c3fd5b04d41dc0c6592661b6d901319b82369efb839ba97f17f47ec'
step_id: 'S11'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
# Establish a sound channel for recovering the filed result disposition before S05 through S08 are attempted, and record the two mis-readings that would otherwise satisfy their precondition falsely. FIRST trap. The persisted source metadata key aeat_tipo_solicitud is NOT the disposition. Its own docstring states it distinguishes an original filing from an amendment, so it is the original-versus-complementaria axis. The Spanish nouns tipo de solicitud and tipo de declaracion are near-identical and that confusion is the likely failure. SECOND trap. The justificante parser extracts only the two printed amounts, total_a_ingresar and total_a_devolver, and carries no disposition code at all. A present devolver amount identifies DEVOLUCION, but COMPENSACION and NEGATIVA both present with neither amount, and suppressing compensacion carry-forward turns on exactly that distinction, so an amounts-based inference cannot decide the case the refund gate exists to decide. Gate. The row names the channel that actually carries the code, or records that none does and that parsing the printed Tipo de declaracion is required, and a test proves COMPENSACION and NEGATIVA stay distinguishable through whichever channel is chosen rather than collapsing to one reading

## Scope

- `src/cadrumo/adapters/inbound/justificante/_extract.py`
- `src/cadrumo/domain/justificante/_schema.py`
- `src/cadrumo/core/_result_disposition.py`

## Description

- Confirm both traps the row names, tracing each to the code rather than to a
  docstring's claim about it.
- Enumerate the candidate channels and test each against evidence, using AEAT's
  own published facsimiles rather than the project's synthetic fixtures.
- Name the channel that carries the code and land a test proving the two
  collapsing cases stay distinguishable through it.
- Implement no recovery. This row is an investigation and its output is a named
  channel plus that test.

## Outcome

**Both traps confirmed, and a third found that is more dangerous than either.**

FIRST TRAP, confirmed. The persisted metadata key is not the disposition. It is
populated from cell index 1 of the declaraciones register grid as free text up to
128 characters, and the projection's own docstring states it is the one field
distinguishing an original filing from an amendment. So the axis is
original-versus-complementaria, exactly as the row says.

But the trap is deeper than the row states, and the extra depth matters. That
docstring is an interpretation, not a verified fact: the register test that
exercises the cell asserts only that the earlier and later filings of one period
carry DIFFERENT values, and its own docstring says "the fixture's exact wording
is not AEAT-verified and is never asserted literally". So this channel is not
merely the wrong axis; nobody has established what AEAT prints in it at all. It
cannot be the disposition channel, and it is not yet safe to call it the
amendment channel either.

SECOND TRAP, confirmed structurally. The parsed receipt record carries
``total_a_ingresar`` and ``total_a_devolver`` and no disposition field, and the
parser extracts only those two amounts. The row's reasoning holds exactly: a
populated devolver amount identifies a refund, but a compensación filing and a
negativa filing both present with neither amount, so the receipt collapses the
one distinction the carry-forward suppression turns on.

There is a further limit on this channel that no reasoning could have supplied.
Every justificante fixture in the tree is synthetic: a provenance census over all
60 sidecars returns ``synthetic_generated`` 60 times and ``real_corpus`` zero
times. So the receipt channel could not have been cleared by reading a bundled
receipt even in principle. A synthetic PDF reports what its generator wrote.

**THIRD TRAP, not in the row, and it is the one that would have shipped.** The
filed declaración render prints the election letters ``C``, ``I`` and ``D`` next
to their sections. They are pre-printed form furniture, present on ALL FOUR
bundled AEAT facsimiles, including the two that elected ingreso rather than
compensación. An implementation that recovered the disposition by finding the
letter would report the same disposition for every filing while appearing to read
the form correctly. This is the same shape as the M036 causa boxes: the printed
mark is positional furniture and the signal is which slot carries a value.

**CHANNEL VERDICT: the filed declaración render carries the code. The receipt and
the register row do not.**

The signal is not the letter but the populated amount casilla. Measured on the
four AEAT published facsimiles for M303 2024, where the resultado of casilla 71
and the amount in casilla 72 move together:

    2024-1T  resultado 71 = 3.288,00   casilla 72 empty        election: ingreso
    2024-2T  resultado 71 = -2.106,00  casilla 72 = 2.106,00    election: compensacion
    2024-3T  resultado 71 = 18.258,00  casilla 72 empty        election: ingreso
    2024-4T  resultado 71 = -2.226,00  casilla 72 = 2.226,00    election: compensacion

Casilla 72 is populated on exactly the two negative-resultado filings and empty on
exactly the two positive ones, and where populated it carries the magnitude of the
negative resultado. The render also prints ``Sin actividad`` as its own numbered
section at a different position from the compensación section, so a negativa
filing occupies a distinct slot rather than sharing one with compensación. That
positional separation is what keeps the two distinguishable here where the receipt
collapses them.

The mechanism to read it already exists and needs no new machinery: the modelo's
declaración extraction profile matches values by label-anchored regex, and it is
the insertion point. It does not target the election sections today.

**What is NOT yet available, stated as the specific named thing the deferred rows
now wait on.** CORRECTED after re-measuring: an earlier reading of this record
said no capture path fetches the copy and no parse of it is wired. Both halves
of that are wrong. The sede capture already downloads the copy as a
``declaration_pdf`` artefact and stores it through the artefact sink, and the
modelo's declaración extraction profile already declares that artefact kind as
accepted and names the declaración parser. The pipeline is built.

What is missing is narrower and further upstream than a capture. Casillas 72
and 73 -- the compensación and devolución election amounts -- do not exist in
the modelo revision at all. Loaded through the registry authority rather than
grepped from a fragment, the revision carries 129 casillas including 70, 71,
74, 109 and 111, and neither 72 nor 73. So the extraction profile has nothing
to target: the two label patterns cannot be added until the two casillas
exist.

The deferred rows therefore wait on a registry-authority change -- two new
grounded casillas -- and then the two label patterns. Not on a capture.

## Verification

    uv run --no-sync pytest src/cadrumo/adapters/inbound/declaracion/tests/test_result_disposition_channel_evidence.py -n0 -q
    15 passed in 11.78s

Mutation proof, with a plugin loaded from OUTSIDE the repository so no tracked
file was edited. The mutation substitutes the naive reading this record calls the
third trap: key the compensación signal on the pre-printed letter rather than on
the populated casilla.

    MUTATION HOLDERS: ['cadrumo.adapters.inbound.declaracion.tests.test_result_disposition_channel_evidence']
    STILL ORIGINAL AFTER REBIND: []
    5 failed, 10 passed in 11.61s

All four per-specimen discrimination assertions and the both-readings assertion go
red, which is what establishes that the suite measures the amount rather than the
letter. The plugin refuses with an explicit error when no module holds the target
name and reports the post-rebind set, so a no-op cannot read as a pass.

Provenance census behind the receipt-channel limit:

    provenance census: {'synthetic_generated': 60}
    total sidecars: 60
    real_corpus files: []

## Notes

The disposition enum carries seven members, not the five named in the dispatch
brief: the two cuenta-corriente codes and the domiciliación code sit alongside
compensación, devolución, ingreso and negativa. That does not change the verdict,
because the collapsing pair the row is about is still compensación versus
negativa, but a recovery keyed on a closed four-way reading would silently
misclassify a cuenta-corriente or domiciliación election.

One honest limit on the negativa side, stated rather than implied: none of the
four bundled specimens filed a negativa, so the test asserts the channel carries a
distinct POSITION for it, not that a ticked sin-actividad box has been observed and
read. Proving the value needs an AEAT specimen of a sin-actividad filing, which
the tree does not bundle. The test says so in its own docstring so a later reader
cannot mistake the shape claim for a value claim.

No recovery was implemented, per the row.
