---
tags:
  - '#adr'
  - '#operator-workflows-expansion'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-operator-workflows-expansion-research]]"
  - "[[2026-04-25-operator-workflows-expansion-plan]]"
---

# `operator-workflows-expansion` adr: cli-integration-coverage

Implementation ADR for wgergely/aeat#340 (child of EPIC #316). Documents
the controlling decisions for adding ten Kent-CLI integration tests to
`tests/integration/test_kent_workflows.py`.

## Context

Audit finding 2026-04-22 (cited by EPIC #316): only Modelo 130 has a
CLI-level integration test asserting the full
parse → ruleset-resolve → verify chain. Eleven Tier-L modelos have
landed extractors and ten of them have at least one landed ruleset, but
a regression in `aeat.entrypoints.cli.filing._handle_declaracion_import` or
`_handle_borrador_import` would silently break the user-facing import
verb for every uncovered modelo without a CI signal. This ADR locks in
the Kent-observable contract for the import surface across all ten
modelos.

## Decisions

### D1. CLI-layer-only coverage

Each new test class invokes the CLI via `typer.testing.CliRunner` —
exactly the surface a Kent runs at the prompt. Direct calls to
`parse_declaracion`, `parse_borrador`, `verify_declaracion`, or
`Engine.audit_against` are forbidden in this file; those are already
exercised at the `aeat.adapters.inbound.declaracion` and `aeat.application.verification` layers.
The audit gap closed by this ADR is at the CLI layer specifically.

### D2. Ten classes, one per Tier-L modelo

The ten new classes are:

1. `TestKentImportsModelo100SummaryBorrador`
2. `TestKentImportsModelo111Declaracion`
3. `TestKentImportsModelo115Declaracion`
4. `TestKentImportsModelo123Declaracion`
5. `TestKentImportsModelo131Declaracion`
6. `TestKentImportsModelo180Declaracion`
7. `TestKentImportsModelo200Declaracion`
8. `TestKentImportsModelo202Declaracion`
9. `TestKentImportsModelo303Declaracion`
10. `TestKentImportsModelo390Declaracion`

NOTE - naming deviation for Modelo 100. The handover prompt's literal
template name was `TestKentImportsModelo100SummaryDeclaracion`, but
Modelo 100 is dispatched via `aeat filing import --from-borrador` (NOT
`--from-declaracion`); `parse_declaracion` does not handle Renta
artefacts. The class is named after the actual CLI flag exercised so
the file reads honestly to the next maintainer. The audit's intent
("CLI-integration coverage for every Tier-L modelo's import path") is
honoured.

### D3. Three mandatory cases per class, optional fourth

Mandatory:

- `test_happy_path_english` - `AEAT_OUTPUT_LANGUAGE=en`, asserts
  `Verification status: VERIFIED` and (where applicable)
  `Extraction status: COMPLETE`.
- `test_happy_path_spanish_default` - env var unset (Spanish is the
  project default), asserts `VERIFIED` plus the Spanish narrative
  fragment (`verificado` / `revisar`).
- `test_partial_extraction_needs_review` - PDF rendered with 50-95%
  of required casillas; asserts `Extraction status: PARTIAL` and that
  at least one expected missing casilla id appears on a warning line.

Optional fourth:

- `test_discrepancy_classified_correctly` - happy-path PDF with one
  computed casilla intentionally drifted by >= 1 EUR; asserts
  `Verification status: NEEDS_REVIEW` and the substring
  `cause=CORRECTNESS_DIVERGENCE` and the affected casilla id.

The 4th case is INCLUDED for every modelo with at least one computed
casilla in its 2025 ruleset. It is SKIPPED for Modelo 200 (no 2025
ruleset -> UNVERIFIABLE -> no formula can diverge).

For Modelo 100-summary the borrador CLI emits no `Extraction status:`
line, so the canonical `test_partial_extraction_needs_review` case is
not meaningful. The third method on that class is therefore renamed
`test_discrepancy_triggers_needs_review` and exercises the same Kent-
observable target as the discrepancy 4th case on the declaracion
classes — a drifted computed casilla that the borrador's
`Engine.audit_against` lights up as a NEEDS_REVIEW verdict. Net
coverage: Modelo 100-summary still has three CLI-integration cases,
all with stable-marker assertions, and the discrepancy classifier IS
locked in.

### D4. Modelo 200 locks in the UNVERIFIABLE verdict

Modelo 200 happy-path tests assert `Verification status: UNVERIFIABLE`
plus the narrative substring `no ruleset registered` (en) /
`no hay ruleset registrado` (es). This is the Kent-observable behaviour
today (2025-template extractor + 2024-only ruleset), and locking it in
makes the future ramp from UNVERIFIABLE -> VERIFIED a deliberate update
of these assertions when the 2025 Modelo 200 ruleset lands. The
PARTIAL case is still meaningful (the extractor still emits
`Extraction status: PARTIAL`); only the 4th discrepancy case is
skipped.

### D5. Stable-marker assertions only - forward-compat with #398 / #399

Every textual assertion is a substring match against a known stable
marker:

- `Extraction status: COMPLETE` / `PARTIAL` / `FAILED`
- `Verification status: VERIFIED` / `NEEDS_REVIEW` / `UNVERIFIABLE`
- `cause=CORRECTNESS_DIVERGENCE` / `EXTRACTION_UNRELIABLE` /
  `UNMODELLED_RULE` / `ROUNDING`
- `casilla XX` (specific id, for warning / discrepancy lines)
- `verified` / `verificado` (narrative language probe)
- `revisar` / `needs review` (narrative language probe)

NO assertions on full multi-line equality, ordering, surrounding chrome,
emoji, ANSI colour, or any field that #398 / #399 / future i18n work
might reshape.

### D6. No new generators

The existing `_generic_quarterly_generator.py` is reused for every
quarterly + annual summary modelo. The dedicated
`modelo_303_generator.py` is reused for Modelo 303. The dedicated
`modelo_100_generator.py` is reused for Modelo 100-summary. Label
maps are inlined into `tests/integration/test_kent_workflows.py` so
the file remains self-contained and any future re-organisation of
`aeat.adapters.inbound.declaracion`-internal test fixtures does not break the
integration suite.

### D7. No mocks. Real PDFs, real CLI, real engine.

`tmp_path` is a pytest builtin (real filesystem). `monkeypatch.setenv`
for `AEAT_OUTPUT_LANGUAGE` is environment manipulation, not a mock. The
synthetic PDFs are fully rendered by `reportlab`; the CLI invocation
goes through Click's runner; the parser, ruleset registry, and
verifier all run unmodified. This satisfies issue #340 DoD bullet 3
explicitly.

### D8. Module-level marker preserved

The existing `pytestmark = [pytest.mark.unit,
pytest.mark.domain_financial_input, pytest.mark.fixture_tier_l3]` is
unchanged. The handover prompt's suggestion to flip to
`domain_submission` is rejected because (a) the parser/CLI work is
owned by the financial-input domain in this repo and (b) flipping the
marker would silently re-route the file in `just test-domain`
selection.

## Self-review (CLAUDE.md compliance)

- Pytest-only, no mocks/skips/patches/stubs/fakes - confirmed by D7.
- Real CLI surface exercised end-to-end - confirmed by D1.
- pydantic v2 strict applies to test-helper config (none introduced).
- typed signatures + Google-style docstrings on every test class - planned.
- Errors inherit from `aeat.core.errors.AeatError` - tests do not raise.
- Logging via `aeat.core.logging.get_logger` - tests do not log.
- Test markers preserved at module level - D8.
- Coverage floor 60% on `src/aeat` - test additions only raise it.
- No new public surface introduced under `src/aeat/`.
- No skips on lint/typecheck.

## Consequences

- 10 new classes x >= 3 cases ~= 33+ new tests under `pytest.mark.unit`.
  CI runtime impact: each case generates one synthetic PDF (~50 ms)
  and runs Click's CliRunner (~50 ms). Estimated total: ~4-5 s of
  added test time on the unit suite per platform.
- Coverage on `src/aeat/entrypoints/cli/filing/__init__.py` and
  `src/aeat/application/verification/_verify.py` rises (positive - these are the
  audited surfaces). Source coverage of `src/aeat` stays well above
  the 60 % floor.
- A future Modelo 200 2025 ruleset (or any ruleset year-coverage
  expansion) requires updating the test assertions to match the new
  verdict - flagged as a deliberate intent in the class docstring.
- A future #398 / #399 merge may surface output drift in chrome or
  rendering format; stable-marker assertions absorb most of this. A
  routine rebase will resolve any residual.
