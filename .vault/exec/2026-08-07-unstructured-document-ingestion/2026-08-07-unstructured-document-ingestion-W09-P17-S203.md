---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:40aaa91408a7258052544684274b2ccfd028a82814b93446295a527264c82cf2'
step_id: 'S203'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Ground the alpha-3 column in the schema that made it necessary

## Scope

- `src/cadrumo/_data`
- `src/cadrumo/domain/iva`

## Description

- Fetch the published Facturae 3.2.2 schema, write it to disk as bytes and read it back before trusting it.
- Extract the CountryType enumeration and bundle the extract, not the schema, with a provenance stamp naming the source URL, the schema version, the retrieval date and the digest of the payload it came from.
- Gate every alpha-3 the country vocabulary carries against that enumeration, with a fixture anchor and a control chosen to be the error the gate actually guards against.
- Assert the residual the authority cannot close, so it is documented by something that runs.
- Replace the header's no-authority disclosure, which the gate supersedes, and state the new residual in its place.

## Description of what was rejected

Two sourcing options were refused on the record. A dependency was rejected because it puts a second country authority in a tree where fragmentation is treated as a criticality, makes reference data a runtime dependency of a shipped wheel, and carries data under a licence the project does not otherwise take. The general registers -- the EU Publications Office country table, UN M49 -- were rejected because they are general country databases, which is the artefact the vocabulary's own inclusion argument refuses, and adopting one would have reopened a boundary a previous row had just settled.

## Outcome

The alpha-3 column existed as hand-authored data with no authority behind it, and the vocabulary's header said so rather than implying otherwise. It is now checked against the Facturae CountryType enumeration.

The choice of authority is the substance rather than the availability of a file. Alpha-3 is carried for exactly one reason: a Facturae invoice states the country as a three-letter code, and a document whose element reads ESP would otherwise be present, parsed, readable and establish nothing. So the set of values Facturae enumerates is not merely an authority for the column, it is the definition of the question the column answers. That is also why it does not reopen the boundary the widening row settled: it is a validation authority for one column, not a general vocabulary adopted wholesale.

What is bundled is the enumeration and not the schema. The published schema is a 190 KB authored artefact stating no redistribution terms anywhere in the file; the enumeration extracted from it is a list of ISO codes, which is fact rather than expression, and it is 235 reviewable lines instead of 190 KB of XML. The stamp records which of the three published 3.2.x schemas grounds the column, because a reader who cannot tell them apart cannot re-derive the extract.

The grounding is weaker than the row assumed, and that is stated rather than glossed. The enumeration carries bare values with no annotations, so it proves membership and not correspondence: a fabricated or mistyped code reds, but PRY and PER are both members and a vocabulary that had swapped them would pass every check here. The correspondence is grounded by the hand-check against AEAT's printed register, so the two are complementary. The residual that survives everything this repository can check is a consistent swap of two real codes between two real countries, and closing it needs an authority mapping alpha-3 to a country name, which nothing bundled provides.

## Verification

The fetch, with the payload written as bytes and read back before being trusted:

    status 200 bytes 190062 sha256 b4bbcd587f5fb0a8a906336cca09b0a40d06ffaa78c6a62f6e438c4e6ea86e07
    BOM: True
    CountryType found: True  n=235 unique=235

Coverage, measured against the vocabulary rather than assumed:

    vocabulary alpha3: 78   not statable in Facturae: none

The controls that make the coverage claim a measurement:

    'PRG' in enumeration: False        (the careless hand's Paraguay)
    'XXX' in enumeration: False        (the placeholder)
    'PRY' in enumeration: True         (the positive control)

Gates:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_alpha3_against_facturae.py -n0 -q -m unit
    5 passed in 0.91s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests -n0 -q -m unit
    683 passed in 21.34s

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -n0 -q -m unit
    1 failed, 3830 passed, 23 deselected in 869.17s

## Notes

The single registry failure is the modelo revision-span gate reporting that modelos 200, 303 and 390 carry revisions spanning published design re-layouts. It is the modelo registry lane, it names no country surface, and this row touches no revision. Reproduced and read rather than inferred from the summary line.

The extract ships in the wheel. The packaging rules exclude only binary corpus formats under the corpus tree, so a small JSON is carried; it is read by a gate rather than at runtime, and at roughly five kilobytes the cost of shipping it is smaller than the cost of a second exclusion rule for one file.

An earlier hand-back on this row reported the authority unreachable after four canonical URLs returned 404. That was a search failure rather than a judgement failure: the site had restructured and the schema now sits under a content-delivery path. Stopping rather than continuing to guess URLs was the right call, and the reasoning that selected this authority over the alternatives was already correct at the point the search failed.
