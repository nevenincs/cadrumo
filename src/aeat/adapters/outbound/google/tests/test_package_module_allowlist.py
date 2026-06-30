"""Module allow-list for the Google OAuth Desktop adapter package.

Pins the exact set of `.py` files under
`src/aeat/adapters/outbound/google/`. A new untracked file fails the
gate so module additions are deliberate.

The test introspects the source tree directly (not via Python import)
so it stays runnable even when the broader import chain is broken.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_PACKAGE_ROOT = Path(__file__).resolve().parent

_ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "_api.py",
        "_calc_sheets_apply.py",
        "_calc_sheets_pull.py",
        "_document_link_resolver.py",  # follow-up contract: scope-compatible Drive doclink resolution
        "_drive_media_server.py",  # contract: real local Drive media endpoint for resolver roundtrips
        "_errors.py",
        "_oauth_flow.py",
        "_active_profile.py",
        "_records.py",
        "_session_store.py",
        "test_api.py",  # contract: execute_request typed response + error-translation contract
        "test_apply_adapter_helpers.py",
        "test_calc_sheets_apply.py",
        "test_calc_sheets_apply_evidence.py",  # online Evidencia render + offline/online evidence parity
        "test_calc_sheets_export_integration.py",  # offline request-pipeline integration for live export
        "test_calc_sheets_offline_online_conformance.py",  # offline/online renderer conformance
        "test_calc_sheets_pull_typing.py",  # contract: _ValueRange / _GoogleResource type-narrowing contract
        "test_calc_sheets_row_set_headers.py",
        "test_column_index_to_letters.py",
        "test_compute_from_pull.py",
        "test_document_link_resolver.py",  # follow-up contract: doclink resolver scope-refusal + parse contract
        "test_document_link_resolve_roundtrip.py",  # contract: doclink fetch-and-encrypt-or-refuse over real storage
        "test_grid_resize.py",
        "test_oauth_flow.py",  # contract: OAuth local-server failures stay inside GoogleAuthError
        "test_oauth_live.py",
        "test_package_module_allowlist.py",
        "test_active_profile.py",  # contract: active-profile resolver localized refusal contract
        "test_pull_adapter_helpers.py",
        "test_pull_result_roundtrip.py",
        "test_records.py",
        "test_session_store_roundtrip.py",
        "test_verify_pull_coverage.py",
        "test_worksheet_export_pull_roundtrip.py",
    },
)


def test_google_package_directory_exists() -> None:
    assert _PACKAGE_ROOT.is_dir(), (
        f"expected {_PACKAGE_ROOT} to exist; if the package was deleted by mistake, restore it"
    )


def test_only_allowed_modules_present_in_package() -> None:
    """Every `.py` in the package must be on the allow-list.

    A new untracked `.py` file means somebody added a module without
    updating the allow-list above. Either add it to `_ALLOWED_MODULES`
    with rationale or remove the file.
    """

    found_files = {entry.name for entry in _PACKAGE_ROOT.iterdir() if entry.is_file() and entry.suffix == ".py"}
    unexpected = sorted(found_files - _ALLOWED_MODULES)
    assert unexpected == [], (
        f"unexpected .py files in {_PACKAGE_ROOT.name}: {unexpected}; add to _ALLOWED_MODULES with rationale or remove"
    )
