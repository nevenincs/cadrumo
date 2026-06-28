---
step_id: "S213"
tags:
  - "#exec"
  - "#m100-marriage-date-axis"
date: 2026-05-27
modified: '2026-05-27'
commit: 81feae7b0
related:
  - "[[2026-05-21-fresh-cli-persona-testimonial-wave-plan]]"
---

# M100 marriage_date axis — S213

## What was delivered

Added `renta_taxpayer.marriage_date` as a `date`-typed profile fact enabling
Art. 82 LIRPF matrimonio-sobrevenido derivation for casillas 0245/0246/0247.

## Key files

- `src/aeat/domain/profile/_marriage_facts.py` — domain helpers: `marriage_full_year`, `marriage_month_start`, `marriage_derived_facts`, `marriage_date_from_facts`, `parse_marriage_date_flag`
- `src/aeat/domain/profile/__init__.py` — exports added
- `src/aeat/application/modelo/_profile_binding.py` — `_inject_derived_marriage_facts()` injects computed integer facts at binding-resolution time using `snapshot.filing_year`
- `src/aeat/application/wizard/_commands.py` — `--taxpayer-marriage-date` CLI flag
- `src/aeat/_data/registry/aeat/user_profile/schema.toml` — four new fields in `renta_taxpayer` section
- Registry TOML: `0014-renta-2024-profile-marriage-full-year.toml`, `0045-renta-2025-profile-marriage-full-year.toml`, `0178-renta-2024-matrimonio-vigente-todo-anio.toml`, `0180-renta-2025-matrimonio-vigente-todo-anio.toml` (remainder already committed in registry hardening)

## Tests

- `src/aeat/domain/profile/test_marriage_facts.py` — 22 oracle tests grounded in Art. 82 LIRPF oracle cases from spec #213
- `src/aeat/application/user_profile/test_marriage_date_persistence_roundtrip.py` — encrypted-SQL roundtrip + anti-tautology
- `src/aeat/application/modelo/test_profile_binding_real_path.py` — fixture updated with `marriage_date=date(2023,6,15)`, injection call added, count updated 30→33

## Oracle cases verified

- `marriage_date=2024-03-22, filing 2024` → 0245=0, 0246=3, 0247=12
- `marriage_date=2023-09-15, filing 2024` → 0245=1, 0246=1, 0247=12
- `marriage_date=None` → no facts emitted, casillas default to 0 via engine missing-binding path

## Gates

- G1 no naked env reads: pass
- G2 typed pydantic at boundaries: pass
- G3 tr() for user messages: pass (locale keys already committed in S177)
- G4 no locale yml hand-edits: pass (keys were already committed; our edits were no-ops)
- G5 no shims/duplication: pass
- G6 no tautological tests: pass (oracle values from Art. 82 LIRPF spec)
