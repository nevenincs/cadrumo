---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ab72f9a191bb6e5338736a95c5642ee1c613569337b734d0a186191d8c6f9bf1'
step_id: 'S215'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# RULED S186 by the coordinator. YES, follow the rename. The resolver's printed-country-name and printed-country-code parameters take a machine-read code from the structured path, so the name asserts typography that path never observed. This campaign already paid for that exact conflation once, when a derived value was treated as printed evidence and shipped a false anchor, and the rung itself was renamed ADDRESS_COUNTRY for the same reason. Consistency is not the argument. The argument is that the parameter name makes a provenance claim which is false on one of its two callers

## Scope

- `src/cadrumo/application/ledger`

## Description

- Rename the ladder resolver's `printed_country_name` and `printed_country_code` parameters to `stated_country_name` and `stated_country_code` on both public entry points and the shared helper in `src/cadrumo/application/ledger/_establishment_ladder.py`.
- Rewrite the parameter documentation to state what the rung actually observes, naming the printed and structured lanes as two ways a document states the same fact.
- Sweep the draft-side caller in the same module and the advisory caller in `src/cadrumo/application/ledger/_party_attribution.py`.
- Sweep the two test harness callers.

## Outcome

The parameter no longer asserts typography. A machine-readable document reaches this rung
through the same call, and its country element was never set in type, so the previous
name made a provenance claim that was false on one of the two callers. `stated_` is the
vocabulary this campaign already uses for a fact a document asserts without a typography
claim, so the rung's parameters now read the same way as the structured country lookup
they feed.

The rung enum member itself was renamed for this reason earlier, so the parameters now
agree with the member they resolve.

Deliberately not renamed: the domain vocabulary lookup that takes a printed country name.
Its input genuinely is a name as printed or stated in prose, which is a different fact
from the code the resolver returns.

## Verification

    uv run --no-sync pytest --collect-only -q
    22976/26990 tests collected (4014 deselected) in 60.03s

Run immediately before the rename, and again after, with the second run collecting 22983
against a tree that had taken another lane's new tests in between. No collection errors
on either side.

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_establishment_ladder.py src/cadrumo/application/ledger/tests/test_registration_concordance.py src/cadrumo/application/ledger/tests/test_party_attribution.py -n0 -q -m unit
    1 failed, 63 passed in 11.30s

The single failure is another lane's: it asserts a gap in the cross-industry parser's
country element which that lane has since closed, and it names no renamed symbol. Its
uncommitted fixtures were sitting in the tree at the time of the run.

## Notes

The rename did not land as one commit, and not by choice. A sweeping commit took the
resolver module out of the working tree between the edit and the commit, leaving the
branch briefly carrying a renamed signature and two callers still passing the old keyword
names. The callers were committed as soon as the split was detected, which is the state
recorded here; the atomicity the Step called for was lost to the sweep rather than to the
authoring.
