"""Any-return and kwargs-Any rationale-marker inventory.

Real-behavior AST + source walk that asserts all -> Any returns and
**kwargs: Any signatures listed below carry their documented
RATIONALE-* markers.

(a) setup_answers.py field_validator Any-return markers
    14 @field_validator(mode='before') def lines carry
    ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR.

(b) wizard_catalogue.py catalogue-slot Any-return markers
    get_setup_flow and get_wizard_flows carry
    ANY-RETURN-RATIONALE-CATALOGUE-SLOT.

(c) google/_calc_sheets_apply.py build-factory Any-return markers
    _drive_service and _sheets_service carry
    ANY-RETURN-RATIONALE-GOOGLE-BUILD-FACTORY.

(d) _borrador_100.py marker-token correctness
    _derive_snapshot_id carries KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH
    (not the superseded CAST-RATIONALE-BORRADOR100-SNAPSHOT-DISPATCH).

(e) core/logging.py overload-impl Any-return marker
    _scrub_value implementation overload carries
    ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL.

(f) adapters/outbound/storage/_google_drive.py build-factory markers.

(g) entrypoints/cli/_stdio.py stdlib-logger regression enrollment.

No mocks, no skips, no tautological assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# Filesystem root
# ---------------------------------------------------------------------------

_SRC = Path(__file__).parent.parent  # src/aeat/


def _source(path: Path) -> str:
    assert path.exists(), f"Expected source file not found: {path}"
    return path.read_text(encoding="utf-8")


def _lines(path: Path) -> list[str]:
    return _source(path).splitlines()


# ---------------------------------------------------------------------------
# (a) setup_answers.py field_validator PYDANTIC-VALIDATOR markers
# ---------------------------------------------------------------------------

_PROFILE_MODULE = _SRC / "core/setup_answers.py"
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
        if stripped.startswith(f"def {func_name}(") or stripped.startswith(f"async def {func_name}("):
            return i
    return None


@pytest.mark.parametrize("func_name", _PROFILE_VALIDATORS)
def test_profile_pydantic_validators_carry_rationale(func_name: str) -> None:
    """Each mode='before' field_validator in setup_answers.py carries the rationale marker."""
    lines = _lines(_PROFILE_MODULE)
    lineno = _find_def_line(lines, func_name)
    assert lineno is not None, f"setup_answers.py: could not locate def {func_name}"
    def_line = lines[lineno - 1]
    assert _PYDANTIC_VALIDATOR_TOKEN in def_line, (
        f"setup_answers.py:{lineno} def {func_name}: missing {_PYDANTIC_VALIDATOR_TOKEN!r}"
    )


# ---------------------------------------------------------------------------
# (b) wizard_catalogue.py CATALOGUE-SLOT markers
# ---------------------------------------------------------------------------

_CATALOGUE_MODULE = _SRC / "core/wizard_catalogue.py"
_CATALOGUE_TOKEN = "ANY-RETURN-RATIONALE-CATALOGUE-SLOT"
_CATALOGUE_FUNCS = ("get_setup_flow", "get_wizard_flows")


@pytest.mark.parametrize("func_name", _CATALOGUE_FUNCS)
def test_wizard_catalogue_slots_carry_rationale(func_name: str) -> None:
    """get_setup_flow and get_wizard_flows must carry ANY-RETURN-RATIONALE-CATALOGUE-SLOT."""
    lines = _lines(_CATALOGUE_MODULE)
    lineno = _find_def_line(lines, func_name)
    assert lineno is not None, f"wizard_catalogue.py: could not locate def {func_name}"
    def_line = lines[lineno - 1]
    assert _CATALOGUE_TOKEN in def_line, f"wizard_catalogue.py:{lineno} def {func_name}: missing {_CATALOGUE_TOKEN!r}"


# ---------------------------------------------------------------------------
# (c) _calc_sheets_apply.py GOOGLE-BUILD-FACTORY markers
# ---------------------------------------------------------------------------

_CALC_SHEETS_MODULE = _SRC / "adapters/outbound/google/_calc_sheets_apply.py"
_GOOGLE_BUILD_TOKEN = "ANY-RETURN-RATIONALE-GOOGLE-BUILD-FACTORY"
_CALC_SHEETS_FUNCS = ("_drive_service", "_sheets_service")


@pytest.mark.parametrize("func_name", _CALC_SHEETS_FUNCS)
def test_calc_sheets_build_factories_carry_rationale(func_name: str) -> None:
    """_drive_service and _sheets_service must carry ANY-RETURN-RATIONALE-GOOGLE-BUILD-FACTORY."""
    lines = _lines(_CALC_SHEETS_MODULE)
    lineno = _find_def_line(lines, func_name)
    assert lineno is not None, f"_calc_sheets_apply.py: could not locate def {func_name}"
    def_line = lines[lineno - 1]
    assert _GOOGLE_BUILD_TOKEN in def_line, (
        f"_calc_sheets_apply.py:{lineno} def {func_name}: missing {_GOOGLE_BUILD_TOKEN!r}"
    )


# ---------------------------------------------------------------------------
# (d) _borrador_100.py marker-token correctness
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
# (e) core/logging.py SCRUB-OVERLOAD-IMPL marker
# ---------------------------------------------------------------------------

_LOGGING_MODULE = _SRC / "core/logging.py"
_SCRUB_OVERLOAD_TOKEN = "ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL"
_SCRUB_FUNC = "_scrub_value"


def test_scrub_value_overload_impl_carries_rationale() -> None:
    """_scrub_value implementation overload in core/logging.py must carry ANY-RETURN-RATIONALE-SCRUB-OVERLOAD-IMPL."""
    lines = _lines(_LOGGING_MODULE)
    # Find all occurrences of _scrub_value def lines; the impl has -> Any.
    impl_lines = [(i, ln) for i, ln in enumerate(lines, start=1) if f"def {_SCRUB_FUNC}(" in ln and "-> Any" in ln]
    assert impl_lines, f"core/logging.py: could not locate implementation overload of {_SCRUB_FUNC} returning Any"
    failures = [
        f"core/logging.py:{lineno} def {_SCRUB_FUNC}: missing {_SCRUB_OVERLOAD_TOKEN!r}"
        for lineno, ln in impl_lines
        if _SCRUB_OVERLOAD_TOKEN not in ln
    ]
    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# (f) adapters/outbound/storage/_google_drive.py build-factory markers
# ---------------------------------------------------------------------------

_GOOGLE_DRIVE_MODULE = _SRC / "adapters/outbound/storage/_google_drive.py"
_GOOGLE_DRIVE_TOKEN = "ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY"

# All def/method names that return Any due to the untyped googleapiclient Resource.
_GOOGLE_DRIVE_ANY_RETURN_FUNCS = (
    "_service_factory",
    "_get_service",
    "_execute",
    "_build_media_body",
)


@pytest.mark.parametrize("func_name", _GOOGLE_DRIVE_ANY_RETURN_FUNCS)
def test_google_drive_any_return_sites_carry_rationale(func_name: str) -> None:
    """Each -> Any site in _google_drive.py must carry ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY.

    googleapiclient.discovery.build() returns an untyped Resource object;
    no stub narrows the concrete type, so -> Any is necessary at these 4 sites.
    """
    lines = _lines(_GOOGLE_DRIVE_MODULE)
    lineno = _find_def_line(lines, func_name)
    assert lineno is not None, f"_google_drive.py: could not locate def {func_name}"
    def_line = lines[lineno - 1]
    assert _GOOGLE_DRIVE_TOKEN in def_line, (
        f"_google_drive.py:{lineno} def {func_name}: missing {_GOOGLE_DRIVE_TOKEN!r}"
    )


# ---------------------------------------------------------------------------
# (g) entrypoints/cli/_stdio.py stdlib-logger regression enrollment
# ---------------------------------------------------------------------------
# _stdio.py intentionally uses ``logging.getLogger(__name__)`` (stdlib) rather
# than ``aeat.core.logging.get_logger`` because the module runs before settings
# are loaded — see the constraint comment at ``_LOGGER`` definition (lines
# 150-155).  The rationale is documented inline; this ratchet asserts the
# comment remains present so future refactors cannot silently remove the
# documented justification.

_STDIO_MODULE = _SRC / "entrypoints/cli/_stdio.py"
_STDIO_LOGGER_TOKEN = "aeat.core.logging"
_STDIO_RATIONALE_TOKEN = "before settings are loaded"


def test_stdio_stdlib_logger_rationale_present() -> None:
    """_stdio.py must carry an inline comment explaining why stdlib getLogger is used.

    The module runs at the top of CLI startup, before settings are loaded,
    so it cannot import aeat.core.logging without pulling project configuration
    eagerly.  The rationale comment (referencing 'before settings are loaded')
    must survive so future reviewers understand the intentional deviation.
    """
    source = _source(_STDIO_MODULE)
    assert _STDIO_RATIONALE_TOKEN in source, (
        f"entrypoints/cli/_stdio.py: missing rationale comment {_STDIO_RATIONALE_TOKEN!r} "
        "— the inline explanation for stdlib getLogger usage has been removed"
    )
    assert "_LOGGER = logging.getLogger(__name__)" in source, (
        "entrypoints/cli/_stdio.py: _LOGGER assignment not found — "
        "stdlib logger survivor enrollment check requires this assignment"
    )
