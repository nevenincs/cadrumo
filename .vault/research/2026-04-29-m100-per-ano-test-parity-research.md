---
tags:
  - '#research'
  - '#m100-per-ano-test-parity'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
---

# `m100-per-ano-test-parity` research: `2024 and 2026 anexo test parity`

Issue `#456` asks for per-anexo worked-example parity for Modelo 100 years 2024 and 2026. The existing 2025-only target surface is `test_anexo_b2_2025.py`, `test_anexo_c_2025.py`, `test_anexo_d_2025.py`, `test_anexo_ef_2025.py`, `test_anexo_g_2025.py`, and `test_anexo_n_2025.py`. The production rulesets split Anexo E and Anexo F into separate modules, so the new 2024 and 2026 parity files should use the seven-anexo issue shape rather than carrying forward the legacy combined 2025 test file shape.

## Findings

- B1 already has 2024, 2025, and 2026 tests and establishes the import/year-scoping pattern.
- The 2025 `test_anexo_ef_2025.py` file remains untouched to keep this issue scoped to the missing years. The new missing-year files split E and F to align with `anexo_e_<year>.py` and `anexo_f_<year>.py`.
- The per-year rulesets expose the same computed casilla set for 2024, 2025, and 2026: B2 `0048/0049`, C `0106/0107`, D `0190/0195/0205/0220/0225/0230/0240/0260`, E/F `0405/0432/0460/0500/0545/0555`, G `0540/0542/0550/0560/0595/0630/0698/0720`, and N `0622`.
- BOE primary anchors verified: LIRPF consolidated text for arts. 23, 25-26, 33-39, 47-61, 63-68, 79, and 85; LIS consolidated text for arts. 12 and 17; RIRPF consolidated text for art. 30; Ley 7/2024 for the 2025+ ahorro top-bracket delta.
- 2024 differs from 2025/2026 in the Anexo G ahorro top bracket: 2024 keeps the pre-Ley 7/2024 state half top rate, while 2025 and 2026 use the post-Ley 7/2024 value.
- 2026 inherits the current 2025 numerical surface where no later BOE change is encoded in the ruleset.
- Soft-collision plan: Anexo C and D files added here are year-specific mirrors of the existing 2025 surface. Sibling PRs for rental and inventory hardening can merge by textual union because they extend the 2025 files and do not require changing these 2024/2026 parity files.
