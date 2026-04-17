"""Live smoke tests for the Docs sub-app.

Hits the scratch doc provisioned by ``aeat bootstrap``. Each test
appends a UUID-prefixed marker, verifies it appears in the rendered
plaintext, and removes it before exiting via ``replaceAllText``.
"""

from __future__ import annotations

from typing import Any

import pytest

from aeat.cli._docs_helpers import (
    build_append_request,
    build_replace_all_request,
    extract_plaintext,
    find_end_index,
)
from aeat.cli._live import (
    docs_service,
    requires_live_enabled,
    requires_scratch_doc,
    skip_if_drive_quota,
    unique_prefix,
)

pytestmark = [pytest.mark.live_read, pytest.mark.domain_infra]


class TestDocsLiveRoundTrip:
    """End-to-end Docs append-and-rollback round-trip."""

    def test_append_get_replace(self) -> None:
        requires_live_enabled()
        doc_id = requires_scratch_doc()

        service: Any = docs_service()
        marker = f"<{unique_prefix()}>"
        try:
            try:
                document = service.documents().get(documentId=doc_id).execute()
            except Exception as exc:
                skip_if_drive_quota(exc)
                return
            end_index = find_end_index(document)
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": build_append_request(marker, end_index)},
            ).execute()

            updated = service.documents().get(documentId=doc_id).execute()
            assert marker in extract_plaintext(updated)
        finally:
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": build_replace_all_request(marker, "")},
            ).execute()

        cleaned = service.documents().get(documentId=doc_id).execute()
        assert marker not in extract_plaintext(cleaned)
