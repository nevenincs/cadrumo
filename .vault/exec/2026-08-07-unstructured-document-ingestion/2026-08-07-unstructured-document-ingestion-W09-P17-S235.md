---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:57ffc0f4397421eb89deed619bb312a5913fc16f4ee82e1d9c7fe0e55d9bc4c6'
step_id: 'S235'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Replace the country vocabulary's admission criterion

## Scope

- `src/cadrumo/_data/registry`

## Description

- Replace the admission test that conditioned inclusion on measuring traffic, which cannot be performed from this repository.
- State the replacement as two conditions, one machine-checked and one a reviewer's reading.
- Record what the new test cannot decide, because a criterion is read as authority for years.
- Name the population it governs, and reconcile that number against the resolver's larger catalogued set.

## Outcome

The criterion this retires said a country became defensible the day somebody measured the traffic rather than the plausibility. It reads as provisional and functions as permanent, because nothing in this repository can perform the measurement: the only document population here is the specimen corpus, sixteen of whose twenty items were authored in-tree, and whose four real documents are two Wikimedia invoices, a derived scan and a ZUGFeRD sample. Not one is a Spanish taxpayer's invoice. A corpus we wrote cannot measure population pressure on a boundary we drew.

The replacement is two conditions. Both of a country's codes must verify against the bundled authorities — the alpha-2 against AEAT's SII enumeration, the alpha-3 against the Facturae enumeration — which gates already assert, so that half is checked rather than attested. And the country must fall inside a bloc this table already declares, which is a reading of the header rather than a lookup, and is the half a reviewer has to exercise.

The header now also states what the test cannot decide. It says a country MAY be added rather than SHOULD; it does not rank by how often a country actually appears, because nothing here measures that; it does not authorise widening the blocs, which is a separate decision; and passing it is not evidence of belonging to a bloc. Recording the limits matters more here than in most prose, because a criterion is the thing a later reader cites rather than re-derives.

The named exclusions survive as a list, with the sentence conditioning them on an unperformable measurement removed. They are now simply admissible on the test, which is the honest state: the tier is argued and held on a separate row, not blocked by this criterion.

## Verification

The population reconciliation, measured rather than taken from the brief:

    name rows: 78 | catalogued codes: 91 | carve-outs: 12
    catalogued but no name row: AX EA GF GG GP IC IM JE MC MQ RE XI YT
      of those, EU members: XI
      of those, carve-outs: AX EA GF GG GP IC IM JE MC MQ RE YT

The registry still loads and the axes are unchanged:

    US -> third_country   DE -> eu_member   MC -> eu_member   'Alemania' -> DE

    uv run --no-sync pytest src/cadrumo/domain/iva/tests -n0 -q -m unit
    703 passed of 703 collected

Deletions in the commit: three lines, all of them the superseded sentence.

## Notes

The brief's reconciliation of the thirteen-code difference was wrong and the correction is load-bearing rather than pedantic. It described them as thirteen EU member states catalogued by enum membership without name rows; they are the twelve territories of the VAT carve-out table plus Northern Ireland, and only Northern Ireland reaches the axis through the Member State catalogue. That matters because the carve-outs are a different axis with a different admission rule — each cites the LIVA provision establishing its treatment — so a criterion written as though they were unlisted countries would have implied this test governs them. It does not, and the header says so.

This row was deliberately not blocked on the specimen derivation. Replacing an unperformable criterion is correct whether or not any country is ever admitted under the new one, and coupling the two would have held a correct change behind an unrelated one.
