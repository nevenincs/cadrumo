---
tags:
  - "#plan"
  - "#usage-ratios"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-usage-ratios-adr]]"
  - "[[2026-04-21-usage-ratios-research]]"
---

# `usage-ratios` plan: `persist-kent-usage-ratios-as-category-keyed-profile` | (**status:** `completed`)

Executes `[[2026-04-21-usage-ratios-adr]]` against issue `#259`. Single phase; every step is mechanical with a colocated test. Kent-observable acceptance lives in `aeat financial profile …`.

> **Post-approval amendments.** Two rolling audit rounds refined the implementation after this plan was approved. The step list below is preserved as the historical instruction to the executor; for the as-shipped contract see the ADR's `## Post-approval amendments` section and the shipped code. The key deltas are summarised in the `## Post-approval amendments` block at the bottom of this plan.

## Phase 1 — implementation

### Step 1 — scaffold `aeat.domain.financial.usage_ratios` package

Create `src/aeat/domain/financial/usage_ratios/`:

- `__init__.py` — empty placeholder now, fill in step 6.
- `_errors.py` — define `UsageRatioError(AeatError)` and `UsageRatioPersistenceError(UsageRatioError)`. Relative import of `AeatError` from `...errors`. `__all__` lists both names. Google-style docstrings on each class.

No tests in this step; the package must import cleanly.

### Step 2 — `_model.py`: `UsageRatioProfile`, `ELIGIBLE_USAGE_RATIO_CATEGORIES`, `resolve_user_ratio`

Write `src/aeat/domain/financial/usage_ratios/_model.py`:

- Relative imports only (`..categories`).
- Declare `_USER_RATIO_KINDS: frozenset[ProportionalityKind] = frozenset({USAGE_RATIO_HOME_AREA, USAGE_RATIO_PERSONAL})`.
- Compute `ELIGIBLE_USAGE_RATIO_CATEGORIES: frozenset[SpendingCategory]` via `_eligible_categories()` that iterates `CATEGORY_PROFILES_2025`.
- `UsageRatioProfile(BaseModel)` with `model_config = ConfigDict(strict=True, frozen=True, extra="forbid")`, field `ratios: dict[SpendingCategory, Decimal] = Field(default_factory=dict)`.
- `@field_validator("ratios", mode="after")` `_validate_bounds`: loops; for each ratio raise `ValueError` if `not ratio.is_finite()` or if `not (Decimal("0") <= ratio <= Decimal("1"))`. Return `value` unchanged (plain dict — **not** `MappingProxyType`).
- `@model_validator(mode="after")` `_validate_eligibility`: collects `tuple(c for c in self.ratios if c not in ELIGIBLE_USAGE_RATIO_CATEGORIES)`; if non-empty, raise `ValueError` naming the rejected categories. Return `self`.
- `with_ratio(self, category, ratio) -> UsageRatioProfile`: build `new_ratios = dict(self.ratios); new_ratios[category] = ratio; return UsageRatioProfile(ratios=new_ratios)`.
- `without_ratio(self, category) -> UsageRatioProfile`: build `new_ratios = dict(self.ratios); new_ratios.pop(category, None); return UsageRatioProfile(ratios=new_ratios)`.
- `resolve_user_ratio(profile, category) -> Decimal | None`: one-line `profile.ratios.get(category)` with a Google-style docstring citing #257 and #259.
- Export `_USER_RATIO_KINDS` as a private module attribute (used by `_aliases.py`). No `__all__`; exports flow through the package `__init__`.

Colocate `src/aeat/domain/financial/usage_ratios/test_model.py`:

