---
tags:
  - "#research"
  - "#usage-ratios"
date: 2026-04-21
modified: '2026-04-21'
related:
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-18-category-assignment-cli-adr]]"
---

# usage-ratios research

## objective

Ground issue `#259` — "Kent configures his own usage ratios once". Kent measures his real home-office share (15 m² of 70 m² = 21%) and wants to persist that coefficient once so every `USAGE_RATIO_*` category defaults to his number instead of the statutory 30% fallback. Research the existing proportionality surface, CLI layout, persistence pattern, and pydantic idioms that the ADR must honour.

## findings

### 1. existing proportionality surface

**Model — `src/aeat/domain/financial/categories/_proportionality.py:64–108`.** `ProportionalityRule` is a frozen pydantic v2 model with `kind: ProportionalityKind`, `fixed_pct: Decimal | None`, `default_ratio: Decimal | None`, `statutory_cap_*`, `citations`, `notes_es`. Cross-field `model_validator(mode="after")` already pins `default_ratio` to `USAGE_RATIO_HOME_AREA` or `USAGE_RATIO_PERSONAL` kinds and bounds every ratio-valued field to `[0, 1]` via `Field(ge=Decimal("0"), le=Decimal("1"))`.

**Kinds — `src/aeat/domain/financial/categories/_proportionality.py:46–54`.**

```
FULL_DEDUCTIBLE, FIXED_PERCENTAGE, USAGE_RATIO_PERSONAL,
USAGE_RATIO_HOME_AREA, STATUTORY_CAP, NON_DEDUCTIBLE
```

Only the two `USAGE_RATIO_*` kinds are candidates for user-override today. `FIXED_PERCENTAGE` is statutory; `STATUTORY_CAP` is legally bounded; `FULL_DEDUCTIBLE` / `NON_DEDUCTIBLE` are not coefficient-shaped.

**Category registry — `src/aeat/domain/financial/categories/_registry.py:400–616` (usage-ratio rows only).**

| `SpendingCategory` | `kind` | `default_ratio` |
|---|---|---|
| `ARRENDAMIENTO_VIVIENDA_AFECTO` | `USAGE_RATIO_HOME_AREA` | `0.30` |
| `SUMINISTROS_HOME_OFFICE_LUZ` | `USAGE_RATIO_HOME_AREA` | `0.30` |
| `SUMINISTROS_HOME_OFFICE_AGUA` | `USAGE_RATIO_HOME_AREA` | `0.30` |
| `SUMINISTROS_HOME_OFFICE_GAS` | `USAGE_RATIO_HOME_AREA` | `0.30` |
| `SUMINISTROS_HOME_OFFICE_INTERNET` | `USAGE_RATIO_HOME_AREA` | `0.30` |
| `TELEFONIA_FIJA` | `USAGE_RATIO_HOME_AREA` | `0.30` |
| `TELEFONIA_MOVIL` | `USAGE_RATIO_PERSONAL` | *(none)* |
| `VEHICULO_COMBUSTIBLE` | `USAGE_RATIO_PERSONAL` | *(none)* |
| `VEHICULO_MANTENIMIENTO` | `USAGE_RATIO_PERSONAL` | *(none)* |
| `VEHICULO_SEGURO` | `USAGE_RATIO_PERSONAL` | *(none)* |
| `VEHICULO_PEAJE` | `USAGE_RATIO_PERSONAL` | *(none)* |
| `VEHICULO_PARKING` | `USAGE_RATIO_PERSONAL` | *(none)* |

Twelve categories in total. No user-override write surface exists today.

**`SpendingCategory` — `src/aeat/domain/financial/categories/_spending_category.py:8–48`.** Closed `StrEnum` of 39 stable identifiers. `SpendingCategoryFamily` groups are declared in the same file (`HOME_OFFICE`, `VEHICLE`, `TELECOMS`, …) and the membership table at lines 69–132 maps each family to its categories.

**`CategoryProfile` container — `src/aeat/domain/financial/categories/_profile.py:29–52`.** Holds the `ProportionalityRule`, per-modelo casilla mappings, and VAT hint. No override slot today.

### 2. CLI layout

**Financial sub-app — `src/aeat/entrypoints/cli/financial/__init__.py:11–33`.** `aeat financial` currently wires three children via `app.add_typer(...)` and `app.command(...)`:

- `ingest` (command) — `aeat financial ingest`
- `txs` (sub-app) — `aeat financial txs list|show|classify|…`
- `invoices` (sub-app) — `aeat financial invoices list|show|link|…`

