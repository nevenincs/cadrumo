"""Live smoke test for the Google Workspace fixture surface.

Exercises the Drive + Sheets + Docs read paths against real,
project-owned fixtures configured via env vars. Every assertion
round-trips through the credential resolver and service builders that
future `@pytest.mark.live_read` tests use, so a passing run certifies
the Google integration path end-to-end.

The test is strictly opt-in. It collects only when both
`AEAT_LIVE_TESTS_ENABLED` and `AEAT_LIVE_TESTS_GOOGLE` are truthy in
the environment, matching `.vault/adr/2026-04-12-google-fixtures-adr.md`.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from aeat.adapters.outbound.google import (
    DOCS_SCOPE,
    DRIVE_SCOPE,
    SHEETS_SCOPE,
    build_docs_service,
    build_drive_service,
    build_sheets_service,
    get_credentials_for_scopes,
)
from aeat.core.config import Settings

SMOKE_SENTINEL = "aeat-fixture-smoke-ok"


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


_LIVE_ENABLED = _truthy(os.environ.get("AEAT_LIVE_TESTS_ENABLED"))
_GOOGLE_ENABLED = _truthy(os.environ.get("AEAT_LIVE_TESTS_GOOGLE"))
_RUN_GOOGLE_LIVE = _LIVE_ENABLED and _GOOGLE_ENABLED

pytestmark = [
    pytest.mark.live_read,
    pytest.mark.domain_core,
    pytest.mark.skipif(
        not _RUN_GOOGLE_LIVE,
        reason=(
            "Google fixture smoke test requires AEAT_LIVE_TESTS_ENABLED=1 and "
            "AEAT_LIVE_TESTS_GOOGLE=1 (dual opt-in)."
        ),
    ),
]


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="module")
def drive_service() -> Any:
    creds = get_credentials_for_scopes([DRIVE_SCOPE])
    return build_drive_service(creds)


@pytest.fixture(scope="module")
def sheets_service() -> Any:
    creds = get_credentials_for_scopes([SHEETS_SCOPE])
    return build_sheets_service(creds)


@pytest.fixture(scope="module")
def docs_service() -> Any:
    creds = get_credentials_for_scopes([DOCS_SCOPE])
    return build_docs_service(creds)


def _flatten_doc_body(document: dict[str, Any]) -> str:
    pieces: list[str] = []
    body = document.get("body", {})
    for element in body.get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for run_element in paragraph.get("elements", []):
            text_run = run_element.get("textRun")
            if not text_run:
                continue
            content = text_run.get("content")
            if isinstance(content, str):
                pieces.append(content)
    return "".join(pieces)


def test_fixture_ids_are_populated(settings: Settings) -> None:
    required = {
        "AEAT_GOOGLE_TEST_FIXTURES_FOLDER_ID": settings.aeat_google_test_fixtures_folder_id,
        "AEAT_GOOGLE_TEST_FIXTURE_SMOKE_SHEET_ID": settings.aeat_google_test_fixture_smoke_sheet_id,
        "AEAT_GOOGLE_TEST_FIXTURE_SMOKE_DOC_ID": settings.aeat_google_test_fixture_smoke_doc_id,
    }
    missing = [name for name, value in required.items() if not value]
    assert not missing, (
        f"fixture env vars are empty: {missing}. "
        "Run `uv run aeat bootstrap` (or set them manually) first."
    )


def test_root_folder_exists(drive_service: Any, settings: Settings) -> None:
    folder_id = settings.aeat_google_test_fixtures_folder_id
    response = drive_service.files().get(fileId=folder_id, fields="id, name, mimeType, trashed").execute()
    assert response.get("id") == folder_id
    assert response.get("mimeType") == "application/vnd.google-apps.folder"
    assert response.get("trashed") is False
    assert isinstance(response.get("name"), str)
    assert response.get("name")


def test_smoke_sheet_has_sentinel(sheets_service: Any, settings: Settings) -> None:
    sheet_id = settings.aeat_google_test_fixture_smoke_sheet_id
    response = sheets_service.spreadsheets().values().get(spreadsheetId=sheet_id, range="A1").execute()
    values = response.get("values") or []
    assert values, f"Sheet {sheet_id} has no value at A1 - re-run bootstrap"
    assert values[0][0] == SMOKE_SENTINEL


def test_smoke_doc_has_sentinel(docs_service: Any, settings: Settings) -> None:
    doc_id = settings.aeat_google_test_fixture_smoke_doc_id
    document = docs_service.documents().get(documentId=doc_id).execute()
    body_text = _flatten_doc_body(document)
    assert SMOKE_SENTINEL in body_text, (
        f"Doc {doc_id} body does not contain {SMOKE_SENTINEL!r}; "
        "re-run `uv run aeat bootstrap` to reseed scratch fixtures."
    )


def test_fixture_children_live_under_root(drive_service: Any, settings: Settings) -> None:
    root_id = settings.aeat_google_test_fixtures_folder_id
    fixture_ids = {
        "AEAT_GOOGLE_TEST_FIXTURE_SMOKE_SHEET_ID": settings.aeat_google_test_fixture_smoke_sheet_id,
        "AEAT_GOOGLE_TEST_FIXTURE_SMOKE_DOC_ID": settings.aeat_google_test_fixture_smoke_doc_id,
    }
    for fixture_name, resource_id in fixture_ids.items():
        metadata = drive_service.files().get(fileId=resource_id, fields="id, parents, trashed").execute()
        parents = metadata.get("parents") or []
        assert metadata.get("trashed") is False, f"fixture {fixture_name} is trashed"
        assert root_id in parents, (
            f"fixture {fixture_name} ({resource_id}) is not parented under "
            f"the root fixture folder {root_id}; parents={parents}"
        )
