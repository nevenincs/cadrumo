---
step_id: "S01"
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#descendant-axis"
related:
  - "[[2026-05-19-profile-lifecycle-disaster-plan]]"
---

# descendant-axis S01 — DescendantInfo per-descendant data + Art. 58 mínimo wiring (Inés #221)

## What was done

Added the `DescendantInfo` pydantic model to `src/aeat/domain/profile/family.py` with
full Art. 58 LIRPF semantics: birth_date, adoption_date, discapacidad_grado (Literal[0,33,65]),
convive_con_contribuyente, nif. Model validators enforce adoption_date ≥ birth_date and
adoption_date ≤ today.

Extended `RentaFamilyProfile` with:
- `descendientes: tuple[DescendantInfo, ...]` field
- Derived properties: `descendientes_count`, `descendientes_menores_3_year_end(year)`,
  `descendientes_eligible_minimum(year)`, `descendientes_full_year_minimum(year)`

Created `src/aeat/domain/profile/_descendant_facts.py` with:
- `descendant_facts_from_list` — serialises DescendantInfo list to flat profile facts
- `descendant_list_from_facts` — reconstructs from flat fact dict
- `parse_descendiente_flag` — parses `--descendiente NACIMIENTO=...,` CLI flag format

Added 2024 registry binding TOML:
- `0012-renta-2024-profile-descendientes-count.toml`
- `0013-renta-2024-profile-descendientes-minimos-aggregate.toml`

Added `wizard.setup.flags.descendiente.help` locale keys to es/en/ca/hu.

## Tests

`src/aeat/domain/profile/test_descendant_info.py` — 42 tests covering:
- Model validation (birth_date required, adoption_date constraints, discapacidad enum)
- Age calculation and eligibility derived methods
- RentaFamilyProfile derived properties
- Oracle cases using AEAT 2024 registry parameters (€2,400/€2,700/€4,000/€4,500/€3,000)
  - 1 descendant born 2023-01-15 → €2,400 + €3,000 = €5,400
  - 2 pre-2024 descendants → €5,100
  - Inés shape (adopted 2024-05-12, before 1-July) → full-year €5,400
  - Half-year prorrata for July birth
- Roundtrip: save 2 DescendantInfo → flat facts → reload → assert equality
- Anti-tautology: removing birth_date from facts → entry dropped on reload
- parse_descendiente_flag unit tests

## Standing gates

- G1: no naked env reads
- G2: typed pydantic boundaries
- G5: no shims — DescendantInfo is additive to existing `RentaDescendantProfile`
- G6: no tautological tests — oracle values from registry TOML parameters, not from formula

## Files touched

- `src/aeat/domain/profile/family.py` — DescendantInfo + RentaFamilyProfile.descendientes
- `src/aeat/domain/profile/__init__.py` — export DescendantInfo
- `src/aeat/domain/profile/_descendant_facts.py` — NEW
- `src/aeat/domain/profile/test_descendant_info.py` — NEW (42 tests)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0012-renta-2024-profile-descendientes-count.toml` — NEW
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0013-renta-2024-profile-descendientes-minimos-aggregate.toml` — NEW
- `src/aeat/locales/es.yml` — descendiente flag help
- `src/aeat/locales/en.yml` — descendiente flag help
- `src/aeat/locales/ca.yml` — descendiente flag help
- `src/aeat/locales/hu.yml` — descendiente flag help
