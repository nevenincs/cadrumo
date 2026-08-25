"""Schema + resolver contract tests for ``source_period_offset_from_target``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema_surfaces import RelationDefinition

from .....core import CasillaId, validated_casilla_id
from ..errors import RegistryValidationError
from ..relations import _derive_offset_source_anchor, derive_offset_source_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IVA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado", surface="_IVA_RESULTADO_CASILLA")


def _relation(**overrides: object) -> RelationDefinition:
    defaults: dict[str, object] = {
        "id": "test-rel",
        "kind": "previous_period",
        "dependency_role": "direct_calculation",
        "source_modelo": "303",
        "source_revision_selector": {"filing_year_delta": 0},
        "source_casilla_id": _IVA_RESULTADO_CASILLA,
        "target_binding": "iva.previo",
        "period_alignment": {"mode": "previous_quarter"},
        "legal_refs": ("ley-37-1992:art-99",),
        "source_refs": ("aeat-modelo-303-procedure",),
    }
    defaults.update(overrides)
    return RelationDefinition.model_validate(defaults)


def test_quarterly_offset_resolves_previous_quarter() -> None:
    relation = _relation(target_periods=("2T", "3T", "4T"), source_period_offset_from_target=-1)
    assert derive_offset_source_period(relation, target_period="2T") == "1T"
    assert derive_offset_source_period(relation, target_period="3T") == "2T"
    assert derive_offset_source_period(relation, target_period="4T") == "3T"


def test_quarterly_offset_wraps_across_year_boundary() -> None:
    """1T with offset=-1 wraps to 4T of the prior year (year_delta=-1).

    IVA carry-forward semantics: Q4 of year N-1 is the legitimate source
    period for Q1 of year N, so the resolver returns the wrapped period
    along with a negative year delta rather than ``None``.
    """
    relation = _relation(target_periods=("1T", "2T", "3T", "4T"), source_period_offset_from_target=-1)
    assert derive_offset_source_period(relation, target_period="1T") == "4T"
    assert _derive_offset_source_anchor(relation, target_period="1T") == (-1, "4T")


def test_pago_fraccionado_offset_resolves_previous_period() -> None:
    """Modelo 202 pago-fraccionado periods 1P/2P/3P with offset=-1.

    Within-year offsets produce the prior pago. 1P with offset=-1 wraps
    to 3P of the prior year (year_delta=-1).
    """
    relation = _relation(target_periods=("1P", "2P", "3P"), source_period_offset_from_target=-1)
    assert derive_offset_source_period(relation, target_period="2P") == "1P"
    assert derive_offset_source_period(relation, target_period="3P") == "2P"
    assert derive_offset_source_period(relation, target_period="1P") == "3P"
    assert _derive_offset_source_anchor(relation, target_period="1P") == (-1, "3P")


def test_monthly_offset_resolves_previous_month() -> None:
    relation = _relation(target_periods=("02", "12"), source_period_offset_from_target=-1)
    assert derive_offset_source_period(relation, target_period="02") == "01"
    assert derive_offset_source_period(relation, target_period="12") == "11"


def test_monthly_offset_wraps_across_year_boundary() -> None:
    """Month 01 with offset=-1 wraps to month 12 of the prior year."""
    relation = _relation(target_periods=("01",), source_period_offset_from_target=-1)
    assert derive_offset_source_period(relation, target_period="01") == "12"
    assert _derive_offset_source_anchor(relation, target_period="01") == (-1, "12")


def test_source_periods_and_offset_mutually_exclusive() -> None:
    with pytest.raises(ValidationError, match="cannot declare source_periods"):
        _relation(source_periods=("1T",), source_period_offset_from_target=-1)


def test_zero_offset_rejected() -> None:
    with pytest.raises(ValidationError, match="must be non-zero"):
        _relation(source_period_offset_from_target=0)


def test_unknown_period_format_rejected_at_construction_and_at_resolution() -> None:
    """An uninterpretable period is refused when DECLARED, and the backstop still holds.

    This drove ``derive_offset_source_period`` with ``"ANUAL"`` and expected the
    resolution-time refusal. ``RelationDefinition.target_periods`` now validates
    the period grammar, so the relation cannot be built at all -- the invariant
    moved to build time, which is the direction the registry's binding rules ask
    for and a strictly earlier catch.

    The resolve-time check remains as a backstop, and a backstop nothing can
    reach through the type is exactly the kind that rots unnoticed, so it is
    still exercised -- on a model built through ``model_construct``, which skips
    validation and is the only way an uninterpretable period reaches it now.
    """
    with pytest.raises(ValidationError, match="invalid period code 'ANUAL'"):
        _relation(target_periods=("ANUAL",), source_period_offset_from_target=-1)

    valid = _relation(target_periods=("0A",), source_period_offset_from_target=-1)
    unvalidated = valid.model_construct(**{**valid.__dict__, "target_periods": ("ANUAL",)})
    with pytest.raises(RegistryValidationError, match="cannot interpret target period"):
        derive_offset_source_period(unvalidated, target_period="ANUAL")
