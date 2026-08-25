---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c0ba4b6160de871f015122d628b0c56599f96e85784e147c3fb62a0a2b9ea809'
step_id: 'S34'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Correct the three sites that ranked a legal provision in the DOC band above the modelo and casilla cards it grounds, and gate the agreement between a record's stamped weight and the class it displays under

## Scope

- `dev/docs/terminology/ and docs/_static/cadrumo-docs.js`

## Description

- Give the legal record kind its own display class beneath casilla instead of aliasing it onto the user-documentation band, across the enum, the weight ladder, the derivation authority, and the shipped reader's closed set, label map, and full-text band rank.
- Correct the per-kind projection that hard-coded the same alias while documenting itself as derived from the one class table.
- Stamp a legal record's ranking weight from its own band rather than the user-documentation band.
- Gate the agreement between the two ranking authorities, and between a record's stamped weight and the class it is displayed under.

## Outcome

The legal kind was aliased onto the user-documentation display class, whose base weight tops the ladder. Every one of the 599 projected provisions therefore outranked all 6377 casilla rows and every modelo card, permanently and regardless of query. Measured before the fix: a `modelo 390` query returned its own modelo card at rank 5 and its casilla card at rank 6, behind four legal records.

The alias lived at three sites, and each was a separate authority that had to be corrected on its own:

- the derivation that assigns a record its display class;
- the per-kind projection used when reweighting against sweep relevance, whose own comment claimed it could never drift from the one declared table while it hard-coded the alias;
- the projector that stamps the shipped ranking weight, which is the one that actually reached the payload.

Because the third site was corrected last, the corpus briefly shipped records labelled as legal while still carrying the top band's weight - the label and the sort order disagreeing. The emitted corpus now measures legal at 0.75 against casilla at 0.8, so a casilla card outranks a legal provision for every record in the corpus.

The general defect is that each projector hard-codes a class literal that nothing ties to the class the derivation later assigns the same record, so a browser test built from an explicit display class cannot observe the divergence. Both new gates target that seam rather than the individual values.

## Verification

    uv run --no-sync pytest dev/docs/terminology/tests/test_unified_record.py -n0 -q
    14 passed in 133.03s (0:02:13)

The four browser ranking gates, which drive the shipped reader against a real Pagefind fixture index:

    uv run --no-sync pytest dev/docs/tests/test_palette_ranking.py -n0 -q
    2 passed in 124s

    uv run --no-sync pytest dev/docs/tests/test_search_page_inline_ladder.py dev/docs/tests/test_search_page_fulltext_class_ranking.py -n0 -q
    2 passed in 152s

Both new gates were mutation-proved from outside the repository, so no tracked file was edited to run the proof. Re-introducing the alias in the per-kind projection:

    ladder: casilla=0.8 legal=1.0 cli=0.7 -> RED=True
    agreement: derived=legal projected=doc -> RED=True

Re-stamping a real projected record with the user-documentation band, which is exactly what the third site emitted:

    healthy: class=legal weight=0.75 expected=0.75 PASS=True
    mutated: class=legal weight=1.0 -> RED=True

The corrected corpus measured through the real projections:

    legal   n= 599 class={'legal'}   weight={0.75}
    casilla n=6377 class={'casilla'} weight={0.8}
    CASILLA OUTRANKS LEGAL: True

## Notes

Full-corpus verification through the built site is not part of this record. The full documentation build fails on 588 CLI sequence golden divergences across 22 pages, none of them owned by this step: the diverging fields are content-addressed identifiers and calculation outputs shifting under concurrent registry work. Refreshing those goldens would bless behaviour this step has not verified, so they were left untouched and the build failure is reported rather than worked around.

The step is verified against the emitted corpus and the browser gates instead. Re-running only the index and record-injection pass over the existing built HTML, which needs no documentation build and so never reaches the failing gate, is the outstanding route to a full-corpus check.

An earlier attempt at that pass aborted on a half-landed refactor in a neighbouring package, where a symbol had been removed from its module while the package facade still exported it. The committed tree was intact, so the working copy was left alone until the window closed on its own.

The originating step for the legal record kind is marked complete and specifies injecting the kind beside the existing kinds with declared weights. The weights it declared carried this defect, so that step was delivered narrower than its text reads.
