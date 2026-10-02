"""Canonical result pages bind every continuation to one complete document."""

from __future__ import annotations

import json

import pytest
from pydantic import JsonValue, ValidationError

from ....core.hashing import canonical_json_bytes, sha256_hex
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..projection_pages import PROJECTION_PAGE_BYTES, ProjectionPage, ProjectionPageRequest, project_document_page

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_utf8_spanning_page_boundary_reassembles_exact_canonical_document() -> None:
    """Pages are byte slices even when a multibyte character spans a boundary."""
    document: dict[str, JsonValue] = {"text": "ñ" * 20_000, "count": 7}
    expected = canonical_json_bytes(document)
    assert expected[PROJECTION_PAGE_BYTES - 1 : PROJECTION_PAGE_BYTES + 1] == "ñ".encode()

    chunks: list[bytes] = []
    offset = 0
    digest: str | None = None
    while offset < len(expected):
        page = project_document_page(document, ProjectionPageRequest(offset=offset, expected_digest=digest))
        chunks.append(page.decode())
        assert page.offset == offset
        assert page.total_bytes == len(expected)
        assert page.document_digest == sha256_hex(expected)
        digest = page.document_digest
        offset += len(chunks[-1])

    assert b"".join(chunks) == expected
    assert json.loads(b"".join(chunks)) == document


def test_continuation_requires_and_checks_original_document_digest() -> None:
    text = "x" * (PROJECTION_PAGE_BYTES + 1)
    document: dict[str, JsonValue] = {"text": text}
    first = project_document_page(document, ProjectionPageRequest())
    with pytest.raises(ValidationError):
        ProjectionPageRequest(offset=PROJECTION_PAGE_BYTES)
    with pytest.raises(ProfileAccessRefusedError) as stale:
        project_document_page(
            {"text": text + "changed"},
            ProjectionPageRequest(
                offset=PROJECTION_PAGE_BYTES,
                expected_digest=first.document_digest,
            ),
        )
    assert stale.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    with pytest.raises(ProfileAccessRefusedError):
        project_document_page(
            document, ProjectionPageRequest(offset=first.total_bytes, expected_digest=first.document_digest)
        )


@pytest.mark.parametrize("encoded", ["!!!!", "e31=", "e30=="])
def test_projection_page_refuses_malformed_or_noncanonical_base64(encoded: str) -> None:
    original = project_document_page({}, ProjectionPageRequest())
    with pytest.raises(ValidationError):
        ProjectionPage.model_validate({**original.model_dump(), "encoded": encoded})


def test_projection_page_refuses_inconsistent_range() -> None:
    original = project_document_page({}, ProjectionPageRequest())
    with pytest.raises(ValidationError):
        ProjectionPage.model_validate({**original.model_dump(), "offset": 1})