No `profile` sub-app exists. Adding `aeat financial profile …` is a matter of dropping a new `profile.py` next to `invoices.py` and appending one `app.add_typer(profile_app, name="profile", …)` line.

**Invoice sub-app template — `src/aeat/entrypoints/cli/financial/invoices.py:33–222`.** Canonical pattern:

- `app = typer.Typer(name=…, no_args_is_help=True, help=…)`
- Each command uses `typer.echo(...)` for tab-separated lists or `typer.echo(model.model_dump_json(indent=2))` for single records.
- Errors surface via `typer.echo(str(exc), err=True)` followed by `raise typer.Exit(code=2) from exc`.
- Path helpers read from `load_settings()` and resolve a default filename (e.g. `_DEFAULT_INVOICE_FILENAME = "invoices.json"`).
- "Load or empty" helper returns a fresh empty catalogue when the file is absent, so read-only commands never fault on a virgin install.

**Command-name convention.** `aeat financial txs classify --category KEY --reason …` (from `2026-04-18-category-assignment-cli-adr`) uses lowercase kebab for commands and accepts `SpendingCategory` enum values as `--category` argument. Any new `set-ratio` / `unset-ratio` command must mirror this.

### 3. persistence pattern

**Invoice service — `src/aeat/domain/financial/invoices/_service.py:71–126`.**

- `load_invoices(path)` → `path.read_text(encoding="utf-8")` → `InvoiceCatalogue.model_validate_json(raw)`; OSError → `InvoicePersistenceError`; ValidationError → `InvoicePersistenceError`.
- `save_invoices(catalogue, path)` → `path.parent.mkdir(parents=True, exist_ok=True)` → write to a sibling `NamedTemporaryFile` in the same directory → `os.replace(tmp, target)` for crash-safe atomic replacement. On OSError, unlink the temp and raise `InvoicePersistenceError`.
- Both log one `INFO` line via `get_logger(__name__)`.

**Transaction service — `src/aeat/domain/financial/transactions/_service.py:23–78`.** Identical shape with its own error type (`TransactionPersistenceError`).

**Takeaway.** The "atomic JSON round-trip" helper pair is the repo's canonical shape for any user-writable profile document. `UsageRatioProfile` must follow it verbatim, including the tempfile + `os.replace` dance.

**Settings path — `src/aeat/config.py:129–140`.** Paths are declared on `Settings` with `PROJECT_ROOT / "var" / "financial" / …` defaults, normalised after-validation via the `_normalize_repo_relative_paths` validator (lines 599–630). Every such field is added to the `@field_validator(..., mode="after")` path-list.

### 4. pydantic v2 idioms

**Frozen boundary model.** `_StrictFrozenModel` in `_proportionality.py:11–14`:

```python
class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
```

Not exported; each package redeclares its own (`_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")` in `invoices/_service.py:37`). Consistent pattern: `extra="forbid"` wherever dicts-from-JSON are accepted.

**Ratio bounds.** `Field(default=None, ge=Decimal("0"), le=Decimal("1"))` on `fixed_pct` / `default_ratio` — the ADR's ratio fields must use the same bounds. `Decimal`, not `float`.

**Cross-field rule.** `@model_validator(mode="after")` returns `self`; raises `ValueError` for shape violations; reuses the `{KIND_A, KIND_B}` set pattern.

**Field validator.** `_service.py:53–58` (`ReconciliationSuggestion.score`) shows the single-field `@field_validator(...)` + `raise ValueError("…")` pattern used for range checks that live-validate at parse time.

### 5. test patterns

**Module-level marker — `src/aeat/domain/financial/categories/test_proportionality.py:19`.**

```python
pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]
```

No per-function markers; axis A (`unit`) + axis B (`domain_financial_input`) applied once.

**CLI test — `src/aeat/entrypoints/cli/financial/test_cli.py:13`** uses the same two markers and drives commands via `CliRunner`. Fixtures live at `tests/fixtures/financial/`.

**Validation assertion pattern — `test_proportionality.py:32–76`.** Every "rejects X" test uses `with pytest.raises(ValidationError): ProportionalityRule(...)`. Round-trip tests instantiate + read back field values directly.

### 6. related vault artifacts

