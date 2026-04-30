---
tags:
  - '#adr'
  - '#m100-per-ano-test-parity'
date: '2026-04-29'
related:
  - "[[2026-04-29-m100-per-ano-test-parity-research]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
---

# `m100-per-ano-test-parity` adr: `mirror combined anexo modules per year` | (**status:** `accepted`)

## Problem Statement

Modelo 100 full-form rulesets exist for 2024, 2025, and 2026, but the worked-example per-anexo tests after B1 existed only for 2025. The missing coverage weakens audit confidence for year-scoped rulesets even when the formula surface is structurally shared.

## Considerations

The repository combines Anexo E and F in `test_anexo_ef_2025.py`. Splitting that file would create a new shape unrelated to the ruleset structure. The safer parity decision is to mirror the six existing 2025 target modules into 2024 and 2026, yielding 12 files.

Expected values remain externally anchored in the same source families as the 2025 files: BOE consolidated LIRPF, LIS, RIRPF, Ley 7/2024, and AEAT/manual provenance already cited by neighboring ruleset citations.

## Constraints

- Test-only change; no production-code edits.
- Module-level markers must remain `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]`.
- No mocks, fakes, stubs, skips, xfails, or live AEAT submission.
- No tests for sibling feature behavior from `#453` or `#454`.

## Implementation

Create 2024 and 2026 copies of B2, C, D, EF, G, and N tests, updating each import to the matching `MODELO_100_<year>` constant. Preserve 2025 worked examples where the statutory surface is inherited. For Anexo G, keep the explicit 2024 ahorro top-bracket test and compare it against the 2025 post-Ley 7/2024 value.

## Rationale

This follows the B1 precedent and the existing combined E/F test module. The result is one parity file per already-existing anexo test module per missing year, with the smallest blast radius and clear soft-collision behavior.

## Consequences

The M100 per-anexo worked-example surface is now present for all implemented years. Future sibling PRs can add new behavior tests without rebasing production ruleset code.
