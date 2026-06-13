---
tags:
  - "#adr"
  - "#usage-ratios"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-usage-ratios-research]]"
  - "[[2026-04-18-category-assignment-cli-adr]]"
  - "[[2026-04-17-export-first-adr]]"
---

# `usage-ratios` adr: `persist-kent-usage-ratios-as-category-keyed-profile` | (**status:** `implemented`)

> **Post-approval amendments** — the sections below were edited in-place after the initial `accepted` milestone to keep the record aligned with shipped code. See the `## Post-approval amendments` log at the bottom of this document for what changed and why.

## Problem Statement

Issue `#259` and data-prep wall **DP7** (`.vault/audit/2026-04-18-kent-data-prep-journey-audit.md:112–127`) require Kent to persist his own proportionality coefficients once, so every `USAGE_RATIO_*` category defaults to his numbers instead of the statutory 30% stub on `ProportionalityRule.default_ratio`. Today the registry at `src/aeat/domain/financial/categories/_registry.py:400–616` hard-codes twelve usage-ratio categories; six inherit `default_ratio=Decimal("0.30")` and six have no default at all. Kent either re-enters a `--pct` override on every transaction (wall DP7) or accepts a wrong statutory default that misrepresents his home-office share. There is no write surface, no persisted profile, and no hook into the future deductibility compute (issue `#257`).

This ADR commits the data model, persistence location, CLI verbs, and the pure-function lookup contract that `#257` will consume.

## Considerations

- **Issue body tolerates two key-granularity designs.** The body cites both concept-level keys (`home_office_area`, `mileage_business`) and category-level keys (`home_office_utilities_luz/agua/gas/internet`). Picking one is a deliberate decision; both satisfy the Kent-observable acceptance criteria.
- **Only two of six `ProportionalityKind` values are ratio-shaped.** `USAGE_RATIO_HOME_AREA` and `USAGE_RATIO_PERSONAL` admit `default_ratio`; the other four kinds reject it at `_proportionality.py:88–89`. Any override surface must reject non-usage-ratio targets with the same strictness.
- **Existing CLI convention already uses `SpendingCategory` values as string arguments** (`2026-04-18-category-assignment-cli-adr`, `aeat financial txs classify --category suministros_home_office_luz`). Introducing a parallel "concept key" taxonomy splits the user-facing identifier space for no data-model reason.
- **Pydantic v2 `frozen=True` only blocks attribute reassignment.** It does *not* freeze mutable interiors. A `dict` stored on a frozen model can still be mutated with `profile.ratios[cat] = v`. Any "immutable" claim must be precisely scoped to attribute-level immutability, and the user-facing contract is "treat `profile.ratios` as read-only; use `with_ratio` / `without_ratio` to produce new profiles".
- **`MappingProxyType` breaks pydantic v2 JSON serialization.** Returning `MappingProxyType(...)` from a validator causes `model_dump_json()` to raise `PydanticSerializationError`. Storage must remain a plain `dict`; read-only enforcement belongs in the contract, not the runtime shape.
- **`Decimal("NaN") <= Decimal("0")` raises `decimal.InvalidOperation`.** Pydantic strict mode rejects `NaN` / `Infinity` at parse time on **both** the JSON boundary and the Python constructor path, so the model field validator does not need its own `is_finite()` guard (see post-approval amendments). The CLI, however, accepts raw user input via `Decimal(raw)` which silently constructs `Decimal("NaN")`, so the CLI parser retains an explicit `is_finite()` check before the range comparison.
- **Persistence must match the invoice / transaction round-trip.** `src/aeat/domain/financial/invoices/_service.py:71–126` is the canonical atomic JSON helper pair. The usage-ratio service mirrors it except for one *intentional* divergence: `load_usage_ratios` returns an empty profile when the file does not exist. Rationale: there is no scenario where a missing profile is an error — it is the virgin state. Moving the "empty fallback" into the service keeps the CLI thin and prevents every caller from repeating the same try/except.
- **Issue `#257` is not in scope here** but will read this profile. The ADR must publish a stable pure function (`resolve_user_ratio`) so the compute service can compile against a fixed signature.
- **Issue `#214` (setup wizard)** will call the same save helper during onboarding. No additional API surface required.
- **Scope of Kent's success moment.** Issue body's success moment is `set-ratio home_office_area 0.21`. A category-keyed design alone forces Kent to type six commands (one per home-office category). To preserve the one-command UX, the CLI accepts three **family aliases** at the `KEY` position — `home_office_area`, `mileage_business`, and `phone_fixed_business` — that expand to every eligible category in that family. The persisted data model is still category-keyed; aliases are a pure CLI convenience that fans out at parse time.

