---
name: r1-vat-enumeration-plan
description: Implementation plan for the Track B R-1 VAT enumeration substrate.
type: plan
tags:
  - "#plan"
  - "#r1-vat-enumeration"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-r1-vat-enumeration-research]]"
  - "[[2026-04-13-r1-vat-enumeration-adr]]"
---

# r1-vat-enumeration plan

## phase 1 — schema + errors + settings

1. Create `src/aeat/domain/financial/__init__.py` (docstring + empty
   `__all__`).
2. Create `src/aeat/domain/financial/vat/_schema.py` with:
   - `_StrictFrozen`, `_StrictMutable` mirrored on
     `aeat.domain.normatives._schema`.
   - `_require_spanish` model-validator helper.
   - StrEnums `VATCategory` (16 members per issue #85 body),
     `EUMemberState` (27 members), `VATRateKind`, `CitationSource`.
   - Models `VATRate`, `Citation`, `VATRegulation`, `VATCatalogue`,
     `VerificationIssue`, `VerificationReport`.
3. Create `src/aeat/domain/financial/vat/errors.py` with `VatError`,
   `VatRateNotFoundError`, `VatCategoryNotFoundError`,
   `VatCatalogueError`.
4. Add `aeat_vat_catalogue_root` to `src/aeat/config.py` and the
   matching `AEAT_VAT_CATALOGUE_ROOT` entry to `env/.env.example`.

**Gate**: `just lint && just typecheck && just test && just hooks`
green.

## phase 2 — catalogue + rates + helpers + verify

1. Populate `src/aeat/domain/financial/vat/_rates.py` with `VAT_RATE_TABLE`
   (≥50 entries; ES/DE/FR/IT/NL fully expanded).
2. Populate `src/aeat/domain/financial/vat/_catalogue.py` with
   `VAT_CATALOGUE_2025` — one `VATRegulation` per `VATCategory`,
   each carrying ≥2 `Citation` records (total ≥32) quoting real
   Ley 37/1992 article text.
3. Add `src/aeat/domain/financial/vat/_lookup.py` (`lookup_rate`, `cite`).
4. Add `src/aeat/domain/financial/vat/_corpus.py`
   (`load_vat_rules_from_manual`).
5. Add `src/aeat/domain/financial/vat/_verify.py` (`verify_catalogue`).
6. Wire everything through `src/aeat/domain/financial/vat/__init__.py`
   public surface.
7. Colocated unit tests: `test_categories.py`, `test_rates.py`,
   `test_rules.py`, `test_corpus.py`, `test_verify.py`.

**Gate**: `just lint && just typecheck && just test && just hooks`
green.

## phase 3 — cli wiring + cli tests

1. Add `src/aeat/entrypoints/cli/vat.py` with the Typer sub-app (`categories
   list`, `rates list`, `show`, `rule`, `verify`).
2. Wire it in `src/aeat/entrypoints/cli/__init__.py`.
3. Add `src/aeat/entrypoints/cli/test_vat_cli.py` exercising the commands with
   `typer.testing.CliRunner`.

**Gate**: `just lint && just typecheck && just test && just hooks`
green.

## acceptance (from issue #85)

- `VATCategory` has the 16 named members.
- `EUMemberState` has all 27 current EU members.
- `VAT_RATE_TABLE` covers ≥27 member states; ES + DE fully expanded;
  total rate entries ≥50.
- `VAT_CATALOGUE_2025` covers every `VATCategory` with ≥1 citation
  each; total citation count ≥32.
- `lookup_rate(EUMemberState.ES, VATRateKind.GENERAL, 2025-06-01)`
  returns 21 %.
- `cite(VATCategory.DOMESTIC_GENERAL_21)` returns a string
  containing "Ley 37/1992".
- `verify_catalogue(VAT_CATALOGUE_2025).clean is True`.
- `aeat vat verify` exits 0 on the shipped catalogue.
- `just lint && just typecheck && just test && just hooks` green.
