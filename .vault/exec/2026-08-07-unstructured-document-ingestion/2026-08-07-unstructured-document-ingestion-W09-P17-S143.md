---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b9032f7a31345df306270982862f862234b4fbfdba920d52f419f2a0734191e3'
step_id: 'S143'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Surface a populated postal code that is not five digits as a draft discrepancy, since the free-text grounder passes an address blob through verbatim into the draft and the operator payload where the surface labels it a postal code. Not a safety defect because the domain resolver returns nothing for it rather than the mainland, and the grounder must stay permissive because dropping the value would destroy the anchor the operator reviews. Add the check at the layer that already owns deterministic read-time findings rather than a second copy of the rule upstream of the domain authority

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add a `POSTAL_CODE_UNREADABLE` discrepancy kind and an
  `UNDETERMINED_ESTABLISHMENT` block reason, the latter forced by the gate's
  import-time totality assertion over the kind enum.
- Add `_postal_shape_finding.py`: per party, report a populated postal code the
  domain resolver cannot read, but only where the printed country did not
  already settle that party's territory.
- Enrol it in `DETERMINISTIC_CHECKS` as `postal_code_shape`, so it reaches the
  structured reader as well as the semantic one.
- Map the new kind in `BLOCKING_REASON_BY_DISCREPANCY_KIND` and extend the
  checks-run stamp's anchor assertion.

## Outcome

The check asks the domain authorities and restates neither rule: readability is
asked by handing the code to the Spanish postal resolver and seeing whether it
answers, and whether the country already settled the territory is asked of the
country resolver. A second spelling of "five digits" upstream of the authority
that owns it would have been the weaker copy.

The finding quotes what the field actually holds. An operator told only that a
postal code is invalid learns nothing they can act on; one shown the printed text
can see an address line landed in the wrong slot and read the real code out of
it. This is why the permissive validator was right to keep the value: dropping it
would have left a blank field and nothing to correct against.

**The scoping is the substantive decision, and it was forced by a property of
the layer.** Every discrepancy kind blocks confirmation by construction — the
gate refuses to import if a kind is unmapped, and there is no advisory tier. A
literal reading of the row, reporting any populated code that is not five digits,
would therefore have refused confirmation on every correctly printed British,
Dutch, Irish or Canadian postal code: a large and entirely legitimate population,
blocked for no gain. That is the alert-fatigue failure this codebase already
names elsewhere — a check firing mostly on documents that are fine teaches an
operator to clear it unread, and is then worth less than nothing on the one
document that mattered.

So the question asked is not whether the code is five digits but whether its
being unreadable costs anything. The postal code is sub-national evidence,
consulted only where the country did not settle the territory alone. A party
whose country resolves is already established. Spain deliberately resolves to no
scope, and a party with no printed country is unsettled for the plainer reason;
those two are exactly the parties whose code was load-bearing.

**What the row asked that this excludes:** an unreadable postal code on a party
whose printed country already settles its territory. Those are reported nowhere,
deliberately, because the value was decorative for the establishment question and
no operator action follows from it.

**On the country field, argued rather than left open.** No shape check is added
for it, because a country name is free text by nature and there is no shape rule
to apply — a name is whatever the issuer's language prints. The failure that
matters there is different: a printed name outside the bounded vocabulary
resolves to nothing and the party silently loses its country rung. That is not a
shape problem and a shape check would not find it; it is a vocabulary-coverage
question, and reporting it belongs beside the vocabulary rather than here. Left
out of this change and stated rather than assumed.

## Verification

The new suite, thirteen cases over the real check and the real domain
authorities:

    uv run --no-sync pytest -n0 -q -p no:randomly
      src/cadrumo/application/ledger/tests/test_postal_shape_finding.py
      -m "unit and not external_tool and not os_keychain and not resident_service"
    13 passed in 2.59s

Both lanes over the owning suites, excluding one peer module whose brand-new
import of an unlanded facade export interrupted collection:

    uv run --no-sync pytest -n0 -q -p no:randomly
      src/cadrumo/application/ledger/tests src/cadrumo/core/tests
      src/cadrumo/entrypoints/cli/tests
      -m "unit and not external_tool and not os_keychain and not resident_service"
    19 failed, 2639 passed, 2991 deselected in 204.44s (0:03:24)

    (same paths, ledger and core)
      -m "integration and not external_tool and not os_keychain and not resident_service"
    1 failed, 21 passed, 1918 deselected in 77.85s (0:01:17)

**None of the twenty failures is this change's.** They were triaged against a
clean tree extracted with `git archive HEAD`, run under the same interpreter:
every failing unit module reproduced there untouched, and the one integration
failure is a peer's signature change to the cloud-consent survey, a function this
change does not reach. The single failure this change did cause — the checks-run
stamp's anchor assertion, which passed at HEAD and failed here — was the enrolment
working as designed and is fixed in the same commit.

Mutation-proved in three arms at plugin module scope, each carrying **its own
positive control**: a banner proves the plugin imported, not that the patch
reached the callable the test invokes, and a single-target mutation has no
sibling result to contradict it. Each arm recorded whether its replacement was
actually invoked and the session refuses to let an unexercised mutation read as
coverage.

Silencing the check reddened the enrolment and blocking tests. Removing the
country gate, so every unreadable code fires, reddened exactly the two
anti-noise tests — the property nothing else pins. Examining only the supplier
reddened the three customer-side tests. All three positive controls confirmed
invocation.

## Notes

The silencing arm reached only the two tests that route through the shared
deterministic list; the other eleven bind the check function directly at import
and kept their own reference. That is a property of how those tests are written
rather than a gap in the gate, and it is recorded rather than presented as
broader coverage than it is.

The row's scope names the ledger package. Two core enums had to be extended as
well — the discrepancy kind and the block reason — because the kind enum lives in
core and the gate refuses to import when a member is unmapped. Not scope creep so
much as the shape of the declaration the row's check has to join.

The change also required deciding that a new finding blocks confirmation, since
the layer offers no advisory tier. That decision is argued in the Outcome above
rather than left implicit, because the row described the underlying issue as not
a safety defect and a blocking instrument reads as a stronger claim than that.
