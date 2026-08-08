---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:28175ab8b6eb40c00339dec0970ab950a20a3ab43447e70a1780255ada2b11de'
step_id: 'S281'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Declare the field-name mapping between InvoiceDraft and the corpus key ground-truth vocabulary, since the two share only 7 names of the key 25 and the rest are the same concepts under different spellings - so a scored run reports 12 missed beside 15 undeclared and a probe recovered 9 of 10 concepts correctly under their other names - the mapping lives harness-side as declared data asserted against the corpus, counterparty resolves by counterparty_role as a rule rather than a rename, composite issuer and recipient score leaf by leaf so one wrong leaf cannot destroy a correct read, and key fields with no draft counterpart are reported as their own class never pooled into missed

## Scope

- `dev/ingest_harness`

## Description

- Add `dev/ingest_harness/_field_mapping.py`: the corpus-to-draft field map, declared as data.
- Keep the map free of transformation: `project_emission` moves values between names and does nothing else, so no value is parsed, coerced or normalised in transit.
- Resolve `counterparty_name` and `counterparty_tax_id` by the document's own `counterparty_role` as a rule rather than a rename, and drop the slot when no usable role is declared.
- Expand `issuer` and `recipient` leaf by leaf, so one wrong leaf cannot destroy a correct read of the others and the report names which leaf failed.
- Split the never-scored fields into two kinds, held apart by a named set consulted at all three branch sites.
- Add `validate_mapping_targets`: refuse a mapping naming a draft field that does not exist, and refuse a key field the table omits.
- Exclude the composite country leaf as a stated interim, named by `COUNTRY_LEAF_IS_UNSCORED_FOR_NOW` and pinned by a case asserting the note says INTERIM and carries its restoration condition.
- Add `dev/ingest_harness/tests/test_field_mapping.py`, asserting the table against the real corpus and the real draft model rather than a fixture.

## Outcome

The key and the product's draft name the same concepts differently. Measured over the whole pinned corpus rather than the pilot sample: only 7 of the key's 33 field names spell a draft field identically, so scoring by name credited 711 of 2873 non-null truth slots and booked the rest as misses. A pilot document scored 3 of 16 whose figures the model had in fact read correctly — a number about a dictionary, not about a reader.

The direction is that the instrument adapts to what it measures: the key is the external authority and the product's vocabulary is a domain decision grounded in AEAT concepts, so growing a corpus-shaped view inside the product would leave the harness measuring a shim. The map is data rather than translating code because a function that helpfully normalised a value on the way across would convert a reading failure into a match invisibly.

Two never-scored kinds, never pooled with each other or into `missed`. One is a corpus assertion about the document, which a reader is not wrong to omit. The other is a real field of the document the draft cannot hold, which is a coverage finding about the product. A single excluded total would hide the second inside the first. Corpus-wide the split is 2425 scored slots, 426 out of scope, 235 coverage gap.

The sharpest coverage gap is the printed total: the corpus checks it against the computed total to catch a document whose printed figure disagrees with its own arithmetic, and there is nowhere on the draft to put it, so that disagreement cannot be surfaced at all. It is pinned by its own case so it cannot drift into the out-of-scope group.

Re-running the same three pilot documents through the map moved them from 3/16, 4/17 and 4/17 to 12/17, 13/18 and 11/15, with undeclared collapsing from 15, 15 and 10 to 1 each. The collapse is the confirmation that the movement is the map rather than the model: had the model changed, matched would move and undeclared would not. Denominators shifted as designed, composites expanding into leaf slots and never-scored fields dropping out.

## Verification

    uv run --no-sync python -m pytest dev/ingest_harness/tests -p no:randomly -n 0 -m "unit or integration" -q
    102 passed in 3.60s

The typo guard is proved rather than asserted: removing one target field from the draft set makes `validate_mapping_targets` raise, so a misspelled target cannot silently reintroduce the misses the table removes. Coverage is proved in the other direction too — the table must name every field the key authors, so a corpus that grows a field fails loudly.

Both role branches are asserted non-empty against the corpus at 173 supplier and 47 customer, so neither branch is proved over an empty set, and every mapping kind is asserted populated for the same reason.

The leaf-by-leaf proof spans both composites, asserting one wrong leaf beside three correct reads, which is exactly what single-slot scoring would have destroyed.

## Notes

An empty collection is scored as a wrong answer rather than an abstention, and that was checked rather than assumed: 97 corpus documents carry a legitimately empty line-item truth, so treating an empty container as silence would have converted 97 correct matches into misses. The change was not made.

The composite country leaf is excluded as an interim, not as a limitation. The reader reports the country correctly as a printed name while the corpus states an ISO code, and the name-to-code resolution already exists on the structured e-invoice path — the reading path simply does not reach it. Scoring the leaf today would dock a reading score for a capability the path lacks; calling it permanent would misfile a built-but-unreached resolver as a missing one.

The facade export was deliberately withheld from the commit that landed the module: the working copy of the package facade carried a peer's import of a module that was not yet tracked, and committing it would have put an import of an uncommitted module into the mainline. A module with no export dangles nothing; an export with no module breaks. Both landed coherently once the peer's module was committed.
