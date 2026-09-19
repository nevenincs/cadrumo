---
tags:
  - '#audit'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:3dcab5bd91a1116cd834e4e873efb52551431721a2b3a3f9841ddb271c8dd352'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# `minimo-descendientes-eligibility` audit: `Art. 81.1 maternidad connect review: two confirmed over-grants`

## Scope

Independent review of the three commits that connected, derived and windowed the Art.
81.1 deducción por maternidad: the operator's declared months reaching casilla 0611, the
child condition routed through the mínimo predicate, and the adopción clause given its
own date-scoped three-year window.

Verdict was REVISION REQUIRED. The architecture was upheld in full — routing the child
condition through the ordinary-eligibility predicate, sharing one reconstruction of the
family record between the mínimo aggregate and the deducción, and refusing rather than
reconciling the calculate flag against the declared records. The defects are two missing
narrowings inside the month window, plus an operator surface that has gone stale against
the law the third commit landed.

Two properties of the review method are worth recording, because they are what produced
the findings. Every critical was confirmed by EXECUTING the shipped predicates against
constructed cases, not by reading them. And the grounding was taken from the bundled AEAT
manuals across three campaign years, deliberately not from the per-article normative
excerpt, which is a two-vintage hybrid and is the subject of its own Step.

## Findings

### union-grants-pre-entry-months | critical | The two-limb union grants months preceding the adopción, in which the child was not yet the filer's

The under-three limb runs from the BIRTH month for every relación, including an adopted
child, so unioning it with the entry window reaches months before the entry event.
Confirmed by execution: a child born 2024-01-10, adopted with inscription 2024-10-05,
twelve declared months, filing year 2024, is granted twelve months and 1.200 € against a
correct three months and 300 €. A second case born 2023-03-04 and inscribed 2024-06-01
yields twelve against a correct seven. Over-grant of 900 € and 500 € respectively.

The manual states the month-of-birth rule the code implements specifically for hijos por
naturaleza, while the amount generally accrues over the months of the period posteriores
al momento en el que se cumplen los requisitos, in relation both to the beneficiaries and
to the children giving rise to the deduction. For an adoptee the clock starts at the entry
event.

The case offered as the union's justification does not support it, and this is the part
worth carrying forward. The claim was that an infant adopted in October has neither limb
reaching twelve, so only their union gives the right answer. Executed, that infant's
under-three limb IS twelve, and the test nominated as proof asserts exactly that on its
own first line — so it demonstrates that the union equals the maximum and proves nothing
about the union. A search for the shape where the union genuinely exceeds the maximum
found exactly one: a year containing both the anchor month and the third-birthday month.
Its single distinguishing month falls BEFORE the adoption. The union's only observable
effect over a maximum is therefore to grant a pre-entry month — it differs from the
alternative only where it is wrong.

### temporal-acogimiento-not-excluded | critical | A relación the statute names as excluded takes the full under-three deduction

The month resolver gates only on the ordinary-eligibility predicate, which is the Art.
58.1 test and deliberately assimilates temporal acogimiento. The Art. 81.1 population is
strictly narrower. Confirmed by execution: a child born 2023-05-01 under a temporal
acogimiento, cohabiting, with twelve declared months, filing 2024, is granted twelve
months and 1.200 € against a correct zero.

The manual is byte-stable on this across the served window: the deduction no resulta
aplicable in the case of nietos and other descendants by consanguinity other than
children, nor for acogimientos familiares simples, de urgencia o temporales, nor for
minors held under judicial guarda y custodia.

The case is fully representable and reachable through the documented entry flag, because
the temporal member exists on the relación axis precisely to give that carer a truthful
value. The exclusion test shipped alongside asserts only that the ENTRY WINDOW is zero for
an eight-year-old temporal placement; it never puts an under-three temporal placement
through the month resolver. This is the landing-one-half-of-a-pair shape, which this Phase
has now produced three times.

A related case is plausible rather than confirmed: a cohabiting grandchild under three is
mínimo-eligible under Art. 58.1 and the manual excludes it from Art. 81.1, but the axis has
no member for it, so it records as an ordinary descendant and takes twelve months. That is
a representability gap in the axis rather than a wrong branch in these commits.

### entry-window-unreachable-through-the-entry-surface | high | The window one commit landed is asked for by no operator-facing prompt