## Constraints

- All fields `Decimal`, never `float`. Bounds `[0, 1]` inclusive. Non-finite values (`NaN`, `+Infinity`, `-Infinity`) are rejected by pydantic strict mode on both JSON and Python construction paths; the CLI parser layers its own `is_finite()` check for user-typed strings that bypass pydantic.
- Persisted keys are `SpendingCategory` enum values — no parallel taxonomy. Unknown strings fail strict pydantic validation. Categories whose `ProportionalityRule.kind ∉ {USAGE_RATIO_HOME_AREA, USAGE_RATIO_PERSONAL}` are rejected by a `@model_validator(mode="after")` cross-field rule.
- `UsageRatioProfile` is `model_config = ConfigDict(strict=True, frozen=True, extra="forbid")`. `frozen=True` only freezes attribute rebinding; callers treat `profile.ratios` as read-only and use `with_ratio` / `without_ratio` for edits. The ADR does **not** claim deep immutability.
- The internal `ratios` storage is a plain `dict[SpendingCategory, Decimal]` (not `MappingProxyType`) so `model_dump_json()` round-trips cleanly.
- Errors inherit from `aeat.core.errors.AeatError` via a local `UsageRatioError` base; persistence failures raise `UsageRatioPersistenceError` (analogue of `InvoicePersistenceError`).
- Save is atomic: `NamedTemporaryFile` sibling + `os.replace`; `parent.mkdir(parents=True, exist_ok=True)` first. No partial writes.
- Load returns an empty profile when the JSON file does not exist (intentional divergence from the invoice pattern). Any other `OSError` or JSON validation error raises `UsageRatioPersistenceError`.
- No absolute `aeat.*` imports inside `src/aeat/`; use relative (`..errors`, `...config`).
- Logging via `aeat.core.logging.get_logger(__name__)` only.
- Settings field `aeat_usage_ratios_path` joins the `_normalize_repo_relative_paths` after-validator at `src/aeat/config.py:599–624`. Documented in `env/.env.example`.
- Tests colocated with their modules (Rust-style). Module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]` matching `_proportionality.py`'s test.
- `resolve_user_ratio(profile, category)` is **pure** — no I/O, no side effects, returns `Decimal | None`. `#257` owns the combination with statutory defaults.
- CLI output uses ASCII only (no em-dash) for cp1252 console safety on Windows.

## Implementation

### The twelve eligible categories

The authoritative list of categories whose `ProportionalityRule.kind` admits a user override, sourced from `src/aeat/domain/financial/categories/_registry.py:400–616`:

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

Exposed at module load as `ELIGIBLE_USAGE_RATIO_CATEGORIES: frozenset[SpendingCategory]`, derived from `CATEGORY_PROFILES_2025` by the same kind predicate.

### Family aliases (CLI-only sugar)

Two disjoint aliases are accepted at the `KEY` position of `set-ratio` / `unset-ratio`. They expand at CLI parse time to a tuple of `SpendingCategory` values and are **never** stored; the library never sees alias names.

| alias | expands to |
|---|---|
| `home_office_area` | all six `USAGE_RATIO_HOME_AREA` categories (including `TELEFONIA_FIJA`) |
| `mileage_business` | `VEHICULO_COMBUSTIBLE`, `VEHICULO_MANTENIMIENTO`, `VEHICULO_SEGURO`, `VEHICULO_PEAJE`, `VEHICULO_PARKING` |

**Disjointness invariant.** Alias expansions must not overlap — otherwise two consecutive `set-ratio` calls using different aliases would silently clobber prior values for the shared category. The original design included a `phone_fixed_business` → `(TELEFONIA_FIJA,)` alias, but `TELEFONIA_FIJA` is already a member of `home_office_area` (it is a `USAGE_RATIO_HOME_AREA` category). That alias was removed; for single-category edits on `TELEFONIA_FIJA`, Kent types the category name directly. `TELEFONIA_MOVIL` has no alias for the same reason. `src/aeat/entrypoints/cli/financial/test_profile_aliases.py::test_no_alias_overlap_across_the_mapping` enforces the invariant.

### package layout

```
src/aeat/domain/financial/usage_ratios/
├── __init__.py        # re-exports UsageRatioProfile, UsageRatioError, load, save, resolve
├── _errors.py         # UsageRatioError, UsageRatioPersistenceError
├── _model.py          # UsageRatioProfile + resolve_user_ratio + ELIGIBLE_USAGE_RATIO_CATEGORIES
├── _service.py        # load_usage_ratios, save_usage_ratios (atomic round-trip)
├── test_model.py
└── test_service.py

src/aeat/entrypoints/cli/financial/
├── profile.py                 # Kent-facing CLI
├── _profile_aliases.py        # FAMILY_ALIASES (CLI-private sugar; never persisted)
├── test_profile.py
└── test_profile_aliases.py
```

