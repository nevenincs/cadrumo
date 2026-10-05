"""A persisted source issue that names a box changes the revision's identity; one stored before boxes did not.

Revision identities are content addresses of stored revisions, so widening the
issue model must leave the identity of every issue stored before the widening
exactly as it was: the box joins the identity only when an issue names one.
"""

from __future__ import annotations

import pytest

from ....core.aggregation import BindingSourceKind
from ..calculation_revision import CalculationSourceIssue, derive_calculation_revision_id
from ..calculation_revision_identity import _source_issues_revision_id_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_WORK_UNIT = "d" * 64


def _revision_id(*issues: CalculationSourceIssue) -> str:
    return derive_calculation_revision_id(
        work_unit_id=_WORK_UNIT,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_issues=issues,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _issue(**changes: object) -> CalculationSourceIssue:
    base = CalculationSourceIssue(
        reason="unrouted_observation",
        binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        message="a row no binding consumes",
    )
    return base.model_copy(update=changes)


def test_an_issue_that_names_no_box_keeps_the_identity_it_had_before_issues_could_name_one() -> None:
    """The payload of an issue without a box is the five parts it always had, in the order stored."""
    payload = _source_issues_revision_id_payload((_issue(),))

    assert payload == {
        "source_issues": (("unrouted_observation", "ledger_iva_aggregation", "", "", "a row no binding consumes"),)
    }


def test_naming_a_box_changes_the_identity_and_two_boxes_differ() -> None:
    unnamed = _revision_id(_issue())
    first = _revision_id(_issue(reason="unresolved_binding", casilla_id="01"))
    second = _revision_id(_issue(reason="unresolved_binding", casilla_id="02"))

    assert len({unnamed, first, second}) == 3


def test_an_issue_without_a_binding_source_has_an_identity() -> None:
    assert _revision_id(_issue(reason="terminal_origin_mismatch", binding_source=None)) != _revision_id(_issue())