The only input feeding the window is the declared months fact, and every description of it
still scopes the question to a child under three — the wizard help, the calculate flag
help, and the entry grammar, which carries the bare range with no prose at all. An operator
answering the question as asked enters zero for a five-year-old adoptee and receives
nothing, so the window is reachable only by an operator who contradicts the prompt.
Under-grant up to 1.200 € per child, and it is the declared-versus-consumed asymmetry the
connect commit set out to close, in the mirror direction: the engine now consumes a figure
the surface never asks for.

### withheld-advisory-misdescribes-the-law-and-the-remedy | medium | The disclosure states a rule the campaign falsified, and directs the operator to alter a birth date

The advisory says the deduction reaches only a descendant under three who also holds the
mínimo por descendientes, which the date-scoped window falsified three commits later. It
closes by telling the operator to correct the birth date, the cohabitation answer or the
rentas figure. For the exact population the window added — an over-three adoptee with no
inscription recorded — the true gap is a missing entry date, and the advisory instead
invites the operator to alter a birth date to make the figure land. That is guidance toward
a false declaration on a filing input.

### flag-plus-withheld-records-is-silent | medium | Refusal and disclosure both miss when every declared month is withheld

The two-authorities refusal keys on the resolved pairs, which are already filtered to
eligible months after the predicate runs, and the advisories are then suppressed whenever
the calculate flag is absent. So a profile that declares months, has every one of them
withheld by the engine, and also supplies the flag reaches neither the refusal nor the
advisory: the flag wins silently. The same holds when the revision does not resolve the
ceilings, which also empties the pairs. The number produced is the operator's own explicit
flag so it is not itself wrong, but this is precisely the branch where being told the
records were rejected is the information they need, and it is the one branch where it is
withheld.

### refusal-remedy-names-a-verb-that-cannot-do-it | medium | Both remedies point at an append-only verb

The refusal and the advisory both tell the operator to clear the declared months using the
descendant add verb, which appends rows onto the existing set. There is no non-interactive
edit-by-index verb, and the paged door that can edit refuses on a piped host. The actual
route is a remove followed by an add re-declaring every other field of that row. For the
autonomous-agent operator this CLI is built for, the instruction as written is not
actionable.

### union-test-docstring-contradicts-its-own-assertions | low | The test nominated as proof of the union asserts the numbers that disprove it

The test docstring states that neither limb's own count is twelve and their union is,
immediately above an assertion that the infant case reaches twelve on the under-three limb
alone. Whatever the union fix lands as, this test needs replacing rather than adjusting: it
is currently green while blessing the 900 € over-grant.

### cleared-on-evidence | low | Four nominated or adjacent concerns proven sound, recorded so they are not reopened

The shared entitling-relación set is correct and reusable across both statutes: Ley 26/2015
provides that every reference to acogimiento preadoptivo is to be understood as referring to
the delegación de guarda para la convivencia preadoptiva, and the manual's own Art. 58.2
table lists them as one entry taking the increase independently of the minor's age. The two
enumerations are the same set under two vocabularies.

The shared first-entitling-event anchor is correct: where adoption follows a period of
acogimiento, the manual states the deduction runs for the time remaining until the maximum
three-year term is exhausted, which is exactly a minimum over the entitling dates rather
than a restart.

The under-three month boundaries are correct: the month of birth is counted whole and the
month in which the child turns three is not counted.

Tutela is correct as shipped: the manual gives the tutor the under-three limb only, and
tutela sits outside the Art. 58.2 entitling set so it opens no entry window.

## Recommendations

Clip the union to the anchor, dropping months strictly before the entry month for any
descendant carrying an Art. 58.2 entry date. The change degenerates to today's behaviour
for every non-entitling relación, and the replacement test must use the only shape where
the two candidate rules disagree rather than the shape that cannot distinguish them.

Declare the Art. 81.1 population as its own closed set in the core layer, alongside the
Art. 58.2 entitling set it must not be confused with, and gate the month resolver on it.
Whether the relación axis needs a member for grandchildren is a separate representability
question of ADR shape, not a patch.

Re-scope every operator-facing description of the declared-months fact to state both limbs,
or the window stays unreachable through the documented surface.

Refresh the withheld advisory to name the entry-date route rather than the birth date, and
point both the advisory and the two-authorities refusal at a route that can actually edit a
declared row.

Fire the withheld and ceilings-unresolved advisories even when the flag is supplied, and
refuse on the declaration itself rather than on the post-eligibility pairs.
