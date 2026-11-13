"""The household doors read the served family rows and submit one served add or remove, never the whole set."""

from __future__ import annotations

from collections.abc import Mapping
from typing import override
from uuid import UUID, uuid4

import pytest

from cadrumo.application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow
from cadrumo.application.user_profile.descendant_rows import ProfileDescendantFact, ProfileDescendantRow
from cadrumo.application.user_profile.family_rows import (
    ProfileFamilyLeafAsk,
    ProfileViewFamilyDraftItem,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
    family_draft_item,
    family_row_items,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfileAscendantsOperationProjection,
    ProfileAscendantsOperationRequest,
    ProfileDescendantsOperationProjection,
    ProfileDescendantsOperationRequest,
)
from cadrumo.application.user_profile.view_operation import ProfileViewOperationProjection, ProfileViewPageKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.descendant_relacion_catalogue import descendant_relacion_adoption_token
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.tui.profile.client_errors import ProfileManagerCompletedViewUnavailableError
from cadrumo.entrypoints.tui.profile.household import HouseholdRowChange
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import ProfileViewCollection
from cadrumo_client.transport.profile_mutations import ProfileMutationCompletion, ProfileMutationRequest

from .....frontend.tui.profile.household_client import (
    HouseholdClient,
    household_from_collection,
    household_request,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DIGEST = "d" * 64
_OPERATION_ID = "f" * 64
_ASCENDANTS = "renta_family.ascendiente"
_STORED = {
    "renta_family.ascendientes_count": "2",
    "renta_family.ascendiente.0.birth_date": "1950-02-03",
    "renta_family.ascendiente.1.birth_date": "1948-07-09",
}


def _served(values: Mapping[str, str]) -> tuple[object, ...]:
    with bundled_indexed_authority().operation() as authority:
        return tuple(family_row_items(dict(values), schema=authority.profile_schema(), operation=authority))


def _collection(profile_id: UUID, items: tuple[object, ...], *, revision: int = 5) -> ProfileViewCollection:
    page = ProfileViewOperationProjection.model_validate(
        {
            "profile_id": profile_id,
            "page_kind": ProfileViewPageKind.FAMILY_ROWS,
            "outcome": "page",
            "record_revision": revision,
            "content_digest": _DIGEST,
            "setup_state": ProfileSetupState.COMPLETE,
            "schema_version": 1,
            "valid": True,
            "cursor": 0,
            "total_items": len(items),
            "items": items,
        }
    )
    return ProfileViewCollection(
        profile_id=profile_id,
        record_revision=revision,
        content_digest=_DIGEST,
        setup_state=ProfileSetupState.COMPLETE,
        schema_version=1,
        valid=True,
        page_kinds=(ProfileViewPageKind.FAMILY_ROWS,),
        pages=(page,),
    )


class _Client(FrontendClient):
    """An exact-profile wire boundary serving one family_rows stream."""

    def __init__(self, items: tuple[object, ...], *, revision: int = 5) -> None:
        self._profile_id = uuid4()
        self._frontend = OperationFrontendProjection.TUI
        self._session_id = uuid4()
        self.items = items
        self.revision = revision
        self.languages: list[OutputLanguage] = []
        self.drafts: list[tuple[str, dict[str, str]]] = []
        self.draft_group: str | None = None

    @override
    def read_profile_view(
        self,
        page_kinds: tuple[ProfileViewPageKind, ...],
        *,
        output_language: OutputLanguage = OutputLanguage.ES,
        expected_revision: int | None = None,
        expected_content_digest: ContentDigest | None = None,
        timeout: float = 60,
        max_pages: int = 512,
    ) -> ProfileViewCollection:
        assert page_kinds == (ProfileViewPageKind.FAMILY_ROWS,)
        self.languages.append(output_language)
        return _collection(self.profile_id, self.items, revision=self.revision)

    @override
    def read_household_draft(
        self,
        group: str,
        answers: Mapping[str, str],
        *,
        output_language: OutputLanguage = OutputLanguage.ES,
        timeout: float = 15,
    ) -> ProfileViewFamilyDraftItem:
        self.languages.append(output_language)
        self.drafts.append((group, dict(answers)))
        with bundled_indexed_authority().operation() as authority:
            item = family_draft_item(self.draft_group or group, answers, operation=authority)
        assert item is not None
        return item


def test_the_household_is_assembled_as_served_group_by_group() -> None:
    items = _served(_STORED)
    view = household_from_collection(_collection(uuid4(), items))
    groups = [item for item in items if isinstance(item, ProfileViewFamilyGroupItem)]
    rows = [item for item in items if isinstance(item, ProfileViewFamilyRowItem)]
    assert [entry.group for entry in view.groups] == groups
    ascendants = next(entry for entry in view.groups if entry.group.group_key == _ASCENDANTS)
    assert list(ascendants.rows) == [row for row in rows if row.group_key == _ASCENDANTS]
    assert len(ascendants.rows) == 2
    assert view.record_revision == 5 and view.content_digest == _DIGEST


def test_a_row_that_does_not_follow_its_group_is_refused() -> None:
    items = _served(_STORED)
    row = next(item for item in items if isinstance(item, ProfileViewFamilyRowItem))
    with pytest.raises(RefusalError):
        household_from_collection(_collection(uuid4(), (row, *items)))


def test_an_add_states_one_person_and_a_remove_one_served_index() -> None:
    profile_id = uuid4()
    added = household_request(
        profile_id,
        HouseholdRowChange(
            operation_id="user-profile.descendants",
            expected_revision=5,
            expected_content_digest=_DIGEST,
            add_row={"relacion": "adoptado", "birth_date": "2020-01-02"},
        ),
    )
    assert added == ProfileDescendantsOperationRequest(
        profile_id=profile_id,
        expected_revision=5,
        expected_content_digest=_DIGEST,
        add_row=ProfileDescendantRow(
            facts=(
                ProfileDescendantFact(field_key="birth_date", value="2020-01-02"),
                ProfileDescendantFact(field_key="relacion", value="adoptado"),
            )
        ),
    )
    removed = household_request(
        profile_id,
        HouseholdRowChange(
            operation_id="user-profile.ascendants",
            expected_revision=5,
            expected_content_digest=_DIGEST,
            remove_row_index="1",
        ),
    )
    assert removed == ProfileAscendantsOperationRequest(
        profile_id=profile_id, expected_revision=5, expected_content_digest=_DIGEST, remove_row_index="1"
    )
    assert isinstance(removed, ProfileAscendantsOperationRequest) and removed.ascendants is None


@pytest.mark.parametrize(
    "change",
    [
        HouseholdRowChange(
            operation_id="user-profile.repeatable-row-remove",
            expected_revision=5,
            expected_content_digest=_DIGEST,
            remove_row_index="0",
        ),
        HouseholdRowChange(
            operation_id="user-profile.ascendants", expected_revision=5, expected_content_digest=_DIGEST
        ),
        HouseholdRowChange(
            operation_id="user-profile.ascendants",
            expected_revision=5,
            expected_content_digest=_DIGEST,
            add_row={"birth_date": "1950-02-03"},
            remove_row_index="0",
        ),
    ],
)
def test_a_change_that_is_not_one_served_add_or_remove_is_refused(change: HouseholdRowChange) -> None:
    with pytest.raises(RefusalError):
        household_request(uuid4(), change)


def _composed(client: _Client, sent: list[ProfileMutationRequest], projection_type: type) -> HouseholdClient:
    def run(subject: FrontendClient, request: ProfileMutationRequest) -> ProfileMutationCompletion:
        assert subject is client
        sent.append(request)
        client.revision = 6
        return ProfileMutationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection_type(profile_id=client.profile_id, record_revision=6, total=1, changed=True),
            effect=OperationEffect.UPDATED,
        )

    return HouseholdClient(client, language=lambda: OutputLanguage.CA, pin=lambda: None, mutation_runner=run)


