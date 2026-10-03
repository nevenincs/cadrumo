"""Actual Drive resolver callbacks admit every request outside error translation."""

from __future__ import annotations

import pytest

from .....application.user_profile.access_contracts import AccessDenialCode
from .....application.user_profile.access_errors import ProfileAccessRefusedError
from .....domain.attachments.enums import AttachmentSource
from ..document_link_resolver import list_drive_folder_documents, resolve_document_link

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class MediaRequest:
    """Controlled media request with a visible invocation count."""

    def __init__(self) -> None:
        self.calls = 0

    def execute(self) -> bytes:
        """Return synthetic content without any network or credential access."""
        self.calls += 1
        return b"%PDF-synthetic"


class PageRequest:
    """Controlled two-page listing preserving the canonical pagination loop."""

    def __init__(self, page: int) -> None:
        self.page = page
        self.calls = 0

    def execute(self, num_retries: int = 0) -> dict[str, object]:
        """Return safe synthetic provider metadata."""
        self.calls += 1
        if self.page == 0:
            return {
                "files": [{"id": "first", "name": "First.pdf", "mimeType": "application/pdf"}],
                "nextPageToken": "next",
            }
        return {"files": [{"id": "second", "name": "Second.pdf", "mimeType": "application/pdf"}]}


class Files:
    """Match the resolver's declared Drive SDK request interfaces."""

    def __init__(self) -> None:
        self.media = MediaRequest()
        self.pages: list[PageRequest] = []

    def get_media(self, **request: object) -> MediaRequest:
        """Build the existing media request shape."""
        return self.media

    def list(self, **request: object) -> PageRequest:
        """Build each canonical pagination request once."""
        page = PageRequest(len(self.pages))
        self.pages.append(page)
        return page


class Drive:
    """Controlled SDK service; no mocked native or product acceptance claim."""

    def __init__(self) -> None:
        self.resource = Files()

    def files(self) -> Files:
        """Expose the resolver's declared files resource."""
        return self.resource


def test_media_admission_failure_retains_original_refusal_and_never_executes() -> None:
    """A current authority refusal must bypass provider failure translation."""
    service = Drive()
    refusal = ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    def deny() -> None:
        raise refusal

    with pytest.raises(ProfileAccessRefusedError) as raised:
        resolve_document_link(
            source=AttachmentSource.GOOGLE_DRIVE,
            reference="https://drive.google.com/file/d/synthetic1234567890",
            service=service,
            before_request=deny,
        )
    assert raised.value is refusal and service.resource.media.calls == 0


def test_each_list_page_renews_authority_and_second_refusal_never_executes() -> None:
    """Listing the first page cannot grant implicit authority for later pages."""
    service = Drive()
    admissions = 0
    refusal = ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    def admit() -> None:
        nonlocal admissions
        admissions += 1
        if admissions == 2:
            raise refusal

    with pytest.raises(ProfileAccessRefusedError) as raised:
        list_drive_folder_documents(folder_id="synthetic-folder", service=service, before_request=admit)
    assert raised.value is refusal and admissions == 2
    assert [page.calls for page in service.resource.pages] == [1, 0]
