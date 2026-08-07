---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e66757c56289773b8140a8e3878852d4366340d6a22e6d6c5dda8a91769f25ab'
step_id: 'S105'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Wire the classification criteria the existing rule table consumes, refusing rather than defaulting when any input is absent

## Scope

- `src/cadrumo/application/ledger`

## Description

- Assemble the criteria record from the landed producers: the classifier input
  envelope, the supply-nature axis, and the establishment resolver.
- Accumulate every unestablished input rather than short-circuiting on the first.
- Refuse when any input is absent, and name the authority that would settle it.
- Call the single rule table, adding no second decision surface.

## Outcome

The rule table has always been complete and was never reachable: its criteria
record was constructed nowhere in production — only in its own docstring
example and in tests — so no real document ever met it. It now has a producer.

**The producer refuses far more often than it answers, and that is the
deliverable rather than a limitation.** Replacing an unreachable classifier with
one that answers on incomplete evidence would be the worse product: the gap
stops being visible and starts being a number on a filing. So every input is
either established or named as missing, and each refusal states which authority
would settle it.

Two authorities are absent by design.

**Registration needs VIES.** A printed VAT identifier establishes a taxable
person, not a valid registration, and the registered status is the trigger for
the intra-community supply exemption. Bridging them would zero-rate a taxable
sale on evidence nobody verified.

**The Spanish territory needs sub-national evidence.** A country code names the
State while the IVA territory inside it stays undetermined, and Spain holds
three the law treats differently. A domestic pair therefore contributes nothing
on that axis. Defaulting it to the mainland would be the
restrictive-provision-as-default shape this repo names explicitly: it silently
captures the Canarias, Ceuta and Melilla population the rule does not govern.

Both are settleable by an explicit operator assertion, which is the sanctioned
path until those authorities exist. **An assertion is the operator's claim made
knowingly; a default would be ours made silently**, and that difference is the
whole reason the assertion parameters exist rather than fallbacks.

Only the general services kind is reachable from printed evidence. The
specialised kinds — land-related, passenger transport, the reverse-charge
sub-kinds — each change the legal answer and none is established by a document
saying it supplies services, so none is inferred.

Gaps accumulate rather than short-circuit: an operator facing four missing
inputs learns all four at once rather than one per attempt.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_classification_assembly.py -m unit -n0 -p no:randomly
    13 passed in 1.06s

Thirteen collected, thirteen ran, none deselected.

Re-run against **exported HEAD content alone**, together with the S100 envelope
it consumes, so the claim is about committed code rather than the shared tree:

    git archive HEAD | tar -x -C <scratch>
    PYTHONPATH=<scratch>/src ... pytest <both suites> -m unit -n0
    25 passed in 2.49s

One mutation per non-negotiable constraint, from a plugin outside the repository:

    bridge_printed_id_to_registered  -> 3 failed, 10 passed
    default_spain_to_mainland        -> 2 failed, 11 passed
    answer_on_incomplete_evidence    -> 6 failed, 7 passed
    refusal_without_a_remedy         -> 1 failed, 12 passed

**The positive control is the one that makes the rest mean anything.** Every
refusal test would pass equally against a producer that could never assemble
anything — which is precisely the state this Step exists to end. So one test
supplies complete evidence, assembles, reaches the table, and asserts the
verdict is the intra-community supply category. Without it, "the classifier is
now reachable" would be an unmeasured claim.

## Notes

**Two defects the build surfaced, both mine, both found by running rather than
reasoning.**

The criteria model requires a Member State whenever a residency is `EU_MEMBER`,
which the first assembly did not establish at all — an input silently absent
rather than refused. It is now resolved from the printed country code and
refused when that code names no Member State the rate schedule carries.

Then the Member State resolution failed on well-formed input because the enum's
tokens are **lower-case** and the normalisation upper-cased them. Two guesses
about a closed vocabulary, both wrong; printing the enum's actual members
settled it in one call. A country code is exactly the kind of value where a
case convention feels obvious and is not.

**Not built, and reported rather than absorbed.** Where a mapping needs a
place-of-supply branch, that branch belongs to S98, which is not built. Nothing
here invents one: the assembly supplies the axes the table already consumes and
stops. A guessed mapping on a rate-bearing surface is the most expensive wrong
thing available on this seam.

The confirm surface is untouched — it is held by another lane, and this Step did
not need to reach it.

No model was loaded, pulled, or contacted, and no network authority was added.
VIES remains deliberately absent.
