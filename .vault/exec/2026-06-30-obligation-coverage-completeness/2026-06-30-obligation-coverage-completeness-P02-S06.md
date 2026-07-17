---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Author the Modelo 190 annual deadline window with legal grounding verified against the bundled corpus.

## Scope

- `src/aeat/_data/registry/aeat/modelos/190`

## Description

- Verify the Modelo 190 annual deadline window under `modelos/190/revisions/2024-y-siguientes/deadline_windows/0001-deadline_windows.toml` is authored and grounded.
- Confirm the two windows (`modelo-190-2024-0a` filing_year 2025, `modelo-190-2025-0a` filing_year 2026), each period_kind annual, open 1 January and close 31 January of the year following the resumen.
- Confirm `legal_refs` cite `rd-439-2007:art-108` (the RD IRPF obligation to file the annual resumen) and `orden-eha-3127-2009:art-1` (the Orden approving the Modelo 190 form and its plazo), both resolving to legal-catalogue entries with a `corpus_ref` to bundled BOE text.
- Confirm `source_refs` `aeat-modelo-190-procedure` and `boe-modelo-190-2025-form` resolve to registered `[sources]` entries.
- Cross-check the closing date against the bundled authoritative corpus for the Orden.

## Outcome

- The bundled corpus `corpus/normatives/html/orden-eha-3127-2009.html` states verbatim under "Plazo de presentación del modelo 190": "plazo de presentación será el comprendido entre el 1 de enero y el 31 de enero del año siguiente al que corresponde el resumen anual". The authored `opens_on = 2025-01-01` / `closes_on = 2025-01-31` matches the authoritative consolidated text, not a blindly-trusted figure.
- `rd-439-2007:art-108` resolves to `corpus/normatives/html/rd-439-2007-art-108.html#a108` (BOE-A-2007-6820); `orden-eha-3127-2009:art-1` resolves to `corpus/normatives/html/orden-eha-3127-2009.html#articulo-1`.
- The window loads clean through `resources().modelos.authority.deadline_windows(2025, modelos=("190",))`, returning a single 2025-01-01 -> 2025-01-31 window with both legal refs attached.
- Registry collect-only is clean (3150 collected, 0 errors); the obligation-coverage suite is green (10 passed). Modelo 190 is now window-backed and seed-ruled, so it resolves to the surfaced disposition on the real calendar, retiring the class-B silent-absence gap the ADR Decision 2 targeted.

## Notes

- The registry TOML and the coverage-test updates that reflect the window-backed M190 landed in a peer commit (`2f582975c9`, "fix(registry): add modelo 190 annual deadline"); this Step verified the grounding against the bundled corpus, confirmed the legal-catalogue and source-ref resolution, and proved the window loads and the coverage invariant holds. No further code change was required.
- The M303-style annual window shape (period token `2024 0A`, `period_kind = "annual"`) mirrors the Modelo 180 annual-resumen window it was modelled on.
