"""Live smoke test for the Google Workspace fixture surface.

Exercises the Drive + Sheets + Docs read paths against the real,
project-owned fixtures provisioned by
``scripts/provision_google_fixtures.py``. Every assertion round-trips
through the credential resolver, service builders, and fixture
catalogue that any future `@pytest.mark.live` test will use, so a
passing run certifies the entire Google integration path end-to-end.

The test is **strictly opt-in**. It collects only when both

* ``AEAT_LIVE_TESTS_ENABLED`` and
* ``AEAT_LIVE_TESTS_GOOGLE``

are truthy in the environment, matching the dual opt-in decided in
``.vault/adr/2026-04-12-google-fixtures-adr.md``. The default CI and
local ``just test`` invocations skip it cleanly.

Per project policy, this module never imports or references any
mocking, patching, stubbing, or fake-service library. Live tests in
this project hit real services or they do not run.
"""

from __future__ import annotations

import importlib.util
import os
from types import ModuleType
from typing import Any

import pytest

from aeat.auth import (
    DOCS_SCOPE,
    DRIVE_SCOPE,
    SHEETS_SCOPE,
    build_docs_service,
    build_drive_service,
    build_sheets_service,
    get_credentials_for_scopes,
)
from aeat.config import PROJECT_ROOT, Settings


def _load_fixture_catalogue() -> ModuleType:
    """Dynamically load ``scripts/_fixture_catalogue.py`` as a module.

    The ``scripts/`` directory is not a package (it is the project's
    documented non-src tooling escape hatch — see ``scripts/README.md``)
    so it cannot be imported via a static ``import`` statement without
    polluting ``sys.path``. ``importlib.util.spec_from_file_location``
    loads it by absolute path at test-run time, keeping the import
    graph clean and the type-checker happy.

    Returns:
        The loaded module, exposing ``CATALOGUE``, ``SMOKE_SENTINEL``,
        and ``FixtureKind``.
    """
    module_path = PROJECT_ROOT / "scripts" / "_fixture_catalogue.py"
    spec = importlib.util.spec_from_file_location("_fixture_catalogue", module_path)
    if spec is None or spec.loader is None:
        msg = f"could not build import spec for {module_path}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_catalogue_module = _load_fixture_catalogue()
CATALOGUE = _catalogue_module.CATALOGUE
SMOKE_SENTINEL: str = _catalogue_module.SMOKE_SENTINEL
FixtureKind = _catalogue_module.FixtureKind


def _truthy(value: str | None) -> bool:
    """Return True for common truthy env-var spellings ("1", "true", "yes").

    Args:
        value: Raw env var value, or ``None`` if unset.

    Returns:
        Boolean verdict. Anything else (including ``None``, ``""``,
        ``"0"``, ``"false"``) evaluates to False.
    """
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


_LIVE_ENABLED = _truthy(os.environ.get("AEAT_LIVE_TESTS_ENABLED"))
_GOOGLE_ENABLED = _truthy(os.environ.get("AEAT_LIVE_TESTS_GOOGLE"))

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (_LIVE_ENABLED and _GOOGLE_ENABLED),
        reason=(
            "Google fixture smoke test requires AEAT_LIVE_TESTS_ENABLED=1 and AEAT_LIVE_TESTS_GOOGLE=1 (dual opt-in)."
        ),
    ),
]


@pytest.fixture(scope="module")
def settings() -> Settings:
    """Load application settings for the live test module."""
    return Settings()


@pytest.fixture(scope="module")
def drive_service() -> Any:
    """Authenticated Drive v3 service scoped to Drive access only."""
    creds = get_credentials_for_scopes([DRIVE_SCOPE])
    return build_drive_service(creds)


@pytest.fixture(scope="module")
def sheets_service() -> Any:
    """Authenticated Sheets v4 service scoped to spreadsheet access only."""
    creds = get_credentials_for_scopes([SHEETS_SCOPE])
    return build_sheets_service(creds)


