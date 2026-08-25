"""Strict and encrypted persistence proofs for the reviewed censo operand."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.operations.secure_references import (
    OPERATION_SECURE_REFERENCE_NAMESPACE,
    operation_secure_reference_repository,
)
from cadrumo.application.operations.models import OperationRequest

from ....adapters.persistence.storage import RepositoryError
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.aeat_literal_fixtures import aeat_url
from ....tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from cadrumo.application.user_profile.censal_observation import CensalObservation, CensalObservationAddress, CensalObservationIdentity
from cadrumo.application.user_profile.censal_operation import CENSAL_OPERATION_DEFINITION, CensalFieldIntent, CensalOperationExecutor, CensalOperationRequest, CensalProfileBaseline, CensalReviewedFieldIntent, CensalReviewedOperand
from cadrumo.application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 12, tzinfo=UTC)


def _domicilio(*, notification: bool) -> CensalObservationAddress:
    return CensalObservationAddress(
        tipo_via="CALLE",
        nombre_via="Mayor",
        tipo_numero="NUM",
        numero_casa="7",
        calificacion_numero="BIS",
        bloque="B",
        portal="2",
        escalera="A",
        planta="3",
        puerta="D",
        complemento="Edificio Norte",
        localidad="Madrid",
        referencia_catastral="1234567VK4713C0001AB",
        indicador_referencia_catastral="Inmueble con referencia catastral",
        codigo_postal="28013",
        municipio="079 - MADRID",
        provincia="MADRID",
        destinatario="Representante Fiscal" if notification else None,
        en_calidad_de="Representante" if notification else None,
    )


def _operand() -> CensalReviewedOperand:
    observation = CensalObservation(
        identity=CensalObservationIdentity(
            nif="12345678Z",
            apellidos_y_nombre="PÉREZ GARCÍA, ANA",
            administracion_domicilio_fiscal="28600 - MADRID",
            lugar_nacimiento="MADRID Pais: ESPAÑA",
            fecha_nacimiento=date(1985, 4, 3),
            pasaporte="PA123456",
            sexo="Mujer",
            nacionalidad="ESPAÑOLA",
            estado_civil="Casada",
            obligado_notificaciones_electronicas=True,
            suscrito_voluntariamente_notificaciones_electronicas=False,
        ),
        domicilio_fiscal=_domicilio(notification=False),
        domicilio_notificacion=_domicilio(notification=True),
        captured_at=_NOW,
        source_url=aeat_url("sede", "/censo/consulta"),
    )
    record = UserProfileRecord(
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z", source="manual_cli"),),
        setup_state=ProfileSetupState.COMPLETE,
        record_revision=2,
        previous_record_digest="a" * 64,
        created_at=_NOW,
        updated_at=_NOW,
    )
    return CensalReviewedOperand(
        observation=observation,
        baseline=CensalProfileBaseline.from_record(record),
        field_intents=(
            CensalReviewedFieldIntent(
                path="contact.fiscal_address",
                intent=CensalFieldIntent.ADOPT,
            ),
            CensalReviewedFieldIntent(
                path="contact.postcode",
                intent=CensalFieldIntent.PRESERVE,
            ),
            CensalReviewedFieldIntent(
                path="contact.fiscal_address_cadastral_reference",
                intent=CensalFieldIntent.ADOPT,
            ),
        ),
    )


def test_reviewed_operand_strict_serialization_round_trip_and_tamper_refusal() -> None:
    operand = _operand()
    assert CensalReviewedOperand.model_validate_json(operand.model_dump_json(), strict=True) == operand

    changed = operand.model_copy(
        update={
            "field_intents": (
                operand.field_intents[0].model_copy(update={"intent": CensalFieldIntent.PRESERVE}),
                operand.field_intents[1],
                operand.field_intents[2],
            )
        }
    )
    with pytest.raises(ValidationError, match="proposed-effect digest"):
        CensalReviewedOperand.model_validate_json(changed.model_dump_json(), strict=True)

    complete = [item.model_dump(mode="json") for item in operand.field_intents]
    invalid_intent_sets = (
        [],
        complete[:-1],
        [complete[0], complete[0], complete[2]],
        list(reversed(complete)),
        [*complete, {"path": "contact.unknown", "intent": "preserve"}],
    )
    for invalid in invalid_intent_sets:
        payload = operand.model_dump(mode="json")
        payload["field_intents"] = invalid
        payload["proposed_effect_digest"] = ""
        with pytest.raises(ValidationError, match="canonical adoptable"):
            CensalReviewedOperand.model_validate_json(json.dumps(payload), strict=True)
    assert tuple(item.path for item in operand.field_intents) == CENSAL_ADOPTABLE_PATHS


def test_reviewed_operand_real_secure_reference_round_trip_and_digest_corruption(tmp_path: Path) -> None:
    operand = _operand()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        objects = profile.repository
        store = operation_secure_reference_repository(objects=objects)
        reference = asyncio.run(store.put(operand, written_at=_NOW))
        assert asyncio.run(store.resolve(reference, CensalReviewedOperand)) == operand
        at_rest = read_db_at_rest_bytes(profile.paths.database_file)
        assert b"12345678Z" not in at_rest
        assert "PÉREZ GARCÍA".encode() not in at_rest

        substituted = operand.model_copy(update={"field_intents": tuple(reversed(operand.field_intents))})
        objects.save(
            namespace=OPERATION_SECURE_REFERENCE_NAMESPACE.namespace,
            object_key=reference,
            classification=OPERATION_SECURE_REFERENCE_NAMESPACE.sensitivity,
            schema_version=OPERATION_SECURE_REFERENCE_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=substituted.model_dump_json().encode(),
        )
        with pytest.raises(RepositoryError, match="digest mismatch"):
            asyncio.run(store.resolve(reference, CensalReviewedOperand))


def test_censal_operation_definition_binds_complete_resumable_request() -> None:
    operand = _operand()
    payload = CensalOperationRequest(
        baseline=operand.baseline,
        field_intents=operand.field_intents,
    )
    request = OperationRequest(
        definition_id=CENSAL_OPERATION_DEFINITION.definition_id,
        subject_ref=str(operand.baseline.profile_id),
        payload=payload,
    )

    assert request.payload == payload
    assert CENSAL_OPERATION_DEFINITION.request_type is CensalOperationRequest
    assert CENSAL_OPERATION_DEFINITION.executor_factory.executor_type is CensalOperationExecutor
    assert CENSAL_OPERATION_DEFINITION.executor_factory.create().__class__ is CensalOperationExecutor

    with pytest.raises(ValidationError, match="every adoptable path"):
        CensalOperationRequest(
            baseline=operand.baseline,
            field_intents=operand.field_intents[:-1],
        )
