"""Real-behaviour tests asserting InputKind enum comparisons preserve
historical truth values at every former bare-string site.

Each test samples a representative comparison that previously used a
bare string literal and verifies the enum member produces the same
boolean outcome against registry-loaded casilla data.  No mocks, no
hardcoded casilla IDs beyond those verified to exist in the relevant
revision.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...domain.calculations.registry import InputKind
from ...domain.calculations.registry._authority import ValidatedRegistryAuthority
from ...core.resources import bundled_path as _bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_REGISTRY_ROOT = _bundled_path("registry", "aeat")


def _authority() -> ValidatedRegistryAuthority:
    return ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=_bundled_path())


# ---------------------------------------------------------------------------
# InputKind enum StrEnum contract
# ---------------------------------------------------------------------------


def test_input_kind_members_equal_their_string_values() -> None:
    """StrEnum contract: every member equals its TOML literal string value."""
    assert InputKind.MANUAL == "manual"
    assert InputKind.BOUND == "bound"
    assert InputKind.COMPUTED == "computed"
    assert InputKind.INFORMATIONAL == "informational"


def test_input_kind_is_a_str() -> None:
    """InputKind members are str subclass instances (StrEnum)."""
    for member in InputKind:
        assert isinstance(member, str), f"{member!r} is not a str"


# ---------------------------------------------------------------------------
# Registry-loaded casilla comparisons
# ---------------------------------------------------------------------------


def test_computed_casilla_comparison_produces_same_truth_as_bare_string() -> None:
    """A registry computed casilla evaluates truthy under InputKind.COMPUTED.

    Mirrors the former bare-string comparison at filing/__init__.py and
    _formula_runtime.py:
        casilla.input_kind == "computed"
    """
    authority = _authority()
    # Modelo 130 is guaranteed to have computed casillas (formula-driven cuota)
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")
    computed = [c for c in snapshot.revision.casillas if c.formula is not None]
    assert computed, "Test invariant: modelo 130 must have at least one computed casilla"
    for casilla in computed:
        assert casilla.input_kind == InputKind.COMPUTED, (
            f"casilla {casilla.id!r} has formula but input_kind={casilla.input_kind!r}"
        )
        # Cross-check: the enum member equals the bare string so legacy
        # comparisons would have produced the same boolean
        assert (casilla.input_kind == InputKind.COMPUTED) == (casilla.input_kind == "computed"), (
            f"StrEnum equality mismatch for casilla {casilla.id!r}"
        )


def test_manual_casilla_comparison_produces_same_truth_as_bare_string() -> None:
    """A registry manual casilla evaluates truthy under InputKind.MANUAL.

    Mirrors the former bare-string comparison at modelo/_actions.py:
        casilla.input_kind == "manual" and casilla.required
    """
    authority = _authority()
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")
    manual_required = [
        c for c in snapshot.revision.casillas if c.required and c.formula is None and c.binding is None
    ]
    assert manual_required, "Test invariant: modelo 130 must have required manual casillas"
    for casilla in manual_required:
        assert casilla.input_kind == InputKind.MANUAL
        assert (casilla.input_kind == InputKind.MANUAL) == (casilla.input_kind == "manual")


def test_bound_casilla_comparison_produces_same_truth_as_bare_string() -> None:
    """A registry bound casilla evaluates truthy under InputKind.BOUND.

    Mirrors the former bare-string comparison at filing/__init__.py,
    verification/_verify.py, and _formula_runtime.py.
    """
    authority = _authority()
    # Modelo 130 has bound casillas (retención anterior from previous filing)
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")
    bound = [c for c in snapshot.revision.casillas if c.binding is not None]
    assert bound, "Test invariant: modelo 130 must have at least one bound casilla"
    for casilla in bound:
        assert casilla.input_kind == InputKind.BOUND
        assert (casilla.input_kind == InputKind.BOUND) == (casilla.input_kind == "bound")


def test_non_computed_casilla_filter_produces_same_set_as_bare_string() -> None:
    """Filtering with != InputKind.COMPUTED gives the same casilla set as != 'computed'.

    Mirrors application/registry/__init__.py:
        casilla.input_kind != "computed"
    """
    authority = _authority()
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")
    casillas = snapshot.revision.casillas
    set_enum = {c.id for c in casillas if c.input_kind != InputKind.COMPUTED}
    set_bare = {c.id for c in casillas if c.input_kind != "computed"}
    assert set_enum == set_bare, "Enum != filter diverges from bare-string != filter"


def test_tuple_membership_with_enum_members_matches_bare_string_tuple() -> None:
    """Tuple-in membership with enum members matches bare-string tuple.

    Mirrors calc_sheets/_engine.py:
        casilla.input_kind in (InputKind.MANUAL, InputKind.BOUND)
    formerly:
        casilla.input_kind in ("manual", "bound")
    """
    authority = _authority()
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")
    casillas = snapshot.revision.casillas
    set_enum = {c.id for c in casillas if c.input_kind in (InputKind.MANUAL, InputKind.BOUND)}
    set_bare = {c.id for c in casillas if c.input_kind in ("manual", "bound")}
    assert set_enum == set_bare, "Enum tuple-in filter diverges from bare-string tuple"


def test_set_membership_with_enum_members_matches_bare_string_set() -> None:
    """Set-in membership with enum members matches bare-string set.

    Mirrors google/_calc_sheets_pull.py:
        casilla.input_kind in {InputKind.COMPUTED, InputKind.INFORMATIONAL}
    formerly:
        casilla.input_kind in {"computed", "informational"}
    """
    authority = _authority()
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")
    casillas = snapshot.revision.casillas
    set_enum = {c.id for c in casillas if c.input_kind in {InputKind.COMPUTED, InputKind.INFORMATIONAL}}
    set_bare = {c.id for c in casillas if c.input_kind in {"computed", "informational"}}
    assert set_enum == set_bare, "Enum set-in filter diverges from bare-string set"


def test_informational_casilla_comparison_produces_same_truth_as_bare_string() -> None:
    """Informational casilla evaluates truthy under InputKind.INFORMATIONAL.

    Mirrors _parity_harness.py:
        casilla.input_kind == "informational"
    """
    authority = _authority()
    # Modelo 303 is known to have informational casillas (ejercicio/periodo)
    snapshot = authority.snapshot("303", filing_year=2026, period="1T")
    informational = [c for c in snapshot.revision.casillas if c.input_kind == InputKind.INFORMATIONAL]
    assert informational, "Test invariant: modelo 303 must have at least one informational casilla"
    for casilla in informational:
        assert casilla.input_kind == InputKind.INFORMATIONAL
        assert (casilla.input_kind == InputKind.INFORMATIONAL) == (casilla.input_kind == "informational")
