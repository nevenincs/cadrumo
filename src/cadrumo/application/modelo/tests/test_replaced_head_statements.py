"""An explicit calculation names every statement of the replaced head it did not carry, and only those."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.identifiers import canonical_decimal_string
from ....domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer, ValueAttestation
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ..caller_context import CalculationCallerContext, caller_context_of
from ..printed_boxes import snapshot_printed_boxes
from ..replaced_head_statements import unused_head_statements
from ..work_calculation_contracts import ModeloHeadStatementKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000ac")
#: The previous year's net income from the economic activity, the carry a Modelo 130 reads from the earlier Modelo 100.
_PRIOR_NET_INCOME = "irpf.previous_year_economic_activity_net_income"
#: Boxes of the Modelo 130 the filer fills.
_KEPT_BOX = "16"
_DROPPED_BOX = "18"
_CLEARED_BOX = "06"


def _amount(text: str) -> str:
    return canonical_decimal_string(Decimal(text))


def _m130_unit(operation: PinnedAuthorityOperation) -> WorkUnit:
    year = filing_year_envelope().horizon
    period = Period.from_year_and_code(year, "1T")
    revision_id = operation.snapshot(
        "130", filing_year=year, period="1T", grade=RegistryAuthorityGrade.CALCULATION
    ).revision.id
    instant = datetime(year, 3, 10, 12, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE), modelo="130", filing_year=year, period=period, revision_id=revision_id
        ),
        bucket_id=str(_PROFILE),
        modelo="130",
        filing_year=year,
        period=period,
        revision_id=revision_id,
        name="First-quarter instalment",
        created_at=instant,
        updated_at=instant,
        state=WorkUnitState.BORRADOR,
    )


def _context(layer: CalculationOperatorLayer | None, *, cleared: tuple[str, ...] = ()) -> CalculationCallerContext:
    empty = caller_context_of(None)
    return CalculationCallerContext(
        operator_layer=layer,
        cleared_casilla_ids=cleared,
        detail_rows=empty.detail_rows,
        filing_instance_evidence=empty.filing_instance_evidence,
        m210_official_tipo_renta_code=None,
        m210_gross_income_source_mode=None,
        borrador_snapshot_id=None,
    )


def test_only_what_the_new_head_does_not_hold_unchanged_is_named(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unit = _m130_unit(authority_operation)
    prior_year = unit.filing_year - 1
    head = _context(
        CalculationOperatorLayer(
            decimal_casilla_inputs={_KEPT_BOX: _amount("150.00"), _DROPPED_BOX: _amount("10.00")},
            binding_overrides={_PRIOR_NET_INCOME: _amount("8000.00")},
            value_attestations={
                _PRIOR_NET_INCOME: ValueAttestation(
                    source_modelo="100", source_filing_year=prior_year, source_period="0A"
                )
            },
        ),
        cleared=(_CLEARED_BOX,),
    )
    # The request typed box 16 again with the same value and gave the carry as a plain value.
    new = _context(
        CalculationOperatorLayer(
            decimal_casilla_inputs={_KEPT_BOX: _amount("150.00")},
            binding_overrides={_PRIOR_NET_INCOME: _amount("8000.00")},
        )
    )

    statements = unused_head_statements(
        head, new, work_unit=unit, operation=authority_operation, language=OutputLanguage.EN
    )

    assert [(row.kind, row.subject, row.value) for row in statements] == [
        (ModeloHeadStatementKind.CASILLA_VALUE, _DROPPED_BOX, _amount("10.00")),
        (ModeloHeadStatementKind.VALUE_ATTESTATION, _PRIOR_NET_INCOME, _amount("8000.00")),
        (ModeloHeadStatementKind.CLEARED_CASILLA, _CLEARED_BOX, None),
    ]
    boxes = snapshot_printed_boxes(
        authority_operation,
        authority_operation.snapshot(
            "130", filing_year=unit.filing_year, period="1T", grade=RegistryAuthorityGrade.CALCULATION
        ),
    )
    dropped, attested, cleared = statements
    assert dropped.box == boxes.number(_DROPPED_BOX)
    unit_snapshot = authority_operation.snapshot(
        "130", filing_year=unit.filing_year, period="1T", grade=RegistryAuthorityGrade.CALCULATION
    )
    (dropped_casilla,) = [casilla for casilla in unit_snapshot.revision.casillas if casilla.id == _DROPPED_BOX]
    assert dropped.label == dropped_casilla.get_label("en")
    assert dropped.words == tr("application.modelo.replaced_head.statement.casilla_value", locale="en")
    assert attested.words == tr("application.modelo.replaced_head.statement.value_attestation", locale="en")
    assert cleared.words == tr("application.modelo.replaced_head.statement.cleared_casilla", locale="en")


def test_a_head_with_an_unknown_operator_layer_names_only_what_it_recorded(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unit = _m130_unit(authority_operation)

    statements = unused_head_statements(
        _context(None, cleared=(_CLEARED_BOX,)),
        _context(CalculationOperatorLayer()),
        work_unit=unit,
        operation=authority_operation,
        language=OutputLanguage.EN,
    )

    assert [(row.kind, row.subject) for row in statements] == [(ModeloHeadStatementKind.CLEARED_CASILLA, _CLEARED_BOX)]


def test_a_new_head_that_holds_every_statement_names_none(authority_operation: PinnedAuthorityOperation) -> None:
    unit = _m130_unit(authority_operation)
    layer = CalculationOperatorLayer(decimal_casilla_inputs={_KEPT_BOX: _amount("150.00")})

    assert (
        unused_head_statements(
            _context(layer), _context(layer), work_unit=unit, operation=authority_operation, language=OutputLanguage.EN
        )
        == ()
    )