`FAMILY_ALIASES` lives in the CLI layer deliberately — aliases are UI sugar that expand at parse time, never reach the persistence model, and must not be inherited by future non-CLI consumers (the #214 setup wizard, the #257 compute service). `src/aeat/domain/financial/__init__.py` is left alone (matches the existing "import from subpackages directly" convention).

### data model — `_model.py`

```python
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..categories import (
    CATEGORY_PROFILES_2025,
    ProportionalityKind,
    SpendingCategory,
)

_USER_RATIO_KINDS: frozenset[ProportionalityKind] = frozenset(
    {ProportionalityKind.USAGE_RATIO_HOME_AREA, ProportionalityKind.USAGE_RATIO_PERSONAL}
)


def _eligible_categories() -> frozenset[SpendingCategory]:
    return frozenset(
        category
        for category, profile in CATEGORY_PROFILES_2025.items()
        if profile.proportionality.kind in _USER_RATIO_KINDS
    )


ELIGIBLE_USAGE_RATIO_CATEGORIES: frozenset[SpendingCategory] = _eligible_categories()


class UsageRatioProfile(BaseModel):
    """Kent's persisted per-category usage-ratio overrides (#259)."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ratios: dict[SpendingCategory, Decimal] = Field(default_factory=dict)

    @field_validator("ratios", mode="after")
    @classmethod
    def _validate_bounds(
        cls, value: dict[SpendingCategory, Decimal]
    ) -> dict[SpendingCategory, Decimal]:
        # Pydantic strict-mode Decimal handling rejects NaN / Infinity before
        # this validator runs (both JSON and Python constructor paths), so no
        # explicit is_finite() check is needed here.
        for category, ratio in value.items():
            if not (Decimal("0") <= ratio <= Decimal("1")):
                raise ValueError(
                    f"usage ratio for {category.value!r} must be in [0, 1] (got {ratio})"
                )
        # Canonicalise key order so two equal profiles serialise to identical
        # bytes — Kent's JSON file is a candidate for git-tracking and
        # insertion-order noise produces spurious diffs.
        return {category: value[category] for category in sorted(value, key=lambda c: c.value)}

    @model_validator(mode="after")
    def _validate_eligibility(self) -> "UsageRatioProfile":
        invalid = tuple(
            category
            for category in self.ratios
            if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES
        )
        if invalid:
            names = ", ".join(sorted(c.value for c in invalid))
            raise ValueError(
                f"usage ratios may only target USAGE_RATIO_* categories; rejected: {names}"
            )
        return self

    def with_ratio(self, category: SpendingCategory, ratio: Decimal) -> "UsageRatioProfile":
        """Return a new profile with one ratio set or replaced."""
        new_ratios = dict(self.ratios)
        new_ratios[category] = ratio
        return UsageRatioProfile(ratios=new_ratios)

    def without_ratio(self, category: SpendingCategory) -> "UsageRatioProfile":
        """Return a new profile with one ratio removed (no-op if absent)."""
        new_ratios = dict(self.ratios)
        new_ratios.pop(category, None)
        return UsageRatioProfile(ratios=new_ratios)


def resolve_user_ratio(
    profile: UsageRatioProfile, category: SpendingCategory
) -> Decimal | None:
    """Return Kent's persisted ratio for a category, or ``None`` if unset.

    Pure function consumed by :mod:`aeat.domain.financial.deductibility` (#257), which
    falls back to ``ProportionalityRule.default_ratio`` when the return is
    ``None`` and records which source won in the transaction's trace fields.
    """
    return profile.ratios.get(category)
```

**Immutability semantics.** `frozen=True` blocks attribute reassignment (`profile.ratios = {}` raises). It does *not* freeze the inner dict. Callers must not mutate `profile.ratios` directly; the `with_ratio` / `without_ratio` helpers return fresh profiles for every edit. This is a contract, not a runtime guarantee — the same contract the repo uses for every `frozen` model that holds `dict` / `list` interiors.

**Canonical key order.** `_validate_bounds` returns a new dict with keys sorted by `SpendingCategory.value`. This guarantees that two equal profiles produce byte-identical JSON payloads regardless of insertion order, which stabilises `git diff` across successive saves and makes cross-system file comparison reliable. `var/financial/usage-ratios.json` is gitignored by default (per the `var/` rule the invoice and transaction catalogues also honour), so the benefit applies only when Kent relocates the file outside `var/` via `AEAT_USAGE_RATIOS_PATH`, or when diffing two Kent machines. Cost on a 12-key profile is ~3 µs.

**Non-finite rejection delegated to pydantic.** An earlier draft carried an explicit `is_finite()` guard inside the validator as defence-in-depth. Empirical testing showed pydantic strict mode already rejects `Decimal("NaN")`, `Decimal("Infinity")`, and their signs at the type-validation layer — on **both** JSON parse and Python constructor paths — before the field validator runs. The guard was therefore dead code and was removed. The CLI parser (`_parse_ratio`) retains its own `is_finite()` check because user-typed strings reach `Decimal(raw)` before pydantic sees them.

### aliases — `_aliases.py`

```python
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from ..categories import ProportionalityKind, SpendingCategory
from ._model import ELIGIBLE_USAGE_RATIO_CATEGORIES, _USER_RATIO_KINDS


def _home_office_area_members() -> tuple[SpendingCategory, ...]:
    from ..categories import CATEGORY_PROFILES_2025

    return tuple(
        sorted(
            (
                category
                for category, profile in CATEGORY_PROFILES_2025.items()
                if profile.proportionality.kind is ProportionalityKind.USAGE_RATIO_HOME_AREA
            ),
            key=lambda c: c.value,
        )
    )


def _mileage_business_members() -> tuple[SpendingCategory, ...]:
    return (
        SpendingCategory.VEHICULO_COMBUSTIBLE,
        SpendingCategory.VEHICULO_MANTENIMIENTO,
        SpendingCategory.VEHICULO_SEGURO,
        SpendingCategory.VEHICULO_PEAJE,
        SpendingCategory.VEHICULO_PARKING,
    )


FAMILY_ALIASES: Mapping[str, tuple[SpendingCategory, ...]] = MappingProxyType(
    {
        "home_office_area": _home_office_area_members(),
        "mileage_business": _mileage_business_members(),
        "phone_fixed_business": (SpendingCategory.TELEFONIA_FIJA,),
    }
)
```

(`MappingProxyType` here is fine — `FAMILY_ALIASES` is a module constant, never passed through pydantic.)

### errors — `_errors.py`

```python
from __future__ import annotations

from ...errors import AeatError


class UsageRatioError(AeatError):
    """Base error for :mod:`aeat.domain.financial.usage_ratios`."""


class UsageRatioPersistenceError(UsageRatioError):
    """Raised when the usage-ratio profile cannot be read or written."""
```

### persistence — `_service.py`

Mirrors `invoices/_service.py:71–126` with one intentional divergence (`FileNotFoundError → empty profile`):

```python
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from ...logging import get_logger
from ._errors import UsageRatioPersistenceError
from ._model import UsageRatioProfile

_LOGGER = get_logger(__name__)


def load_usage_ratios(path: Path) -> UsageRatioProfile:
    """Load the usage-ratio profile or return an empty one when absent."""
    target = path.resolve()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        _LOGGER.info("usage-ratios file not found at %s; returning empty profile", target)
        return UsageRatioProfile()
    except OSError as exc:
        raise UsageRatioPersistenceError(
            f"unable to read usage-ratio profile: {target}"
        ) from exc
    try:
        profile = UsageRatioProfile.model_validate_json(raw)
    except ValidationError as exc:
        raise UsageRatioPersistenceError(
            f"invalid usage-ratio profile JSON: {target}"
        ) from exc
    _LOGGER.info("loaded %s usage ratios from %s", len(profile.ratios), target)
    return profile


def save_usage_ratios(profile: UsageRatioProfile, path: Path) -> None:
    """Persist the profile atomically via `os.replace`."""
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = profile.model_dump_json(indent=2)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f"{target.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
        os.replace(tmp_path, target)
    except OSError as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise UsageRatioPersistenceError(
            f"unable to write usage-ratio profile: {target}"
        ) from exc
    _LOGGER.info("saved %s usage ratios to %s", len(profile.ratios), target)
```

### settings — `src/aeat/config.py`

Add one field in the `# ── Financial ingest` block:

```python
aeat_usage_ratios_path: Path = Field(
    default=PROJECT_ROOT / "var" / "financial" / "usage-ratios.json",
    description="User-configured per-category usage ratio overrides (#259)",
)
```

Append `"aeat_usage_ratios_path"` to the `@field_validator(..., mode="after")` path list at `config.py:599–624` so `AEAT_USAGE_RATIOS_PATH=var/...` anchors to `PROJECT_ROOT`.

Add to `env/.env.example`:

```
# Per-category usage-ratio overrides file (#259)
AEAT_USAGE_RATIOS_PATH=var/financial/usage-ratios.json
```

### CLI — `src/aeat/entrypoints/cli/financial/profile.py` (new file)

Verbs are placed flat under `profile` to preserve the exact wording of the issue body (`set-ratio`, `unset-ratio`) while nesting `list` under a `ratios` sub-app to scope the noun. The asymmetry is a deliberate literal match to the issue's own verb shape; renaming would diverge from the issue wording without meaningfully improving UX.

```python
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

import typer

from ...config import load_settings
from ...financial.categories import CATEGORY_PROFILES_2025, SpendingCategory
from ...financial.usage_ratios import (
    ELIGIBLE_USAGE_RATIO_CATEGORIES,
    FAMILY_ALIASES,
    UsageRatioError,
    UsageRatioProfile,
    load_usage_ratios,
    save_usage_ratios,
)

_MISSING = "(none)"

app = typer.Typer(
    name="profile",
    no_args_is_help=True,
    help="Kent's financial profile: per-category usage ratios (#259).",
)

ratios_app = typer.Typer(
    name="ratios",
    no_args_is_help=True,
    help="List Kent's persisted usage ratios.",
)
app.add_typer(ratios_app, name="ratios")


@ratios_app.command(name="list", help="List Kent's configured ratios.")
def list_cmd() -> None:
    profile = _load_profile()
    if not profile.ratios:
        typer.echo("No usage ratios configured.")
        return
    typer.echo("category\tkind\tuser_ratio\tstatutory_default")
    for category in sorted(profile.ratios, key=lambda c: c.value):
        rule = CATEGORY_PROFILES_2025[category].proportionality
        default_raw = rule.default_ratio
        default_str = _format_decimal(default_raw) if default_raw is not None else _MISSING
        typer.echo(
            "\t".join(
                [
                    category.value,
                    rule.kind.value,
                    _format_decimal(profile.ratios[category]),
                    default_str,
                ]
            )
        )


@app.command(name="set-ratio", help="Set Kent's usage ratio for one category or family alias.")
def set_ratio_cmd(
    key: str = typer.Argument(
        ..., help="Category id (e.g. suministros_home_office_luz) or family alias (home_office_area, mileage_business, phone_fixed_business)."
    ),
    value: str = typer.Argument(..., help="Ratio in [0, 1] as a decimal, e.g. 0.21."),
) -> None:
    categories = _resolve_key(key)
    ratio = _parse_ratio(value)
    profile = _load_profile()
    updated = profile
    for category in categories:
        try:
            updated = updated.with_ratio(category, ratio)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
    _save_profile(updated)
    for category in categories:
        typer.echo(f"set {category.value} = {_format_decimal(ratio)}")


@app.command(name="unset-ratio", help="Remove Kent's usage ratio for one category or family alias.")
def unset_ratio_cmd(
    key: str = typer.Argument(..., help="Category id or family alias."),
) -> None:
    categories = _resolve_key(key)
    profile = _load_profile()
    updated = profile
    removed: list[SpendingCategory] = []
    for category in categories:
        if category in updated.ratios:
            updated = updated.without_ratio(category)
            removed.append(category)
    if not removed:
        typer.echo(f"no user ratio set for {key}")
        return
    _save_profile(updated)
    for category in removed:
        typer.echo(f"unset {category.value}")


def _resolve_key(raw: str) -> tuple[SpendingCategory, ...]:
    """Expand a family alias or validate a single category id."""
    alias_members = FAMILY_ALIASES.get(raw)
    if alias_members is not None:
        return alias_members
    try:
        category = SpendingCategory(raw)
    except ValueError as exc:
        aliases = ", ".join(sorted(FAMILY_ALIASES))
        typer.echo(
            f"unknown key: {raw!r}; accepted family aliases: {aliases}",
            err=True,
        )
        raise typer.Exit(code=2) from exc
    if category not in ELIGIBLE_USAGE_RATIO_CATEGORIES:
        eligible = ", ".join(sorted(c.value for c in ELIGIBLE_USAGE_RATIO_CATEGORIES))
        typer.echo(
            f"{category.value!r} does not accept a usage ratio; eligible categories: {eligible}",
            err=True,
        )
        raise typer.Exit(code=2)
    return (category,)


def _parse_ratio(raw: str) -> Decimal:
    try:
        ratio = Decimal(raw)
    except InvalidOperation as exc:
        typer.echo(f"invalid ratio: {raw!r}", err=True)
        raise typer.Exit(code=2) from exc
    if not ratio.is_finite():
        typer.echo(f"ratio must be finite (got {ratio})", err=True)
        raise typer.Exit(code=2)
    if not (Decimal("0") <= ratio <= Decimal("1")):
        typer.echo(f"ratio must be in [0, 1] (got {ratio})", err=True)
        raise typer.Exit(code=2)
    return ratio


def _load_profile() -> UsageRatioProfile:
    try:
        return load_usage_ratios(_usage_ratios_path())
    except UsageRatioError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _save_profile(profile: UsageRatioProfile) -> None:
    try:
        save_usage_ratios(profile, _usage_ratios_path())
    except UsageRatioError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _usage_ratios_path() -> Path:
    return load_settings().aeat_usage_ratios_path.resolve()


def _format_decimal(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")
```

**Register** in `src/aeat/entrypoints/cli/financial/__init__.py`:

```python
from .profile import app as profile_app
...
app.add_typer(profile_app, name="profile", help="Kent's financial profile (#259).")
```

### tests

**`src/aeat/domain/financial/usage_ratios/test_model.py`** — module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]` — covers:

1. empty profile → `UsageRatioProfile()` with zero ratios.
2. valid construction with `SUMINISTROS_HOME_OFFICE_LUZ=Decimal("0.21")` → round-trip via `model_dump_json` + `model_validate_json` reconstructs equal profile.
3. ratio `< 0`, `> 1`, `NaN`, `+Infinity`, `-Infinity` → `ValidationError` at model construction.
4. unknown string key in JSON payload → `ValidationError` from `SpendingCategory` parse.
5. ineligible category (`MATERIAL_OFICINA`, which is `FULL_DEDUCTIBLE`) → `ValidationError` naming the rejected key.
6. `frozen=True` attribute reassignment → `ValidationError`.
7. `with_ratio` and `without_ratio` return new profiles; original is untouched.
8. `without_ratio` on an unset category is a no-op (no exception).
9. `resolve_user_ratio` returns `Decimal` for set category, `None` for unset.
10. `ELIGIBLE_USAGE_RATIO_CATEGORIES` contains exactly the twelve categories enumerated above (assert equal to an explicit literal set).
11. Simulated `#257` usage: given a profile with `SUMINISTROS_HOME_OFFICE_LUZ=0.21`, a caller calls `resolve_user_ratio` and falls back to `ProportionalityRule.default_ratio` when `None` — demonstrates the consumer contract.

