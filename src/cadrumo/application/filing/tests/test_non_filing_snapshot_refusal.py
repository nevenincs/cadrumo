"""Real filing-boundary refusals for revisions without filing-grade authority.

Two refusal paths meet here and they are deliberately different, which is the
point of this module:

* When the caller does NOT name the modelo, the provider is sweeping the whole
  registry and a modelo below filing grade is simply not part of the answer.
  The refusal that reaches the caller is the filing layer's own typed
  :class:`ModeloBuilderError`, and it must not leak a registry exception type
  across the boundary.
* When the caller NAMES the modelo, dropping it and then reporting an empty
  registry would describe the wrong problem: the registry holds the modelo, it
  just declares a lower rung than a filing draft needs. So the provider
  re-raises the registry's own :class:`RegistryValidationError`, whose message
  keeps the modelo, its revision, the grade it declares and the grade that was
  requested. Those four facts are the remediation, so they are asserted here.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.filing.errors import ModeloBuilderError
from ..draft_construction import _load_registry_snapshot
from ..runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "038"
_PERIOD = Period.from_year_and_code(2025, "01")
_DECLARED_GRADE = "applicability"
_REQUESTED_GRADE = "filing"


def _assert_names_modelo_revision_and_both_grades(message: str) -> None:
    """The refusal must carry every fact the caller needs to act on it."""
    assert f"modelo {_MODELO}" in message
    assert "revision 2025-y-siguientes" in message
    assert f"'{_DECLARED_GRADE}' authority grade" in message
    assert f"'{_REQUESTED_GRADE}' snapshot authority" in message


def test_non_filing_grade_snapshot_is_typed_at_build_draft_boundary() -> None:
    """The filing resolver refuses M038 without exposing RegistryValidationError."""
    with pytest.raises(ModeloBuilderError) as exc_info:
        _load_registry_snapshot(modelo=_MODELO, period=_PERIOD)

    assert exc_info.value.translated_message == "application.filing.build_draft.errors.registry_snapshot_unavailable"
    assert exc_info.value.context == {
        "modelo": _MODELO,
        "filing_year": _PERIOD.filing_year,
        "period": _PERIOD.registry_token,
        "registry_error_type": "RegistryValidationError",
    }


def test_named_non_filing_modelo_keeps_the_registry_grade_refusal() -> None:
    """Naming M038 must surface the registry's own grade refusal, not an empty registry.

    Wrapping this in the filing layer's ``registry_snapshot_unavailable`` would
    say the snapshot could not be obtained, which is untrue and unactionable:
    the snapshot exists, at a rung below the one a filing draft needs. The raw
    refusal names the modelo, the revision and both grades.
    """
    with pytest.raises(RegistryValidationError) as exc_info:
        build_runtime_schema_provider(modelos=(_MODELO,))

    _assert_names_modelo_revision_and_both_grades(str(exc_info.value))


def test_named_non_filing_modelo_keeps_the_grade_refusal_when_period_scoped() -> None:
    """A period-scoped request for a named M038 refuses on the same grade terms.

    Reds against the earlier behaviour, which swallowed the grade refusal and
    reported ``registry_empty_for_period`` -- a message that blames the period
    for a mismatch the period had nothing to do with.
    """
    with pytest.raises(RegistryValidationError) as exc_info:
        build_runtime_schema_provider(
            modelos=(_MODELO,),
            filing_year=_PERIOD.filing_year,
            period=_PERIOD,
        )

    _assert_names_modelo_revision_and_both_grades(str(exc_info.value))
