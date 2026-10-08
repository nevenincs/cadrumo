# Facturae 3.2.2 enumerations and total composition

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-194` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope and assessment

This three-file data bundle is a compact, sourced reference for Facturae 3.2.2. All three JSON documents were parsed in full. The country-code enumeration has 235 entries with no duplicates; the invoice-class enumeration has six code/label pairs in English and Spanish; and the invoice-totals composition has an ordered list of 19 elements, each marked required or optional and accompanied by schema documentation. The provenance objects identify the published Facturae 3.2.2 XML source, byte/hash details, extraction encoding, and retrieval dates in August 2026.

The data supports document parsing or validation by supplying closed codes and expected element order. The InvoiceTotals documentation also records arithmetic annotations—for example, gross amount before taxes is gross less total discounts plus total surcharges, and invoice total adds output taxes and subtracts withheld taxes. These are schema-derived documentation strings; the files do not implement or validate arithmetic. The source schema remains the authority, and this bounded review does not establish that every code, field, or formula is consumed correctly by a parser.

This is declarative JSON only, with no executable code or taxpayer records. Provenance checks and unique counts establish internal shape, not that the archived schema remains the latest Facturae release. No security concern is evident in these files.

## Complete assigned-file coverage

- facturae-3-2-2-country-codes.json (`src/cadrumo/_data/corpus/facturae/facturae-3-2-2-country-codes.json`) — 3,101 bytes; all 235 codes and provenance parsed.
- facturae-3-2-2-invoice-class.json (`src/cadrumo/_data/corpus/facturae/facturae-3-2-2-invoice-class.json`) — 1,569 bytes; all six bilingual codes and provenance parsed.
- facturae-3-2-2-invoice-totals.json (`src/cadrumo/_data/corpus/facturae/facturae-3-2-2-invoice-totals.json`) — 7,915 bytes; full 19-element ordering, optionality, and documentation parsed.
<!-- /preserved:article -->
