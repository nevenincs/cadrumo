# Casillas Catalogue Workflow

This document explains how to add a new canonical AEAT casilla catalogue under `corpus/casillas/` and validate it before commit.

## Scope

Use this workflow when you need to add a new `(modelo, period)` catalogue such as:

- `MODELO_130` + `2025Q4`
- `MODELO_390` + `2025`

This is a contributor workflow for checked-in corpus data. It is not an automated sync pipeline, and it does not promote draft files automatically.

## Canonical Layout

Canonical catalogues live under:

```text
corpus/casillas/<modelo.lower()>/<period>.json
```

Examples:

- `corpus/casillas/modelo_130/2025Q4.json`
- `corpus/casillas/modelo_303/2025Q4.json`
- `corpus/casillas/modelo_390/2025.json`

The default corpus root is `PROJECT_ROOT / "corpus" / "casillas"`. It is configured through:

- `AEAT_CASILLAS_ROOT`
- `AEAT_CASILLAS_REVIEW_REQUIRED`

Both live in `src/aeat/config.py` and are mirrored in `env/.env.example`.

## Package Surface

The public casillas API lives in `aeat.casillas`. Callers should import from `aeat.casillas`, not internal modules.

Relevant surfaces:

- `src/aeat/casillas/__init__.py`: public package surface
- `src/aeat/casillas/models.py`: canonical models and invariants
- `src/aeat/casillas/catalogue.py`: loader, verifier, canonical path resolution, and canonical persistence
- `src/aeat/cli/casillas.py`: `aeat casillas ...` subcommands
- `src/aeat/cli/__init__.py`: root CLI wiring

## Bootstrap

```bash
uv sync
uv run vaultspec-core install
```

Read the issue and mandate comment before changing the corpus:

```bash
gh issue view 23 --comments
gh issue view 23 --json number,title,body,comments
```

## Adding A New Modelo

Supported modelos are currently hardcoded in `KNOWN_MODELO_IDS` inside `src/aeat/casillas/models.py`.

If you add a new modelo, update that set first. Otherwise the new catalogue will fail model validation before it reaches verification.

## Supported Period Formats

Periods currently accept only:

- `YYYY`
- `YYYYQ1`
- `YYYYQ2`
- `YYYYQ3`
- `YYYYQ4`
- `YYYY-MM`

Examples:

- `2025`
- `2025Q4`
- `2025-03`

## Record Requirements

Canonical casilla payloads are strict frozen Pydantic v2 models. The persisted types are:

- `CasillaDataType`
- `SelectOption`
- `LLMDraftProvenance`
- `CasillaRecord`
- `CasillaCatalogue`

Every checked-in canonical record must include:

- `synthetic: false`
- `modelo`
- `period`
- `casilla_id`
- `label`
- `help`
- `data_type`
- `required`
- `computed`
- `references_casillas`
- `references_rules`
- `validation`
- `source_manual_url`
- `definition_reviewed_by`
- `definition_reviewed_at`

Current validator rules:

- `synthetic` must be `false`
- `casilla_id` must be 2 to 4 digits
- `label` must include authoritative Spanish text
- `help` must include authoritative Spanish text
- `select_options` are required only when `data_type=select`
- duplicate `(modelo, period, casilla_id)` keys are rejected
- `references_casillas` must point to records in the same catalogue
- `definition_reviewed_by` and `definition_reviewed_at` are required when review enforcement is enabled

## Human Review Policy

LLM output is draft-only. It is never the source of truth for committed corpus data.

Canonical corpus files are expected to be human-reviewed before commit. Records lacking `definition_reviewed_by` or `definition_reviewed_at` fail verification by default.

## Draft Workflow

The current `extract` and `translate` commands are dependency-gated. They keep
the command surface reserved for the future issue-21 integration, but they do
not fabricate draft output when that dependency is missing. The current CLI
loads the requested canonical catalogue, prints a dependency message, and exits
with code `2`.

Examples:

```bash
uv run aeat casillas extract --modelo MODELO_130 --period 2025Q4
uv run aeat casillas translate --modelo MODELO_130 --period 2025Q4
```

There is also no command today that promotes a reviewed draft into
`corpus/casillas/...`. After review and manual edits, place the final reviewed
JSON yourself at the canonical path.

## Creating A New Canonical Catalogue

1. Add the modelo identifier to `KNOWN_MODELO_IDS` in `src/aeat/casillas/models.py`.
2. Create `corpus/casillas/<modelo.lower()>/<period>.json`.
3. Ensure every record has:
   - `synthetic: false`
   - trilingual `label`
   - trilingual `help`
   - `source_manual_url`
   - `definition_reviewed_by`
   - `definition_reviewed_at`
4. Ensure `references_casillas` only point to records in the same file.
5. Ensure `select_options` are present only for `data_type=select`.
6. Verify the canonical file until it passes:

```bash
uv run aeat casillas verify --modelo <ID> --period <PERIOD>
```

7. Inspect the normalized payload:

```bash
uv run aeat casillas list --modelo <ID> --period <PERIOD>
```

## Non-Default Roots

All casillas CLI commands support overriding the corpus root:

```bash
uv run aeat casillas verify --modelo MODELO_130 --period 2025Q4 --root <path>
uv run aeat casillas list --modelo MODELO_130 --period 2025Q4 --root <path>
uv run aeat casillas extract --modelo MODELO_130 --period 2025Q4 --root <path>
uv run aeat casillas translate --modelo MODELO_130 --period 2025Q4 --root <path>
```

Use this for local experimentation when you do not want to touch the checked-in corpus.

## Quality Gates

Run the full project gates before treating the change as ready:

```bash
just lint
just typecheck
just test
just hooks
```

To opt into the current live suite:

```bash
AEAT_LIVE_TESTS_ENABLED=true just test-live
```

`tests/test_config.py` also enforces alignment between `Settings` and `env/.env.example`.

## Existing Examples

Use the checked-in catalogues as references for shape and path conventions:

- `corpus/casillas/modelo_130/2025Q4.json`
- `corpus/casillas/modelo_303/2025Q4.json`
- `corpus/casillas/modelo_390/2025.json`

## Known Caveats

- Issue `#23` originally described `src/aeat/schema/casillas.py`, but the implemented package lives under `src/aeat/casillas/`. The codebase path is authoritative.
- Persisted formula and validation payloads currently use Pydantic stand-ins (`FormulaReference`, `ValidationRuleReference`) while broader future-facing stubs live in `src/aeat/casillas/_protocols.py`.
- The issue text expects live extract/translate tests against a real LLM provider. Current live tests stay skipped until the real issue-21 client surface lands.
- The issue text mentions glossary constraints. Current verification enforces authoritative Spanish text, but there is no separate glossary-specific verifier yet.
- Current code uses `AEAT_LIVE_TESTS_ENABLED=true`, not `AEAT_LIVE_TESTS=1`.
- Current reviewer enforcement is minimal: non-empty `definition_reviewed_by` plus non-null `definition_reviewed_at`.

## Quick Reference

Inspect a catalogue:

```bash
uv run aeat casillas list --modelo MODELO_130 --period 2025Q4
```

Verify a catalogue:

```bash
uv run aeat casillas verify --modelo MODELO_130 --period 2025Q4
```

Invoke the dependency-gated extraction command:

```bash
uv run aeat casillas extract --modelo MODELO_130 --period 2025Q4
```

Invoke the dependency-gated translation command:

```bash
uv run aeat casillas translate --modelo MODELO_130 --period 2025Q4
```