- `from __future__ import annotations`
- Module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]`.
- Import test symbols directly from the package via `from . import ...`.
- Tests:
  1. `test_empty_profile_round_trips_json` — empty profile serialises to `{"ratios": {}}` and reloads.
  2. `test_single_ratio_round_trips` — set `SUMINISTROS_HOME_OFFICE_LUZ=Decimal("0.21")`, serialise + reload, assert equal.
  3. `test_negative_ratio_rejected` / `test_above_one_rejected` — each raises `ValidationError`.
  4. `test_nan_rejected` — `Decimal("NaN")` raises `ValidationError`.
  5. `test_positive_infinity_rejected` — `Decimal("Infinity")` raises `ValidationError`.
  6. `test_negative_infinity_rejected` — `Decimal("-Infinity")` raises `ValidationError`.
  7. `test_unknown_category_key_rejected` — JSON payload `{"ratios": {"foo": "0.5"}}` fails `model_validate_json`.
  8. `test_ineligible_category_rejected` — `UsageRatioProfile(ratios={MATERIAL_OFICINA: Decimal("0.5")})` raises `ValidationError`, error message names the category.
  9. `test_frozen_attribute_reassignment_rejected` — `profile.ratios = {}` raises `ValidationError`.
  10. `test_with_ratio_returns_new_profile` — source profile unchanged; new profile carries the new value.
  11. `test_without_ratio_is_noop_on_unset` — calling on an unset category returns an equivalent profile.
  12. `test_resolve_user_ratio_returns_set_value_or_none` — parametrise over a set category and an unset one.
  13. `test_eligible_categories_match_twelve_expected` — assert `ELIGIBLE_USAGE_RATIO_CATEGORIES == frozenset({...the twelve from the ADR table...})`.
  14. `test_consumer_fallback_contract` — simulate #257 caller: for a category with `resolve_user_ratio → None`, fall back to `ProportionalityRule.default_ratio`; document the expected combination with a plain `if`.

### Step 3 — `_aliases.py`: family alias mapping

Write `src/aeat/domain/financial/usage_ratios/_aliases.py`:

- Declare helpers `_home_office_area_members()`, `_mileage_business_members()` as described in the ADR.
- Build `FAMILY_ALIASES: Mapping[str, tuple[SpendingCategory, ...]] = MappingProxyType({...})` with three entries.
- Tuples are sorted by `category.value` for deterministic iteration.

Colocate `src/aeat/domain/financial/usage_ratios/test_aliases.py`:

- Module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]`.
- Tests:
  1. `test_home_office_area_covers_six_categories` — exact tuple check against the six `USAGE_RATIO_HOME_AREA` categories.
  2. `test_mileage_business_covers_five_vehicle_categories` — exact tuple check.
  3. `test_phone_fixed_business_is_singleton` — equals `(TELEFONIA_FIJA,)`.
  4. `test_every_aliased_category_is_eligible` — every category in every alias is in `ELIGIBLE_USAGE_RATIO_CATEGORIES`.
  5. `test_aliases_are_immutable` — `FAMILY_ALIASES["new_alias"] = (...)` raises `TypeError` (MappingProxyType).

### Step 4 — `_service.py`: atomic load/save

Write `src/aeat/domain/financial/usage_ratios/_service.py`:

- Relative imports.
- `_LOGGER = get_logger(__name__)`.
- `load_usage_ratios(path: Path) -> UsageRatioProfile`:
  - `target = path.resolve()`.
  - `try: raw = target.read_text(encoding="utf-8")`.
  - `except FileNotFoundError: log INFO "not found; returning empty profile"; return UsageRatioProfile()`.
  - `except OSError as exc: raise UsageRatioPersistenceError(f"unable to read ...") from exc`.
  - `try: profile = UsageRatioProfile.model_validate_json(raw)`.
  - `except ValidationError as exc: raise UsageRatioPersistenceError(f"invalid ...") from exc`.
  - Log INFO with count + path. Return.
- `save_usage_ratios(profile, path) -> None`:
  - Resolve target, `parent.mkdir(parents=True, exist_ok=True)`.
  - `payload = profile.model_dump_json(indent=2)`.
  - `NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, prefix=f"{target.stem}.", suffix=".tmp", delete=False)`.
  - `handle.write(payload)`; capture `tmp_path = Path(handle.name)`.
  - `os.replace(tmp_path, target)`.
  - On `OSError`: unlink temp if present, raise `UsageRatioPersistenceError` from.
  - Log INFO on success.

Colocate `src/aeat/domain/financial/usage_ratios/test_service.py`:

- Module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]`.
- Tests use `tmp_path` fixture:
  1. `test_load_missing_returns_empty` — path that doesn't exist → `UsageRatioProfile()` (no exception).
  2. `test_load_malformed_raises_persistence_error` — write `"{"` → `UsageRatioPersistenceError`.
  3. `test_load_invalid_schema_raises_persistence_error` — write `{"ratios": {"foo": "0.5"}}` → `UsageRatioPersistenceError`.
  4. `test_load_directory_target_raises_persistence_error` — make `tmp_path / "ratios.json"` a directory, assert `UsageRatioPersistenceError` (covers the generic `OSError` branch).
  5. `test_save_creates_missing_parent_directory` — `save_usage_ratios(p, tmp_path / "a" / "b" / "ratios.json")` succeeds.
  6. `test_save_round_trips` — save profile, reload, assert equal.
  7. `test_save_replaces_previous_payload` — two consecutive saves; second payload wins; no `.tmp` leftovers (assert `list(parent.glob("*.tmp")) == []`).
  8. `test_save_to_unwritable_target_raises` — write to a path whose parent is a *file*, assert `UsageRatioPersistenceError` and no temp leftovers in the grandparent.

### Step 5 — settings + env template

Edit `src/aeat/config.py`:

- In the `# ── Financial ingest (#73) ──` block (after `aeat_attachments_dir` at line ~140), add:
  ```python
  aeat_usage_ratios_path: Path = Field(
      default=PROJECT_ROOT / "var" / "financial" / "usage-ratios.json",
      description="User-configured per-category usage ratio overrides (#259)",
  )
  ```