def test_a_change_is_submitted_then_the_household_is_read_again_in_the_current_language() -> None:
    client = _Client(_served(_STORED))
    sent: list[ProfileMutationRequest] = []
    doors = _composed(client, sent, ProfileAscendantsOperationProjection)
    assert doors.accepts("user-profile.ascendants") and not doors.accepts("user-profile.field-mutation")
    view = doors.change(
        HouseholdRowChange(
            operation_id="user-profile.ascendants",
            expected_revision=5,
            expected_content_digest=_DIGEST,
            add_row={"birth_date": "1950-02-03"},
        )
    )
    assert view.record_revision == 6
    assert client.languages == [OutputLanguage.CA]
    assert sent == [
        ProfileAscendantsOperationRequest(
            profile_id=client.profile_id,
            expected_revision=5,
            expected_content_digest=_DIGEST,
            add_row=ProfileAscendantRow(facts=(ProfileAscendantFact(field_key="birth_date", value="1950-02-03"),)),
        )
    ]


def test_a_settled_change_whose_projection_is_not_its_own_is_completed_not_failed() -> None:
    client = _Client(_served(_STORED))
    doors = _composed(client, [], ProfileDescendantsOperationProjection)
    with pytest.raises(ProfileManagerCompletedViewUnavailableError) as raised:
        doors.change(
            HouseholdRowChange(
                operation_id="user-profile.ascendants",
                expected_revision=5,
                expected_content_digest=_DIGEST,
                remove_row_index="0",
            )
        )
    assert raised.value.effect is OperationEffect.UPDATED


def test_the_asks_of_unsaved_answers_are_the_ones_the_backend_resolves_in_the_current_language() -> None:
    client = _Client(_served({}))
    doors = HouseholdClient(client, language=lambda: OutputLanguage.HU, pin=lambda: None, mutation_runner=_never_run)
    with bundled_indexed_authority().operation() as authority:
        adoption = descendant_relacion_adoption_token(authority=authority).value
    asks = {
        entry.leaf: entry.ask
        for entry in doors.read_draft("renta_family.descendiente", {"relacion": adoption, "convivencia": "true"})
    }
    assert asks["inscripcion_registro_civil"] is ProfileFamilyLeafAsk.ASKED
    assert asks["dependencia_economica"] is ProfileFamilyLeafAsk.NOT_ASKED
    assert client.drafts == [("renta_family.descendiente", {"relacion": adoption, "convivencia": "true"})]
    assert client.languages == [OutputLanguage.HU]


def test_asks_served_for_another_group_than_the_one_asked_are_refused() -> None:
    client = _Client(_served({}))
    client.draft_group = "renta_family.ascendiente"
    doors = HouseholdClient(client, language=lambda: OutputLanguage.ES, pin=lambda: None, mutation_runner=_never_run)
    with pytest.raises(RefusalError):
        doors.read_draft("renta_family.descendiente", {})


def _never_run(_client: FrontendClient, _request: ProfileMutationRequest) -> ProfileMutationCompletion:
    raise AssertionError("reading the asks submits no change")
