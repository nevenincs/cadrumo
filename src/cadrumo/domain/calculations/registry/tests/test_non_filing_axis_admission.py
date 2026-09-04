"""Teeth for the declared-reason precondition on a non-filing date axis.

Every dated value that ships today is on ``filing_period``, and for most
regulated figures that is correct: the period a declaration covers IS what the
law keys to. The other axes exist for figures fixed by an EVENT -- a capital
good's acquisition, an invoice's issue date -- where the filing period genuinely
cannot express the rule.

Moving a figure onto an event axis therefore changes WHICH LAW applies to an old
fact. That is a legal claim, so it must be declared rather than inferred, and
this gate is the precondition that lands BEFORE any parameter uses such an axis.

The rule binds in both directions, which is what makes it enumerable: a
parameter using a non-filing axis must carry an admission, and a parameter
carrying an admission must use the axis it admits. Neither an undeclared axis
nor an unused declaration can exist, so the set of admissions and the set of
non-filing parameters are provably the same set.
"""

from __future__ import annotations

from datetime import date

import pytest

from .._validate_parameter_temporal import (
    non_filing_axis_parameters,
    validate_non_filing_axis_admission,
)
from ..authority import ValidatedRegistryAuthority, bundled_authority
from ..schema_formula import ParameterDefinition

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_KNOWN_LEGAL_REF = "ley-37-1992:art-107"
_LEGAL_CATALOGUE = {_KNOWN_LEGAL_REF: object()}

_REASON = "The window is fixed when the good is acquired, so the filing period cannot express it."

_FILING_VALUES = ({"value": "4", "date_axis": "filing_period", "valid_from": date(2025, 1, 1)},)
_EVENT_VALUES = ({"value": "4", "date_axis": "transaction_date", "valid_from": date(2016, 1, 1)},)
_ADMISSION = {
    "date_axis": "transaction_date",
    "legal_ref": _KNOWN_LEGAL_REF,
    "reason": _REASON,
}


@pytest.fixture(scope="session")
def registry_authority() -> ValidatedRegistryAuthority:
    """The bundled validated authority."""
    return bundled_authority()


def _parameter(**overrides: object) -> ParameterDefinition:
    """Build one parameter definition around the axis fields under test."""
    payload: dict[str, object] = {
        "id": "probe",
        "data_type": "integer",
        "unit": "years",
        "legal_refs": (_KNOWN_LEGAL_REF,),
        "source_refs": ("aeat-modelo-303-procedure",),
    }
    payload.update(overrides)
    return ParameterDefinition.model_validate(payload)


def test_a_filing_period_parameter_needs_no_admission() -> None:
    """The ordinary shape, which must stay silent or every shipped value breaks."""
    assert not validate_non_filing_axis_admission(
        "probe",
        _parameter(values=_FILING_VALUES),
        _LEGAL_CATALOGUE,
    )


def test_a_declared_admission_admits_the_event_axis() -> None:
    """The capability the gate exists to permit, not merely to forbid."""
    assert not validate_non_filing_axis_admission(
        "probe",
        _parameter(values=_EVENT_VALUES, non_filing_axis_admission=_ADMISSION),
        _LEGAL_CATALOGUE,
    )


def test_an_undeclared_non_filing_axis_is_refused() -> None:
    """TEETH: the defect the gate exists for -- a silent move onto an event axis."""
    failures = validate_non_filing_axis_admission(
        "probe",
        _parameter(values=_EVENT_VALUES),
        _LEGAL_CATALOGUE,
    )
    assert len(failures) == 1
    assert "without a declared admission" in failures[0]
    assert "transaction_date" in failures[0]


def test_an_admission_without_a_non_filing_value_is_refused() -> None:
    """TEETH, the other direction: a declaration nothing uses.

    Without this the two sets could drift apart, and an author could leave a
    stale admission standing that reads as justifying a move already made.
    """
    failures = validate_non_filing_axis_admission(
        "probe",
        _parameter(values=_FILING_VALUES, non_filing_axis_admission=_ADMISSION),
        _LEGAL_CATALOGUE,
    )
    assert len(failures) == 1
    assert "remove the admission or key the values to the axis it admits" in failures[0]


def test_an_admission_naming_a_different_axis_is_refused() -> None:
    """TEETH: the declaration cannot drift away from the data it justifies."""
    failures = validate_non_filing_axis_admission(
        "probe",
        _parameter(
            values=_EVENT_VALUES,
            non_filing_axis_admission={**_ADMISSION, "date_axis": "invoice_date"},
        ),
        _LEGAL_CATALOGUE,
    )
    assert any("must name the axis actually used" in failure for failure in failures)


def test_an_admission_on_an_unknown_provision_is_refused() -> None:
    """TEETH: the reason cannot rest on an invented citation.

    An earlier campaign step had a parameter withdrawn rather than repointed
    when its cited article turned out not to exist; the same discipline is
    enforced structurally here.
    """
    failures = validate_non_filing_axis_admission(
        "probe",
        _parameter(
            values=_EVENT_VALUES,
            non_filing_axis_admission={**_ADMISSION, "legal_ref": "ley-99-9999:art-1"},
        ),
        _LEGAL_CATALOGUE,
    )
    assert any("unknown legal reference" in failure for failure in failures)


def test_a_reason_too_short_to_be_a_reason_is_refused() -> None:
    """TEETH: the field cannot be satisfied by a placeholder.

    A one-word reason would let the declaration exist while explaining nothing,
    which is the failure mode a free-text justification invites.
    """
    with pytest.raises(ValueError, match="reason"):
        _parameter(
            values=_EVENT_VALUES,
            non_filing_axis_admission={**_ADMISSION, "reason": "event"},
        )


def test_the_live_tree_declares_no_non_filing_axis_parameter(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The enumerator answers the question the decision requires be answerable.

    Today the answer is "none", and that is worth pinning: it is the baseline
    against which the first admitted parameter will be read, and it proves the
    gate above is not silently excusing something already shipped.
    """
    admitted: list[str] = []
    # Every modelo the authority actually holds, so the sweep cannot silently
    # miss one and report a false "none" -- and so no exception needs swallowing.
    for modelo in registry_authority.modelos:
        for revision in modelo.revisions.values():
            admitted.extend(parameter.id for parameter, _ in non_filing_axis_parameters(revision))
    assert admitted == [], (
        f"parameters {admitted} are keyed to a non-filing axis. That is now permitted, but it "
        "changes this gate's baseline: each must carry a declared admission naming the provision "
        "and the axis, and this assertion should be updated to name them deliberately."
    )