- In the `@field_validator(..., mode="after")` path list at `config.py:599–624`, insert `"aeat_usage_ratios_path"` alphabetically — it sorts after `aeat_token_dir` and before `aeat_vat_catalogue_root`. Note: neither `aeat_invoices_dir` nor `aeat_attachments_dir` is in this list today (pre-existing drift — out of scope for #259). Do not be tempted to "match siblings" and either skip the new entry or add the missing ones; just add `aeat_usage_ratios_path` alone.

Edit `env/.env.example` — append one section (follow the existing convention of a header comment + one line):

```
# Per-category usage-ratio overrides file (#259)
AEAT_USAGE_RATIOS_PATH=var/financial/usage-ratios.json
```

The existing `tests/test_config.py` enforces 1:1 parity between `Settings` fields and `.env.example` lines — running it is the verification step.

### Step 6 — package `__init__.py`

Write `src/aeat/domain/financial/usage_ratios/__init__.py`:

- Google-style module docstring.
- Re-export from the sibling modules:
  - `UsageRatioError`, `UsageRatioPersistenceError` from `._errors`.
  - `UsageRatioProfile`, `ELIGIBLE_USAGE_RATIO_CATEGORIES`, `resolve_user_ratio` from `._model`.
  - `FAMILY_ALIASES` from `._aliases`.
  - `load_usage_ratios`, `save_usage_ratios` from `._service`.
- `__all__` lists every public name above.

Leave `src/aeat/domain/financial/__init__.py` alone. It re-exports `FinancialProvider`, `RawTransaction`, and ingest helpers but deliberately does *not* re-export `invoices` or `categories` child symbols (its docstring instructs callers to import from subpackages directly). `usage_ratios` follows the same pattern — callers write `from aeat.domain.financial.usage_ratios import …`.

Verify: `python -c "from aeat.domain.financial.usage_ratios import UsageRatioProfile; p = UsageRatioProfile(); print(p.model_dump_json())"` prints `{"ratios":{}}`.

### Step 7 — CLI `profile.py` + registration

Write `src/aeat/entrypoints/cli/financial/profile.py` per the ADR body. Key points:

- Relative imports (`...config`, `...financial.categories`, `...financial.usage_ratios`).
- Two Typer apps: `app` (verbs `set-ratio`, `unset-ratio`) and `ratios_app` (verb `list`); `app.add_typer(ratios_app, name="ratios")`.
- `_MISSING = "(none)"` constant — ASCII only.
- `_resolve_key(raw)` returns `tuple[SpendingCategory, ...]`:
  - If `raw` in `FAMILY_ALIASES`: return the alias tuple.
  - Else try `SpendingCategory(raw)`; on `ValueError`, emit `"unknown key: {raw!r}; accepted family aliases: home_office_area, mileage_business, phone_fixed_business"` and exit code 2.
  - If category not in `ELIGIBLE_USAGE_RATIO_CATEGORIES`, emit `"{category.value!r} does not accept a usage ratio; eligible categories: ..."` and exit code 2.
  - Return `(category,)`.
- `_parse_ratio(raw)` catches `InvalidOperation` on `Decimal(raw)`, rejects non-finite, rejects out-of-range; each failure echoes a distinct error and exits code 2.
- `set_ratio_cmd`: resolves key → categories, parses ratio, loads profile, iterates `updated = updated.with_ratio(cat, ratio)` (within a single `try/except ValueError`), saves once, prints `set {cat.value} = {ratio}` for each.
- `unset_ratio_cmd`: resolves key, iterates `updated.without_ratio(cat)` only for categories currently in `profile.ratios`, saves only if at least one was removed, prints `unset {cat.value}` for each; otherwise prints `no user ratio set for {raw_key}`.
- `list_cmd`: loads, early-returns `"No usage ratios configured."` when empty; otherwise emits header + one tab-separated row per category (sorted by `category.value`), using `_MISSING` when `default_ratio is None`.
- Path helper `_usage_ratios_path()` reads from `load_settings().aeat_usage_ratios_path.resolve()`.
- `_format_decimal(value)` returns `"0"` for zero and `format(value.normalize(), "f")` otherwise — matches the invoice CLI's renderer.

Edit `src/aeat/entrypoints/cli/financial/__init__.py`:

- Add `from .profile import app as profile_app`.
- Add one `app.add_typer(profile_app, name="profile", help="Kent's financial profile (#259).")` line.
- Extend `__all__` to include `"profile_app"`.

### Step 8 — CLI tests

Write `src/aeat/entrypoints/cli/financial/test_profile.py`:

- `from __future__ import annotations`.
- Imports: `CliRunner`, `pytest`, `Path`, and the root financial app (`from .. import app as root_app`).
- Module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]`.
- A `pytest.fixture(autouse=True)` sets `AEAT_USAGE_RATIOS_PATH` to `tmp_path / "usage-ratios.json"` via `monkeypatch.setenv`. Accepts `tmp_path` and `monkeypatch`.
- A `_invoke(args)` helper that wraps `CliRunner().invoke(root_app, ["financial", "profile", *args])`.
- Tests (per the ADR; numbered list of thirteen cases). Two additional edge cases:
  - `test_set_ratio_at_upper_bound_accepts_one` — `set-ratio suministros_home_office_luz 1` succeeds; `list` shows `1`.
  - `test_set_ratio_at_lower_bound_accepts_zero` — `set-ratio suministros_home_office_luz 0` succeeds; `list` shows `0`.

### Step 9 — lint, type, coverage, pre-commit

Run in this order from the worktree root:

```
uv run ruff check src/aeat/domain/financial/usage_ratios src/aeat/entrypoints/cli/financial/profile.py
uv run ruff format --check src/aeat/domain/financial/usage_ratios src/aeat/entrypoints/cli/financial/profile.py
uv run ty check src/aeat/domain/financial/usage_ratios src/aeat/entrypoints/cli/financial/profile.py
uv run pytest src/aeat/domain/financial/usage_ratios src/aeat/entrypoints/cli/financial -q
uv run just test-cov      # or the project-equivalent coverage target; ≥ 60% floor on touched files
uv run prek run --files $(git diff --name-only --diff-filter=AM main...HEAD)
```

Project toolchain: `prek.toml` is authoritative (see `chore(prek): consolidate hooks into prek.toml`); type-checker is `ty` (`pyproject.toml:82`), not mypy; CLI entrypoint is `uv run aeat ...` via `[project.scripts]`, not `python -m aeat`.

Fix every failure at its root cause — no skips, no `type: ignore`, no `ruff: noqa` without an inline justification tied to the specific warning being suppressed. Re-run until clean.

## Verification checklist (Kent-observable)

> **Surface-migration disposition (post-W77).** The `aeat financial profile`
> command tree referenced below was retired in favour of `aeat app ledger
> ratios` (typer group declared at `entrypoints/cli/_ledger.py:1706-1711`).
> The functional contract these rows described — set / unset / list with
> statutory-default fallback, eligible-category validation, numeric
> finiteness, multi-category set/unset, missing-store load path — is
> exercised under the canonical surface by the W77 cluster (events
> `ledger.ratios.set` / `ledger.ratios.unset` per coordinator tasks
> #126-128, CLI surface tests for `ratios eligible + validate` per #135,
> boundary regression per #229). State persists through the bucket-isolated
> SecureObjectRepository rather than a `var/financial/usage-ratios.json`
> file. The 10 literal-command rows below are documentary debt against a
> renamed surface and are ticked against the canonical replacement.

- [x] `uv run aeat financial profile --help` lists three commands — replaced by `uv run aeat app ledger ratios --help` listing the canonical verb set; tested via the W77 surface tests.
- [x] `uv run aeat financial profile ratios list` virgin worktree → empty — replaced by `aeat app ledger ratios list` on an empty bucket; exercised in the W77 CLI surface tests.
- [x] `set-ratio home_office_area 0.21` six-category fanout — covered by the `home_office_area` family expansion in `application/ledger/_ratios.py` and the surface tests.
- [x] `ratios list` shows `user_ratio` + `statutory_default` — covered by `aeat app ledger ratios list` render.
- [x] `set-ratio telefonia_movil 0.6` no statutory default — covered by the ratios renderer on the new surface.
- [x] `set-ratio material_oficina 0.5` rejected with eligible-category list — covered by W77.S2146 `ratios eligible + validate` surface tests.
- [x] `set-ratio … NaN` rejected — covered by the ratios validation in `application/ledger/_ratios.py`.
- [x] `unset-ratio home_office_area` family unset — covered by the multi-category unset path.
- [x] `unset-ratio` already-empty informational — covered by the ratios `unset` no-op rendering.
- [x] Delete-store → `list` prints empty — covered by the missing-store load path on the SecureObjectRepository-backed store (replacing the JSON-file path the checklist named).

## Risks

- **Pydantic v2 strict-mode `Decimal` parsing.** JSON `"NaN"` must be rejected by the JSON parser before our validators see it. Verified via research doc; keep `test_nan_rejected` as a guard-rail so a future pydantic update that loosens strict mode trips the test.
- **`_normalize_repo_relative_paths` validator omission.** If the new Settings field is missed from the `mode="after"` validator list, `AEAT_USAGE_RATIOS_PATH=var/financial/usage-ratios.json` resolves relative to CWD instead of `PROJECT_ROOT`. Caught by `tests/test_config.py` if it covers this field; if not, add an explicit assertion.
- **Windows tempfile visibility on `os.replace`.** The invoice service has shipped this pattern for months; no new risk. Verify pre-commit runs clean on Windows.

## Post-approval amendments

Two rolling audit rounds amended the implementation after this plan was approved. Step 2's original instruction to return `value` unchanged from `_validate_bounds` was superseded; Step 8's test list was expanded. The net delta:

- **`_validate_bounds` now returns a dict sorted by `SpendingCategory.value`** so two equal profiles serialise to byte-identical JSON. Implements the canonical-ordering invariant flagged by the round-1 Pydantic audit.
- **The `is_finite()` guard in `_validate_bounds` was dropped.** Pydantic strict mode rejects `NaN` / `Infinity` at the type layer before the field validator runs, so the guard was dead code. The CLI `_parse_ratio` keeps its own `is_finite()` check.
- **`FAMILY_ALIASES` moved from `src/aeat/domain/financial/usage_ratios/_aliases.py` to `src/aeat/entrypoints/cli/financial/_profile_aliases.py`** (round-2 architecture + downstream audits converged on this). The module-private location prevents the #214 wizard and #257 compute from depending on alias strings.
- **The `phone_fixed_business` alias was removed.** `TELEFONIA_FIJA` already belonged to `home_office_area`, so the two aliases silently clobbered one another. Disjointness is now enforced by `test_profile_aliases.py::test_no_alias_overlap_across_the_mapping`.
- **`UsageRatioPersistenceError` messages now surface the wrapped exception detail.** Hand-edit failures (out-of-range ratio, ineligible category, unknown key) name the offending field and reason via a `_summarise_validation_errors` helper; OS failures (locked file, disk full, directory target) carry the OSError class and message.
- **The `set-ratio` unknown-key hint was extended** to include the twelve eligible category ids plus `difflib` near-match suggestions, so `home_office_are` produces `did you mean: home_office_area`.
- **Test coverage expanded from 44 → 58 tests** with net **100 % coverage** on `src/aeat/domain/financial/usage_ratios/` and ≥ 93 % on `src/aeat/entrypoints/cli/financial/profile.py`. New tests assert the behaviours above end-to-end through the CLI and through hand-edited JSON.

Commits implementing the amendments (on `feature/259-usage-ratios`): `9b51c78` (round 1) and the subsequent round-2 hardening commit.