**`src/aeat/domain/financial/usage_ratios/test_service.py`** covers:

1. `load_usage_ratios` on missing path → empty profile, no exception.
2. `load_usage_ratios` on malformed JSON → `UsageRatioPersistenceError`.
3. `load_usage_ratios` on a non-`FileNotFoundError` OSError (simulated via a directory-as-path) → `UsageRatioPersistenceError`.
4. `save_usage_ratios` writes valid JSON that reloads identically.
5. `save_usage_ratios` creates missing parent directories.
6. Two successive saves replace cleanly; no stale `.tmp` files left in the directory.
7. `save_usage_ratios` on an unwritable target (directory) → `UsageRatioPersistenceError`, temp file unlinked.

**`src/aeat/domain/financial/usage_ratios/test_aliases.py`** covers:

1. `FAMILY_ALIASES["home_office_area"]` contains all six `USAGE_RATIO_HOME_AREA` categories.
2. `FAMILY_ALIASES["mileage_business"]` contains the five vehicle categories.
3. `FAMILY_ALIASES["phone_fixed_business"]` is `(TELEFONIA_FIJA,)`.
4. Every aliased category is in `ELIGIBLE_USAGE_RATIO_CATEGORIES`.
5. `FAMILY_ALIASES` is immutable at the mapping level (attempting to assign a new key raises).

