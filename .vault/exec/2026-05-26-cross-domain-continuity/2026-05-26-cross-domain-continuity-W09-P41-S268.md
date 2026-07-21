---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S268'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-W10-A extract HAC/242/2025 art-8 text into corpus HTML and add required_text to orden-hac-242-2025:art-8 entry in irpf.toml

## Scope

- `src/aeat/_data/registry/aeat/legal/irpf.toml`

## Description

- Verify the HAC/242/2025 Articulo 8 corpus extraction is present in `src/aeat/_data/corpus/normatives/html/orden-hac-242-2025.html`.
- Verify `src/aeat/_data/registry/aeat/legal/irpf.toml` declares `orden-hac-242-2025:art-8` with `required_text` for the Articulo 8 filing window and Articulo 13.3 domiciliation cutoff.
- Ground the closure with `uvx vaultspec-rag search "orden-hac-242-2025 art-8 corpus required_text irpf deadline windows" --type code`.
- Run the focused normatives gate that validates the legal reference against the bundled BOE corpus.

## Outcome

Closed as already implemented and test-verified. The bundled BOE HTML contains the Articulo 8 heading and filing window text for 2 April through 30 June 2025, plus the Articulo 13.3 domiciliation text for 2 April through 25 June 2025. The IRPF legal catalogue now carries matching `required_text` entries, and `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_catalogue_verification_normatives.py::test_orden_hac_242_2025_art_8_deadline_links_to_full_boe_corpus -q` passed.

## Notes

The first attempt to run the normatives gate was blocked by an unrelated Modelo 136 registry-load failure. The Modelo 136 grounding lane repaired that blocker in commits `fee68502d` and `5e7bdd11a`, after which this HAC/242 gate passed.
