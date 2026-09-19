---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:3a7842a3be75d0c570f506d4ddc33dbac0a8b2751e9a7e545d6f13c4024dd4d5'
step_id: 'S13'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---
# Make the screen see the defect class the ADR is about

## Scope

- `dev/audit/legal_excerpt_vintage_screen.py`
- `dev/audit/tests/`

## Description

- Add an excerpt-side clause count beside the existing absent-clause count in `_classify`, so divergence is measured in both directions rather than one.
- Carry the new count on `Finding` as `clauses_extra` and render it as a second column on every comparable finding line.
- Add the exhaustive verdict `excerpt_carries_more` for the class `matches` was absorbing, and read the declared-vintage test before either direction so a deliberately historical excerpt is not reclassified as the defect.
- Take the excerpt-side count against the current provision's title AND body, so an article's own caption cannot register as text the excerpt adds when the extractor left the heading inline.
- Drop curator provenance annotations from the excerpt-side count by the same rule the oracle side already drops BOE's editorial note, recognised by the BOE document identifier that operative legal text does not carry.
- Fold the new class into the reconciled summary's comparable and diverging sums, with a line naming it as the direction a presence-only gate cannot express.
- Correct the `matches` docstring, which asserted there was nothing for a gate to catch off a measurement taken in one direction only.
- State the asymmetry, its title-inclusive bound and its provenance-drop bound in the module's MEASURED LIMIT prose.

## Outcome

The corrected split, run rather than re-derived. Population 324, reconciled: no_oracle 49, oracle_indeterminate 0, unresolved 0, misresolved 1, matches 88, excerpt_carries_more 4, vintaged 15, diverges_gate_fires 18, diverges_gate_green 149. Comparable 274 of 324; of 186 measured divergences the gate catches 18, of which 15 are vintaged by design and 4 are excerpt-side only.

The same run taken before a concurrent sibling re-pointed one catalogue entry read 325 screened with matches 93 and excerpt_carries_more 5, the consolidated-oracle stratum moving from 89 matching entries to 88. Five entries left `matches` on the change: four ordenes and RGAT article 25.

RGAT article 25 is the measured case the review named, and it classified `excerpt_carries_more` with zero current clauses absent and two excerpt clauses absent from current text: the empresarios/profesionales and personas juridicas limbs of the old apartado 2 list. It was reported matching before. Its article-endpoint capture concatenates two dated redactions, which is why it holds them, and the sibling row remediating that pile re-pointed the entry to the consolidated document mid-run, taking it out of the screened population. The proof was therefore re-anchored on the two bundled documents rather than on whichever entry cites them.

RD 439/2007 article 115 also carried one excerpt-side clause and is an artefact, not a finding: the clause is a curator's stamp naming the consolidated document and its redaction vintage. It is distinguished by the provenance rule and stays `matches` at zero in both directions, so a correctly transcribed excerpt does not share a worklist with a surviving repealed clause.

Verified: the corpus-pinned controls still resolve opposite ways. LIVA article 163 octiesdecies matches with zero in both directions; LIRPF article 81 diverges at 15 of 15 absent plus 3 extra; LIVA article 122 diverges with the gate firing. Totals reconcile at every stratum and the summary still refuses a split that does not add up.

Proven to bite by two deliberate breaks, each a runtime rebind from outside the repository with nothing under `src` or `dev` edited. Making every clause look like provenance turned RGAT article 25 back into a zero-extra match and reddened the superset control. Making the provenance stamp unrecognisable turned RD 439/2007 article 115 into a false `excerpt_carries_more` and reddened the artefact control. Both restored.

Gates: the 49 tests of the two screens pass sequentially. Ruff format and check clean; `ty` clean on the changed files. Full-tree collection clean at 25474 tests with no collection errors.

## Notes

Landed in one commit with the sibling row that shares this file, because a catalogue-loader relocation must be atomic across both screens and the two rows' edits interleave in the same functions. Splitting them would have required a bridge state the relocation discipline forbids.

The corpus and registry suites were run sequentially and returned 75 failures and 6 errors, all outside the owner surface and none in `dev/audit`. Two causes, both peer-owned: concurrent registry writes during the run, which the loader itself diagnoses by refusing with a message naming the concurrent write, and pre-existing registry-data violations in the modelo 303 casilla fragments and the external-constants literal census. The working-tree change for this row touches only `dev/audit`.
