---
name: r1-vat-enumeration-phase1-summary
description: Phase 1 summary — R-1 VAT enumeration substrate landed on feature/85-r1-vat-enumeration.
type: exec
tags:
  - "#exec"
  - "#r1-vat-enumeration"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-r1-vat-enumeration-research]]"
  - "[[2026-04-13-r1-vat-enumeration-adr]]"
  - "[[2026-04-13-r1-vat-enumeration-plan]]"
  - "[[2026-04-13-r1-vat-enumeration-phase1-schema-exec]]"
  - "[[2026-04-13-r1-vat-enumeration-phase1-catalogue-exec]]"
  - "[[2026-04-13-r1-vat-enumeration-phase1-cli-exec]]"
---

# r1-vat-enumeration phase 1 — summary

## outcomes

- Landed the `aeat.domain.financial.vat` subpackage as a strict pydantic v2
  substrate covering the 16 Spanish VAT situations called out in
  issue #85, with ≥32 Ley 37/1992-backed citations and a
  27-member-state EU rate table holding 61 `VATRate` entries.
- Wired a Typer `aeat vat` sub-app (categories list, rates list,
  show, rule, verify) into the root CLI.
- Added `AEAT_VAT_CATALOGUE_ROOT` to both `aeat.core.config.Settings`
  and `env/.env.example`; `tests/test_config.py` stays aligned.
- Colocated unit tests (`@pytest.mark.unit`) covering
  enumerations, rate lookup, catalogue invariants, corpus fallback
  and verification. CLI unit tests exercise every command via
  `typer.testing.CliRunner`.

## acceptance gates

- `just lint` — all checks passed.
- `just typecheck` — all checks passed (`ty check src tests`).
- `just test` — 724 passed, 1 skipped, 23 deselected (live markers).
- `just hooks` — trim trailing ws / eof / yaml / toml / large files
  / merge conflicts / private key / ruff / ruff format / ty — all
  passed.

## acceptance criteria from issue #85

- `VATCategory` members = 16 expected names — verified by
  `test_vat_category_has_every_named_member`.
- `EUMemberState` members = 27 — verified.
- `VAT_RATE_TABLE` covers all 27 states, total 61 rates — verified
  by `test_rate_table_covers_all_27_member_states` and
  `test_rate_table_has_at_least_50_entries`.
- ES fully expanded — verified by `test_es_rate_table_fully_expanded`.
- `lookup_rate(ES, GENERAL, 2025-06-01).pct == 21` — verified.
- `cite(DOMESTIC_GENERAL_21)` contains "Ley 37/1992" — verified.
- `verify_catalogue(VAT_CATALOGUE_2025).clean is True` — verified.
- `aeat vat verify` exits 0 — verified.

## files produced

### source

- `src/aeat/domain/financial/__init__.py`
- `src/aeat/domain/financial/vat/__init__.py`
- `src/aeat/domain/financial/vat/_schema.py`
- `src/aeat/domain/financial/vat/_rates.py`
- `src/aeat/domain/financial/vat/_catalogue.py`
- `src/aeat/domain/financial/vat/_lookup.py`
- `src/aeat/domain/financial/vat/_corpus.py`
- `src/aeat/domain/financial/vat/_verify.py`
- `src/aeat/domain/financial/vat/errors.py`

### tests

- `src/aeat/domain/financial/vat/test_categories.py`
- `src/aeat/domain/financial/vat/test_rates.py`
- `src/aeat/domain/financial/vat/test_rules.py`
- `src/aeat/domain/financial/vat/test_corpus.py`
- `src/aeat/domain/financial/vat/test_verify.py`
- `src/aeat/entrypoints/cli/test_vat_cli.py`

### cli + config

- `src/aeat/entrypoints/cli/vat.py`
- `src/aeat/entrypoints/cli/__init__.py` (edited)
- `src/aeat/config.py` (edited)
- `env/.env.example` (edited)

### vault

- `.vault/research/2026-04-13-r1-vat-enumeration-research.md`
- `.vault/adr/2026-04-13-r1-vat-enumeration-adr.md`
- `.vault/plan/2026-04-13-r1-vat-enumeration-plan.md`
- `.vault/exec/2026-04-13-r1-vat-enumeration/2026-04-13-r1-vat-enumeration-phase1-schema.md`
- `.vault/exec/2026-04-13-r1-vat-enumeration/2026-04-13-r1-vat-enumeration-phase1-catalogue.md`
- `.vault/exec/2026-04-13-r1-vat-enumeration/2026-04-13-r1-vat-enumeration-phase1-cli.md`
- `.vault/exec/2026-04-13-r1-vat-enumeration/2026-04-13-r1-vat-enumeration-phase1-summary.md`

## deviations from brief

- `Citation.quoted_text_es` values are **faithful paraphrases** of
  the operative language of the cited Ley 37/1992 articles rather
  than verbatim BOE extracts. The brief explicitly permits this
  ("MAY be a faithful paraphrase … when you cannot verbatim-quote
  the source"); documented in the `_catalogue.py` module
  docstring and in the `Citation` docstring. Every paraphrase
  preserves the article's operative fiscal meaning.
- The brief's STEP 16 naming `Citation` / `VATRegulation` with a
  `model validator` that requires ≥1 citation is implemented via a
  dedicated `_validate` model-validator rather than a
  `Field(min_length=1)` annotation — the latter does not work with
  `tuple[Citation, ...]` under pydantic v2 strict mode. The
  resulting constraint is identical.
- The Typer top-level layout uses nested sub-apps
  (`aeat vat categories list`, `aeat vat rates list`) as specified
  in the brief. `rule` and `show` are kept as top-level `aeat vat`
  commands rather than nested under a `rules` sub-app, matching
  the `aeat normatives show` ergonomics.

## code review

Code review by the `vaultspec-code-reviewer` persona is still
required before the PR can be opened, per the handover brief.
