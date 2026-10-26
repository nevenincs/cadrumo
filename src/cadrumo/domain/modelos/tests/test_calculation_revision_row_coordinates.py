"""A calculation revision's repeating-row channels refuse a repeated coordinate."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.aggregation import BindingSourceKind
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ...calculations.row_source_identity import RowSourceIdentity
from ..calculation_revision import CalculationRevision, CalculationRevisionState, derive_calculation_revision_id
from ..calculation_revision_identity import canonical_row_binding_values
from ..errors import ModeloValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_SECURE = {"secure_calculation_revision": True}
_BINDING = "modelo-190-perceptor-row-nif"


def _identity(row_identity: str) -> RowSourceIdentity:
    return RowSourceIdentity(
        source_kind=BindingSourceKind.WITHHOLDING,
        source_row_identity=row_identity,
        fingerprint="a" * 64,
    )


def _secure_payload() -> dict[str, object]:
    created = datetime(2026, 8, 23, tzinfo=UTC)
    row_binding_values = {_BINDING: {"1": "10.00", "2": "20.00"}}
    row_source_identities = {(_BINDING, 1): _identity("row-1"), (_BINDING, 2): _identity("row-2")}
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values=row_binding_values,
            row_source_identities=row_source_identities,
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id="a" * 64,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id="2026-y-siguientes",
            modelo_year=2026,
            period="1T",
        ),
        state=CalculationRevisionState.BORRADOR,
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        filing_instance_evidence=None,
        source_provenance=(),
        created_at=created,
        updated_at=created,
    )
    return STR_KEYED_MAPPING_ADAPTER.validate_python(revision.model_dump(mode="python", context=_SECURE))


def test_secure_wire_form_with_distinct_coordinates_rehydrates_in_coordinate_order() -> None:
    payload = _secure_payload()
    identities = payload["row_source_identities"]
    assert isinstance(identities, list)
    payload["row_source_identities"] = list(reversed(identities))

    rehydrated = CalculationRevision.model_validate(payload, context=_SECURE)

    assert tuple(rehydrated.row_source_identities) == ((_BINDING, 1), (_BINDING, 2))
    assert rehydrated.row_source_identities[(_BINDING, 2)].source_row_identity == "row-2"


def test_secure_wire_form_refuses_two_source_identities_at_one_coordinate() -> None:
    payload = _secure_payload()
    identities = payload["row_source_identities"]
    assert isinstance(identities, list)
    first, _second = identities
    rival = {**first, "source_row_identity": "row-rival"}
    payload["row_source_identities"] = [first, rival]

    with pytest.raises(ValidationError, match="row source identities contain a duplicate coordinate"):
        CalculationRevision.model_validate(payload, context=_SECURE)


@pytest.mark.parametrize(
    ("field", "row", "message"),
    [
        (
            "row_casilla_values",
            {"casilla_id": "01", "row_index": 1, "value": "1.00"},
            "row casilla values contain a duplicate coordinate",
        ),
        (
            "row_casilla_provenance",
            {
                "casilla_id": "01",
                "row_index": 1,
                "source_binding_id": _BINDING,
                "source_row_index": 1,
                "source_identity": _identity("row-1").model_dump(mode="json"),
                "materialization_rule_id": _BINDING,
                "materialization_rule_version": "2026-y-siguientes",
            },
            "row casilla provenance contains a duplicate coordinate",
        ),
    ],
)
def test_secure_wire_form_refuses_a_repeated_row_casilla_coordinate(
    field: str,
    row: dict[str, object],
    message: str,
) -> None:
    payload = _secure_payload()
    payload[field] = [row, dict(row)]

    with pytest.raises(ValidationError, match=message):
        CalculationRevision.model_validate(payload, context=_SECURE)


def test_row_binding_values_refuse_two_spellings_of_one_row_index() -> None:
    with pytest.raises(ModeloValidationError, match="contains duplicate row '1'"):
        canonical_row_binding_values({_BINDING: {"1": "10.00", 1: "11.00"}}, surface="row_binding_values")


def test_row_binding_values_keep_distinct_rows_in_numeric_order() -> None:
    canonical = canonical_row_binding_values({_BINDING: {"10": "3", 2: "2", "1": "1"}}, surface="row_binding_values")

    assert canonical == {_BINDING: {"1": "1", "2": "2", "10": "3"}}
    assert list(canonical[_BINDING]) == ["1", "2", "10"]