@pytest.fixture(scope="module")
def docs_service() -> Any:
    """Authenticated Docs v1 service scoped to documents access only."""
    creds = get_credentials_for_scopes([DOCS_SCOPE])
    return build_docs_service(creds)


def _flatten_doc_body(document: dict[str, Any]) -> str:
    """Concatenate every text run in a Google Doc body into one string.

    The Docs API represents body content as a tree of structural
    elements; only ``paragraph.elements[*].textRun.content`` carries
    user-visible text. We walk the tree and join every text run in
    document order so the smoke test can assert on a simple substring.

    Args:
        document: The ``documents.get`` response body.

    Returns:
        The document body flattened into a single string.
    """
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


def test_fixture_catalogue_ids_are_populated(settings: Settings) -> None:
    """Every catalogue env var must carry a non-empty ID in the loaded settings.

    Catches the common "ran the test before provisioning" mistake with a
    clearer message than a Google 404 would provide.
    """
    missing: list[str] = []
    for spec in CATALOGUE:
        value = getattr(settings, spec.env_var_name.lower(), "")
        if not value:
            missing.append(spec.env_var_name)
    assert not missing, f"fixture env vars are empty: {missing}. Run `just google-fixtures-provision` first."


def test_root_folder_exists(drive_service: Any, settings: Settings) -> None:
    """The root fixture folder must exist and be readable under the active creds."""
    folder_id = settings.aeat_google_test_fixtures_folder_id
    response = drive_service.files().get(fileId=folder_id, fields="id, name, mimeType, trashed").execute()
    assert response.get("id") == folder_id
    assert response.get("mimeType") == "application/vnd.google-apps.folder"
    assert response.get("trashed") is False
    root_spec = CATALOGUE.root_folder_spec()
    assert response.get("name") == root_spec.title


def test_smoke_sheet_has_sentinel(sheets_service: Any, settings: Settings) -> None:
    """The smoke-test Sheet's cell A1 must hold the catalogue sentinel."""
    sheet_id = settings.aeat_google_test_fixture_smoke_sheet_id
    response = sheets_service.spreadsheets().values().get(spreadsheetId=sheet_id, range="A1").execute()
    values = response.get("values") or []
    assert values, f"Sheet {sheet_id} has no value at A1 — re-run provisioning"
    assert values[0][0] == SMOKE_SENTINEL


def test_smoke_doc_has_sentinel(docs_service: Any, settings: Settings) -> None:
    """The smoke-test Doc's body must contain the catalogue sentinel."""
    doc_id = settings.aeat_google_test_fixture_smoke_doc_id
    document = docs_service.documents().get(documentId=doc_id).execute()
    body_text = _flatten_doc_body(document)
    assert SMOKE_SENTINEL in body_text, (
        f"Doc {doc_id} body does not contain {SMOKE_SENTINEL!r}; "
        "re-run `just google-fixtures-teardown` followed by "
        "`just google-fixtures-provision`."
    )


def test_every_catalogued_child_lives_under_root(drive_service: Any, settings: Settings) -> None:
    """Every non-root fixture must be a direct child of the root folder.

    Guards against catalogue / provisioning drift where a fixture ends
    up orphaned under My Drive root instead of the dedicated container.
    """
    root_id = settings.aeat_google_test_fixtures_folder_id
    for spec in CATALOGUE:
        if spec.kind is FixtureKind.DRIVE_FOLDER and spec.parent_id is None:
            continue
        resource_id = getattr(settings, spec.env_var_name.lower(), "")
        metadata = drive_service.files().get(fileId=resource_id, fields="id, parents, trashed").execute()
        parents = metadata.get("parents") or []
        assert metadata.get("trashed") is False, f"fixture {spec.fixture_id} is trashed"
        assert root_id in parents, (
            f"fixture {spec.fixture_id} ({resource_id}) is not parented under "
            f"the root fixture folder {root_id}; parents={parents}"
        )
