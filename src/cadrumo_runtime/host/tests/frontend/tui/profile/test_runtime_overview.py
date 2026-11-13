"""TUI overview reconstruction from real encrypted profile view pages."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.modelo.export_m202_profile import PRINCIPAL_CNAE_CLASSIFICATION_PATH
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.overview import ProfileFieldChoice, build_profile_overview
from cadrumo.application.user_profile.password_kdf_notice import profile_kdf_floor_notice
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.section_rows import add_profile_repeatable_section_row
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_MAX_ITEMS,
    PROFILE_VIEW_MAX_RESULT_BYTES,
    ProfileViewFieldItem,
    ProfileViewOperationProjection,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.application.user_profile.view_reader import read_profile_view_page
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.json_contract import Notice
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.cnae_classification import cnae_classification_names
from cadrumo.domain.calculations.registry.renta_codes_catalogue import ue_eea_country_codes
from cadrumo.domain.iva.establishment import catalogued_country_codes
from cadrumo.domain.user_profile.schema import ProfileFieldCodeList
from cadrumo_client.transport.frontend_client_contracts import ProfileViewCollection

from .....frontend.tui.profile.overview_client import profile_overview_from_client_view

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_PASSWORD = "runtime-overview-test-passphrase"  # noqa: S105 - isolated test credential


def _register() -> UUID:
    with bundled_indexed_authority().operation() as authority:
        created = register_profile_with_credentials(
            label="Stored profile label",
            passphrase=_PASSWORD,
            profile_create_context=authority.profile_create_context(),
            profile_decode_context=authority.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=created.profile_id,
            passphrase_callback=lambda: _PASSWORD,
            profile_decode_context=authority.profile_decode_context(),
        )
    return UUID(created.profile_id)


def _collection(
    profile_id: UUID, authority: PinnedAuthorityOperation, *, limit: int = PROFILE_VIEW_MAX_ITEMS
) -> ProfileViewCollection:
    pages: list[ProfileViewOperationProjection] = []
    cursor = 0
    while True:
        result = read_profile_view_page(
            ProfileViewOperationRequest(
                profile_id=profile_id,
                page_kind=ProfileViewPageKind.OVERVIEW,
                cursor=cursor,
                limit=limit,
                expected_revision=pages[0].record_revision if pages else None,
                expected_content_digest=pages[0].content_digest if pages else None,
                output_language=OutputLanguage.ES,
            ),
            authority_operation=authority,
        )
        assert result.outcome == "page"
        page = ProfileViewOperationProjection.model_validate(result.model_dump(mode="python"))
        pages.append(page)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    first = pages[0]
    return ProfileViewCollection(
        profile_id=profile_id,
        record_revision=first.record_revision,
        content_digest=first.content_digest,
        setup_state=first.setup_state,
        schema_version=first.schema_version,
        valid=first.valid,
        page_kinds=(ProfileViewPageKind.OVERVIEW,),
        pages=tuple(pages),
    )


def test_empty_profile_overview_uses_fewer_bounded_reads(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        with bundled_indexed_authority().operation() as authority:
            previous = _collection(profile_id, authority, limit=8)
            current = _collection(profile_id, authority)
    assert len(current.pages) < len(previous.pages)
    # Fewest reads under the byte budget: every page but the last has no room for the next page's first item.
    for page, following in zip(current.pages, current.pages[1:], strict=False):
        assert len(page.model_dump_json().encode("utf-8")) + len(
            following.items[0].model_dump_json().encode("utf-8")
        ) + 1 > (PROFILE_VIEW_MAX_RESULT_BYTES)
    assert tuple(item for page in current.pages for item in page.items) == tuple(
        item for page in previous.pages for item in page.items
    )
    assert current.record_revision == previous.record_revision
    assert current.content_digest == previous.content_digest
    assert all(len(page.model_dump_json().encode("utf-8")) <= PROFILE_VIEW_MAX_RESULT_BYTES for page in current.pages)
    assert profile_overview_from_client_view(current, profile_label="Profile") == profile_overview_from_client_view(
        previous, profile_label="Profile"
    )


def test_real_encrypted_overview_pages_round_trip_every_field(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        with bundled_indexed_authority().operation() as authority:
            repository = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=authority.profile_decode_context()
            )
            baseline = repository.load(profile_id)
            added = add_profile_repeatable_section_row(
                profile_id=str(profile_id),
                section_key="activities",
                values={"description": "Additional activity"},
                expected_revision=baseline.record_revision,
                expected_content_digest=baseline.content_digest,
                schema=authority.profile_schema(),
                profile_decode_context=authority.profile_decode_context(),
                authority=authority,
            )
            collection = _collection(profile_id, authority)
            assert len(collection.pages) > 1
            with override_settings(cadrumo_output_language="es"):
                expected = build_profile_overview(
                    added.record,
                    label="Public inventory label",
                    schema=authority.profile_schema(),
                    flow=build_setup_flow(authority),
                    code_lists={
                        ProfileFieldCodeList.COUNTRIES: tuple(sorted(catalogued_country_codes(operation=authority))),
                        ProfileFieldCodeList.EU_EEA_COUNTRIES: tuple(sorted(ue_eea_country_codes(authority=authority))),
                    },
                    registry_choices={
                        PRINCIPAL_CNAE_CLASSIFICATION_PATH: tuple(
                            ProfileFieldChoice(value=identifier, label=name)
                            for identifier, name in cnae_classification_names(authority=authority).items()
                        ),
                    },
                )
                floor = profile_kdf_floor_notice(profile_id)
            # The isolated storage declines KDF measurement, so the envelope sits at the fixed fallback and the
            # reader appends the custody notice after the overview's own notices.
            assert floor is not None
            expected = expected.model_copy(
                update={
                    "notices": (
                        *expected.notices,
                        Notice(severity=floor.severity, code=floor.code, message=floor.message),
                    )
                }
            )
            actual = profile_overview_from_client_view(collection, profile_label="Public inventory label")
            assert actual == expected
            assert actual.record_revision == added.record.record_revision
            assert actual.content_digest == added.record.content_digest
            assert any(field.row_index is not None for section in actual.sections for field in section.fields)
            fields = [field for section in actual.sections for field in section.fields]
            assert any(field.references_section is not None for field in fields)
            cnae = next(field for field in fields if field.path == PRINCIPAL_CNAE_CLASSIFICATION_PATH)
            assert {choice.value for choice in cnae.choices} >= {"cnae-2009", "cnae-2025"}


def test_runtime_overview_rejects_broken_page_and_field_membership(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        with bundled_indexed_authority().operation() as authority:
            collection = _collection(profile_id, authority)
            first = collection.pages[0]
            broken = replace(collection, pages=(first.model_copy(update={"cursor": 1}), *collection.pages[1:]))
            with pytest.raises(ValueError, match="collected stream"):
                profile_overview_from_client_view(broken, profile_label="Public inventory label")
            for page_index, page in enumerate(collection.pages):
                for item_index, item in enumerate(page.items):
                    if isinstance(item, ProfileViewFieldItem):
                        altered = item.model_copy(update={"section_key": "wrong-section"})
                        items = (*page.items[:item_index], altered, *page.items[item_index + 1 :])
                        pages = list(collection.pages)
                        pages[page_index] = page.model_copy(update={"items": items})
                        malformed = replace(collection, pages=tuple(pages))
                        with pytest.raises(ValueError, match="outside its section"):
                            profile_overview_from_client_view(malformed, profile_label="Public inventory label")
                        return
            pytest.fail("canonical overview did not contain a field")
