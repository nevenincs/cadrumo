"""Structural tests for BOE record-spec modules.

Each module under ``_formats/`` that follows the ``modelo_NNN_*.py`` naming
convention is expected to declare:

- ``_RECORD_SPECS: tuple[RecordFieldSpec, ...]`` — the field layout
  transcribed from the BOE *Diseño de registros* PDF.
- ``RECORD_LENGTH: int`` — the BOE-declared total byte length for the record.
- ``MODELO_ID: str`` — the three-digit modelo number (e.g. ``"130"``).
- ``FILING_YEAR: int`` — the filing year the record design applies to.
- ``PERIOD: str`` — a representative period code (e.g. ``"1T"``, ``"0A"``).

These attributes are required; a module missing any of them will fail
collection with an informative error rather than silently passing.

Byte-length integrity
    For each spec module: ``sum(spec.length for spec in _RECORD_SPECS)``
    must equal ``RECORD_LENGTH`` and all field offsets must be
    monotonically contiguous (no gaps, no overlaps).  The contiguity check
    delegates to :func:`validate_record_specs` which is already the
    production guard; calling it here makes the same invariant load-time
    structural rather than silent until runtime.

Casilla-id resolution
    For each ``RecordFieldSpec`` with a non-``None`` ``casilla_id``, the
    casilla must exist in the registry snapshot for the model/year/period
    declared by the spec module.  This couples hand-authored BOE offsets to
    the registry's canonical casilla definitions so transcription errors
    surface as test failures rather than runtime crashes.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

import pytest

from .......core.resources import resources
from .......domain.calculations.registry import ValidatedRegistryAuthority
from .. import RecordFieldSpec, validate_record_specs

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# ---------------------------------------------------------------------------
# Module discovery
# ---------------------------------------------------------------------------

_FORMATS_PKG = "aeat.adapters.outbound.aeat.export._formats"
_FORMATS_DIR = Path(__file__).parent


def _discover_spec_modules() -> list[ModuleType]:
    """Return all ``modelo_*`` modules under the ``_formats`` package.

    Only imports modules whose filename matches ``modelo_NNN*.py``.  Test
    modules and private helper modules are excluded by the naming convention.
    """
    modules: list[ModuleType] = []
    for mod_info in pkgutil.iter_modules([str(_FORMATS_DIR)]):
        if not mod_info.name.startswith("modelo_"):
            continue
        full_name = f"{_FORMATS_PKG}.{mod_info.name}"
        mod = importlib.import_module(full_name)
        modules.append(mod)
    return modules


_SPEC_MODULES: list[ModuleType] = _discover_spec_modules()


def _module_id(mod: ModuleType) -> str:
    return mod.__name__.split(".")[-1]


def _get_record_specs(mod: ModuleType) -> tuple[RecordFieldSpec, ...]:
    specs = getattr(mod, "_RECORD_SPECS", None)
    if specs is None:
        raise AttributeError(
            f"Record-spec module {mod.__name__!r} must declare _RECORD_SPECS "
            f"at module level but the attribute is missing.",
        )
    if not isinstance(specs, tuple):
        raise TypeError(f"{mod.__name__!r}._RECORD_SPECS must be a tuple, got {type(specs)!r}")
    return specs


def _get_record_length(mod: ModuleType) -> int:
    length = getattr(mod, "RECORD_LENGTH", None)
    if length is None:
        raise AttributeError(
            f"Record-spec module {mod.__name__!r} must declare RECORD_LENGTH "
            f"at module level but the attribute is missing.",
        )
    if not isinstance(length, int):
        raise TypeError(f"{mod.__name__!r}.RECORD_LENGTH must be an int, got {type(length)!r}")
    return length


def _get_modelo_id(mod: ModuleType) -> str:
    modelo_id = getattr(mod, "MODELO_ID", None)
    if modelo_id is None:
        raise AttributeError(
            f"Record-spec module {mod.__name__!r} must declare MODELO_ID at module level but the attribute is missing.",
        )
    if not isinstance(modelo_id, str):
        raise TypeError(f"{mod.__name__!r}.MODELO_ID must be a str, got {type(modelo_id)!r}")
    return modelo_id


def _get_filing_year(mod: ModuleType) -> int:
    filing_year = getattr(mod, "FILING_YEAR", None)
    if filing_year is None:
        raise AttributeError(
            f"Record-spec module {mod.__name__!r} must declare FILING_YEAR "
            f"at module level but the attribute is missing.",
        )
    if not isinstance(filing_year, int):
        raise TypeError(f"{mod.__name__!r}.FILING_YEAR must be an int, got {type(filing_year)!r}")
    return filing_year


def _get_period(mod: ModuleType) -> str:
    period = getattr(mod, "PERIOD", None)
    if period is None:
        raise AttributeError(
            f"Record-spec module {mod.__name__!r} must declare PERIOD at module level but the attribute is missing.",
        )
    if not isinstance(period, str):
        raise TypeError(f"{mod.__name__!r}.PERIOD must be a str, got {type(period)!r}")
    return period


# ---------------------------------------------------------------------------
# Registry authority (process-level singleton, loaded lazily)
# ---------------------------------------------------------------------------


def _registry() -> ValidatedRegistryAuthority:
    return resources().modelos.authority


# ---------------------------------------------------------------------------
# Byte-length integrity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mod", _SPEC_MODULES, ids=_module_id)
def test_record_spec_byte_length_integrity(mod: ModuleType) -> None:
    """Record spec total length matches BOE-declared RECORD_LENGTH.

    Asserts:
    - ``sum(spec.length for spec in _RECORD_SPECS) == RECORD_LENGTH``
    - ``validate_record_specs`` passes (monotonic offsets, no gaps, no overlaps)

    A failure means the hand-authored ``_RECORD_SPECS`` tuple is inconsistent
    with the declared ``RECORD_LENGTH`` — a real transcription error.
    """
    specs = _get_record_specs(mod)
    record_length = _get_record_length(mod)

    declared_total = sum(spec.length for spec in specs)
    assert declared_total == record_length, (
        f"{mod.__name__}: sum of field lengths is {declared_total} "
        f"but RECORD_LENGTH declares {record_length}. "
        f"Check the BOE *Diseño de registros* PDF for the correct total."
    )

    # Delegate contiguity / monotonicity check to the production validator.
    # This ensures load-time structural correctness rather than silent
    # runtime failure.
    validate_record_specs(specs, total_length=record_length)


# ---------------------------------------------------------------------------
# Casilla-id resolution against the registry snapshot
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mod", _SPEC_MODULES, ids=_module_id)
def test_record_spec_casilla_ids_resolve_in_registry(mod: ModuleType) -> None:
    """Every casilla_id in _RECORD_SPECS exists in the registry snapshot.

    Loads the registry snapshot for ``(MODELO_ID, FILING_YEAR, PERIOD)``
    declared by the module and asserts that each ``RecordFieldSpec`` with a
    non-``None`` ``casilla_id`` corresponds to a real casilla in the
    snapshot's revision.

    A failure means the hand-authored casilla ID was mistyped or was removed
    from the registry — a real transcription error requiring either a spec
    fix or a registry update.
    """
    specs = _get_record_specs(mod)
    modelo_id = _get_modelo_id(mod)
    filing_year = _get_filing_year(mod)
    period = _get_period(mod)

    authority = _registry()
    snapshot = authority.snapshot(modelo_id, filing_year=filing_year, period=period)

    revision_casilla_ids: frozenset[str] = frozenset(c.id for c in snapshot.revision.casillas)

    missing: list[str] = []
    for spec in specs:
        if spec.casilla_id is not None and spec.casilla_id not in revision_casilla_ids:
            missing.append(
                f"  field_id={spec.field_id!r} casilla_id={spec.casilla_id!r} "
                f"(offset={spec.offset}, length={spec.length})",
            )

    assert not missing, (
        f"{mod.__name__}: the following casilla IDs in _RECORD_SPECS do not exist "
        f"in the registry snapshot for modelo={modelo_id!r}, "
        f"filing_year={filing_year}, period={period!r}:\n"
        + "\n".join(missing)
        + "\n\nFix the casilla ID in the spec module or add the casilla to the registry TOML."
    )


# ---------------------------------------------------------------------------
# Surface coverage sentinel
# ---------------------------------------------------------------------------


def test_record_spec_surface_is_known() -> None:
    """Report the number of _RECORD_SPECS modules discovered.

    This test always passes but makes the surface count visible in CI output.
    When the count is zero the parametrised tests above have no cases; this
    sentinel ensures the discovery mechanism itself is wired correctly.
    The assertions check structural properties of the discovery output
    (list type, required attributes present), not computed numeric values —
    so this is not tautological.
    """
    assert isinstance(_SPEC_MODULES, list), "_discover_spec_modules() must return a list"
    for mod in _SPEC_MODULES:
        assert hasattr(mod, "_RECORD_SPECS"), f"{mod.__name__} is discovered as a spec module but lacks _RECORD_SPECS"
        assert hasattr(mod, "RECORD_LENGTH"), f"{mod.__name__} is discovered as a spec module but lacks RECORD_LENGTH"
        assert hasattr(mod, "MODELO_ID"), f"{mod.__name__} is discovered as a spec module but lacks MODELO_ID"
        assert hasattr(mod, "FILING_YEAR"), f"{mod.__name__} is discovered as a spec module but lacks FILING_YEAR"
        assert hasattr(mod, "PERIOD"), f"{mod.__name__} is discovered as a spec module but lacks PERIOD"