**`src/aeat/entrypoints/cli/financial/test_profile.py`** — module-level `pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]` — drives commands via `CliRunner` with `AEAT_USAGE_RATIOS_PATH` pointed at `tmp_path` via `monkeypatch.setenv` (matching how `test_cli.py` isolates filesystem state):

1. `profile ratios list` on empty profile → "No usage ratios configured.".
2. `profile set-ratio suministros_home_office_luz 0.21` → exit 0; `profile ratios list` prints a row with `user_ratio=0.21`, `kind=usage_ratio_home_area`, `statutory_default=0.3`.
3. `profile set-ratio home_office_area 0.21` (family alias) → sets all six `USAGE_RATIO_HOME_AREA` categories to `0.21` in a single call; `ratios list` shows six rows.
4. `profile set-ratio mileage_business 0.6` → sets five vehicle categories.
5. `profile set-ratio material_oficina 0.5` → exit code 2 listing the twelve eligible categories.
6. `profile set-ratio suministros_home_office_luz 1.5` → exit code 2, "ratio must be in [0, 1]".
7. `profile set-ratio suministros_home_office_luz NaN` → exit code 2, "ratio must be finite".
8. `profile set-ratio suministros_home_office_luz not-a-number` → exit code 2, "invalid ratio".
9. `profile set-ratio foo 0.5` → exit code 2, "unknown key" with aliases listed.
10. `profile unset-ratio suministros_home_office_luz` on set key → removes; listing a second time after another unset → "no user ratio set".
11. `profile unset-ratio home_office_area` (family alias) when all six are set → removes all six.
12. `profile unset-ratio home_office_area` when none set → "no user ratio set for home_office_area" (no write).
13. `profile set-ratio telefonia_movil 0.6` (category with `default_ratio is None`) → listing shows `statutory_default=(none)`.

