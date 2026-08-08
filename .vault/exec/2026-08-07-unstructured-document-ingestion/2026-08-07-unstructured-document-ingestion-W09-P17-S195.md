---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:dc3bc3537e97581699b5a3da7e9b98ea5eaeb70b5bfe3a86380a0f1d080cc129'
step_id: 'S195'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Move the two country-vocabulary conditions onto the non-blocking advisory channel

## Scope

- `src/cadrumo/application/ledger`

## Description

- Delete `COUNTRY_CODE_UNASSIGNED` and `COUNTRY_CODE_UNCATALOGUED` from the draft-discrepancy axis, and record on the axis why the two conditions are absent rather than listed and exempted: membership on that axis IS blocking, since the confirmation gate refuses to import while a member carries no block reason.
- Drop the two rows from the gate's blocking-reason table, and state at the table where a deliberately non-blocking condition goes instead.
- Replace `_country_vocabulary_finding.py` with `_country_vocabulary_advisory.py`: same borrowed judgements, same two-kind split, now returning a typed `CountryVocabularyAdvisory` carrying each party's role, field, stated code, status and sentence, with a `by_status` projection so a consumer cannot merge the kinds.
- Retire the `country_vocabulary` entry from the deterministic check list, which is the blocking channel, and record in that module that every check enrolled there blocks.
- Promote `CountryVocabularyAdvisory`, `CountryVocabularyWarning`, `country_vocabulary_advisory` and `COUNTRY_VOCABULARY_ADVISED_STATUSES` through the package facade before the consuming CLI change was authored.
- Project the advisory onto the review envelope's typed notice channel as one WARNING notice per kind, under two distinct codes, with the stated code in the notice context and the text lines rebuilt from the notice itself so the two renderings cannot drift. No bespoke `result` field was added.
- Set both notice messages in all four locale catalogues through the locale CLI.
- Regenerate the API stubs for the module rename and stage only the two stubs naming this module.

## Outcome

An uncatalogued or ISO-unassigned country code is now reported and not refused. The distinction the operator acts on survives the move: a reserved code is a typo they fix off the page, an uncatalogued one is a gap only a registry commit closes, and the two arrive under separate notice codes with separate sentences.

Nothing was given up in the under-declaration direction. The refusal that prevented the silent zero-rating is the classification assembly's, not the review gate's: an unresolved country yields no `customer_residency`, the criteria do not assemble, and the export category stays unreachable. That assertion is carried unchanged and re-measured beside the new one.

The premise the plan step rested on was verified at HEAD before it was relied on, not taken from the brief: the review CLI does call the sibling attribution advisory.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_country_vocabulary_narrowing.py src/cadrumo/application/ledger/tests/test_checks_run_stamp.py -n0 -q -m unit
    37 passed in 3.38s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_country_cli.py src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_attribution_cli.py -n0 -q -m integration
    10 passed in 15.70s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q -m unit
    1 failed, 1100 passed, 22 deselected, 16 warnings in 207.40s (0:03:27)

The one failure is another lane's: `test_evidence_confirm_rate_derived_category` asserts a rate unregistered on the issue date resolves to nothing, and `domain/iva/_classification.py` and `_lookup.py` carry uncommitted peer edits. Nothing in it reaches the country axis or the confirmation gate. Both readings cover the `unit` lane only for the application paths and the `integration` lane only for the CLI paths.

Mutation proof, from a pytest plugin held outside the repository so no tracked file entered a mutated state. The plugin re-enrols a country check on the blocking channel, refuses to start unless the check list actually changed, and asserts before any test runs that an uncatalogued code now raises a confirmation blocker.

    [MUTATION] STATE: 'TH' draft raises 1 confirmation blocker(s)
    9 failed, 28 passed in 1.17s
    [MUTATION] patched check reached 10 time(s), emitted 9 blocking finding(s)

    1 failed, 4 passed in 10.02s

Reddened under mutation: every parametrisation of the no-blocker case, every parametrisation of the still-blocks postal control, the check-name stamp, and the CLI assertion that the shipped payload carries no blocker.

## Notes

The first draft of the non-blocking gate was vacuous and the positive control caught it. The confirmation gate reads findings off the draft; it does not run the checks. A bare draft therefore raises no blocker for any reason whatever, so "the country condition does not block" was true of the fixture rather than of the product. Both the application gate and the CLI fixture now stamp the draft through the real check list first, using the same copy the structured reader performs.

The locale scaffold reported both new keys as orphans on the first pass. The keys had been reached through a status-keyed table rather than written as literal arguments, and the scaffold discovers keys by reading literals out of the source, so it would have swept them back out. The projection now branches and each key appears literally at its call.

A sweeper committed most of this work under its own message while it was still being edited; the remainder landed under an explicit pathspec. The commits are recorded in the campaign's own log rather than here.
