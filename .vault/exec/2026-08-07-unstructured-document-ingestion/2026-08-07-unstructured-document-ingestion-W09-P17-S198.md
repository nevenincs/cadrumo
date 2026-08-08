---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:9aaaa0c42d21574ced91119b6c013ef6c03f01603ef048b9bd2659dfe1464a3f'
step_id: 'S198'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec W09.P17.S198

## Scope

- `src/cadrumo/application/ledger, dev`

## Description

- Search semantically for the co-location resolver and the measurement harness before writing anything, then confirm the partition rules with a targeted read of the production module.
- Establish that the in-tree evidence corpus cannot answer the row's question, and find the population that can.
- Promote the printed-excerpt authority to the ledger facade, a precondition of the measuring change rather than a follow-up.
- Add the ceiling measurement to the existing ingestion measurement harness rather than starting a second one.
- Take every anchor from an authored source and every verdict from the production partition, so no part of the figure is derived from the reader being scored.
- Give each unpartitionable document a measured reason, and add a population whose emptiness is the assertion that the reason still explains the corpus.
- Split the instrument's controls onto the unit lane and the corpus figure onto the integration lane, and record which of the two carries which claim.

## Outcome

The measurement is a CEILING rather than an observed rate, and that is the row's constraint honoured rather than worked around. An observed rate scores the model's quoted headings, which means scoring a reader against a truth derived from that same reader. So every anchor here comes from an authored source and every verdict from the production partition itself. The question the figure answers is therefore "could a PERFECT reader partition this document at all", and its answer is a property of the document. A perfect reader is an upper bound on every real one, so a document failing here cannot be rescued by a better prompt, a larger model or a second pass, and the figure cannot rot as the reader changes.

The in-tree evidence corpus turned out unable to answer the question, which is worth recording because it looks like the natural population. It holds four documents of real provenance. Three reach the prose path and none of them transcribes on host: two are images, and the third is declared in its own sidecar as derived from the first, so the distinct count is two rather than three. The fourth transcribes but probes to an embedded-XML shape and routes to the structured reader, which never reaches co-location at all. Reading the two distinct documents directly settles it further: one is a blank letterhead form with no recipient block filled in, the other a 1906 bill of lading carrying no tax identities. Neither is a two-party invoice. A fraction over that population would have been a number with no content.

The population that can answer it is the external pinned corpus the harness already owns: 302 documents, of which 48 carry an authored reference transcription, of which 28 carry an authored identity for both parties. That 28 is the honest denominator. The other 20 are excluded rather than scored zero, because a document with no authored truth has no rate rather than a low one.

**The ceiling is 0 of 28**, scored against key sha256 `e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593`. Not one document in the measurable population could be partitioned by any authored anchor pair. Every one of the 28 fails for the same measured cause: both anchors land on the same line. The reason is the two-column invoice header, issuer left and recipient right, which a reading-order text extractor emits as one line carrying both parties. Both candidate anchor kinds collapse together, the labels onto one line and the names printed under them onto the next, so two anchors yield one zero-width span and the partition is empty by design. The resolver's own docstring anticipated two headings printed on one line as an edge case; on this corpus it is not an edge case but the entire population.

That answers the row directly. The resolver landing is not the hole closing, and the distance between them is the whole hole: on the measured corpus the bar is not merely rarely cleared but structurally unclearable, and no improvement to the reader moves it. The failure direction remains safe, since unresolved keeps the interim advisory, so nothing is wrong today and nothing announces it either.

## Verification

The instrument's own defect came first, and finding it changed the result's meaning. The reason attached to a failure was originally inferred: both anchors located plus an empty partition was read as "they must share a line". That is a fall-through, and it would relabel every future cause as the current one, so a population that is 100 percent one reason produced that way is a fact about the instrument rather than about the corpus. The reason is now derived from the two line indices, and a separate population carries the case where both anchors sit on different lines and the partition is still empty. Its purpose is to stay empty; a member means the shared-line reading has stopped explaining the corpus and the figure must be re-derived before it is quoted again.

