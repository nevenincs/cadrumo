# EU VAT-rate reference sources

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-193` · **Topic:** [Bundled knowledge and localization](../topics/bundled-knowledge-and-localization.md)

<!-- preserved:article -->
## Scope and sample

This chunk contains six reference documents totaling 1,948,148 bytes. I inspected headings and bounded rate/date passages from all four HTML pages, extracted limited text from both PDFs, and recorded size and SHA-256 for every file. I did not treat this as a current-law check or read every document page in full.

The set combines different levels of authority and purpose: an EU Parliament Research Service briefing about the EU framework for setting VAT rates; national tax-authority pages/notices for Estonia, Finland, Lithuania, and Romania; and a Your Europe cross-country overview file labeled 2026-07-13. The national pages contain time-bounded change notices and examples. The sample identifies, for instance, Estonia's move from 22% examples to a 24% standard rate, Finland's reduced-rate change from 14% through 2025 to 13.5% in 2026, Lithuania's selected reduced-rate transition from 9% through 2025 to 12% from 2026-01-01, and Romania's August 2025 change to a 21% standard rate and 11% reduced rate. These are statements found in archived sources, not tax advice or a verification that every taxpayer/supply is covered by those rates. The EU briefing is explanatory policy material rather than an operative country-by-country rulebook.

The documents can inform cross-border IVA context, but rates and product/tax categories are sensitive to effective dates, transitional rules, product classifications, and exceptions. The aggregate Your Europe page is not itself a complete legal basis. The archive has no independent freshness verification in this chunk, so consumers must bind the applicable country, supply type, and date to the appropriate primary source before using a rate. See the EU Parliament briefing (`src/cadrumo/_data/corpus/eu_official/iva/eprs-iva-rates-eu-2025-07-01.pdf`), Estonian tax authority page (`src/cadrumo/_data/corpus/eu_official/iva/estonia-iva-rate-change-2025.html`), Finnish tax authority page (`src/cadrumo/_data/corpus/eu_official/iva/finland-iva-rate-change-2026.html`), Lithuanian tax authority page (`src/cadrumo/_data/corpus/eu_official/iva/lithuania-iva-rate-change-2026.html`), Romanian tax authority notice (`src/cadrumo/_data/corpus/eu_official/iva/romania-iva-rate-change-2025.pdf`), and Your Europe overview (`src/cadrumo/_data/corpus/eu_official/iva/your-europe-iva-rates-2026-07-13.html`).

## Trust and quality notes

The sample covers primary national-tax pages alongside a policy briefing and an EU-wide overview, so downstream code should retain source attribution and effective-date context instead of flattening every value into one timeless rate table. The Lithuanian HTML snapshot contains scripts and remote analytics references; if a consumer renders downloaded HTML as active content, it crosses a browser/network trust boundary. No such renderer was inspected here, and the observation does not establish an exploitable product path. PDF text extraction was used only for bounded static reading; it does not check visual tables, footnotes, or extraction fidelity. No application was run and no source files were changed.

## Complete assigned-file coverage

- eprs-iva-rates-eu-2025-07-01.pdf (`src/cadrumo/_data/corpus/eu_official/iva/eprs-iva-rates-eu-2025-07-01.pdf`) — 901,491 bytes; bounded text sample inspected.
- estonia-iva-rate-change-2025.html (`src/cadrumo/_data/corpus/eu_official/iva/estonia-iva-rate-change-2025.html`) — 247,451 bytes; title, headings, and rate-change passages sampled.
- finland-iva-rate-change-2026.html (`src/cadrumo/_data/corpus/eu_official/iva/finland-iva-rate-change-2026.html`) — 115,198 bytes; title, headings, and 2026 rate passages sampled.
- lithuania-iva-rate-change-2026.html (`src/cadrumo/_data/corpus/eu_official/iva/lithuania-iva-rate-change-2026.html`) — 273,571 bytes; headings and effective-date/rate passages sampled; active script references noted.
- romania-iva-rate-change-2025.pdf (`src/cadrumo/_data/corpus/eu_official/iva/romania-iva-rate-change-2025.pdf`) — 195,087 bytes; bounded text sample inspected.
- your-europe-iva-rates-2026-07-13.html (`src/cadrumo/_data/corpus/eu_official/iva/your-europe-iva-rates-2026-07-13.html`) — 215,350 bytes; title/headings and explanatory rate text sampled.
<!-- /preserved:article -->
