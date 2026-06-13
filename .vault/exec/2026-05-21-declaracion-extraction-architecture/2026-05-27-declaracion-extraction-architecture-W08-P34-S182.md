---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S182"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-27-declaracion-extraction-architecture-audit]]"
---

# declaracion-extraction-architecture W08.P34.S182

## Step

Tag all 16 GROUNDED profiles with the appropriate `verification_source` enum value reflecting actual provenance.

## What was done

Categorised all 16 grounded profiles by actual grounding method and added `verification_source = "..."` immediately after `corpus_round_trip_verified = true` in each TOML file.

**real_aeat_corpus_pdf** (4 modelos, 7 profiles — real AEAT-issued PDF round-trips exercised):

| Modelo | Revision | Profile |
|--------|----------|---------|
| M100 | 2021 | modelo-100-2021-declaracion-pdf |
| M100 | 2022 | modelo-100-2022-declaracion-pdf |
| M100 | 2023 | modelo-100-2023-declaracion-pdf |
| M190 | 2024-y-siguientes | (extraction_profiles) |
| M303 | 2009-y-siguientes | modelo-303-declaracion-pdf |
| M303 | 2023-y-siguientes | modelo-303-declaracion-pdf |
| M390 | 2010-y-siguientes | (extraction_profiles) |

**synthetic_from_aeat_published_text** (12 modelos, 14 profiles — SANITIZED fixture built from AEAT-published text):

| Modelo | Revision | Profile |
|--------|----------|---------|
| M036 | 2025-02-03-y-siguientes | modelo-036-declaracion-pdf |
| M115 | 2019-y-siguientes | modelo-115-declaracion-pdf |
| M123 | 2019-2023 | (revision) |
| M123 | 2024-y-siguientes | (revision) |
| M180 | 2023-y-siguientes | modelo-180-declaracion-pdf |
| M184 | 2015-y-siguientes | (extraction_profiles) |
| M193 | 2024-y-siguientes | (extraction_profiles) |
| M232 | 2016-2017 | modelo-232-2016-declaracion-pdf |
| M232 | 2018-y-siguientes | modelo-232-2018-declaracion-pdf |
| M347 | 2008-y-siguientes | (347.toml) |
| M349 | 2020-y-siguientes | (extraction_profiles) |
| M369 | esquema-union | modelo-369-union-declaracion-pdf |
| M720 | 2013-y-siguientes | modelo-720-declaracion-pdf |
| M840 | 2003-y-siguientes | modelo-840-declaracion-pdf |

**Correction for M303:** The two M303 revision files had a pre-existing `verification_source = "synthetic_from_aeat_published_text"` tag (wrong — M303 had 15 real corpus PDFs exercised across 2 templates). These were corrected to `"real_aeat_corpus_pdf"`.

## Files changed

21 TOML files under `src/aeat/_data/registry/aeat/modelos/`

## Commit

`3c8a15e66` — H1/S182: tag all 16 GROUNDED profiles with verification_source enum

## Test result

115 passed in 33.76s (gate + specimen + long_tail_data_types)
