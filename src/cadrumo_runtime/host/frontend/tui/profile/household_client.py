"""The household doors of the profile manager over one exact authenticated client session.

The household is read from the ``family_rows`` stream of the profile view and
assembled as served: each group followed by the rows that belong to it. A change
is one served add or remove control's registered operation: the add states one
new person and the remove the ``row_index`` a read served, each against the
revision the screen read, and neither resends anyone else.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final
from uuid import UUID

from cadrumo.application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow
from cadrumo.application.user_profile.descendant_rows import ProfileDescendantFact, ProfileDescendantRow
from cadrumo.application.user_profile.family_question import ProfileViewFamilyQuestionItem
from cadrumo.application.user_profile.family_rows import ProfileViewFamilyGroupItem, ProfileViewFamilyRowItem
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID,
    PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
    ProfileAscendantsOperationProjection,
    ProfileAscendantsOperationRequest,
    ProfileDescendantsOperationProjection,
    ProfileDescendantsOperationRequest,
    ProfileMutationOperationProjection,
)
from cadrumo.application.user_profile.view_operation import ProfileViewPageKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.entrypoints.tui.profile.client_errors import ProfileManagerCompletedViewUnavailableError
from cadrumo.entrypoints.tui.profile.household import HouseholdGroupView, HouseholdRowChange, HouseholdView
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import ProfileViewCollection
from cadrumo_client.transport.profile_mutations import ProfileMutationCompletion, ProfileMutationRequest

type _MutationRunner = Callable[[FrontendClient, ProfileMutationRequest], ProfileMutationCompletion]

_SUBMITTED_OPERATIONS: Final = frozenset(
    {PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID, PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID}
)


def household_from_collection(collection: ProfileViewCollection) -> HouseholdView:
    """Assemble the household from one complete ``family_rows`` stream, refusing a malformed one."""
    if collection.page_kinds != (ProfileViewPageKind.FAMILY_ROWS,):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    groups: list[tuple[ProfileViewFamilyGroupItem, list[ProfileViewFamilyRowItem]]] = []
    for item in collection.items(ProfileViewPageKind.FAMILY_ROWS):
        if isinstance(item, ProfileViewFamilyGroupItem):
            if any(group.group_key == item.group_key for group, _ in groups):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            groups.append((item, []))
        elif isinstance(item, ProfileViewFamilyRowItem):
            # A row belongs to the group served immediately before it.
            if not groups or groups[-1][0].group_key != item.group_key:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            groups[-1][1].append(item)
        elif not isinstance(item, ProfileViewFamilyQuestionItem):
            raise RefusalError(RefusalCode.INVALID_FRAME)
    return HouseholdView(
        profile_id=str(collection.profile_id),
        record_revision=collection.record_revision,
        content_digest=collection.content_digest,
        groups=tuple(HouseholdGroupView(group=group, rows=tuple(rows)) for group, rows in groups),
    )


def household_request(profile_id: UUID, change: HouseholdRowChange) -> ProfileMutationRequest:
    """The registered request a served add or remove control submits, built from the change it names."""
    if (change.add_row is None) == (change.remove_row_index is None):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if change.operation_id == PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID:
        return ProfileDescendantsOperationRequest(
            profile_id=profile_id,
            expected_revision=change.expected_revision,
            expected_content_digest=change.expected_content_digest,
            add_row=None if change.add_row is None else _descendant(change.add_row),
            remove_row_index=change.remove_row_index,
        )
    if change.operation_id == PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID:
        return ProfileAscendantsOperationRequest(
            profile_id=profile_id,
            expected_revision=change.expected_revision,
            expected_content_digest=change.expected_content_digest,
            add_row=None if change.add_row is None else _ascendant(change.add_row),
            remove_row_index=change.remove_row_index,
        )
    raise RefusalError(RefusalCode.INVALID_FRAME)


def _descendant(person: Mapping[str, str]) -> ProfileDescendantRow:
    return ProfileDescendantRow(
        facts=tuple(ProfileDescendantFact(field_key=key, value=value) for key, value in sorted(person.items()))
    )


def _ascendant(person: Mapping[str, str]) -> ProfileAscendantRow:
    return ProfileAscendantRow(
        facts=tuple(ProfileAscendantFact(field_key=key, value=value) for key, value in sorted(person.items()))
    )


def _projection_type(operation_id: str) -> type[ProfileMutationOperationProjection]:
    if operation_id == PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID:
        return ProfileDescendantsOperationProjection
    return ProfileAscendantsOperationProjection


class HouseholdClient:
    """The household port of one pinned profile manager composition."""

    def __init__(
        self,
        client: FrontendClient,
        *,
        language: Callable[[], OutputLanguage],
        pin: Callable[[], None],
        mutation_runner: _MutationRunner,
    ) -> None:
        """Bind the client, the current output language, the composition's pin and its mutation runner."""
        self._client = client
        self._language = language
        self._pin = pin
        self._mutation_runner = mutation_runner

    def accepts(self, operation_id: str, /) -> bool:
        """Whether a served control's registered operation is one this host submits."""
        return operation_id in _SUBMITTED_OPERATIONS

    def read(self) -> HouseholdView:
        """Read the household of the pinned profile in the current output language."""
        self._pin()
        collection = self._client.read_profile_view(
            (ProfileViewPageKind.FAMILY_ROWS,), output_language=self._language()
        )
        self._pin()
        if collection.profile_id != self._client.profile_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return household_from_collection(collection)

    def change(self, change: HouseholdRowChange, /) -> HouseholdView:
        """Submit one served add or remove, then read the household as storage now holds it.

        A settled operation whose household cannot be read again raises
        :class:`ProfileManagerCompletedViewUnavailableError`, never a failure:
        the change completed.
        """
        self._pin()
        request = household_request(self._client.profile_id, change)
        completed = self._mutation_runner(self._client, request)
        try:
            projection = completed.projection
            if (
                type(projection) is not _projection_type(change.operation_id)
                or projection.profile_id != self._client.profile_id
                or projection.record_revision < change.expected_revision
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            current = self.read()
            if current.record_revision < projection.record_revision:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            return current
        except Exception as error:
            raise ProfileManagerCompletedViewUnavailableError(completed) from error


__all__ = ["HouseholdClient", "household_from_collection", "household_request"]