Mutation proof, from a plugin resident outside the repository. It rebinds by object identity across every loaded module after the first attempt patched only the measurement module while the test module held its own import and went on calling the real function.

    CEILMUT_MODE=blind     -- the partition can never see a region
    [ceilmut] RUNG 3: (stacked, two-column) (True, False) -> (False, False)
    3 failed, 25 passed, 13 deselected

    CEILMUT_MODE=credulous -- the partition sees a region everywhere
    [ceilmut] RUNG 3: (stacked, two-column) (True, False) -> (True, True)
    3 failed, 25 passed, 13 deselected

    CEILMUT_MODE=guess     -- the line lookup always answers line 0
    [ceilmut] RUNG 3: _line_of(absent)=0
    2 failed, 26 passed, 13 deselected

Under `blind` the positive control reds and the not-yet-explained population actually fires, which proves it is a reachable tripwire rather than dead code. Under `credulous` the negative control reds. Under `guess` a document whose anchors are not printed at all is mislabelled as sharing a line, which is what proves the reason is measured rather than assumed.

**A limitation of the corpus-lane assertion, measured rather than suspected, and recorded in its own docstring.** It passed under all three mutations. With a true ceiling of zero, a partition mutated to answer "never" changes nothing, and one mutated to answer "always" satisfies every property asserted there because none of them pins a rate. So a green on the corpus lane states explainability and non-vacuity only. The claim that the instrument can tell a partitionable document from an unpartitionable one rests entirely on the unit-lane controls, which do red under both. Read together they are sound; read alone the corpus one would be coverage-shaped and empty.

Nothing pins the ceiling as a number. A tally encodes a moment, and the day a stacked-header document is added the ceiling rises and a gate asserting the current value would fail on an improvement.

    uv run --no-sync pytest dev/ingest_harness/tests -n0 -q
    28 tests ran; 13 DESELECTED by -m 'unit and not external_tool and not os_keychain'
    28 passed, 13 deselected in 2.41s

    uv run --no-sync pytest dev/ingest_harness/tests -n0 -q -m integration
    13 tests ran; 28 DESELECTED by -m 'integration'
    13 passed, 28 deselected in 2.47s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q
    1218 tests ran; 26 deselected
    1218 passed, 26 deselected, 16 warnings in 148.64s

    uv run --no-sync pytest src/cadrumo/tests/test_import_hygiene_gate.py -n0 -q
    19 passed in 120.07s

    uv run --no-sync ruff check / ty check <changed modules>   All checks passed!

## Notes

The measurement needed the printed-excerpt authority, which the co-location module's own docstring already cross-references as a public symbol while it was in fact private. Promoting it was a precondition of the consuming change rather than a follow-up, and it is a genuinely shared primitive rather than a single caller's reach: the module that documents it calls it the one authority for whether a region prints a given form. Promoted at all three facade sites in one change, with the import-hygiene gate green afterwards.

The measurement was added to the existing ingestion measurement harness rather than to a new package. That harness already encodes this row's discipline in its own docstring: no figure without the key it was scored against, no accuracy over documents with no authored truth, every denominator re-derived from the key rather than inherited from prose. A second measurement home would have been a duplicate authority.

Readings are HEAD. A sweeper again committed part of this Step's working copy mid-flight, taking the facade promotion, the harness wiring and a first version of the measurement module; the measured-reason correction, the type widening, the unit-lane controls and the corpus-lane assertion were committed under this Step's own explicit pathspec. Both were confirmed present at HEAD before this record was written. The ledger facade file is left uncommitted in the working tree because its only remaining difference is line-ending churn on two lines belonging to another lane.

The three draft-to-payload parity failures reported against the previous Step are no longer failing; that lane's payload half has landed.

Both lanes are covered for the harness package. The ledger suite reading is the unit lane only.
