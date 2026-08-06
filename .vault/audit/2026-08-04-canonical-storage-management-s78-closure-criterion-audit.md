---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:f243070975f59d4b3be40008950303965634fa66b1029b0ad9d21a69edcad13a'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# `canonical-storage-management` audit: `what closing S78 would claim, and what the evidence supports`

## Scope

What claim closing `W03.P16.S78` would make, and whether the evidence on record
supports that claim or a narrower one. Audited at pin `1d18094002`. **This is not
a close decision and does not recommend one either way on the Step's own title
until finding 5 is settled.**

The question was posed as *"what would justify checking `S78`"*, given that the
closure statement's own element `5h` disqualifies the obvious evidence: four of
six classification dispositions leave no readable trace, so a clean scan is
consistent with every site having been classified and with none having been.
That framing is correct and it survives this audit. But it is not the first
question, because it presupposes something finding 1 shows to be false.

## Findings

### s78-does-not-gate-closure-by-the-plans-own-statement | high | The plan places S78's phase off the closure path, so the premise of the question is false

`S78` is the plan's single remaining unchecked Step — verified, one `- [ ]` row in
the whole document. But its phase is `W03.P16`, and the plan states in the
`W03.P23` phase description that the bulk test-migration phases `W03.P14` through
`P16` *"remain real drift-reduction work but are not on the closure path under the
operator's sharpened definition."*

So *"the campaign's last Step"* and *"the campaign's last closure obstacle"* are
two different things, and only the first is true. The sharpened criterion — every
path-**choosing** site enrolled — is assessed in the closure statement's criterion
element and is satisfied there. `S78` burns down incidental literals in tests,
which the operator's own correction explicitly separated from enrollment: a test
creating a file is not a production site producing one.

**This is the campaign's own silence-reads-as-coverage shape, inverted.** Elsewhere
a clean report was mistaken for a checked surface. Here a single open checkbox
reads as an incomplete campaign, when the document that owns the checkbox says
that phase was never on the path. **A progress count is an instrument too, and
"114 of 115" measures Steps, not closure.**

### the-step-specifies-a-method-the-burndown-did-not-use | high | Phase says per-package with per-package gates; execution was per-literal-band

The phase heading is *"incidental test literal burndown **by package**"* and its
description specifies the method and its verification together: *"one test package
at a time, each Step gated by the provenance gate **scoped to that package** plus
**that package's own suite**."*

The burndown was executed **by literal band** — `cadrumo.db`, `secrets`,
`iva-wallet`, `invoices`, the LLM trio, `live`, `runs`, `financial`, and a
thirteen-segment small-band tail. Bands and packages are different partitions of
the same corpus. A band sweep can be complete over literals while never producing
the artefact this Step asks for, because *"the provenance gate scoped to package X
plus package X's suite, for every X"* is not a by-product of sweeping literals.

The band approach may well have been the better engineering choice — a literal is
the unit a rename breaks, and the collapse-predictor work depended on band
framing. **That is not the question.** The question is whether the evidence on
record matches the claim the Step's text makes, and a Step closed under a
different method than it specifies is either a *recorded narrowing* or an
*unrecorded substitution*. Only the exec record distinguishes those, which is the
shape already established for `S114`.

**The independent read has returned and it confirms the divergence on every
axis.** A second auditor, reading only what exists in `.vault/exec/`, found: every
band's enumeration was a **raw literal grep** (`git grep -n '"<literal>"'` filtered
to test paths after the fact), never an AST path-composition scan, never a package
walk; **no band ran the Step's specified gate** — verification was `ruff check` plus
`pytest` over *the specific files edited*, and the provenance gate appears in the
one exec record only as a file being classified, never as a check invoked; and
there is **no record of a package-by-package walk anywhere in the feature**, the
only textual match being that exec record's own heading, which restates the Step's
title verbatim.

The single exec record under `W03.P16` covers a ten-file `cadrumo.db` batch and
describes its inputs as *"pre-identified"* — so even for the one band that reached
the vault, the enumeration method is **NOT STATED**; the record documents what was
done with a handed-off list, not how the list was produced.

### most-of-the-s78-work-never-reached-the-vault | high | The durable ledger is one exec record; the rest exists only in the relay chain

The second auditor's sharpest result was about its own work: **none of the band
sweeps it performed has a `.vault/exec/` record at all.** They exist as
SendMessage reports and task descriptions — the relay chain — not as durable
artefacts.

This directly refutes *"the ledger is complete"* as a closure argument, in the only
sense that matters for a closure decision. It is complete as a **conversation** and
nearly absent as a **record**: one exec record for a corpus of ten-plus bands. A
reader inheriting this campaign next month has the plan, this audit, the closure
statement, and a single ten-file exec record.

**And it makes the method-divergence question partly unanswerable from the vault
alone** — which is a second-order instance of the same failure. The `5h` finding
is that four of six dispositions leave no trace *in the tree*. This is the
same shape one level out: **most of the classification work left no trace in the
vault either.** The tree cannot answer whether `S78` is complete, and now neither
can the record, because the record largely does not exist.

