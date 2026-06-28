---
tags:
  - '#audit'
  - '#modelo-180-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-28-modelo-180-calc-verify-plan]]"
  - "[[2026-04-28-modelo-180-calc-verify-adr]]"
  - "[[2026-04-28-modelo-180-calc-verify-reference]]"
---

# `modelo-180-calc-verify` Code Review

MODEL180-001 | HIGH | Registry smoke tests omitted `modelo_180.2026`

Reviewer confirmed `modelo_180.2026` was registered but `src/aeat/domain/formulas/test_registry.py` and `src/aeat/domain/formulas/test_smoke.py` still expected the old ruleset set. Resolution: both tests now include `modelo_180.2026`, and registry coverage adds an explicit 2026 annual resolve assertion.

MODEL180-002 | HIGH | Cumulation rounding disagreed with the annual ruleset

Reviewer identified that summing rounded quarterly retentions could disagree with `03 = annual base x 19 percent` on tiny edge cases. Resolution: the cumulation helper now derives annual casilla 03 from the annual base using two-decimal ROUND_HALF_UP, and `test_cumulation_uses_annual_rounding_for_retenciones` pins the edge case.

MODEL180-003 | MEDIUM | Vault structure check conflicts with issue-mandated artifact filenames

Resolution: the Modelo 180 vault artifacts were normalized to vault-standard filenames during the Modelo 200 vault cleanup. `vaultspec-core vault check all` now reports clean structure, links, dangling links, schema, and references.

MODEL180-004 | LOW | `uv.lock` changed during bootstrap

The lockfile changed because the issue explicitly requested `uv sync --all-groups --upgrade` and `uv lock --upgrade` during bootstrap. The change is retained as bootstrap evidence unless the maintainer prefers to restore it before PR.

MODEL180-005 | P2 | Codex review found 2026 formula provenance leaked a 2025 formula id

`codex review --base origin/main` found that `modelo_180.2026` reused `_FORMULAS_2025`, causing discrepancy reports to show `modelo_180.2025.total_retenciones` for 2026 audits. Resolution: `modelo_180_2026.py` now defines its own same-body formula with id `modelo_180.2026.total_retenciones`, and `test_formula_id_uses_2026_namespace` pins the provenance.

MODEL180-006 | P2 | Codex review found annual recipient count summed quarterly appearances

`codex review --base origin/main` found that summing quarterly M115 casilla 01 overcounts recurring landlords. Resolution: quarterly cumulation sources now require recipient identities, validate the printed quarterly count against unique ids, and annual Modelo 180 casilla 01 is the count of unique recipient ids across the four quarters. Tests pin both recurring-recipient aggregation and invalid fixture rejection.
