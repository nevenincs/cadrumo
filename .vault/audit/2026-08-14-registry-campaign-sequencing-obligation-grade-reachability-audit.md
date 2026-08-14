---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:237c07837aaa197af0a37d693933f827156a977337fdc1cc42f2b58db225a6b4'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
---

# `registry-campaign-sequencing` audit: `Obligation is law-derived but reads through the filing authority`

## Scope

One unresolved conflict, recorded because it is currently harmless and will not
stay that way. Determining whether a taxpayer is OBLIGED to declare Modelo 720 or
721 is a law-derived question answered before, and independently of, filing. It
currently reads through the validated registry authority, which now refuses at
load while filing capability is absent. The obligation question is therefore
unanswerable.

An operator ruling accepted this. The finding exists so that whoever wires the
missing surface resolves the conflict deliberately rather than discovering it.

## Findings

### obligation-unanswerable-not-unfilable | high | A gate one rung too high makes a lower-rung question unanswerable rather than unsafe

Obligation and filing are different questions with different answers and
different consequences. "This modelo cannot be filed" is a capability gap an
operator can see and plan around. "I cannot tell you whether you are required to
declare" is silence where a legal duty should have been reported, and Modelo 720
carries real penalties for non-declaration.

The threshold resolver originally built a filing-grade snapshot to read two
declaration-floor parameters. With every revision unattested, that made the
obligation question refuse. It was repaired to read the non-filing revision
inspection, and then made unanswerable again — for a different reason — when the
registry began refusing at load, because the resolver reaches the authority
through the resident resources handle.

The general shape is worth stating beyond this instance: **a gate placed one rung
above the question being asked does not merely inconvenience the caller, it
removes an answer the caller was entitled to.** Strictness and correctness are
not the same axis.

### exposure-is-latent-not-live | medium | Nothing reachable by an operator asks the obligation question today

The consumer chain was traced before weighing the conflict. The threshold
resolver is called by the foreign-asset redeclaration module, which is exported
from the calculations package facade and carries operator-facing locale strings
in all four catalogues, so it was built to speak to a user. Nothing under the
entrypoints tree imports it: there is no command, no verb, and no path from an
operator action to that code.

The penalty exposure is therefore latent. Nobody is being told the wrong thing
about a Modelo 720 obligation, because nobody can ask. That is what makes
accepting the conflict affordable today, and it is precisely what stops being
true when the surface is built.

### routing-around-the-authority-is-a-different-violation | medium | The available workaround trades one defect for another

Reading the compiler tier directly answers the obligation question — measured
working, returning the declaration floor with its attestation stamp. It was
deliberately not adopted for production.

Everything that legitimately reads at that tier today is authoring or
measurement tooling: the export generator, the coverage and worklist gates, and
test fixtures. The loader is a compiler implementation detail and production
paths are required to request through the authority. Putting a production
consumer on the compiler tier is not a smaller violation of the same rule, it is
a different one, and it would have been bought at the price of an explicit
exception to a directive that has none.

### notice-channel-does-not-reach | low | There is no envelope to carry an advisory to

Surfacing the attestation state belongs on the typed notice channel of the shared
CLI envelope. That channel does not reach the resolver: it returns a bare
mapping, its own consumer returns a frozen set, and neither carries a diagnostics
channel. With no command consuming either, there is nothing for an advisory to
attach to.

No second advisory mechanism was invented. The attestation fact is instead
carried on the threshold value itself, beside its legal and source references,
which is the same kind of provenance and the precondition for any later
surfacing.

## Recommendations

The threshold value now carries the review status of the revision its figures
came from, with a derived reading of whether that revision is operator-attested.
Keep it. It is provenance on a value rather than a disposition, it lets no gate
pass, and it is what the surface will need on the day it exists.

Neither option debated at the time is the right long-term shape, and the finding
should not be closed by choosing between them. **The authority should expose a
modelo-scoped, graded accessor**, so a consumer needing applicability-grade facts
for one modelo does not trigger whole-tree validation at all. That is the
authority-grade ladder completed rather than bypassed: production stays on the
authority, the filing gate stays hard, and a law-derived question is answered at
the rung it actually occupies.

The defect underneath all of this is that loading the authority eagerly validates
everything, which is also what pushed tooling down to the compiler tier in the
first place. Addressing it is real work and needs an operator decision before
anyone starts.

When a CLI surface is built over the foreign-asset obligation path, it needs both
halves in the same change: the graded accessor so the question can be answered,
and the attestation advisory so the answer carries the fact that its threshold is
unverified. A surface built with neither would answer from an unattested figure
silently, which is the failure this whole finding exists to prevent.
