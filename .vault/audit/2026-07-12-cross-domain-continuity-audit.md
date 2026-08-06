---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:f7aeee722eda0b9e12327522efccda9e1bc7b5a1ee2625da54f962807075e06f'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` audit: `Wave 10 terminal audit`

## Scope

Wave 10 terminal verification of registry deadline-window backfill. It combines independent legal/consumer review and encrypted public calendar journeys across the supported modelos.

## Findings

### wave-10-annual-tax-year-key | high | annual windows used campaign years while workflow selected tax years

Modelo 100 2020/2021 and Modelo 180 2024/2025 windows retained correct legal following-year dates but stored campaign years in `filing_year`. Registry discovery could list the records, while DeadlineEngine and workflow scheduling queried work-unit tax years and omitted their own windows. S441 and S442 corrected the four keys without changing legal dates and added direct engine/workflow regressions.

### wave-10-calendar-personas | low | registry discovery and applicability suppression are operator-honest

Fresh personas surfaced expected M100, M111, M131, M180, M200, M202, M349, and M390 entries. M232 was suppressed as incomplete without qualifying related-party facts rather than shown as a false obligation. Raw registry discovery was not treated as proof of workflow selection, which the annual-key repairs now cover.

### wave-10-deadline-prose | low | one explanation still names the retired campaign-year key interpretation

The deadline behavior is repaired, but an explanatory phrase still describes Modelo 100 annual windows as campaign-year keyed. S443 owns the documentation-only correction under the required workflow.

### s422-tax-year-publication | low | the 2026 campaign does not publish a tax-year 2026 Modelo 100

AEAT's 2026 campaign material is for tax year 2025: the March 2026 order,
May dictionary refresh, and June XSD refresh all identify exercise 2025. The
current registry correctly selects its 2025 revision by tax/work-unit year and
refuses 2026 because no authoritative tax-year 2026 revision exists. The newer
2025 dictionary and XSD refreshes also remain unbundled, so they cannot be
misrepresented as a 2026 registry release. S422 remains an external
publication dependency; a future implementation must ingest genuine tax-year
2026 evidence and prove the resulting M130-to-M100 projection.

## Recommendations

- Treat registry `filing_year` as the consumer's tax/work-unit key, even when the legal campaign dates fall in the next calendar year.
- Pair registry-discovery persona checks with direct deadline-engine and workflow selection regressions for annual forms.
- Preserve M232 applicability suppression as a first-class, visible state.
- Keep S422 open until AEAT or BOE publish a tax-year 2026 Modelo 100 release;
  campaign-2026 tax-year-2025 material is not a substitute.
