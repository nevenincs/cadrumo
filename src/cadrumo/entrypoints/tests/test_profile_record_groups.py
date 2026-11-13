"""Rental rows served as one group per property, and as ledger link choices, from a real encrypted profile.

The profile rows are written through the repeatable-row door and the ledger rows through the
production ledger ports, so the grouped read joins what the stores actually hold, and the
entry options read draws its rental choices through the production profile read.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application.aggregation.prevision_social_contribution_repository import (
    record_prevision_social_contribution,
)
from ...application.ledger.action_ports import LedgerActionPorts
from ...application.ledger.entry_options_operation import ledger_entry_options
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.models import OperationRequest
from ...application.operations.registry import OperationRegistry
from ...application.prevision_social_contribution.contracts import (
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
)
from ...application.prevision_social_contribution.ports import PrevisionSocialPorts
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.login_session import authenticate_profile_for_invocation
from ...application.user_profile.profile_operation_contracts import (
    PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
)
from ...application.user_profile.record_group_contracts import (
    PENSION_CONTRIBUTION_SECTION_KEY,
    PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID,
    ProfileRecordDoor,
    ProfileRecordGroupItem,
    ProfileRecordGroupKind,
    ProfileRecordGroupsRefusalCode,
    ProfileRecordGroupsRequest,
    ProfileRecordGroupsResult,
    ProfileRecordLedgerRowItem,
    ProfileRecordMemberItem,
)
from ...application.user_profile.record_group_operation import (
    build_record_groups_definition,
    build_record_groups_registration,
)
from ...application.user_profile.record_group_words import (
    EDIT_DOOR_LABEL_LOCALE_KEYS,
    GROUP_KIND_WORDS_LOCALE_KEYS,
    LEDGER_ROW_KIND_WORDS_LOCALE_KEY,
    REFUSAL_WORDS_LOCALE_KEYS,
    REMOVE_DOOR_LABEL_LOCALE_KEYS,
    SECTION_KIND_WORDS_LOCALE_KEYS,
)
from ...application.user_profile.record_groups import read_profile_record_groups
from ...application.user_profile.registration import register_profile_with_credentials
from ...application.user_profile.section_rows import add_profile_repeatable_section_row
from ...application.user_profile.view_operation import (
    ProfileViewFieldItem,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from ...application.user_profile.view_reader import read_profile_view_page
from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation
from ...core.operations import OperationFrontendProjection, profile_operation_subject
from ...core.prevision_social import PrevisionSocialBeneficiario, PrevisionSocialClave, PrevisionSocialSubclave
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.gasto_capital_inmobiliario import require_gasto_capital_inmobiliario
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION
from ...domain.renta.prevision_social_contribution import PrevisionSocialContribution
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import Transaction
from ...domain.transactions.rental_link import RENTAL_LINK_IRPF_CATEGORY
from ..ledger_action_composition import (
    compose_ledger_action_ports,
    load_entry_option_profile_facts,
    load_ledger_rows_for_rental_references,
)
from ..prevision_social_contribution_composition import build_prevision_social_contribution_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_PRINCIPAL_CATASTRAL = "9872023VH5797S0001WX"
_ACCESSORY_ADDRESS = "Calle Sintetica 1, trastero"


class _World(NamedTuple):
    profile_id: str
    operation: PinnedAuthorityOperation
    principal: int
    accessory: int
    lease: int


def _add(profile_id: str, operation: PinnedAuthorityOperation, section: str, values: dict[str, str]) -> int:
    decode = operation.profile_decode_context()
    return add_profile_repeatable_section_row(
        profile_id=profile_id,
        section_key=section,
        values=values,
        schema=decode.schema,
        profile_decode_context=decode,
        authority=operation,
    ).row_index


def _property(**extra: str) -> dict[str, str]:
    return {
        "situacion": "1",
        "titularidad_regimen": "pleno_dominio",
        "titular": "primer_declarante",
        "porcentaje_propiedad": "100",
        "importe_adquisicion": "150000",
        "valores_catastrales": f"{_YEAR}:80000:48000",
        **extra,
    }


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"record-groups-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Record groups",
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
        profile_id = outcome.profile_id
        principal = _add(
            profile_id, operation, INMUEBLE_SECTION, _property(referencia_catastral=_PRINCIPAL_CATASTRAL.lower())
        )
        accessory = _add(
            profile_id,
            operation,
            INMUEBLE_SECTION,
            _property(
                referencia_catastral="9872023VH5797S0002EZ".lower(),
                direccion=_ACCESSORY_ADDRESS,
                inmueble_principal=str(principal),
            ),
        )
        lease = _add(
            profile_id,
            operation,
            ARRENDAMIENTO_SECTION,
            {
                "inmueble": str(principal),
                "fecha_contrato": date(_YEAR, 1, 10).isoformat(),
                "fecha_inicio": date(_YEAR, 2, 1).isoformat(),
                "inquilinos": "12345678z:otra:no",
            },
        )
        yield _World(profile_id, operation, principal, accessory, lease)


@pytest.fixture
def ports(world: _World) -> LedgerActionPorts:
    return compose_ledger_action_ports(bucket_id=world.profile_id, operation=world.operation)


def _ledger_row(world: _World, ports: LedgerActionPorts, **fields: object) -> Transaction:
    values: dict[str, object] = {
        "bucket_id": world.profile_id,
        "booked_date": date(_YEAR, 5, 2),
        "amount": Decimal("800.00"),
        "direction": TransactionDirection.INCOMING,
        "description": "rent",
        "business_classification": BusinessClassification.BUSINESS,
        "irpf_category": RENTAL_LINK_IRPF_CATEGORY,
        **fields,
    }
    return create_manual_transaction(ManualLedgerTransactionCommand.model_validate(values), ports=ports).transaction


def _read(world: _World, **request: object) -> ProfileRecordGroupsResult:
    return read_profile_record_groups(
        ProfileRecordGroupsRequest.model_validate(
            {"profile_id": UUID(world.profile_id), "group_kind": ProfileRecordGroupKind.RENTAL_PROPERTY, **request}
        ),
        authority_operation=world.operation,
        ledger_rows=load_ledger_rows_for_rental_references,
        contribution_ports=build_prevision_social_contribution_ports,
    )


def test_a_property_is_served_with_its_lease_its_accessory_and_the_ledger_rows_naming_any_of_them(
    world: _World, ports: LedgerActionPorts
) -> None:
    rent = _ledger_row(world, ports, arrendamiento_ref=str(world.lease))
    expense = _ledger_row(
        world,
        ports,
        booked_date=date(_YEAR, 6, 3),
        amount=Decimal("85.00"),
        direction=TransactionDirection.OUTGOING,
        description="cuota",
        inmueble_ref=str(world.accessory),
        gasto_capital_inmobiliario=require_gasto_capital_inmobiliario("comunidad", authority=world.operation),
    )

    page = _read(world, output_language=OutputLanguage.EN)

    principal = f"{INMUEBLE_SECTION}.{world.principal}"
    accessory = f"{INMUEBLE_SECTION}.{world.accessory}"
    lease = f"{ARRENDAMIENTO_SECTION}.{world.lease}"
    assert page.outcome == "page" and page.next_cursor is None and page.total_items == 5
    head, *members, first, second = page.items
    # The accessory names the principal, so it is a member of the principal's group and heads none.
    assert isinstance(head, ProfileRecordGroupItem)
    assert (head.group_key, head.member_count, head.ledger_row_count) == (principal, 2, 2)
    assert _PRINCIPAL_CATASTRAL in head.summary_words
    assert all(isinstance(member, ProfileRecordMemberItem) for member in members)
    assert {
        (member.row_ref, member.parent_ref, member.relation)
        for member in members
        if isinstance(member, ProfileRecordMemberItem)
    } == {
        (accessory, principal, f"{INMUEBLE_SECTION}.inmueble_principal"),
        (lease, principal, f"{ARRENDAMIENTO_SECTION}.inmueble"),
    }
    assert any(
        _ACCESSORY_ADDRESS in member.summary_words for member in members if isinstance(member, ProfileRecordMemberItem)
    )
    assert isinstance(first, ProfileRecordLedgerRowItem) and isinstance(second, ProfileRecordLedgerRowItem)
    assert (first.transaction_id, first.linked_ref, first.concept) == (rent.transaction_id, lease, None)
    assert (second.transaction_id, second.linked_ref, second.concept) == (
        expense.transaction_id,
        accessory,
        "comunidad",
    )
    assert second.concept_words == lookup_translation(
        "application.ledger.entry_options.gasto_capital_inmobiliario.comunidad", locale="en"
    )
    assert second.amount.decimal == "85.00" and second.direction is TransactionDirection.OUTGOING


def test_every_word_is_served_in_the_language_asked_for(world: _World) -> None:
    words: dict[OutputLanguage, tuple[str, ...]] = {}
    for language in OutputLanguage:
        page = _read(world, output_language=language)
        served = tuple(
            text
            for item in page.items
            if isinstance(item, ProfileRecordGroupItem | ProfileRecordMemberItem)
            for text in (item.summary_words, getattr(item, "relation_words", ""))
            if text
        )
        assert all(
            item.summary_words_language is language
            for item in page.items
            if isinstance(item, ProfileRecordGroupItem | ProfileRecordMemberItem)
        )
        assert all("record_groups" not in text for text in served)
        words[language] = served
    assert len({served for served in words.values()}) == len(OutputLanguage)


def test_a_continuation_is_pinned_and_refused_once_the_linked_ledger_rows_move(
    world: _World, ports: LedgerActionPorts
) -> None:
    _ledger_row(world, ports, arrendamiento_ref=str(world.lease))
    first = _read(world, limit=1)
    assert first.outcome == "page" and len(first.items) == 1 and first.next_cursor == 1
    pin = {
        "expected_revision": first.record_revision,
        "expected_content_digest": first.content_digest,
        "expected_ledger_digest": first.ledger_digest,
    }

    second = _read(world, cursor=1, limit=1, **pin)
    assert second.outcome == "page" and isinstance(second.items[0], ProfileRecordMemberItem)

    _ledger_row(world, ports, arrendamiento_ref=str(world.lease), description="second rent")
    stale = _read(world, cursor=1, limit=1, **pin)
    assert stale.outcome == "refused" and stale.refusal_code is ProfileRecordGroupsRefusalCode.STALE_REVISION
    assert stale.items == ()


def _words(key: str, language: OutputLanguage) -> str:
    served = lookup_translation(key, locale=language.value)
    assert served is not None
    return served


def test_each_stored_row_carries_its_edit_and_remove_doors_routed_to_the_registered_row_operations(
    world: _World,
) -> None:
    for language in OutputLanguage:
        page = _read(world, output_language=language)
        rows = [item for item in page.items if isinstance(item, ProfileRecordGroupItem | ProfileRecordMemberItem)]
        assert len(rows) == 3
        for row in rows:
            assert [
                (action.door, action.operation_definition_id, action.label_words, action.label_words_language)
                for action in row.actions
            ] == [
                (
                    ProfileRecordDoor.EDIT,
                    PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
                    _words(EDIT_DOOR_LABEL_LOCALE_KEYS[row.section_key], language),
                    language,
                ),
                (
                    ProfileRecordDoor.REMOVE,
                    PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
                    _words(REMOVE_DOOR_LABEL_LOCALE_KEYS[row.section_key], language),
                    language,
                ),
            ]
    head = _read(world, output_language=OutputLanguage.EN).items[0]
    assert isinstance(head, ProfileRecordGroupItem)
    # The group's own doors are its head row's: a property is edited and removed as a property.
    assert {action.label_words for action in head.actions} == {
        _words(EDIT_DOOR_LABEL_LOCALE_KEYS[INMUEBLE_SECTION], OutputLanguage.EN),
        _words(REMOVE_DOOR_LABEL_LOCALE_KEYS[INMUEBLE_SECTION], OutputLanguage.EN),
    }


def test_every_item_says_what_kind_of_thing_it_is_in_the_language_asked_for(
    world: _World, ports: LedgerActionPorts
) -> None:
    _ledger_row(world, ports, arrendamiento_ref=str(world.lease))
    for language in OutputLanguage:
        page = _read(world, output_language=language)
        kinds: set[str] = set()
        for item in page.items:
            if isinstance(item, ProfileRecordGroupItem):
                expected = _words(GROUP_KIND_WORDS_LOCALE_KEYS[item.payload_kind], language)
            elif isinstance(item, ProfileRecordMemberItem):
                expected = _words(SECTION_KIND_WORDS_LOCALE_KEYS[item.section_key], language)
            else:
                expected = _words(LEDGER_ROW_KIND_WORDS_LOCALE_KEY, language)
            assert (item.kind_words, item.kind_words_language) == (expected, language)
            kinds.add(item.kind)
        assert kinds == {"group", "member", "ledger_row"}


def test_a_stale_continuation_is_refused_with_served_words_in_the_language_asked_for(
    world: _World, ports: LedgerActionPorts
) -> None:
    first = _read(world, limit=1)
    pin = {
        "expected_revision": first.record_revision,
        "expected_content_digest": first.content_digest,
        "expected_ledger_digest": first.ledger_digest,
    }
    _ledger_row(world, ports, arrendamiento_ref=str(world.lease))
    for language in OutputLanguage:
        stale = _read(world, cursor=1, limit=1, output_language=language, **pin)
        assert stale.refusal_code is ProfileRecordGroupsRefusalCode.STALE_REVISION
        assert (stale.refusal_words, stale.refusal_words_language) == (
            _words(REFUSAL_WORDS_LOCALE_KEYS[ProfileRecordGroupsRefusalCode.STALE_REVISION], language),
            language,
        )
    assert first.refusal_words is None and first.refusal_words_language is None


def test_a_page_that_starts_inside_a_groups_ledger_rows_states_their_place_and_total(
    world: _World, ports: LedgerActionPorts
) -> None:
    for day in (2, 3, 4):
        _ledger_row(world, ports, booked_date=date(_YEAR, 5, day), arrendamiento_ref=str(world.lease))
    whole = _read(world)
    head = whole.items[0]
    assert isinstance(head, ProfileRecordGroupItem) and head.ledger_row_count == 3
    first_ledger = 1 + head.member_count
    pin = {
        "expected_revision": whole.record_revision,
        "expected_content_digest": whole.content_digest,
        "expected_ledger_digest": whole.ledger_digest,
    }

    tail = _read(world, cursor=first_ledger + 1, limit=1, **pin)

    assert tail.outcome == "page" and tail.next_cursor == first_ledger + 2
    (row,) = tail.items
    assert isinstance(row, ProfileRecordLedgerRowItem)
    assert (row.group_key, row.ledger_row_index, row.ledger_row_total) == (head.group_key, 1, 3)
    served = [item for item in whole.items if isinstance(item, ProfileRecordLedgerRowItem)]
    assert [(item.ledger_row_index, item.ledger_row_total) for item in served] == [(0, 3), (1, 3), (2, 3)]
    assert served[1].transaction_id == row.transaction_id


def test_the_entry_options_offer_the_profiles_own_leases_and_properties_worded_by_their_summary(
    world: _World,
) -> None:
    facts = load_entry_option_profile_facts(world.profile_id, world.operation)
    options = ledger_entry_options(
        UUID(world.profile_id), operation=world.operation, language=OutputLanguage.ES, profile_facts=facts
    )

    families = {family.family: family.options for family in options.families}
    assert [option.value for option in families["rental_property"]] == [str(world.principal), str(world.accessory)]
    assert [option.value for option in families["rental_lease"]] == [str(world.lease)]
    group = _read(world, output_language=OutputLanguage.ES)
    served = {
        item.summary_words for item in group.items if isinstance(item, ProfileRecordGroupItem | ProfileRecordMemberItem)
    }
    for option in (*families["rental_property"], *families["rental_lease"]):
        assert option.label_key is None and option.label_words_language is OutputLanguage.ES
        assert option.label_words in served


def test_the_profile_field_view_marks_each_field_that_names_another_sections_row(world: _World) -> None:
    references: dict[str, str | None] = {}
    cursor, pin = 0, {}
    while True:
        page = read_profile_view_page(
            ProfileViewOperationRequest.model_validate(
                {
                    "profile_id": UUID(world.profile_id),
                    "page_kind": ProfileViewPageKind.OVERVIEW,
                    "cursor": cursor,
                    **pin,
                }
            ),
            authority_operation=world.operation,
        )
        references.update(
            {
                item.field.path: item.field.references_section
                for item in page.items
                if isinstance(item, ProfileViewFieldItem)
            }
        )
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
        pin = {"expected_revision": page.record_revision, "expected_content_digest": page.content_digest}

    marked = {path: section for path, section in references.items() if section is not None}
    assert marked == {
        f"{INMUEBLE_SECTION}.{world.principal}.inmueble_principal": INMUEBLE_SECTION,
        f"{INMUEBLE_SECTION}.{world.accessory}.inmueble_principal": INMUEBLE_SECTION,
        f"{ARRENDAMIENTO_SECTION}.{world.lease}.inmueble": INMUEBLE_SECTION,
    }


def _access(context_profile: UUID, payload_profile: UUID, subject_profile: UUID) -> object:
    definition = build_record_groups_definition(
        load_ledger_rows_for_rental_references, build_prevision_social_contribution_ports
    )
    registration = build_record_groups_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return resolve_operation_access(
        registry=registry,
        request=OperationRequest[BaseModel](
            definition_id=PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(subject_profile)),
            payload=ProfileRecordGroupsRequest(
                profile_id=payload_profile, group_kind=ProfileRecordGroupKind.RENTAL_PROPERTY
            ),
        ),
        context=OperationAccessContext(
            profile_id=context_profile,
            destination_id=uuid4(),
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.CLI,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
            admitted_request=None,
        ),
    )


_OWN = UUID("41414141-4141-4141-8141-414141414141")
_OTHER = UUID("42424242-4242-4242-8242-424242424242")


def test_the_read_is_admitted_for_its_own_profile_only() -> None:
    assert _access(_OWN, _OWN, _OWN) is not None
    for context_profile, payload_profile, subject_profile in ((_OTHER, _OWN, _OWN), (_OWN, _OTHER, _OWN)):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            _access(context_profile, payload_profile, subject_profile)
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


_ISSUER = "V00010082"
_PLAN = "V00010090"
_CERTIFICATE = b"%PDF-1.4 synthetic pension contribution certificate"


def _contribution(
    ports: PrevisionSocialPorts, ejercicio: int, *, amount: str, plan: str | None
) -> PrevisionSocialContribution:
    repository = ports.repository
    captured_at = datetime.now(UTC)
    record = PrevisionSocialContribution(
        ejercicio=ejercicio,
        issuer_tax_id=_ISSUER,
        issuer_legal_name="Gestora Sintetica SA",
        issuer_ref=repository.issuer_reference(_ISSUER),
        plan_tax_id=plan,
        plan_name=None if plan is None else "Plan Sintetico",
        plan_ref=None if plan is None else repository.plan_reference(plan),
        clave=PrevisionSocialClave.CLAVE_A,
        subclave=PrevisionSocialSubclave.SUBCLAVE_01,
        amount=Decimal(amount),
        beneficiary=PrevisionSocialBeneficiario.TAXPAYER,
        evidence_fingerprint=ports.custody.ingest(
            source_path=Path("certificate.pdf"), data=_CERTIFICATE, mime_type="application/pdf", captured_at=captured_at
        ),
        captured_at=captured_at,
    )
    record_prevision_social_contribution(
        record,
        repository=repository,
        authority=ports.authority,
        custody=ports.custody,
        expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
    )
    return record


class _Pension(NamedTuple):
    first: PrevisionSocialContribution
    second: PrevisionSocialContribution
    third: PrevisionSocialContribution
    ports: PrevisionSocialPorts


@pytest.fixture
def pension(world: _World) -> _Pension:
    ports = build_prevision_social_contribution_ports(profile_id=UUID(world.profile_id), operation=world.operation)
    older, newer = sorted(filing_year_envelope().years)[-2:]
    return _Pension(
        _contribution(ports, newer, amount="1000.00", plan=_PLAN),
        _contribution(ports, newer, amount="250.50", plan=None),
        _contribution(ports, older, amount="400.00", plan=_PLAN),
        ports,
    )


def _read_pension(world: _World, **request: object) -> ProfileRecordGroupsResult:
    return _read(world, group_kind=ProfileRecordGroupKind.PENSION_CONTRIBUTION, **request)


def test_pension_certificates_are_served_one_group_per_ejercicio_with_their_doors_and_no_tax_identifier(
    world: _World, pension: _Pension
) -> None:
    page = _read_pension(world, output_language=OutputLanguage.EN)

    older, newer = pension.third.ejercicio, pension.first.ejercicio
    assert page.outcome == "page" and page.next_cursor is None and page.total_items == 5
    older_head, older_member, newer_head, *newer_members = page.items
    assert isinstance(older_head, ProfileRecordGroupItem) and isinstance(newer_head, ProfileRecordGroupItem)
    assert [
        (head.row_key, head.member_count, head.ledger_row_count, head.actions) for head in (older_head, newer_head)
    ] == [(str(older), 1, 0, ()), (str(newer), 2, 0, ())]
    assert older_head.payload_kind is ProfileRecordGroupKind.PENSION_CONTRIBUTION
    assert str(newer) in newer_head.summary_words
    members = [older_member, *newer_members]
    assert all(isinstance(member, ProfileRecordMemberItem) for member in members)
    for member in members:
        assert isinstance(member, ProfileRecordMemberItem) and member.contribution is not None
        row = member.contribution
        stored, revision_id = pension.ports.repository.load_revisioned(
            (row.ejercicio, row.issuer_ref, row.plan_ref, row.clave, row.subclave)
        )
        assert stored is not None and row.revision_id == revision_id
        assert member.parent_ref == f"{PENSION_CONTRIBUTION_SECTION_KEY}.{row.ejercicio}"
        assert [(action.door, action.operation_definition_id) for action in member.actions] == [
            (ProfileRecordDoor.EDIT, PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID),
            (ProfileRecordDoor.REMOVE, PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID),
        ]
        assert member.kind_words == _words(
            SECTION_KIND_WORDS_LOCALE_KEYS[PENSION_CONTRIBUTION_SECTION_KEY], OutputLanguage.EN
        )
        assert str(stored.amount) in member.summary_words
        placed = pension.ports.authority.placement(stored)
        box = getattr(placed, "casilla_id", None)
        assert row.casilla_id == box
        assert (box is not None) == (str(box) in member.summary_words)
    served = page.model_dump_json()
    assert _ISSUER not in served and _PLAN not in served


def test_pension_certificates_are_worded_in_every_language_and_pinned_to_their_revisions(
    world: _World, pension: _Pension
) -> None:
    summaries = set()
    for language in OutputLanguage:
        page = _read_pension(world, output_language=language)
        for item in page.items:
            if isinstance(item, ProfileRecordGroupItem | ProfileRecordMemberItem):
                assert (item.kind_words_language, item.summary_words_language) == (language, language)
                assert "record_groups" not in item.summary_words and "record_groups" not in item.kind_words
        members = [item for item in page.items if isinstance(item, ProfileRecordMemberItem)]
        assert {action.label_words for member in members for action in member.actions} == {
            _words(EDIT_DOOR_LABEL_LOCALE_KEYS[PENSION_CONTRIBUTION_SECTION_KEY], language),
            _words(REMOVE_DOOR_LABEL_LOCALE_KEYS[PENSION_CONTRIBUTION_SECTION_KEY], language),
        }
        summaries.add(tuple(member.summary_words for member in members))
    assert len(summaries) == len(OutputLanguage)

    first = _read_pension(world, limit=2)
    assert first.outcome == "page" and first.next_cursor == 2
    pin = {
        "expected_revision": first.record_revision,
        "expected_content_digest": first.content_digest,
        "expected_ledger_digest": first.ledger_digest,
    }
    second = _read_pension(world, cursor=2, limit=2, **pin)
    assert second.outcome == "page" and len(second.items) == 2 and second.next_cursor == 4

    repository = pension.ports.repository
    repository.delete_revisioned(
        pension.second.identity, expected_revision_id=repository.load_revisioned(pension.second.identity)[1]
    )
    stale = _read_pension(world, cursor=2, limit=2, **pin)
    assert stale.outcome == "refused" and stale.refusal_code is ProfileRecordGroupsRefusalCode.STALE_REVISION


def test_a_profile_without_certificates_serves_no_pension_group(world: _World) -> None:
    page = _read_pension(world)
    assert page.outcome == "page" and page.items == () and page.total_items == 0
