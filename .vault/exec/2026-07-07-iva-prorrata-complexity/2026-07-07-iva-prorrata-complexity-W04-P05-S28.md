---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
step_id: 'S28'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Surface a non-blocking WARNING Notice on ledger add when --sector names a sector absent from the bucket's declared SectorDefinition partition, so a typo'd sector tag that would silently deduct at the common-use percentage is instead disclosed (LIVA arts. 9.1.c / 101)

## Scope

- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`
- `src/aeat/entrypoints/cli/tests/test_prorrata_register_cli.py`

## Description

- Add the `_prorrata_sector_unmatched_notice` helper mirroring the S24 `_prorrata_especial_inert_notice` shape: it loads the bucket's prorrata register through `ProrrataRegisterService` and returns a non-blocking WARNING `Notice` (code `ledger.add.sector_unmatched`) when the row's `--sector` tag names a sector absent from the declared `SectorDefinition` partition, and `None` when the sector is declared or no tag was supplied.
- Wire the notice into the `ledger_add` emit path alongside the idempotent-noop and inert-classification notices, appending its message to both the typed `notices` list and the text `noop_lines`.
- Add the `cli.ledger.add.sector_unmatched` key to all four locale catalogues through `python -m aeat.locales set` (real en/es/ca/hu translations grounded in LIVA arts. 9.1.c / 101), naming the sector, stating it deducts at the common-use percentage, and pointing to `app ledger prorrata declare-sector`.
- Add two real-behaviour CLI tests driving the actual `ledger add` path: the WARNING fires when `--sector` names an absent sector, and is silent once the sector is declared via `declare-sector`.

## Outcome

An operator who mistypes `--sector` (or tags a sector not yet declared) now receives a visible advisory instead of the input silently deducting at the common-use percentage — closing the last gating MEDIUM (`no-silent-under-declaration`) from the W04 code-review. The declare-order remains intentionally free: a not-yet-declared sector is legitimate, so the surface warns rather than refuses. Locale scaffold `--check` is clean across all four catalogues; `test_parity.py` + `test_locale_translation_honesty.py` pass (22); the prorrata register CLI suite passes (14, including the two new fires/silent tests); ruff, ruff format, ty, the 140-test JSON-schema conformance suite, and `src/aeat` collect-only (15152 tests) are all green.

## Notes

- The `python -m aeat.locales set` calls for the en/es/ca values needed a `--` option-parsing terminator because the message text begins with the literal `--sector`; without it the leaf value was consumed as a CLI flag and silently not written (caught by `scaffold --check` before commit). The hu value starts with a letter and wrote directly.