### the-scope-field-and-the-denominator-describe-different-populations | medium | The Step names a scope one-tenth the size of its own stated denominator

The Step's scope field is `src/cadrumo/tests/` — the shared test-support package,
171 modules. Its denominator is *"roughly 108 files carrying path-valued overrides
and roughly 350 hand-rolled override sites."* Measured at pin `1d18094002` with
the AST path-composition scanner:

```
inside src/cadrumo/tests/   171 modules      28 undeclared hits   10 declared
whole test tree            2651 modules     353 undeclared      147 declared
```

The `~350` denominator matches the **whole test tree** (353), not the declared
scope (28). So the Step can be read two ways, and they are an order of magnitude
apart:

- **narrow** — burn down the literals in `src/cadrumo/tests/`, the fixture package.
  28 undeclared hits remain.
- **broad** — burn down ~350 override sites across all tests, using
  `src/cadrumo/tests/` fixtures as the mechanism. 353 undeclared hits remain.

Closing the Step commits to one of these and the text does not say which. Note the
two counts are produced by *this* scanner, which counts taxonomy segments used as
path-composition operands; the plan's original `~108`/`~350` were measured by an
unstated method at authoring time, so they are **not** a comparable baseline and
must not be differenced against these.

### the-burndown-moved-the-population-and-that-is-measurable | medium | Two instruments agree the corpus shrank; neither can show it is empty

Same scanner, two pins: **442 → 353** undeclared path-composition hits, with
declared pins rising 101 → 147. Independently, the coinciding-tail population was
measured falling **702 → 307** between two pins by a separate auditor and
instrument.

Two instruments, different definitions, same direction. This is real evidence the
burndown moved what it was meant to move, and it is the strongest positive
evidence available. **It is also evidence of progress and not of completion**, and
element `5h` explains exactly why no scan can upgrade it: the four unreadable
dispositions mean a residual of zero and a residual unexamined are the same
picture.

### the-residual-sample-argues-against-the-broad-claim | high | A sample of unclassified sites found roughly a quarter rename-sensitive

A random sample of sites the burndown did not classify was measured at roughly
**23% rename-sensitive, 61–212 sites**, taken after the ledger reported every band
swept. If that population lies inside the Step's scope, it directly refutes the
broad reading of the claim: the surface is not clean, and a quarter of what was
not looked at would break under the rename the campaign exists to make safe.

**This figure is relayed and is not reproduced by this auditor.** Two things about
it are unknown here and both are decisive: whether the sampled population falls
inside `src/cadrumo/tests/` or across the whole test tree, and whether
*rename-sensitive* means *not enrolled* or merely *would need editing*. A
rename-sensitive site that is a correctly-declared pin is resolved work, not
residual.

**This is the input that should not be skipped**, and it is the one that decides
the broad reading. It is recorded here as the open question rather than as a
count.

## Recommendations

**Do not close `S78` on the claim its title makes.** The broad reading —
*the test tree has no hand-rolled taxonomy literals* — is contradicted by 353
measured undeclared hits and by the residual sample in finding 5. The narrow
reading is closable on evidence but is not what the title says.

**The narrowest claim the evidence does support, stated in full:**

> Every literal in the enumerated bands was classified under one of six
> dispositions, each band's enumeration method recorded in its report; the
> path-composition population fell 442 → 353 in tests and 702 → 307 by an
> independent instrument; 28 undeclared hits remain inside the Step's declared
> scope and 353 across the whole test tree; **no claim is made that the enumerated
> bands exhaust the corpus**, because four of six dispositions leave no readable
> trace and no scan can establish exhaustion.

If the Step is closed, it should be closed on **that** sentence, in an exec record
that states the narrowing, names the method substitution in finding 2, and carries
the residual counts. A Step closed on a narrower claim with the narrowing recorded
is a decision; the same close without the record is indistinguishable from
abandonment.

**Before any close, write the exec records.** Finding 6 is the cheapest and most
valuable remaining action in the campaign and it does not depend on resolving any
of the others: the band sweeps that exist only in the relay chain should be
recorded, each naming its enumeration method (literal grep), its verification
(`ruff` plus `pytest` over the edited files), and its site list. That is a
transcription task, not an investigation. Without it, a close of any width rests
on a ledger a future reader cannot open — and the relay chain is the least durable
artefact this campaign produced, as four expired-premise incidents in a single
thread demonstrated.

**Two cheap measurements would change this assessment, and both should precede a
close on the broad reading:** resolve which population the residual sample drew
from and what *rename-sensitive* meant in it (finding 5), and decide which of the
two readings in finding 3 the Step means, since the answer changes the remaining
work by an order of magnitude.

**Separately and independently of all the above:** finding 1 means `S78` need not
be closed for the campaign to close on its criterion. Closing the campaign and
leaving `S78` open as recorded drift-reduction work is available, is consistent
with the plan's own statement, and does not require any of the above to be
resolved first. **That is the option the framing of the question concealed.**