### consumer contract for `#257`

`resolve_user_ratio(profile, category) -> Decimal | None` is the stable pure function the deductibility-compute service will call first; when it returns `None`, `#257` falls back to `ProportionalityRule.default_ratio` and records the resolution source in the transaction's `proportionality_applied` / provenance fields. `#257` will be written against this signature.

## Acceptance criteria (verification)

- `aeat financial profile set-ratio home_office_area 0.21` writes `var/financial/usage-ratios.json` with six home-office categories at `0.21`.
- `aeat financial profile set-ratio suministros_home_office_luz 0.21` writes a single category entry.
- `aeat financial profile ratios list` prints the rows with `user_ratio=0.21` and `statutory_default=0.3`.
- Same command for an ineligible category (`material_oficina`) exits non-zero and names the eligible categories.
- Ratios `-0.1`, `1.1`, `NaN`, `Infinity`, `not-a-number` all exit non-zero with a clear error.
- `resolve_user_ratio(profile, SUMINISTROS_HOME_OFFICE_LUZ)` returns `Decimal("0.21")`; `resolve_user_ratio(profile, SUMINISTROS_HOME_OFFICE_AGUA)` returns `None` when unset.
- `uv run just test-cov` reports ≥ 60% coverage on `src/aeat/domain/financial/usage_ratios/` and `src/aeat/entrypoints/cli/financial/profile.py`.
- Pre-commit passes on every touched file.

