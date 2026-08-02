"""Real-behaviour roundtrip tests for modelo CLI payload schemas.

``CalculationRevisionPayload.input_values_by_casilla_id`` was typed as
``dict[str, object]`` while the domain source (``CalculationRevision``)
and the application constructor both produce ``dict[CasillaId, str]``
(canonical casilla ids with canonical Decimal/string values). These
tests pin the corrected ``dict[CasillaId, str]`` contract at the CLI wire boundary for
``CalculationRevisionPayload``, ``WorkCalculateResult``, and
``WorkRevisionResult``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry import (
    CasillaId,
    CasillaObservation,
    RelationId,
    validated_casilla_id,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    derive_calculation_revision_id,
)
from .._config._google_payloads import GoogleSyncCalcComputeCasillaPayload
from .._modelo_payloads import (
    CalculationRevisionPayload,
    CasillaObservationPayload,
    DeltaRowPayload,
    FindingPayload,
    ObservationPayload,
    WorkCalculateResult,
    WorkObservationsResult,
    WorkRevisionResult,
)
from .._modelo_rendering import calculation_revision_payload
from .._modelo_revision_payload_parts import DetailRowPayload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REVISION_ID = "a" * 64
_WORK_UNIT_ID = "b" * 64
_NOW = "2025-01-01T00:00:00+00:00"
_REVISION_TIMESTAMP = datetime(2025, 1, 1, tzinfo=UTC)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


_PAYLOAD_CASILLA: CasillaId = _casilla_id("001")
_INPUT_EJERCICIO_CASILLA: CasillaId = _casilla_id("ejercicio")
_INPUT_PERIODO_CASILLA: CasillaId = _casilla_id("periodo")
_NON_CANONICAL_KEY = "bad key"
_RELATION_OVERRIDE: RelationId = "renta-2024-rel-130-pagos-fraccionados"


def _base_revision_fields() -> dict[str, Any]:
    return dict(
        calculation_revision_id=_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        state="BORRADOR",
        casilla_values={_PAYLOAD_CASILLA: "1234.56"},
        observations=(
            ObservationPayload(
                casilla_id=_PAYLOAD_CASILLA,
                value="1234.56",
                formula_id="f1",
                legal_refs=("ley-58-2003:art-120",),
                operand_refs=(_PAYLOAD_CASILLA, "iva.rate"),
                operand_casilla_refs=(_PAYLOAD_CASILLA,),
                source_refs=("libro-1",),
            ),
        ),
        detail_rows=(
            DetailRowPayload(
                index=1,
                row_type="operador",
                fields={
                    "codigo_pais": "DE",
                    "nif_comunitario": "DE123456789",
                    "razon_social": "DE Auto GmbH",
                    "clave_operacion": "E",
                    "importe": "1500.00",
                },
            ),
            DetailRowPayload(
                index=2,
                row_type="operador",
                fields={
                    "codigo_pais": "FR",
                    "nif_comunitario": "FR12345678901",
                    "razon_social": "Equipement Garage SARL",
                    "clave_operacion": "E",
                    "importe": "900.00",
                },
            ),
        ),
        binding_overrides={"src1": "ledger-abc"},
        relation_overrides={_RELATION_OVERRIDE: "725.75"},
        input_values_by_casilla_id={_INPUT_EJERCICIO_CASILLA: "2024", _INPUT_PERIODO_CASILLA: "1T"},
        created_at=_NOW,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# CalculationRevisionPayload
# ---------------------------------------------------------------------------


def test_calculation_revision_payload_input_values_by_casilla_id_roundtrips() -> None:
    """input_values_by_casilla_id dict[CasillaId, str] survives model_dump_json / model_validate_json."""
    original = CalculationRevisionPayload(**_base_revision_fields())
    json_str = original.model_dump_json()
    restored = CalculationRevisionPayload.model_validate_json(json_str)

    assert restored == original
    assert restored.input_values_by_casilla_id == {_INPUT_EJERCICIO_CASILLA: "2024", _INPUT_PERIODO_CASILLA: "1T"}
    assert restored.relation_overrides == {_RELATION_OVERRIDE: "725.75"}
    assert restored.detail_rows[0].fields["nif_comunitario"] == "DE123456789"
    assert restored.detail_rows[1].fields["importe"] == "900.00"


def test_calculation_revision_payload_input_values_by_casilla_id_rejects_non_string_values() -> None:
    """Strict pydantic must reject a non-string value in input_values_by_casilla_id."""
    fields = _base_revision_fields()
    # Inject an integer value - must not pass dict[CasillaId, str] validation.
    fields["input_values_by_casilla_id"] = {_INPUT_EJERCICIO_CASILLA: 2024}

    with pytest.raises(ValidationError):
        CalculationRevisionPayload(**fields)


def test_calculation_revision_payload_input_values_by_casilla_id_rejects_non_canonical_casilla_key() -> None:
    fields = _base_revision_fields()
    fields["input_values_by_casilla_id"] = {_NON_CANONICAL_KEY: "2024"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevisionPayload(**fields)


def test_calculation_revision_payload_casilla_values_rejects_non_canonical_casilla_key() -> None:
    fields = _base_revision_fields()
    fields["casilla_values"] = {_NON_CANONICAL_KEY: "1234.56"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevisionPayload(**fields)


def test_observation_payload_rejects_non_canonical_casilla_id() -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        ObservationPayload(
            casilla_id=_NON_CANONICAL_KEY,
            value="1234.56",
            legal_refs=("ley-58-2003:art-120",),
            source_refs=("libro-1",),
        )


def test_verification_finding_payload_preserves_the_domain_contract() -> None:
    finding = FindingPayload(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=_PAYLOAD_CASILLA,
        expectation_id="m130-rendimiento-neto-non-negative",
        message="Rendimiento neto cannot be negative.",
        next_action="Correct casilla 001 and rerun verification.",
        legal_refs=["ley-35-2006:art-28"],
        source_refs=["modelo-130-2025-instructions"],
    )

    assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.model_dump(mode="json")["kind"] == "blocking_rule"


def test_verification_finding_payload_rejects_ungrounded_or_malformed_rows() -> None:
    raw = {
        "kind": "blocking_rule",
        "severity": "blocking",
        "message": "Rendimiento neto cannot be negative.",
        "legal_refs": ["ley-35-2006:art-28"],
        "source_refs": ["modelo-130-2025-instructions"],
    }

    for field, value in (
        ("kind", "bogus"),
        ("severity", "bogus"),
        ("message", ""),
        ("legal_refs", []),
        ("expectation_id", "bad expectation"),
    ):
        with pytest.raises(ValidationError):
            FindingPayload.model_validate({**raw, field: value})


def test_casilla_provenance_payloads_share_formula_identifier_validation() -> None:
    """Every CLI casilla provenance surface accepts and rejects the same FormulaId grammar."""
    observation = CasillaObservationPayload(
        casilla_id=_PAYLOAD_CASILLA,
        value="1234.56",
        formula_id="m130-test-formula",
        legal_refs=["ley-58-2003:art-120"],
        source_refs=["libro-1"],
    )
    delta = DeltaRowPayload(
        casilla_id=_PAYLOAD_CASILLA,
        label="Rendimiento neto",
        section="Liquidación",
        year_a_value="100.00",
        year_b_value="1234.56",
        delta="1134.56",
        pct_change="1134.56",
        formula_id="m130-test-formula",
        legal_refs=["ley-58-2003:art-120"],
        source_refs=["libro-1"],
    )
    google = GoogleSyncCalcComputeCasillaPayload(
        casilla_id=_PAYLOAD_CASILLA,
        value="1234.56",
        formula_id="m130-test-formula",
        legal_refs=["ley-58-2003:art-120"],
        source_refs=["libro-1"],
    )

    assert observation.formula_id == delta.formula_id == google.formula_id == "m130-test-formula"

    for payload_type, payload in (
        (CasillaObservationPayload, observation.model_dump()),
        (DeltaRowPayload, delta.model_dump()),
        (GoogleSyncCalcComputeCasillaPayload, google.model_dump()),
    ):
        payload["formula_id"] = "bad formula"
        with pytest.raises(ValidationError, match="String should match pattern"):
            payload_type.model_validate(payload)


def test_observation_payload_rejects_non_canonical_operand_casilla_ref() -> None:
    with pytest.raises(ValidationError, match="String should match pattern"):
        ObservationPayload(
            casilla_id=_PAYLOAD_CASILLA,
            value="1234.56",
            operand_refs=("iva.rate",),
            operand_casilla_refs=(_NON_CANONICAL_KEY,),
            legal_refs=("ley-58-2003:art-120",),
            source_refs=("libro-1",),
        )


def test_observation_payload_carries_formula_op_through_json_channel() -> None:
    """The typed ``op`` survives model_dump_json / model_validate_json.

    The draft-review inline trace (``op(refs) = op(values) = value``) is fully
    reconstructible from the JSON observation, so ``op`` must round-trip through
    the strict envelope alongside the operand lineage.
    """

    original = ObservationPayload(
        casilla_id=_PAYLOAD_CASILLA,
        value="1234.56",
        formula_id="f1",
        op="subtract",
        operand_refs=(_PAYLOAD_CASILLA, "iva.rate"),
        operand_casilla_refs=(_PAYLOAD_CASILLA,),
        operand_values=("2000.00", "765.44"),
        legal_refs=("ley-58-2003:art-120",),
        source_refs=("libro-1",),
    )
    restored = ObservationPayload.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.op == "subtract"


def test_observation_payload_rejects_untraced_operand_casilla_ref() -> None:
    with pytest.raises(ValidationError, match="declares operand_casilla_refs"):
        ObservationPayload(
            casilla_id=_PAYLOAD_CASILLA,
            value="1234.56",
            operand_refs=("iva.rate",),
            operand_casilla_refs=(_PAYLOAD_CASILLA,),
            legal_refs=("ley-58-2003:art-120",),
            source_refs=("libro-1",),
        )


def test_calculation_revision_payload_input_values_by_casilla_id_json_channel_rejects_non_string() -> None:
    """Non-string value injected via raw JSON string must also be rejected."""
    original = CalculationRevisionPayload(**_base_revision_fields())
    raw = json.loads(original.model_dump_json())
    raw["input_values_by_casilla_id"] = {_INPUT_EJERCICIO_CASILLA: 2024}

    with pytest.raises(ValidationError):
        CalculationRevisionPayload.model_validate(raw)


def test_calculation_revision_payload_json_channel_rejects_non_canonical_casilla_key() -> None:
    original = CalculationRevisionPayload(**_base_revision_fields())
    raw = json.loads(original.model_dump_json())
    raw["casilla_values"] = {_NON_CANONICAL_KEY: "1234.56"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevisionPayload.model_validate_json(json.dumps(raw))


# ---------------------------------------------------------------------------
# WorkCalculateResult — sibling carrying the same field
# ---------------------------------------------------------------------------


def test_work_calculate_result_input_values_by_casilla_id_roundtrips() -> None:
    """WorkCalculateResult.input_values_by_casilla_id dict[CasillaId, str] roundtrips through JSON."""
    payload = WorkCalculateResult(
        saved=True,
        saved_confirmation="Saved revision a" * 2,
        **_base_revision_fields(),
    )
    restored = WorkCalculateResult.model_validate_json(payload.model_dump_json())

    assert restored == payload
    assert isinstance(restored.input_values_by_casilla_id, dict)
    assert all(isinstance(v, str) for v in restored.input_values_by_casilla_id.values())
    assert restored.detail_rows[0].fields["razon_social"] == "DE Auto GmbH"


def test_work_calculate_result_input_values_by_casilla_id_rejects_non_string_values() -> None:
    fields = _base_revision_fields()
    fields["input_values_by_casilla_id"] = {_INPUT_EJERCICIO_CASILLA: 2024}

    with pytest.raises(ValidationError):
        WorkCalculateResult(
            saved=True,
            saved_confirmation="Saved",
            **fields,
        )


def test_work_calculate_result_input_values_by_casilla_id_rejects_non_canonical_casilla_key() -> None:
    fields = _base_revision_fields()
    fields["input_values_by_casilla_id"] = {_NON_CANONICAL_KEY: "2024"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        WorkCalculateResult(
            saved=True,
            saved_confirmation="Saved",
            **fields,
        )


# ---------------------------------------------------------------------------
# WorkRevisionResult — sibling carrying the same field
# ---------------------------------------------------------------------------


def test_work_revision_result_input_values_by_casilla_id_roundtrips() -> None:
    """WorkRevisionResult.input_values_by_casilla_id dict[CasillaId, str] roundtrips through JSON."""
    payload = WorkRevisionResult(**_base_revision_fields())
    restored = WorkRevisionResult.model_validate_json(payload.model_dump_json())

    assert restored == payload
    assert isinstance(restored.input_values_by_casilla_id, dict)
    assert all(isinstance(v, str) for v in restored.input_values_by_casilla_id.values())
    assert {row.fields["nif_comunitario"] for row in restored.detail_rows} == {"DE123456789", "FR12345678901"}


def test_work_revision_result_input_values_by_casilla_id_rejects_non_string_values() -> None:
    fields = _base_revision_fields()
    fields["input_values_by_casilla_id"] = {_INPUT_EJERCICIO_CASILLA: 2024}

    with pytest.raises(ValidationError):
        WorkRevisionResult(**fields)


def test_work_revision_result_casilla_values_rejects_non_canonical_casilla_key() -> None:
    fields = _base_revision_fields()
    fields["casilla_values"] = {_NON_CANONICAL_KEY: "1234.56"}

    with pytest.raises(ValidationError, match="String should match pattern"):
        WorkRevisionResult(**fields)


def test_work_observations_result_roundtrips_observation_contract() -> None:
    """The observations-only command preserves the same strict observation payload contract."""
    fields = _base_revision_fields()
    payload = WorkObservationsResult(
        calculation_revision_id=fields["calculation_revision_id"],
        work_unit_id=fields["work_unit_id"],
        state=fields["state"],
        observation_count=len(fields["observations"]),
        observations=fields["observations"],
    )
    restored = WorkObservationsResult.model_validate_json(payload.model_dump_json())

    assert restored == payload
    assert restored.observation_count == 1
    assert restored.observations[0].legal_refs == ("ley-58-2003:art-120",)


def test_calculation_revision_projection_preserves_absent_by_design_marker() -> None:
    """An intentional zero must stay distinguishable from a value-bearing zero at the CLI edge.

    :class:`CasillaObservation` persists ``absent_by_design`` so a casilla whose
    binding produced no source anchor for the period (Modelo 130 casilla 15 at
    1T) is not read as a declared zero. The projection dropped the marker, so
    the operator-facing payload could not tell the two apart.
    """
    absent = CasillaObservation(
        casilla_id=_PAYLOAD_CASILLA,
        value=Decimal("0"),
        legal_refs=("ley-58-2003:art-120",),
        source_refs=("libro-1",),
        absent_by_design=True,
    )
    declared_zero = CasillaObservation(
        casilla_id=_INPUT_EJERCICIO_CASILLA,
        value=Decimal("0"),
        legal_refs=("ley-58-2003:art-120",),
        source_refs=("libro-1",),
    )
    casilla_values = {_PAYLOAD_CASILLA: Decimal("0"), _INPUT_EJERCICIO_CASILLA: Decimal("0")}
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=_WORK_UNIT_ID,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=casilla_values,
        ),
        work_unit_id=_WORK_UNIT_ID,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=(absent, declared_zero),
        created_at=_REVISION_TIMESTAMP,
        updated_at=_REVISION_TIMESTAMP,
    )

    payload = calculation_revision_payload(revision)
    by_casilla = {row.casilla_id: row for row in payload.observations}

    assert by_casilla[_PAYLOAD_CASILLA].absent_by_design is True
    assert by_casilla[_INPUT_EJERCICIO_CASILLA].absent_by_design is False

    restored = CalculationRevisionPayload.model_validate_json(payload.model_dump_json())
    restored_by_casilla = {row.casilla_id: row for row in restored.observations}
    assert restored_by_casilla[_PAYLOAD_CASILLA].absent_by_design is True
    assert restored_by_casilla[_INPUT_EJERCICIO_CASILLA].absent_by_design is False