**`.vault/audit/2026-04-18-kent-data-prep-journey-audit.md` — wall DP7 (lines 112–127).** Names #259 as the owner of the missing override surface: "Kent's 21% home-office ratio is his — not a default for every autónomo. `CategoryProfile.proportionality.default_ratio` is a statutory default." Mapping table at lines 200–214 binds DP7 → #259. No existing ADR covers user ratios; closest priors are `2026-04-18-category-assignment-cli-adr` (`--category` on `txs classify`) and `2026-04-18-unclassified-state-adr` (enum split + history).

**`.vault/adr/2026-04-18-rename-corpus-review-schema-adr.md` and peers.** Establish the pattern of "frozen pydantic model ⇢ JSON file under `var/` ⇢ load/save helpers ⇢ CLI verbs". `UsageRatioProfile` belongs in the same row.

### 7. downstream dependencies

**Issue #257 (deductibility compute).** The consumer. Once the profile exists, #257's compute service reads `UsageRatioProfile`, falls back to `ProportionalityRule.default_ratio`, and records which source won in the transaction's trace fields (`proportionality_applied`, `provenance`). The ADR must describe the lookup contract so #257 has a fixed signature to compile against, even though the actual compute module ships in a separate PR.

**Issue #214 (setup wizard).** Will call the same save helper during onboarding to capture ratios up-front. No API tension expected — the save helper is the same function either way.

**Issue #258 (`txs classify --category`).** Unrelated but confirms the CLI convention for `SpendingCategory` values as string arguments.

## key decisions for the ADR

1. **Ratio-key taxonomy — category-keyed vs concept-keyed.** Issue body lists mixed-granularity keys (`home_office_area` + `home_office_utilities_luz/agua/gas/internet`). Two clean options:
   - **(A) `SpendingCategory`-keyed.** Keys are the 12 usage-ratio-eligible category values. Pro: no new taxonomy, validates via the existing enum, trivial lookup in compute. Con: Kent sets 6 separate home-office keys to get a uniform ratio across electricity/water/gas/internet/rent/fixed phone.
   - **(B) Concept-keyed.** Introduce a small `UsageRatioKey` enum (e.g., `HOME_OFFICE_AREA`, `MILEAGE_BUSINESS`, `PHONE_MOBILE_BUSINESS`) plus a `SpendingCategory → UsageRatioKey` table. Pro: matches Kent's mental model ("my home office is 21%, full stop"). Con: a new taxonomy, a new `.py` file, and breakage risk if the `ProportionalityRule` kinds evolve.
   - **Recommendation:** (A) for scope (#259 is `effort:M`, `priority:P2-medium`) with a small concession — the CLI accepts a family sugar like `--family home_office` that expands to every eligible category in one call. Backstop the 6-home-office-keys UX without inventing a new taxonomy layer.
2. **Ratio bounds.** Strict `[0, 1]` (inclusive both ends) matching `ProportionalityRule.default_ratio`. Reject `< 0`, `> 1`, and non-numeric input at model boundary.
3. **Eligibility check.** `UsageRatioProfile` must reject a key whose category's `ProportionalityRule.kind` is neither `USAGE_RATIO_HOME_AREA` nor `USAGE_RATIO_PERSONAL`. This is a data-integrity check — Kent cannot override a ratio on a category that is `FULL_DEDUCTIBLE` by statute.
4. **Persistence shape.** One JSON file, `var/financial/usage-ratios.json`, round-tripped via `model_dump_json()` / `model_validate_json()`, atomic write via the `NamedTemporaryFile + os.replace` pattern from `invoices/_service.py:96–126`.
5. **Settings field.** `aeat_usage_ratios_path: Path = Field(default=PROJECT_ROOT / "var" / "financial" / "usage-ratios.json", description="...")`. Add to the `_normalize_repo_relative_paths` list. Document in `env/.env.example`.
6. **Consumer contract for #257.** Publish a `resolve_user_ratio(profile, category) -> Decimal | None` pure helper that returns the user-set ratio or `None`. #257 decides how to combine with `default_ratio`; this ADR does not commit to a compute semantics beyond "profile wins over statutory default when present".

## references

- `src/aeat/domain/financial/categories/_proportionality.py`
- `src/aeat/domain/financial/categories/_registry.py`
- `src/aeat/domain/financial/categories/_spending_category.py`
- `src/aeat/domain/financial/categories/_profile.py`
- `src/aeat/entrypoints/cli/financial/__init__.py`
- `src/aeat/entrypoints/cli/financial/invoices.py`
- `src/aeat/domain/financial/invoices/_service.py`
- `src/aeat/domain/financial/transactions/_service.py`
- `src/aeat/config.py`
- `.vault/audit/2026-04-18-kent-data-prep-journey-audit.md`
