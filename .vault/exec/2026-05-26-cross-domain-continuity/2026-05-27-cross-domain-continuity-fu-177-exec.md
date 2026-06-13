---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: "S177"
date: 2026-05-27
modified: '2026-05-27'
commit: 9ed6837f7
related:
  - "[[2026-05-27-cross-domain-continuity-fu-176-exec]]"
---

# S177: Art. 59 LIRPF custodia compartida prorrata 50 %

## What was done

- Added `custodia_compartida: bool = False` to `DescendantInfo` in `family.py`
  with docstring citing Art. 59 LIRPF.
- Added three methods to `RentaFamilyProfile`:
  - `custodia_compartida_count(filing_year)` — count of eligible descendants with the flag
  - `custodia_compartida_prorrata_factor(d, filing_year)` — returns `Decimal("0.5")` when eligible+flagged, else `Decimal("1")`
  - `custodia_compartida_advisory(filing_year)` — calls `tr("profile.descendiente.custodia_compartida_prorrata_applied", count=n)` or returns `None`
- Updated `_descendant_facts.py`: serialise `custodia_compartida=True` as a fact key; absent key defaults to False on load. Regex updated. `parse_descendiente_flag` accepts `CUSTODIA=true|false`.
- Added locale key `profile.descendiente.custodia_compartida_prorrata_applied` in es/en/ca/hu.
- Updated `descendiente:` flag help text to document `CUSTODIA=` parameter.
- 22 new unit tests in `test_custodia_compartida.py`.

## Verification

```
pytest src/aeat/domain/profile/test_custodia_compartida.py -q
# 22 passed

pytest src/aeat/domain/profile/ -q
# 113 passed

python -m aeat.locales audit
# ca.yml ok  en.yml ok  es.yml ok  hu.yml ok
```

## Files changed

- `src/aeat/domain/profile/family.py`
- `src/aeat/domain/profile/_descendant_facts.py`
- `src/aeat/domain/profile/test_custodia_compartida.py`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`
