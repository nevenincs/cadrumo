"""The off-host release bar reads the exact profile's own setting and refuses what it cannot read.

The profile owner's capability policy and the service's view of the facts run for
real; only the registered read's transport is replaced, as the sibling profile
client tests replace it. The same read over a real runtime is asserted where the
runtime's fixtures live.
"""

from __future__ import annotations

from typing import Final, override
from uuid import UUID, uuid4

import pytest

from cadrumo.application.user_profile.view_operation import (
    ProfileViewFactItem,
    ProfileViewItem,
    ProfileViewOperationProjection,
    ProfileViewPageKind,
)
from cadrumo.core.capabilities import ServiceCapability
from cadrumo.core.config import Settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError, ProfileViewCollection
from cadrumo_client.transport.service_profile_view import InstalledServiceProfileView

from ...providers.application.attachment_releases import DisclosureRefusalCode
from ...providers.application.tests.runtime_connection import RuntimeConnection, service_client, synthetic_lease
from ..profile_cloud_eligibility import ProfileCloudEligibilityRead, disclosure_bar

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIGEST: Final[ContentDigest] = "a" * 64
_PATH: Final = ServiceCapability.CLOUD_EVIDENCE_UPLOAD.schema_path


class _ServedProfile(InstalledServiceProfileView):
    """The service's real profile view, answering the registered read from synthetic facts."""

    def __init__(self, *, facts: dict[str, str], failure: Exception | None = None, profile_id: UUID | None = None):
        connection = RuntimeConnection(synthetic_lease())
        super().__init__(service_client(connection))
        self.facts = facts
        self.failure = failure
        self.served_profile = self.profile_id if profile_id is None else profile_id
        self.reads = 0
        self.timeouts: list[float] = []

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
        self.reads += 1
        self.timeouts.append(timeout)
        if self.failure is not None:
            raise self.failure
        items: tuple[ProfileViewItem, ...] = tuple(
            ProfileViewFactItem(path=path, value=value) for path, value in self.facts.items()
        )
        page = ProfileViewOperationProjection(
            profile_id=self.served_profile,
            page_kind=ProfileViewPageKind.FACTS,
            outcome="page",
            record_revision=3,
            content_digest=_DIGEST,
            setup_state=ProfileSetupState.COMPLETE,
            schema_version=1,
            valid=True,
            cursor=0,
            total_items=len(items),
            items=items,
        )
        return ProfileViewCollection(
            profile_id=self.served_profile,
            record_revision=3,
            content_digest=_DIGEST,
            setup_state=ProfileSetupState.COMPLETE,
            schema_version=1,
            valid=True,
            page_kinds=page_kinds,
            pages=(page,),
        )


def _read(view: _ServedProfile) -> ProfileCloudEligibilityRead:
    return ProfileCloudEligibilityRead(view=view, timeout_seconds=4.0)


def _settings(*, permitted: bool = True, gestor: bool = False) -> Settings:
    return Settings(cadrumo_evidence_gestor_mode=gestor, cadrumo_evidence_cloud_upload_permitted=permitted)


def test_a_profile_that_enabled_the_setting_under_an_opted_in_deployment_has_no_bar() -> None:
    view = _ServedProfile(facts={_PATH: "true", "identity.tax_id": "00000000T"})

    assert disclosure_bar(_read(view), _settings()) is None
    assert view.timeouts == [4.0]


def test_a_profile_that_disabled_the_setting_is_not_eligible() -> None:
    assert (
        disclosure_bar(_read(_ServedProfile(facts={_PATH: "false"})), _settings())
        is DisclosureRefusalCode.PROFILE_NOT_ELIGIBLE
    )


def test_a_profile_that_never_chose_is_not_eligible_because_the_owner_defaults_off() -> None:
    assert (
        disclosure_bar(_read(_ServedProfile(facts={"identity.tax_id": "00000000T"})), _settings())
        is DisclosureRefusalCode.PROFILE_NOT_ELIGIBLE
    )


@pytest.mark.parametrize(
    "failure",
    [
        FrontendRefusedError(AccessDenialCode.SESSION_INACTIVE.value),
        RefusalError(RefusalCode.TIMEOUT),
        TimeoutError("synthetic"),
        ConnectionResetError("synthetic"),
        ValueError("synthetic malformed answer"),
    ],
    ids=lambda failure: type(failure).__name__,
)
def test_a_profile_that_cannot_be_read_is_never_taken_for_an_opt_in(failure: Exception) -> None:
    read = _read(_ServedProfile(facts={_PATH: "true"}, failure=failure))

    assert disclosure_bar(read, _settings()) is DisclosureRefusalCode.PROFILE_UNREADABLE


def test_an_answer_for_another_profile_is_unreadable_not_eligible() -> None:
    view = _ServedProfile(facts={_PATH: "true"}, profile_id=uuid4())

    assert disclosure_bar(_read(view), _settings()) is DisclosureRefusalCode.PROFILE_UNREADABLE


def test_gestor_mode_refuses_first_and_the_profile_is_not_asked() -> None:
    view = _ServedProfile(facts={_PATH: "true"})

    assert disclosure_bar(_read(view), _settings(gestor=True)) is DisclosureRefusalCode.GESTOR_MODE
    assert view.reads == 0


def test_a_deployment_that_did_not_opt_in_refuses_before_the_profile_is_asked() -> None:
    view = _ServedProfile(facts={_PATH: "true"})

    assert disclosure_bar(_read(view), _settings(permitted=False)) is DisclosureRefusalCode.CLOUD_UPLOAD_NOT_PERMITTED
    assert view.reads == 0


def test_every_decision_reads_the_profile_again() -> None:
    view = _ServedProfile(facts={_PATH: "true"})
    read = _read(view)

    assert disclosure_bar(read, _settings()) is None
    view.facts = {_PATH: "false"}
    assert disclosure_bar(read, _settings()) is DisclosureRefusalCode.PROFILE_NOT_ELIGIBLE
    view.failure = FrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
    assert disclosure_bar(read, _settings()) is DisclosureRefusalCode.PROFILE_UNREADABLE
    assert view.reads == 3
