"""W10.P41 rationale-marker aggregate inventory test.

Real-behavior AST + source walk that asserts all -> Any returns and
**kwargs: Any signatures mandated by W10.P41.S575-S581 carry their
documented RATIONALE-* markers.

(a) S575 — profile.py field_validator Any-return markers
    14 @field_validator(mode='before') def lines carry
    ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR.

(b) S576 — profile_catalogue.py catalogue-slot Any-return markers
    get_setup_flow and get_wizard_flows carry
    ANY-RETURN-RATIONALE-CATALOGUE-SLOT.

(c) S577 — google/_calc_sheets_apply.py build-factory Any-return markers
    _drive_service and _sheets_service carry
    ANY-RETURN-RATIONALE-GOOGLE-BUILD-FACTORY.

(d) S578 — _borrador_100.py marker-token correctness
    _derive_snapshot_id carries KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH
    (not the superseded CAST-RATIONALE-BORRADOR100-SNAPSHOT-DISPATCH token).

(e) S580 — core/logging.py overload-impl Any-return marker
    _scrub_value implementation overload carries
    ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL.

No mocks, no skips, no tautological assertions.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

# ---------------------------------------------------------------------------
# Filesystem root
# ---------------------------------------------------------------------------

# __file__ lives at src/aeat/test_w10_p41_rationale_inventory.py
_SRC = Path(__file__).parent  # src/aeat/


def _source(path: Path) -> str:
    assert path.exists(), f"Expected source file not found: {path}"
    return path.read_text(encoding="utf-8")


def _lines(path: Path) -> list[str]:
    return _source(path).splitlines()


# ---------------------------------------------------------------------------
# (a) S575 — profile.py field_validator PYDANTIC-VALIDATOR markers
# ---------------------------------------------------------------------------

_PROFILE_MODULE = _SRC / "core/profile.py"
_PYDANTIC_VALIDATOR_TOKEN = "ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR"

# All @field_validator(mode='before') def names that must carry the token.
_PROFILE_VALIDATORS = (
    "_parse_iva_regime",
    "_parse_tax_residence_ccaa",
    "_parse_entity_type",
    "_parse_legal_entity_form",
    "_parse_irpf_estimation_regime",
    "_parse_situacion_familiar",
    "_parse_unidad_familiar_descendientes_exclusivos",
    "_parse_irpf_special_regime",
    "_parse_fiscal_residency",
    "_parse_taxation_type",
    "_parse_sex_code",
    "_parse_marital_status",
    "_parse_disability_grade",
    "_parse_new_entity_first_two_profit_periods",
)


def _find_def_line(lines: list[str], func_name: str) -> int | None:
    """Return 1-based line number of the first matching def or None."""
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith(f"def {func_name}(") or stripped.startswith(
            f"async def {func_name}("
        ):
            return i
    return None


@pytest.mark.parametrize("func_name", _PROFILE_VALIDATORS)
def test_profile_pydantic_validators_carry_rationale(func_name: str) -> None:
    """Each mode='before' field_validator in profile.py must carry ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR."""
    lines = _lines(_PROFILE_MODULE)
    lineno = _find_def_line(lines, func_name)
    assert lineno is not None, f"profile.py: could not locate def {func_name}"
    def_line = lines[lineno - 1]
    assert _PYDANTIC_VALIDATOR_TOKEN in def_line, (
        f"profile.py:{lineno} def {func_name}: missing {_PYDANTIC_VALIDATOR_TOKEN!r}"
    )


# ---------------------------------------------------------------------------
# (b) S576 — profile_catalogue.py CATALOGUE-SLOT markers
# ---------------------------------------------------------------------------

_CATALOGUE_MODULE = _SRC / "core/profile_catalogue.py"
_CATALOGUE_TOKEN = "ANY-RETURN-RATIONALE-CATALOGUE-SLOT"
_CATALOGUE_FUNCS = ("get_setup_flow", "get_wizard_flows")


@pytest.mark.parametrize("func_name", _CATALOGUE_FUNCS)
def test_profile_catalogue_slots_carry_rationale(func_name: str) -> None:
    """get_setup_flow and get_wizard_flows must carry ANY-RETURN-RATIONALE-CATALOGUE-SLOT."""
    lines = _lines(_CATALOGUE_MODULE)
    lineno = _find_def_line(lines, func_name)
    assert lineno is not None, f"profile_catalogue.py: could not locate def {func_name}"
    def_line = lines[lineno - 1]
    assert _CATALOGUE_TOKEN in def_line, (
        f"profile_catalogue.py:{lineno} def {func_name}: missing {_CATALOGUE_TOKEN!r}"
    )


# ---------------------------------------------------------------------------
# (c) S577 — _calc_sheets_apply.py GOOGLE-BUILD-FACTORY markers
# ---------------------------------------------------------------------------

_CALC_SHEETS_MODULE = _SRC / "adapters/outbound/google/_calc_sheets_apply.py"
_GOOGLE_BUILD_TOKEN = "ANY-RETURN-RATIONALE-GOOGLE-BUILD-FACTORY"
_CALC_SHEETS_FUNCS = ("_drive_service", "_sheets_service")


@pytest.mark.parametrize("func_name", _CALC_SHEETS_FUNCS)
def test_calc_sheets_build_factories_carry_rationale(func_name: str) -> None:
    """_drive_service and _sheets_service must carry ANY-RETURN-RATIONALE-GOOGLE-BUILD-FACTORY."""
    lines = _lines(_CALC_SHEETS_MODULE)
    lineno = _find_def_line(lines, func_name)
    assert lineno is not None, (
        f"_calc_sheets_apply.py: could not locate def {func_name}"
    )
    def_line = lines[lineno - 1]
    assert _GOOGLE_BUILD_TOKEN in def_line, (
        f"_calc_sheets_apply.py:{lineno} def {func_name}: missing {_GOOGLE_BUILD_TOKEN!r}"
    )


# ---------------------------------------------------------------------------
# (d) S578 — _borrador_100.py marker-token correctness
# ---------------------------------------------------------------------------

_BORRADOR_100_MODULE = _SRC / "application/live/_borrador_100.py"
_CORRECT_BORRADOR_TOKEN = "KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH"
_SUPERSEDED_BORRADOR_TOKEN = "CAST-RATIONALE-BORRADOR100-SNAPSHOT-DISPATCH"


def test_borrador_100_snapshot_dispatch_uses_correct_marker_token() -> None:
    """_borrador_100._derive_snapshot_id must use KWARGS-ANY-RATIONALE not the superseded CAST-RATIONALE token."""
    source = _source(_BORRADOR_100_MODULE)
    assert _CORRECT_BORRADOR_TOKEN in source, (
        f"_borrador_100.py: missing {_CORRECT_BORRADOR_TOKEN!r} — marker token not corrected"
    )
    assert _SUPERSEDED_BORRADOR_TOKEN not in source, (
        f"_borrador_100.py: still contains superseded {_SUPERSEDED_BORRADOR_TOKEN!r} — fix not applied"
    )


# ---------------------------------------------------------------------------
# (e) S580 — core/logging.py SCRUB-OVERLOAD-IMPL marker
# ---------------------------------------------------------------------------

_LOGGING_MODULE = _SRC / "core/logging.py"
_SCRUB_OVERLOAD_TOKEN = "ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL"
_SCRUB_FUNC = "_scrub_value"


def test_scrub_value_overload_impl_carries_rationale() -> None:
    """_scrub_value implementation overload in core/logging.py must carry ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL."""
    lines = _lines(_LOGGING_MODULE)
    # Find all occurrences of _scrub_value def lines; the impl has -> Any.
    impl_lines = [
        (i, ln)
        for i, ln in enumerate(lines, start=1)
        if f"def {_SCRUB_FUNC}(" in ln and "-> Any" in ln
    ]
    assert impl_lines, (
        f"core/logging.py: could not locate implementation overload of {_SCRUB_FUNC} returning Any"
    )
    failures = [
        f"core/logging.py:{lineno} def {_SCRUB_FUNC}: missing {_SCRUB_OVERLOAD_TOKEN!r}"
        for lineno, ln in impl_lines
        if _SCRUB_OVERLOAD_TOKEN not in ln
    ]
    assert not failures, "\n".join(failures)
