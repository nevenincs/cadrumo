"""Proofs that the wire submission's two translation directions agree.

``to_submission`` has always existed, because the executor consumes the wire
form. Its inverse did not, which is why the registered apply operation had no
caller outside this package's own tests: a surface that stages domain intents
could not reach it. These tests hold the two directions against each other, so
a field added to one and forgotten in the other fails here rather than
silently dropping an operator's edit somewhere downstream.

See Also:
    :class:`cadrumo.application.modelo.operation_definitions.ModeloEditApplySubmissionV1`
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.temporal import select_revision
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...operations.registry import OperationSchemaIdentityV1
from .._edit_execution import _reachable_scalar_inputs
from ..edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from ..edit_models import (
    ModeloDetailRowEditIntentV1,
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmittedV1,
    ModeloEditDetailRowAddressV1,
    ModeloEditDetailRowIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ..edit_services import admit_modelo_edit, modelo_edit_request_schema_identity, modelo_edit_result_schema_identity
from ..operation_definitions import ModeloEditApplySubmissionV1
from ..work_addressing import ModeloExactWorkUnitTarget
from ..workspace_models import ModeloWorkspaceExactWorkUnitTargetV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_MODELO = "130"
_FILING_YEAR = 2026
_DIGEST = "a" * 64

#: Restated from the execution boundary's own set rather than imported, because
#: that constant is private to a sibling module; the proof below drives the real
#: function, so a divergence surfaces there rather than hiding here.
_NUMERIC_TYPES = frozenset({"decimal", "money", "integer", "ratio", "year"})


def _identity() -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)


def _baseline():
    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    modelo = ModeloCode(_MODELO)
    revision_id = select_revision(
        bundled_authority().validate_modelo(modelo), filing_year=_FILING_YEAR, period="1T"
    ).id
    now = datetime(2026, 1, 10, tzinfo=UTC)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=modelo, filing_year=_FILING_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{_FILING_YEAR}-1T",
        created_at=now,
        updated_at=now,
    )
    result = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(
            target=ModeloWorkspaceExactWorkUnitTargetV1(
                target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
            ),
            mutation_family=ModeloEditMutationFamily.CALCULATE,
        ),
        bucket_id=work_unit.bucket_id,
        work_catalogue=WorkUnitCatalogue.from_work_units((work_unit,)),
        calculation_catalogue=CalculationRevisionCatalogue(),
        compatibility=ModeloEditCompatibilityTupleV1(
            contract_set_digest=_DIGEST,
            operation_definition_id="modelo.calculate",
            definition_contract_digest=_DIGEST,
            request_schema=modelo_edit_request_schema_identity(),
            result_schema=modelo_edit_result_schema_identity(),
            review_projection_contract_version=None,
            review_schema=None,
            workspace_refresh_target_schema=_identity(),
            financial_operand_schema=_identity(),
        ),
    )
    assert isinstance(result, ModeloEditAdmittedV1), f"admission refused: {result}"
    return result.baseline


def _writable_casilla_id(baseline: object) -> str:
    """Return one casilla the admission actually permits writing, and that is numeric.

    Both filters matter and neither is incidental. The permitted surface
    carries NON-writable entries too, and they have casilla ids, so taking the
    first entry with an id addresses a casilla the contract would refuse --
    which is what an earlier version of this helper did. And the amount proofs
    below distinguish the numeric input channel from the text one, so the
    casilla must be one the registry declares numeric or the distinction is
    untestable.
    """
    for entry in baseline.permitted_surface:
        if getattr(entry, "kind", None) == "writable_scalar" and getattr(entry, "data_type", None) in _NUMERIC_TYPES:
            return str(entry.casilla_id)
    pytest.fail("the real M130 admission permits no numeric writable scalar; these proofs would be vacuous")


def test_a_submission_survives_the_round_trip_through_the_wire_form() -> None:
    """Domain to wire and back must reproduce the submission exactly.

    Strict equality on the whole record rather than field sampling: a
    drops-a-field regression is invisible to a partial comparison, and the
    wire form exists precisely to be a total translation.

    Driven with a text value, because the round trip is deliberately NOT an
    identity for ``Decimal`` -- see the sibling test, which pins that case to
    the property that actually holds instead of asserting one that never did.
    """
    baseline = _baseline()
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=_writable_casilla_id(baseline)),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value="150.00",
            ),
        ),
    )

    restored = ModeloEditApplySubmissionV1.from_submission(submission).to_submission()

    assert restored == submission


def test_a_decimal_amount_crosses_as_text_and_is_rebuilt_from_the_registry_type() -> None:
    """The amount's characters survive the wire, and the registry decides its type.

    The wire union has no ``Decimal`` member, so an amount crosses as
    characters and comes back as a ``str`` -- the round trip is NOT an
    identity here, and asserting that it is would be asserting something the
    code never did. What must hold is stronger and is what this pins: the
    exact digits are preserved across the wire, and the execution boundary
    reconstructs the ``Decimal`` from the CASILLA'S declared registry
    ``data_type`` rather than from whichever Python type happened to survive.
    An amount silently arriving with different digits, or a numeric casilla
    receiving text, is what would actually harm a filing.
    """
    baseline = _baseline()
    casilla_id = _writable_casilla_id(baseline)
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=casilla_id),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value=Decimal("1234.56"),
            ),
        ),
    )

    wire = ModeloEditApplySubmissionV1.from_submission(submission)

    assert wire.scalar_intents[0].value == "1234.56", "the amount must cross as its exact characters"

    reached = _reachable_scalar_inputs(wire.to_submission())
    assert isinstance(reached, tuple), f"the executor refused a well-formed submission: {reached}"
    numeric, text, cleared = reached
    assert numeric.get(casilla_id) == Decimal("1234.56"), (
        "the execution boundary must rebuild the exact amount for a numeric casilla"
    )
    assert casilla_id not in text, "a numeric casilla must not receive the value as text"
    assert cleared == ()


def test_the_baseline_mirror_carries_every_wire_field() -> None:
    """Anti-tautology: prove the round trip is not passing on a hollow baseline.

    Without this, both proofs above would pass equally well if from_baseline
    silently omitted fields whose domain counterparts happen to default.
    """
    baseline = _baseline()

    wire = ModeloEditApplySubmissionV1.from_submission(
        ModeloEditSubmissionV1(baseline=baseline, mutation_family=ModeloEditMutationFamily.CALCULATE)
    ).baseline

    assert wire.baseline_id == baseline.baseline_id
    assert wire.modelo == str(baseline.modelo)
    assert wire.period_filing_year == baseline.period.filing_year
    assert wire.period_code == baseline.period.code
    assert wire.permitted_surface == baseline.permitted_surface
    assert wire.permitted_surface, "an empty permitted surface would make the comparison vacuous"
    assert wire.issued_at == baseline.issued_at
    assert wire.expires_at == baseline.expires_at


def test_a_detail_row_submission_refuses_rather_than_guessing_its_components() -> None:
    """The domain address carries only the joined key; splitting it would guess.

    Refusing is the honest answer. A split would reconstruct the identity
    components correctly for most rows and wrongly for exactly the rows whose
    own identifier contains the separator -- a defect that would surface as a
    misaddressed edit on a real record, not as an error.
    """
    baseline = _baseline()
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        detail_row_intents=(
            ModeloDetailRowEditIntentV1(
                address=ModeloEditDetailRowAddressV1(detail_row_kind="perceptor", natural_key="A|B"),
                kind=ModeloEditDetailRowIntentKind.DELETE_ROW,
            ),
        ),
    )

    with pytest.raises(ValueError, match="identity components"):
        ModeloEditApplySubmissionV1.from_submission(submission)