## Out of scope

- Deductibility compute (`#257`) — this ADR publishes only the lookup contract.
- Setup wizard prompts (`#214`) — the wizard will call `save_usage_ratios` later.
- Multi-user / per-year profiles — single-user, single-profile scope. `ELIGIBLE_USAGE_RATIO_CATEGORIES` is derived from `CATEGORY_PROFILES_2025` at import time; future multi-year support will need to re-derive per year.
- Concurrent writers. Two parallel `set-ratio` invocations race at `os.replace`; last writer wins. Acceptable for a single-user CLI; revisit if Kent ever scripts parallel invocations.
- No-op protection when a user's ratio equals the statutory default — Kent may deliberately pin a value to preserve intent under future statutory changes.

## Post-approval amendments

The implementation was hardened in two rolling audit rounds after the initial `accepted` milestone. Source-code snippets earlier in this ADR are **illustrative** — consult the shipped files for the current contract.

### Round 1 (commit `9b51c78`)

- **Dropped `is_finite()` guard from `_validate_bounds`.** Pydantic strict mode rejects `NaN` / `Infinity` at the type layer on both JSON and Python paths before the field validator runs, so the guard was unreachable dead code. CLI `_parse_ratio` keeps its own `is_finite()` check because user-typed strings reach `Decimal(raw)` first.
- **Added canonical key ordering on persist.** `_validate_bounds` now returns a dict sorted by `SpendingCategory.value`, so two equal profiles serialise to byte-identical JSON — preventing spurious diffs when Kent's `usage-ratios.json` is git-tracked.
- **Strengthened test quality.** Replaced tautological type-checks with behavioural assertions, dropped byte-exact round-trip assertions, added edge cases (locale comma decimal, target-is-directory save, Kent narrative replay, repeated-set replaces, successive-set accumulates, ineligible-category resolve returns `None`).

### Round 2 (commit `437dab7`)

