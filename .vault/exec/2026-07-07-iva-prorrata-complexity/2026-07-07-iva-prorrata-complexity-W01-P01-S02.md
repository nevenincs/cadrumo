---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Add the Art104TresExclusion core enum and the operator-declared exclusion tag on the ledger transaction, with save/load roundtrip + anti-tautology proof

## Scope

- `src/aeat/core/`
- `src/aeat/domain/transactions/_models.py`

## Description

- Add the core `Art104TresExclusion` StrEnum with the six art-104.Tres exclusions as one typed closed set, plus the `ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS` / `ART_104_TRES_AUTO_DERIVED_EXCLUSIONS` frozensets that encode the operator-vs-auto split as declared data.
- Export the enum and the two partition sets from the `core` package facade.
- Add an operator-declared `art_104_tres_exclusion` tag to the ledger `Transaction`, coerced from JSON, with a validator that accepts ONLY the two judgment members (foreign permanent establishment, non-habitual inmobiliario/financiero) and refuses the four auto-derived members.
- Add a strict JSON save/load/equality roundtrip with the tag set non-default, plus an anti-tautology proof that a persisted payload tampered to an auto-derived member is refused on load; add a core enum-partition test.

## Outcome

- Modified files: `src/aeat/core/_prorrata_exclusions.py` (new), `src/aeat/core/__init__.py`, `src/aeat/core/tests/test_prorrata_exclusions.py` (new), `src/aeat/domain/transactions/_models.py`, `src/aeat/domain/transactions/tests/test_models.py`.
- 38 focused core + transaction tests pass; ruff / ruff-format / ty clean.
- Committed as `b4ae2205cd`.

## Notes

- The enum lives in its own `core` module (distinct from the register lifecycle enums in `_prorrata_register.py`) because art-104.Tres exclusion is a distinct concept from the register regime axis.
- The operator-declared-only validator is deliberate: the four auto-derived exclusions are recognised from the category / register / structure, so tagging one on a transaction would double-count or misroute a value the ledger already excludes.
