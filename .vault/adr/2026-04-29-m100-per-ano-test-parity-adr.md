---
tags:
  - '#adr'
  - '#m100-per-ano-test-parity'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - "[[2026-04-29-m100-per-ano-test-parity-research]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
---

# `m100-per-ano-test-parity` adr: `split E and F for missing years` | (**status:** `accepted`)

## Problem Statement

Modelo 100 full-form rulesets exist for 2024, 2025, and 2026, but the worked-example per-anexo tests after B1 existed only for 2025. The missing coverage weakens audit confidence for year-scoped rulesets even when the formula surface is structurally shared.

## Considerations

The repository combines Anexo E and F in `test_anexo_ef_2025.py`, but the production rulesets already split those anexos into `anexo_e_<year>.py` and `anexo_f_<year>.py`. Carrying forward the combined test-file shape would conflict with the issue title's seven-anexo wording. The safer parity decision is to keep 2025 untouched and split only the new missing-year E/F tests, yielding 14 files.

Expected values remain externally anchored in the same source families as the 2025 files: BOE consolidated LIRPF, LIS, RIRPF, Ley 7/2024, and AEAT/manual provenance already cited by neighboring ruleset citations.

## Constraints

- Test-only change; no production-code edits.
- Module-level markers must remain `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`.
- No mocks, fakes, stubs, skips, xfails, or live AEAT submission.
- No tests for sibling feature behavior from `#453` or `#454`.

## Implementation

Create 2024 and 2026 copies of B2, C, D, E, F, G, and N tests, updating each import to the matching `MODELO_100_<year>` constant. Preserve 2025 worked examples where the statutory surface is inherited. Split the 2025 combined E/F test body into separate E and F modules for the missing years only. For Anexo G, keep the explicit 2024 ahorro top-bracket test and compare it against the 2025 post-Ley 7/2024 value.

## Rationale

This follows the B1 precedent while aligning the missing-year files with production anexo boundaries. Keeping 2025 combined avoids unrelated churn; splitting 2024 and 2026 satisfies the seven-anexo acceptance wording.

## Consequences

The M100 per-anexo worked-example surface is now present for all implemented years. Future sibling PRs can add new behavior tests without rebasing production ruleset code.