- **Moved `FAMILY_ALIASES` from the library to the CLI layer.** Aliases are CLI-only parse-time sugar; keeping them in the library package invited the #214 wizard and #257 compute to cargo-cult alias names into persistence paths. Now at `src/aeat/entrypoints/cli/financial/_profile_aliases.py` with tests at `src/aeat/entrypoints/cli/financial/test_profile_aliases.py`.
- **Removed the `phone_fixed_business` alias.** It expanded to `(TELEFONIA_FIJA,)` which is already a member of `home_office_area` (both are `USAGE_RATIO_HOME_AREA`). The overlap meant that `set-ratio home_office_area 0.3` followed by `set-ratio phone_fixed_business 0.9` silently clobbered the earlier value with no warning. A regression test at `test_profile_aliases.py::test_no_alias_overlap_across_the_mapping` pins the disjointness invariant.
- **Surfaced pydantic `ValidationError` detail in `UsageRatioPersistenceError`.** When Kent hand-edits `usage-ratios.json` and introduces a semantic error (out-of-range ratio, ineligible category, unknown key), the CLI now names the offending field and reason instead of collapsing to a generic "invalid usage-ratio profile JSON". The helper `_summarise_validation_errors` walks `exc.errors()` and emits one line per finding.
- **Surfaced `OSError` class and message on read/write failures.** `unable to read/write usage-ratio profile: <path>` now carries the wrapped exception class name and text (e.g. `PermissionError: [Errno 13] Permission denied`), giving Kent enough to diagnose locked files, ACL denials, and disk-full scenarios.
- **Extended the unknown-key hint.** The CLI parser now emits the 12 eligible category ids alongside the two family aliases and includes `difflib.get_close_matches` near-match suggestions — so a typo like `home_office_are` surfaces `did you mean: home_office_area`.

### Round 3 (commits `dce6eed` + `6354eea`)

- **Fixed stale `phone_fixed_business` in `--help` text** (regression introduced by Round 2). Derived `_SET_RATIO_KEY_HELP` and `_UNSET_RATIO_KEY_HELP` from `FAMILY_ALIASES` at module load so the Typer help text can never again drift from the source of truth. Pinned by `test_set_ratio_help_lists_only_current_aliases`.
- **Tolerated UTF-8 BOM on load.** `load_usage_ratios` strips a leading `﻿` before handing to pydantic. Windows Notepad (pre-2019) defaults to UTF-8-with-BOM when Kent hand-edits the JSON.
- **Replaced pydantic's default 38-entry enum dump** with a focused 12-category list when a hand-edited file has an unknown ratio key. Detects the pydantic "dict-key enum failure" shape in `_summarise_validation_errors` and substitutes.
- **Stripped pydantic's "Value error, " prefix** from custom-validator errors in the summary helper.
- **Wrapped long category lists** with `textwrap.fill(width=78, subsequent_indent="    ")` via a new `_indented_wrap` helper. Both the unknown-key and does-not-accept-ratio branches now use the same layout — no more 350+ col single lines. Pinned by `test_set_ratio_ineligible_hint_wraps_and_stays_consistent` (asserts every output line ≤ 80 cols).
- **Tolerated leading/trailing whitespace** in the CLI key argument (common when Kent copy-pastes).
- **Rewrote the tautological `test_aliases_reject_mutation_at_runtime`** to exercise real runtime mutation rejection instead of taking a synthetic-raise branch.
- **Filed follow-up issue #310** for the concurrent-writer data-loss scenario surfaced by the CLI stress audit. Kept as out-of-scope per this ADR's original stance, but the auditor confirmed the failure mode is stronger than last-writer-wins (whole keys vanish).

### Round 4 (commit `231424f`)

- **Persisted JSON now ends with a trailing LF newline** (`\n`, not `\r\n`). `save_usage_ratios` forces `newline="\n"` on the tempfile and appends `"\n"` to the payload. POSIX convention plus cleaner `git diff` when Kent relocates the file outside `var/`.
- **Hoisted `ELIGIBLE_USAGE_RATIO_CATEGORIES` import** in `_service.py` to module top and deleted a misleading "avoid circular import" comment (the cycle does not exist).
- **Guarded empty-items edge case in `_indented_wrap`** and documented the ~65-char per-item budget.
- **Closed six test blindspots** identified by the Round-4 mutation audit:
  - Atomicity pin: monkeypatch `os.replace` to raise; assert target bytes unchanged and no temp file leaks. This was the highest-severity gap — a refactor that dropped atomicity would previously have passed all tests.
  - CLI silent-swallow pin: hand-edit file to corrupt JSON; assert `ratios list` and `set-ratio` both exit non-zero and leave bytes untouched.
  - Exact-token zero-formatting pin (the prior substring assertion was loose).
  - Pydantic "Value error, " prefix-stripping pin.
  - `difflib` cutoff pin: wildly unrelated key produces no `did you mean` suggestion.
  - Payload-indent pin and UTF-8-bytes pin.
- **Softened the ADR's canonical-key-order rationale** to reflect that `var/` is gitignored by default; the diff-stability benefit applies to successive saves, cross-system comparison, and Kent-relocated paths outside `var/`.
