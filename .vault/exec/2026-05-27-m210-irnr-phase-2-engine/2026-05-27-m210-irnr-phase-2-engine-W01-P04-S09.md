---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:8b8a2a9ec17e3bd8c0d1d932f6c54e11f922383d1c576d5344edda75d54d436f'
step_id: 'S09'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# FETCH-GATED (fetch: per-treaty BOE consolidated convenio texts for FR/PT/US/NL/BE) - author tranche-1 Convenio corpus, `legal/irnr.toml` entries, and `treaties/es-XX.toml` rows keyed by `TipoRentaIrnr` with typed `ConvenioOverrideKind`, pinned by continuity parity tests

## Scope

- `src/aeat/_data/registry/aeat/treaties`

## Description

- Fetch the BOE consolidated text of the Spain-France double-taxation treaty (`BOE-A-1997-12729`, firmado 10-10-1995, en vigor 01-07-1997) and confirm the source-state ceilings verbatim: art 10.2.a dividendos "no podrá exceder del 15 por 100 del importe bruto de los dividendos" and art 11.2 intereses "no puede exceder del 10 por 100 del importe bruto de los intereses".
- Bundle the two article excerpts as corpus HTML carrying the verbatim BOE phrases.
- Author `treaties/es-fr.toml` with a dividend ceiling override (rate 0.15) and an interest ceiling override (rate 0.10), both `kind = "ceiling"` and `valid_from = 2025-01-01`, so the tipo resolver applies min(domestic 0.19, treaty).
- Author the `convenio-es-fr-1995:art-10` and `:art-11` legal-catalogue entries with `corpus_ref` and the verbatim BOE `required_text`, cross-checked against the bundled excerpts.
- Add a grounded continuity parity test asserting a FR-resident dividend resolves to 0.15 and interest to 0.10 (min against the 19% domestic rate), plus that the legal entries carry the BOE-grounded ceiling phrases.

## Outcome

France is enrolled as the tranche-1 treaty. The engine resolves FR/dividend to 0.15 and FR/interest to 0.10; the registry loads; the legal-grounding required_text cross-check passes against the bundled BOE corpus; 359 grounding/catalogue gates and the new + existing 210 tests pass; `ruff`, `ruff format`, and `ty` are clean. Committed as `16fdd05a9b`.

## Notes

Scope held to France only per the tranche-1 brief. Portugal, the United States, the Netherlands, Belgium, and all royalties (cánones) remain deferred and untouched: they are ungroundable as-fetched and would require their own per-treaty BOE fetches under the demand-driven enrolment contract. The art 10.2.b qualified-participation dividend exemption is not modelled (the override is the general 15% ceiling). A non-treaty country on a dividend/interest renta still resolves through the existing tipo-resolver sentinel path (unchanged by this slice).
