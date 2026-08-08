---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:853bab518d6f2fe30b4a5064db84629b3315f2a1febcbc44f2f754b835f42166'
step_id: 'S230'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec W09.P17.S230

## Scope

- `src/cadrumo/application/ledger`

## Description

- Search semantically for the anchor haystack before writing anything, having recognised the row's description from prose read during an earlier Step.
- Reproduce the row's exact measurement at HEAD, against the same UBL document and the same value and element path.
- Establish that the remediation is already landed, find the commit that landed it, and sweep every call site rather than trusting one.
- Confirm the narrowed haystack is populated on every parsing route, since an empty one would unanchor everything while looking safe.
- Mutation-prove the shipped gate in both directions rather than certifying a row on a passing test nobody probed.
- Probe for a residual of the same family, and establish whether it is reachable.
- Write no code, because the deliverable was already in the tree and a second implementation of one concept is a mission-level defect here.

## Outcome

**The row's remediation is already landed, and this Step verified it rather than repeating it.** The defect is real and reproduces exactly as the row describes when the haystack is the record's serialization: against a UBL document carrying no country element at all, the value `ID` with a country element path grounds ANCHORED with anchor `ID`, because `ID` matches the `cbc:ID` tag. Against the haystack the code actually passes, the same call returns UNANCHORED with no anchor.

The fix is a parser-side helper returning every text node and no markup, joined by a NUL so two adjacent nodes cannot merge into an assembled value. Both production call sites already pass it; there are exactly two, both in the evidence-draft provenance builder, and the sweep found no third passing a serialization. The narrowed haystack is populated on every route that parses, including the embedded-PDF route which sets it separately from the standalone one, so there is no shape where the check degrades to an empty haystack. It landed in a sweeper commit, so authorship is not attributable from the history.

A regression gate for the exact reproduction was already present, together with a companion gate for the hazard the narrowing itself introduces: a Facturae party name is composed from three sibling elements, and joining text nodes on whitespace instead of a NUL would make that composed string appear in the haystack and anchor as though the document printed it. That refusal was a property of the raw-file haystack and is the thing a careless narrowing drops silently.

**What the row calls "the remaining way a country envelope can assert provenance it does not have" is narrowed rather than eliminated, and the difference is worth stating.** The markup route is closed. A substring route is not: against the same country-less UBL document, the value `ES` grounds ANCHORED, matching inside the VAT identifier `ESB12345674`, and `SL` grounds against a company suffix. The anchor search is boundary-aware only at numeric edges, which is a documented and deliberate acceptance elsewhere, but its consequence differs here — for the alpha-3 case it is an accidental hit on the very value being described, while this would be an anchor on an unrelated token.

Measured as unreachable on the structured path today, not assumed. Every country reader returns either its own element's text or nothing, and the provenance builder skips a field the record did not state, so no structured reader can emit a country the document lacks and therefore no envelope is built for one. **The guard is the parser, not the anchor check** — while the anchor check's own docstring claims it catches a reader that pointed at an element the document does not carry, which for a two-letter code it demonstrably does not. That is a live gap between a documented property and the behaviour, currently masked by a guard in a different module, and it is reported rather than fixed here because closing it is a change to the anchor search's matching rule and belongs to its own decision.

## Verification

Mutation proof from a plugin resident outside the repository, rebinding by object identity across every loaded module. Two directions, because the gate has to catch both the defect returning and the fix degrading.

    MARKUPMUT_MODE=serialization  -- the haystack becomes the whole decoded record
    [markupmut] RUNG 3: haystack 306 -> 3725 chars, carries markup=True
    FAILED ...::test_markup_cannot_ground_a_country_the_record_does_not_state
    1 failed, 23 passed in 8.49s

    MARKUPMUT_MODE=emptyhaystack  -- the haystack becomes empty
    [markupmut] RUNG 3: haystack 306 -> 0 chars, carries markup=False
    4 failed, 20 passed in 7.19s

The first is the gate doing its job precisely: the defect's return reds exactly one test, the one written for it, and nothing else. The second is the positive control, and it is the case a narrowing gate most easily misses. An empty haystack anchors nothing, which looks like the safe direction and would satisfy any assertion phrased as "this must not ground"; four separate tests that require a real country to ground DO red, so the suite cannot be satisfied by a check that has stopped checking. That control already existed in the suite rather than being added here.

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_path_country_codes.py -n0 -q
    24 passed in 8.47s

Reproduction of the residual, against the same document, through the same entry point: `ID` unanchored, `ES` anchored, `SL` anchored, `AC` and `ZZ` unanchored.

## Notes

No production code was written for this Step and none should have been. The deliverable was in the tree before the row was dispatched, with its gate, its companion gate and its call sites complete. Writing a second narrowing would have been a duplicate authority for one concept.

There was no exec record for this Step, so the three states the campaign warns about were indistinguishable from outside: delivered as specified, delivered narrower, and recorded-but-not-implemented. This record resolves it to the first, with the mutation evidence that the gate keeping it delivered has been made to fire.

The substring residual above is a separate finding and needs its own row. It is not a carry-forward of this one: this row asked for the haystack to be the text nodes, and it is.

The reading is HEAD for the parser and its gates, which are clean in the working tree. The evidence-draft module carries another lane's uncommitted work; the call site this Step verified was read from HEAD and is identical in both.

The unit lane only.
