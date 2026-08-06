---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:af372c85f2486e1aa5e096c7eed4d5fae15745044f08295eb129505b41728b17'
step_id: 'S28'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Build and verify an evidence-only 2025 0613 cap and rounding addendum without changing production schema wiring

## Scope

- `.vault/research/2026-08-05-modelo-parity-rollup-s17-0613-cap-rounding-research.md`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:54765-55022`
- `src/cadrumo/domain/contribuyente/family.py:984-1060,1373-1398`
- `src/cadrumo/application/modelo/_profile_binding.py:235-286`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:19-55,1651-1657`

## Description

Use VaultSpec-RAG and official AEAT examples to close the evidence-only S17 gate for the per-child 0613 cap and rounding semantics. No production schema, formula, binding, profile selector, or casilla producer is in scope until SOL authorizes it.

## Grounding

Ran vaultspec-rag against the S17/0613 legal, profile, formula, and parity intent. The combined index matched the live workspace (`code_indexed_count=77844`, `vault_indexed_count=28040`, target match true). The search surfaced the accepted parity ADR, the S17 evidence and candidate-contract research, the prior S17 execution boundary, the 2025 official-manual extraction, and the current family/profile-binding implementation.

The bundled 2025 manual establishes complete-month eligibility, the 83.33 monthly description, the per-child 1,000 annual limit, effective non-subsidized spend, both-parent amounts, subsidies/employer exclusions, and the turning-three window. Official AEAT pages and worked examples were also checked. The published examples do not establish one executable rounding stage: the 2021 example reports eight months as 666.64, the 2022 FAQ reports seven months as 583.33, and the 2025 manual reports two months as 166.67 and six as 500.

## SOL boundary

SOL returned DEFER. No 2025/0613 formula, binding, selector, profile schema change, or casilla producer is authorized. The next permitted gate is an evidence-only oracle covering the 12-month cap, 2/6/7/8-month rounding, spend-limited, month-cap-limited, effective-spend-limited, zero, turning-three, and two-child unequal-cap cases. `cotizaciones_ss_madre_2024` must not be reused, and an aggregate `min(total spend,total cap)` cannot replace per-child minima.

## Outcome

Authored the VaultSpec-RAG-grounded research addendum at `.vault/research/2026-08-05-modelo-parity-rollup-s17-0613-cap-rounding-research.md`. It records the evidence, competing rounding interpretations, missing per-child effective-spend contract, rejected 2024 cloning, required independent matrix, and the non-promotion boundary. No production files were changed.

A Luna Max worker was dispatched with the exclusive research-document scope. The first tool-enforced Luna role stopped before execution requesting unavailable parent configuration proof; a retry with explicit gpt-5.6-luna/max settings remained unresponsive and was shut down. It made no file changes. The research body was then written through the VaultSpec Core body-edit channel, preserving CLI-owned frontmatter.

## Verification

- `uv run --no-sync pytest -q -n 0 src/cadrumo/domain/contribuyente/tests/test_guarderia_2025_facts.py src/cadrumo/application/modelo/tests/test_guarderia_monthly_reaches_the_calculate_path.py src/cadrumo/domain/calculations/registry/tests/test_modelo_100_2025_semantic_boundaries.py` -> 17 passed.
- VaultSpec research body edit -> updated with no checks reported.
- `uv run --no-sync vaultspec-core vault check all --feature modelo-parity-rollup --json` -> all substantive checks clean; the first run reported only stale feature index, missing exec sections, and an unreferenced research warning, which are being repaired in this step.

## Notes

This step closes the evidence addendum only. M100/2025/0613 remains manual/open. No production parity claim, independent code-review claim, or full Modelo 100 parity claim is made. The next authorized action is to obtain an authoritative resolution of the cap/rounding discrepancy and then return to SOL before any registry producer change.
