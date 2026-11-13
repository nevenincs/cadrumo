"""The packed rental fields served and written as typed parts, against a real encrypted profile.

``usos``, ``valores_catastrales``, ``mejoras`` and ``inquilinos`` stay one stored text each. The
profile view serves the same facts as parts, and the registered row operations accept the parts
in place of the text; both directions go through the one grammar, so every case here reads the
stored text, the served parts and the operation outcome of the production code.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.operations.tests.supervision_support import run_to_settlement
from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.operations.models import OperationRequest
from ...application.operations.persistence.journal import OperationPersistedSnapshot
from ...application.operations.registry import OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...application.user_profile.custody_ports import profile_custody_secure_object_repository
from ...application.user_profile.login_session import authenticate_profile_for_invocation
from ...application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowPartsValue,
    ProfileRepeatableRowUpdateOperationRequest,
    ProfileRepeatableRowValue,
)
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.registration import register_profile_with_credentials
from ...application.user_profile.row_parts import (
    INVALID_LOCALE_KEY,
    NOT_PACKED,
    ProfileFieldInquilinoPart,
    ProfileFieldPartsSpec,
    ProfileFieldUsoPart,
    ProfileRowInquilinoValues,
    ProfileRowMejoraValues,
    ProfileRowPartInput,
    ProfileRowUsoValues,
    ProfileRowValorCatastralValues,
    RowPartKind,
    compound_part_kind,
    field_parts,
    packed_text_of_parts,
)
from ...application.user_profile.section_rows import add_profile_repeatable_section_row
from ...application.user_profile.view_operation import (
    ProfileViewFieldItem,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from ...application.user_profile.view_reader import read_profile_view_page
from ...core.config import override_settings
from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION, rows_from_facts
from ...domain.user_profile.errors import ProfileSchemaValidationError
from ...domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

CATASTRAL = "9872023VH5797S0001WX"
TENANT = "12345678Z"
YEAR = filing_year_envelope().horizon


def _on(years_back: int, month: int, day: int) -> str:
    return date(YEAR - years_back, month, day).isoformat()


USE_FROM, USE_TO, USE_LATER = _on(8, 1, 1), _on(7, 12, 31), _on(6, 1, 1)
IBI_FIRST, IBI_SECOND, VIGOR = YEAR - 3, YEAR - 2, YEAR - 14
MEJORA_FIRST, MEJORA_SECOND = _on(6, 5, 1), _on(4, 3, 15)
USOS = f"vivienda_habitual:{USE_FROM}:{USE_TO};disposicion_propietario:{USE_LATER}:"
VALORES = f"{IBI_FIRST}:80000.00:48000.00:{VIGOR};{IBI_SECOND}:82000.50:49000.00"
MEJORAS = f"{MEJORA_FIRST}:1500.00;{MEJORA_SECOND}:320.25"
INQUILINOS = f"{TENANT}:18_35:no;X1234567L:otra:si"


@dataclass
class _World:
    root: Path
    profile_id: UUID
    operation: PinnedAuthorityOperation
    settled: int = field(default=0)

    def facts(self) -> dict[str, object]:
        record = ProfileRecordRepository.for_current_session(
            str(self.profile_id), profile_decode_context=self.operation.profile_decode_context()
        ).load(str(self.profile_id))
        return {fact.path: fact.value for fact in record.facts if fact.value is not None}

    def stored(self, section: str, row: int) -> dict[str, str]:
        return rows_from_facts(section, self.facts())[row]

    def add(self, section: str, values: dict[str, str]) -> int:
        decode = self.operation.profile_decode_context()
        return add_profile_repeatable_section_row(
            profile_id=str(self.profile_id),
            section_key=section,
            values=values,
            schema=decode.schema,
            profile_decode_context=decode,
            authority=self.operation,
        ).row_index

    def view_field(self, path: str, language: OutputLanguage = OutputLanguage.ES) -> ProfileViewFieldItem:
        """Read the profile overview page by page and return the field served at ``path``."""
        cursor, pin = 0, {}
        while True:
            page = read_profile_view_page(
                ProfileViewOperationRequest.model_validate(
                    {
                        "profile_id": self.profile_id,
                        "page_kind": ProfileViewPageKind.OVERVIEW,
                        "cursor": cursor,
                        "output_language": language,
                        **pin,
                    }
                ),
                authority_operation=self.operation,
            )
            for item in page.items:
                if isinstance(item, ProfileViewFieldItem) and item.field.path == path:
                    return item
            if page.next_cursor is None:
                raise AssertionError(f"{path} is not served")
            cursor = page.next_cursor
            pin = {"expected_revision": page.record_revision, "expected_content_digest": page.content_digest}

    def request_context(self) -> tuple[str, int, str]:
        record = ProfileRecordRepository.for_current_session(
            str(self.profile_id), profile_decode_context=self.operation.profile_decode_context()
        ).load(str(self.profile_id))
        return str(self.profile_id), record.record_revision, record.content_digest

    def settle(
        self,
        definition_id: str,
        payload: ProfileRepeatableRowMutationOperationRequest | ProfileRepeatableRowUpdateOperationRequest,
    ) -> OperationPersistedSnapshot:
        with profile_custody_secure_object_repository(profile_id=self.profile_id, dek=b"", root=self.root) as objects:
            assert isinstance(objects, SecureObjectRepository)
            journal = OperationJournalRepository(storage_root=self.root)
            supervisor = OperationSupervisor(
                authority_operation=self.operation,
                registry=OperationRegistry(
                    definitions=USER_PROFILE_OPERATION_DEFINITIONS,
                    public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
                ),
                journal=journal,
                event_stream=journal,
                leases=OperationLeaseFilesystemRepository(storage_root=self.root),
                operands=operation_secure_reference_repository(objects=objects),
                owner_id="a" * 64,
                lease_token_factory=lambda: "b" * 64,
                clock=lambda: datetime.now(UTC),
                lease_duration=timedelta(minutes=6),
            )
            self.settled += 1
            operation_id = f"{self.settled:064x}"

            async def run() -> OperationPersistedSnapshot:
                created = await supervisor.submit(
                    OperationRequest(
                        definition_id=definition_id, subject_ref=f"profile:{self.profile_id}", payload=payload
                    ),
                    operation_id=operation_id,
                )
                return await run_to_settlement(supervisor, created)

            return asyncio.run(run())

    def add_through_operation(
        self,
        section: str,
        values: dict[str, str],
        parts: tuple[ProfileRepeatableRowPartsValue, ...] = (),
    ) -> OperationPersistedSnapshot:
        profile_id, revision, digest = self.request_context()
        return self.settle(
            PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
            ProfileRepeatableRowMutationOperationRequest(
                profile_id=UUID(profile_id),
                expected_revision=revision,
                expected_content_digest=digest,
                section_key=section,
                values=tuple(ProfileRepeatableRowValue(field_key=key, value=value) for key, value in values.items()),
                part_values=parts,
            ),
        )

    def update_through_operation(
        self,
        section: str,
        row: int,
        values: dict[str, str] | None = None,
        parts: tuple[ProfileRepeatableRowPartsValue, ...] = (),
    ) -> OperationPersistedSnapshot:
        profile_id, revision, digest = self.request_context()
        return self.settle(
            PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
            ProfileRepeatableRowUpdateOperationRequest(
                profile_id=UUID(profile_id),
                expected_revision=revision,
                expected_content_digest=digest,
                section_key=section,
                row_key=str(row),
                values=tuple(
                    ProfileRepeatableRowValue(field_key=key, value=value) for key, value in (values or {}).items()
                ),
                part_values=parts,
            ),
        )


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"row-parts-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path) as root,
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Row parts",
            passphrase=secret,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=outcome.label,
            passphrase_callback=secret.__str__,
            profile_decode_context=operation.profile_decode_context(),
        )
        register_minimal_profile(profile_id=outcome.profile_id)
        yield _World(root, UUID(outcome.profile_id), operation)


def _property(**packed: str) -> dict[str, str]:
    return {
        "situacion": "1",
        "referencia_catastral": CATASTRAL,
        "titularidad_regimen": "pleno_dominio",
        "titular": "primer_declarante",
        "porcentaje_propiedad": "100",
        "importe_adquisicion": "150000",
        **packed,
    }


def _lease(inmueble: int, **packed: str) -> dict[str, str]:
    return {"inmueble": str(inmueble), "fecha_contrato": _on(0, 1, 10), "fecha_inicio": _on(0, 2, 1), **packed}


def _outcome(settled: OperationPersistedSnapshot) -> tuple[object, ...]:
    """What an operation settled as, apart from its identity: the condition, the effect and the refusal sentence."""
    receipt = settled.terminal_receipt
    assert receipt is not None
    return (
        receipt.condition,
        receipt.effect,
        receipt.failure_error_code,
        receipt.error_detail_ref,
        receipt.refusal_detail_ref,
    )


def _parts(field_key: str, *parts: ProfileRowPartInput) -> tuple[ProfileRepeatableRowPartsValue, ...]:
    return (ProfileRepeatableRowPartsValue(field_key=field_key, parts=parts),)


def _served(
    world: _World, section: str, row: int, field_key: str
) -> tuple[ProfileViewFieldItem, ProfileFieldPartsSpec]:
    item = world.view_field(f"{section}.{row}.{field_key}")
    assert item.field.parts_spec is not None
    return item, item.field.parts_spec


def test_each_packed_field_is_served_as_parts_beside_its_unchanged_text(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property(usos=USOS, valores_catastrales=VALORES, mejoras=MEJORAS))
    lease = world.add(ARRENDAMIENTO_SECTION, _lease(prop, inquilinos=INQUILINOS))

    usos, usos_spec = _served(world, INMUEBLE_SECTION, prop, "usos")
    assert usos.field.value == USOS
    assert usos.field.parts == (
        ProfileFieldUsoPart(
            tipo="vivienda_habitual",
            desde=USE_FROM,
            hasta=USE_TO,
            tipo_words="Vivienda habitual",
            tipo_words_language=OutputLanguage.ES,
        ),
        ProfileFieldUsoPart(
            tipo="disposicion_propietario",
            desde=USE_LATER,
            hasta=None,
            tipo_words="A disposición del propietario",
            tipo_words_language=OutputLanguage.ES,
        ),
    )
    assert usos_spec.part_kind is RowPartKind.USO and not usos_spec.invalid and usos_spec.invalid_words is None
    assert [sub.key for sub in usos_spec.sub_fields] == ["tipo", "desde", "hasta"]
    assert [choice.value for choice in usos_spec.sub_fields[0].choices] == [
        "vivienda_habitual",
        "disposicion_propietario",
        "actividad_economica",
    ]
    assert all(sub.label and sub.help for sub in usos_spec.sub_fields)
    assert [sub.required for sub in usos_spec.sub_fields] == [True, True, False]

    valores, _ = _served(world, INMUEBLE_SECTION, prop, "valores_catastrales")
    assert valores.field.parts == (
        ProfileRowValorCatastralValues(year=IBI_FIRST, total="80000.00", construccion="48000.00", vigor=VIGOR),
        ProfileRowValorCatastralValues(year=IBI_SECOND, total="82000.50", construccion="49000.00", vigor=None),
    )
    mejoras, _ = _served(world, INMUEBLE_SECTION, prop, "mejoras")
    assert mejoras.field.parts == (
        ProfileRowMejoraValues(fecha=MEJORA_FIRST, importe="1500.00"),
        ProfileRowMejoraValues(fecha=MEJORA_SECOND, importe="320.25"),
    )
    inquilinos, inquilinos_spec = _served(world, ARRENDAMIENTO_SECTION, lease, "inquilinos")
    assert inquilinos.field.value == INQUILINOS
    tenants = [part for part in inquilinos.field.parts or () if isinstance(part, ProfileFieldInquilinoPart)]
    assert [(part.nif, part.franja_edad, part.extranjero) for part in tenants] == [
        (TENANT, "18_35", False),
        ("X1234567L", "otra", True),
    ]
    assert all(part.franja_edad_words for part in tenants)
    assert [choice.value for choice in inquilinos_spec.sub_fields[2].choices] == ["true", "false"]


@pytest.mark.parametrize(
    ("section", "field_key"),
    [
        (INMUEBLE_SECTION, "usos"),
        (INMUEBLE_SECTION, "valores_catastrales"),
        (INMUEBLE_SECTION, "mejoras"),
        (ARRENDAMIENTO_SECTION, "inquilinos"),
    ],
)
def test_the_served_parts_serialise_back_to_the_stored_text(world: _World, section: str, field_key: str) -> None:
    prop = world.add(INMUEBLE_SECTION, _property(usos=USOS, valores_catastrales=VALORES, mejoras=MEJORAS))
    row = prop if section == INMUEBLE_SECTION else world.add(ARRENDAMIENTO_SECTION, _lease(prop, inquilinos=INQUILINOS))
    stored = world.stored(section, row)[field_key]

    item, _ = _served(world, section, row, field_key)

    assert item.field.parts is not None and len(item.field.parts) > 0
    assert packed_text_of_parts(section, field_key, item.field.parts) == stored


def test_an_unstated_packed_field_serves_no_parts_and_an_unpacked_field_serves_none(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property())

    usos, spec = _served(world, INMUEBLE_SECTION, prop, "usos")
    assert usos.field.value is None and usos.field.parts == () and not spec.invalid

    direccion = world.view_field(f"{INMUEBLE_SECTION}.{prop}.situacion")
    assert direccion.field.parts is None and direccion.field.parts_spec is None
    assert field_parts(INMUEBLE_SECTION, "situacion", "1") is NOT_PACKED
    assert compound_part_kind(INMUEBLE_SECTION, "situacion") is None


def test_a_stored_value_that_does_not_parse_is_served_without_parts_and_marked_invalid(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property(usos=USOS))
    upsert_test_profile_facts(
        world.profile_id,
        [UserProfileFact(path=f"{INMUEBLE_SECTION}.{prop}.usos", value="vivienda_habitual:ayer:")],
        root=world.root,
    )

    item, spec = _served(world, INMUEBLE_SECTION, prop, "usos")

    assert item.field.value == "vivienda_habitual:ayer:"
    assert item.field.parts is None
    assert spec.invalid and spec.invalid_words == lookup_translation(INVALID_LOCALE_KEY, locale="es")
    assert spec.sub_fields


@pytest.mark.parametrize(
    ("language", "tipo_words"),
    [
        (OutputLanguage.EN, "Main home"),
        (OutputLanguage.CA, "Habitatge habitual"),
        (OutputLanguage.HU, "Állandó lakóhely"),
    ],
)
def test_the_words_of_every_token_follow_the_output_language(
    world: _World, language: OutputLanguage, tipo_words: str
) -> None:
    prop = world.add(INMUEBLE_SECTION, _property(usos=f"vivienda_habitual:{USE_FROM}:"))

    item = world.view_field(f"{INMUEBLE_SECTION}.{prop}.usos", language)

    assert item.field.parts is not None and len(item.field.parts) == 1
    part = item.field.parts[0]
    assert isinstance(part, ProfileFieldUsoPart)
    assert part.tipo_words == tipo_words and part.tipo_words_language is language
    assert item.field.parts_spec is not None and item.field.parts_spec.words_language is language


def test_parts_stated_on_an_edit_are_stored_as_the_canonical_text(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property())

    settled = world.update_through_operation(
        INMUEBLE_SECTION,
        prop,
        parts=(
            *_parts(
                "valores_catastrales",
                ProfileRowValorCatastralValues(year=IBI_SECOND, total="82000.5", construccion="49000", vigor=None),
                ProfileRowValorCatastralValues(year=IBI_FIRST, total="80000", construccion="48000.00", vigor=VIGOR),
            ),
            *_parts("mejoras", ProfileRowMejoraValues(fecha=MEJORA_SECOND, importe="320.25")),
            *_parts(
                "usos",
                ProfileRowUsoValues(tipo="disposicion_propietario", desde=USE_LATER),
                ProfileRowUsoValues(tipo="vivienda_habitual", desde=USE_FROM, hasta=USE_TO),
            ),
        ),
    )

    assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert settled.effect is OperationEffect.UPDATED
    stored = world.stored(INMUEBLE_SECTION, prop)
    assert stored["valores_catastrales"] == VALORES
    assert stored["mejoras"] == f"{MEJORA_SECOND}:320.25"
    assert stored["usos"] == USOS


def test_parts_stated_on_an_add_land_beside_the_text_of_the_other_fields(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property())

    settled = world.add_through_operation(
        ARRENDAMIENTO_SECTION,
        _lease(prop),
        parts=_parts(
            "inquilinos",
            ProfileRowInquilinoValues(nif=TENANT.lower(), franja_edad="18_35", extranjero=False),
            ProfileRowInquilinoValues(nif="X1234567L", franja_edad="otra", extranjero=True),
        ),
    )

    assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
    (lease,) = (row for row in rows_from_facts(ARRENDAMIENTO_SECTION, world.facts()))
    assert world.stored(ARRENDAMIENTO_SECTION, lease)["inquilinos"] == INQUILINOS
    assert world.stored(ARRENDAMIENTO_SECTION, lease)["inmueble"] == str(prop)


def test_a_field_stated_as_text_and_as_parts_in_one_request_is_refused(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property())
    before = world.facts()

    with pytest.raises(ValidationError, match="text or as parts, not both"):
        ProfileRepeatableRowUpdateOperationRequest(
            profile_id=world.profile_id,
            expected_revision=1,
            expected_content_digest="0" * 64,
            section_key=INMUEBLE_SECTION,
            row_key=str(prop),
            values=(ProfileRepeatableRowValue(field_key="usos", value=USOS),),
            part_values=_parts("usos", ProfileRowUsoValues(tipo="vivienda_habitual", desde=USE_FROM)),
        )
    with pytest.raises(ValidationError, match="text or as parts, not both"):
        ProfileRepeatableRowMutationOperationRequest(
            profile_id=world.profile_id,
            expected_revision=1,
            expected_content_digest="0" * 64,
            section_key=INMUEBLE_SECTION,
            values=(ProfileRepeatableRowValue(field_key="usos", value=USOS),),
            part_values=_parts("usos", ProfileRowUsoValues(tipo="vivienda_habitual", desde=USE_FROM)),
        )
    assert world.facts() == before


def test_a_part_is_refused_exactly_as_its_text_entry_is(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property())
    before = world.facts()

    by_text = world.update_through_operation(INMUEBLE_SECTION, prop, {"usos": f"vivienda_habitual:{YEAR}-13-01:"})
    by_parts = world.update_through_operation(
        INMUEBLE_SECTION,
        prop,
        parts=_parts("usos", ProfileRowUsoValues(tipo="vivienda_habitual", desde=f"{YEAR}-13-01")),
    )

    assert by_text.terminal_condition is OperationTerminalCondition.REFUSED
    assert _outcome(by_parts) == _outcome(by_text)
    assert world.facts() == before


def test_a_part_the_record_does_not_cohere_with_is_refused_as_the_text_is(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property())
    before = world.facts()

    twice = world.update_through_operation(
        INMUEBLE_SECTION,
        prop,
        parts=_parts(
            "valores_catastrales",
            ProfileRowValorCatastralValues(year=IBI_SECOND, total="1.00", construccion="1.00"),
            ProfileRowValorCatastralValues(year=IBI_SECOND, total="2.00", construccion="1.00"),
        ),
    )
    text = world.update_through_operation(
        INMUEBLE_SECTION, prop, {"valores_catastrales": f"{IBI_SECOND}:1.00:1.00;{IBI_SECOND}:2.00:1.00"}
    )

    assert text.terminal_condition is OperationTerminalCondition.REFUSED
    assert _outcome(twice) == _outcome(text)
    assert world.facts() == before


def test_a_tenant_part_is_checked_as_the_text_is(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property())
    lease = world.add(ARRENDAMIENTO_SECTION, _lease(prop))
    before = world.facts()

    text = world.update_through_operation(ARRENDAMIENTO_SECTION, lease, {"inquilinos": "99999999A:otra:no"})
    parts = world.update_through_operation(
        ARRENDAMIENTO_SECTION,
        lease,
        parts=_parts("inquilinos", ProfileRowInquilinoValues(nif="99999999A", franja_edad="otra", extranjero=False)),
    )

    assert text.terminal_condition is OperationTerminalCondition.REFUSED
    assert _outcome(parts) == _outcome(text)
    assert world.facts() == before


def test_a_part_of_another_kind_or_for_an_unpacked_field_is_refused() -> None:
    use = ProfileRowUsoValues(tipo="vivienda_habitual", desde=USE_FROM)

    with pytest.raises(ProfileSchemaValidationError):
        packed_text_of_parts(INMUEBLE_SECTION, "mejoras", (use,))
    with pytest.raises(ProfileSchemaValidationError):
        packed_text_of_parts(INMUEBLE_SECTION, "direccion", (use,))
    with pytest.raises(ProfileSchemaValidationError):
        packed_text_of_parts(ARRENDAMIENTO_SECTION, "usos", (use,))


def test_a_part_cannot_smuggle_the_separators_of_the_text_form() -> None:
    forged = ProfileRowUsoValues(tipo=f"vivienda_habitual:{USE_FROM}:;actividad_economica", desde=USE_FROM)

    with pytest.raises(ProfileAnswerTypeError):
        packed_text_of_parts(INMUEBLE_SECTION, "usos", (forged,))


def test_an_empty_list_of_parts_is_a_blank_value_the_row_operation_refuses(world: _World) -> None:
    prop = world.add(INMUEBLE_SECTION, _property(usos=USOS))
    before = world.facts()

    settled = world.update_through_operation(INMUEBLE_SECTION, prop, parts=_parts("usos"))

    assert settled.terminal_condition is OperationTerminalCondition.REFUSED
    assert world.facts() == before
