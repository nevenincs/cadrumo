"""A persisted source issue that names a box changes the revision's identity; one stored before boxes did not.

Revision identities are content addresses of stored revisions, so widening the
issue model must leave the identity of every issue stored before the widening
exactly as it was: the box joins the identity only when an issue names one, and
a resolver's stated outcome only when an issue states one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.aggregation import BindingSourceKind, BindingValueOutcome
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ..calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
    derive_calculation_revision_id_from_revision,
)
from ..calculation_revision_identity import source_issues_revision_id_payload
from ..calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence, CalculationSourceIssue
from ..errors import ModeloValidationError

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
    payload = source_issues_revision_id_payload((_issue(),))

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


def _capped_issue(**changes: object) -> CalculationSourceIssue:
    """A capped casilla 06 value of 510,00 as the calculation persists it, before any outcome is stated."""
    base = CalculationSourceIssue(
        reason="advisory_binding_value",
        binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        message="capped",
        source_ref="modelo-130-actividad-economica-retenciones-cumulative",
        casilla_id="06",
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.ADVISORY_IMPUTATION_PERIOD_UNGROUNDED,
            box="06",
            amount="510.00",
            binding="modelo-130-actividad-economica-retenciones-cumulative",
        ),
    )
    return base.model_copy(update=changes)


# The parts this capped issue's identity was stored with: the reason, source, reference, resolver,
# message, box and its fact, in that order.
_STORED_CAPPED_PARTS: tuple[str, ...] = (
    "advisory_binding_value",
    "ledger_renta_income_aggregation",
    "modelo-130-actividad-economica-retenciones-cumulative",
    "",
    "capped",
    "06",
    "advisory_imputation_period_ungrounded",
    "amount",
    "510.00",
    "binding",
    "modelo-130-actividad-economica-retenciones-cumulative",
    "box",
    "06",
)
# The id this capped issue's revision was stored under before issues could state an outcome, derived by
# the identity code as it stood then; it must never move.
_STORED_CAPPED_REVISION_ID = "a29d3d893331cef3de30443b44fe05f58a95babbddef445e381da8650c25f2be"


def test_a_capped_issue_stored_without_an_outcome_keeps_its_stored_identity() -> None:
    issue = _capped_issue()

    assert source_issues_revision_id_payload((issue,)) == {"source_issues": (_STORED_CAPPED_PARTS,)}
    assert _revision_id(issue) == _STORED_CAPPED_REVISION_ID


def test_a_stated_outcome_joins_the_identity_and_each_outcome_differs() -> None:
    silent = _revision_id(_capped_issue())
    proven = _revision_id(_capped_issue(value_outcome=BindingValueOutcome.PROVEN_ZERO))
    bearing = _revision_id(_capped_issue(value_outcome=BindingValueOutcome.FROM_BEARING_ROWS))

    assert len({silent, proven, bearing}) == 3
    payload = source_issues_revision_id_payload((_capped_issue(value_outcome=BindingValueOutcome.PROVEN_ZERO),))
    assert payload == {"source_issues": ((*_STORED_CAPPED_PARTS, "value_outcome=proven_zero"),)}


def test_only_a_capped_value_states_an_outcome() -> None:
    with pytest.raises(ValidationError, match="only a capped binding value") as refused:
        CalculationSourceIssue(
            reason="unresolved_binding",
            binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
            message="a box with no value",
            casilla_id="01",
            value_outcome=BindingValueOutcome.PROVEN_ZERO,
        )
    assert isinstance(refused.value.errors()[0]["ctx"]["error"].__cause__, ModeloValidationError)


def test_a_capped_issue_stored_before_outcomes_loads_without_one() -> None:
    stored = _capped_issue().model_dump(mode="json")
    del stored["value_outcome"]

    loaded = CalculationSourceIssue.model_validate_json(json.dumps(stored))

    assert loaded.value_outcome is None
    assert _revision_id(loaded) == _STORED_CAPPED_REVISION_ID


@pytest.mark.usefixtures("operation")
def test_a_revision_stored_before_outcomes_loads_and_replays_to_its_stored_id() -> None:
    """A whole stored revision, its issue in the old shape, passes the identity check the load runs."""
    issue = _capped_issue()
    clock = datetime(2026, 4, 6, 10, 0, tzinfo=UTC)
    revision = CalculationRevision(
        calculation_revision_id=_STORED_CAPPED_REVISION_ID,
        work_unit_id=_WORK_UNIT,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="130", revision_id="2019-y-siguientes", modelo_year=2026, period="1T"
        ),
        state=CalculationRevisionState.PRESENTADO,
        casilla_values={},
        observations=(),
        created_at=clock,
        updated_at=clock,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=(issue,),
        verified_at=clock,
        verified_by="operator",
        filed_at=clock,
        filed_by="operator",
    )
    stored = revision.model_dump(mode="json")
    for stored_issue in stored["source_issues"]:
        del stored_issue["value_outcome"]

    loaded = CalculationRevision.model_validate_json(json.dumps(stored))

    assert loaded.calculation_revision_id == _STORED_CAPPED_REVISION_ID
    assert derive_calculation_revision_id_from_revision(loaded) == _STORED_CAPPED_REVISION_ID
    assert loaded.source_issues[0].value_outcome is None
