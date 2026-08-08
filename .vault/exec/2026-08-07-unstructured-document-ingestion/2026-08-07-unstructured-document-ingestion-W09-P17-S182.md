---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:59db07762e5665d9671881a637630055002cf9d4497d27de0b98ebc79978175f'
step_id: 'S182'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Narrow both country legs to the bounded vocabulary in one change

## Scope

- `src/cadrumo/domain/iva`
- `src/cadrumo/application/ledger`

## Description

- Add a bounded country vocabulary to the IVA establishment authority: the union of the printed-name registry table's alpha-2 column and the Member State catalogue, so Northern Ireland stays a member and Spain stays a deliberate territorial refusal.
- Narrow the country resolver from a shape check to a vocabulary match, so a well-formed code no country is allocated to fires no rung and returns no scope.
- Narrow the structured leg's alpha-2 branch against the same vocabulary, so a machine-stated code establishes exactly what the identical printed code establishes.
- Add the stated-code status axis distinguishing a catalogued code, an ISO user-assigned code that denotes nothing, and a code the vocabulary does not yet carry.
- Replace the resolver's module and function docstrings, which documented the retired shape-based default.
- Add the country vocabulary check to the deterministic check list, raising a typo finding for a reserved code and a catalogue-gap finding for an uncatalogued one, each quoting the string the field held.
- Add both discrepancy kinds to the closed axis and map them to the undetermined-establishment review reason.
- Replace the classification assembly's "not a well-formed two-letter country code" refusal, which would have described a perfectly well-formed unmatched code as malformed.
- Rewrite the resolver test that asserted the retired behaviour: its discriminating control used reserved codes as stand-ins for third countries, so the control shared the defect's premise.

## Outcome

The measured defect is closed at the authority and end to end. At the prior HEAD `XX`, `ZZ` and `QQ` each resolved to third country from both legs, and an issued goods invoice to a customer stating `XX` assembled cleanly and classified as `export_third_country_zero_rated`: an exempt operation derived from a string with no referent, with no refusal and no advisory. Those codes now resolve to no scope from every consumer, the assembly refuses with `customer_residency` named, and the operator is told which string was stated and whether the fix is theirs or ours.

The narrowing did not buy that by refusing real exports: a catalogued third country still assembles and still classifies as the export, and every Member State including Northern Ireland still resolves. The two advisory kinds are separate members of the closed discrepancy axis rather than one message with two wordings, so a document typo and a gap in the bundled vocabulary cannot arrive wearing the same sentence.

One deliberate departure from the governing ruling's wording, recorded rather than smoothed over: the ruling calls both signals advisories, and they are enrolled here on the deterministic findings channel, which the confirmation gate treats as blocking. The alternative channel is not wired to any operator surface, so an advisory placed there would have been invisible; blocking matches the sibling postal-code check, whose reasoning is identical, and the resolution the gate asks for is to supply the territory rather than to attest that a disagreement is acceptable.

## Verification

The defect measured at the prior HEAD, before any change:

    'XX' -> third_country | stated -> XX
    'ZZ' -> third_country | stated -> ZZ
    'QQ' -> third_country | stated -> QQ
    'TH' -> third_country | stated -> TH
    XX assembled= True [] ; category -> export_third_country_zero_rated

Owner-surface unit lane:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests -n0 -q -m "unit"
    1699 passed, 22 deselected, 15 warnings in 215.67s (0:03:35)

Integration lane over the same surfaces plus core:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests src/cadrumo/core/tests -n0 -q -m "integration"
    22 passed, 2598 deselected in 87.86s (0:01:27)

Mutation proof, from a plugin outside the repository restoring the shape-only resolver at module scope on the defining module and every consumer that bound the name:

    19 failed, 39 passed in 1.46s
    [mutation] patched callable invoked 34 times: ['AA', 'BR', 'DE', 'ES', 'JP', 'QM', 'QQ', 'TH', 'US', 'XA', 'XI', 'XX', 'ZZ']

The invocation count is the control rather than the banner: a single-target mutation has no sibling to expose a probe that never reached the patched callable, and a probe that missed it would look exactly like a gate that does not bite.

The structured leg holds its own membership check, so it passed under that mutation and was mutated separately with its own control:

    3 failed, 33 passed in 1.38s
    [mutation] patched callable invoked 13 times: ['AA', 'BR', 'JP', 'QM', 'QQ', 'TH', 'US', 'XA', 'XX', 'ZZ']

Type checkers and the generated reference:

    uv run --no-sync python -m dev.quality.types
    17 diagnostics in the establishment module, every one inside the pre-existing TOML indexers, none below the added code

    uv run --no-sync python -m dev.docs.apidocs scaffold
    Scaffolded 2 changed stubs, left 1351 unchanged, removed 0 stale stubs.

## Notes

The source half of this change reached HEAD through a sweeper commit rather than one of this lane's own, so only the two generated reference stubs were committed here, by explicit pathspec, after confirming the sweeper's tree matched the intended content byte for byte on all eleven source and test files.

Three repository-wide gates are red for unrelated reasons and were left alone: the AEAT route-literal centralisation gate over the outbound auth tests, the combined-period-string gate over tabular and financial fixture filenames, and three import-hygiene test-debt counters over the reading, consent and registry-loader lanes. None names a file on this surface.

A stale comment was found and deliberately not fixed, since it belongs to a neighbouring lane and predates this change: the establishment ladder's concordant-registration rung explains a null return by saying Northern Ireland is not an ISO jurisdiction the catalogue resolves, while `XI` has in fact resolved to the Member State scope both before and after this change. Every Member State was re-measured to confirm the rung itself is unaffected.

The bundled vocabulary carries fifty-eight countries, so any real jurisdiction outside that set now refuses instead of resolving to third country. That is the ruling's designed consequence and the catalogue-gap finding exists to make it fixable, but it is a live population and worth an owner: widening the vocabulary is the follow-up this change makes visible rather than closes.
