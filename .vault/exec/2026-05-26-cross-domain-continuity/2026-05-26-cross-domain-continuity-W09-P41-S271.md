---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S271'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-W09-B S268 corpus gap: HAC/242/2025 art-8 is referenced by the M100 2024 deadline-window registration but the corpus file currently exists only as .json without required_text

## Scope

- `complete the corpus entry with the full BOE text`
- `.vault/research/`

## Description

- Confirm the former S268 corpus gap is no longer present: HAC/242/2025 Articulo 8 is represented by the full bundled BOE HTML corpus, not by a JSON placeholder without verification text.
- Verify the Modelo 100 exercise-2024 deadline legal reference uses corpus-checked `required_text` from `orden-hac-242-2025:art-8`.
- Ground the closure with `uvx vaultspec-rag search "orden-hac-242-2025 art-8 corpus required_text irpf deadline windows" --type vault --doc-type exec` and `--type vault --doc-type plan`.
- Run the focused normatives gate after the registry-load blocker was cleared.

## Outcome

Closed as evidence-complete. Prior exec record `2026-05-27-cross-domain-continuity-P50-S179` documented that Articulo 8 text had been omitted to avoid a false corpus-verification failure. Current code now contains the BOE HTML corpus and `required_text`, and the focused gate `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_catalogue_verification_normatives.py::test_orden_hac_242_2025_art_8_deadline_links_to_full_boe_corpus -q` passed.

## Notes

No production edit was required for this closeout. The work performed here was tracker closure and verification after the registry-load blocker was fixed.
