"""Module allow-list for the Google OAuth Desktop adapter tests package.

Pins the accepted ``.py`` files in the directory containing this test. A
new untracked test module fails the gate so additions are deliberate and
carry local rationale in ``_ALLOWED_MODULES``; stale allow-list entries
are enforced for test modules by the ``test_`` prefix. The test
introspects the source tree directly rather than importing the package,
so it stays runnable even when the broader import chain is broken during
adapter restructuring.

See Also:
    :mod:`~adapters.outbound.google`
        Public Google outbound adapter facade whose colocated tests are
        guarded by this inventory check.
    :mod:`~adapters.outbound.google.oauth_flow`
        Desktop OAuth flow surface whose legacy predecessors remain outside
        the allowed module list.
    :mod:`~adapters.outbound.google.session_store`
        Secure per-profile OAuth session persistence enrolled as a deliberate
        package module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_PACKAGE_ROOT = Path(__file__).resolve().parent

_ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "api.py",
        "calc_sheets_apply.py",
        "_calc_sheets_apply_formatting.py",  # pure Sheets presentation and validation request builders
        "calc_sheets_pull.py",
        "calc_sheets_pull_coverage.py",  # export-plan versus pull structural coverage validator
        "calc_sheets_pull_records.py",  # typed Google Sheets pull wire records and payload projection
        "_calc_sheets_support.py",  # shared modelo-130 registry snapshot fixture builder
        "test_calc_sheets_transport_facet_parity.py",  # contract: offline/online transports render the same plan facets (alignment, protection)
        "document_link_resolver.py",  # follow-up contract: scope-compatible Drive doclink resolution
        "_drive_entries.py",  # shared Drive owned-entry query escaping, lookup/backfill policy, and id validation
        "drive_media_server.py",  # contract: real local Drive media endpoint for resolver roundtrips
        "errors.py",
        "impersonation.py",  # service-account impersonation credential source
        "oauth_flow.py",
        "active_profile.py",
        "_records.py",
        "session_store.py",
        "test_session_store_logout_atomicity.py",  # contract: logout removes the token and its companion metadata, or neither
        "test_auth_preconditions.py",  # contract: every Google-auth refusal producer states its terminal precondition
        "test_calc_sheets_typed_outcomes.py",  # contract: the calculation-sheet adapters return typed terminal outcomes
        "test_preconditions_structure.py",  # contract: terminal-precondition transport stays owned by its declaring module
        "test_session_store_namespace_binding.py",  # contract: session-store secure-object namespace-binding roundtrip
        "test_api.py",  # contract: execute_request typed response + error-translation contract
        "test_api_typeddicts.py",  # contract: API response TypedDicts declare their required keys
        "test_apply_adapter_helpers.py",
        "test_calc_sheets_apply_evidence.py",  # online Evidencia render + offline/online evidence parity
        "test_calc_sheets_apply_no_empty_window.py",  # apply never leaves the workbook empty (write-then-clear-stale ordering)
        "test_calc_sheets_export_integration.py",  # offline request-pipeline integration for live export
        "test_calc_sheets_export_preview.py",  # dry-run export preview: pure diff + never-writes structural proof
        "test_calc_sheets_offline_online_conformance.py",  # offline/online renderer conformance
        "test_calc_sheets_pull_typing.py",  # contract: _ValueRange / _GoogleResource type-narrowing contract
        "test_calc_sheets_row_set_headers.py",
        "test_column_index_to_letters.py",
        "test_compute_from_pull.py",
        "test_document_link_resolver.py",  # follow-up contract: doclink resolver scope-refusal + parse contract
        "test_document_link_resolve_roundtrip.py",  # contract: doclink fetch-and-encrypt-or-refuse over real storage
        "test_drive_entries.py",  # contract: shared owned-entry query escaping, id validation, ownership policy
        "test_drive_folder_listing.py",  # contract: Drive-folder bulk listing/filter/pagination/refusal
        "test_drive_folder_bulk_fetch_roundtrip.py",  # contract: folder sweep fetch-and-encrypt-or-refuse
        "test_grid_resize.py",
        "test_impersonation.py",  # service-account ADC discovery, IAM refusal, and config validation
        "test_impersonation_live.py",  # live opt-in IAM token minting for provisioned service accounts
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

    found_files = {entry.name for entry in scan_directory(_PACKAGE_ROOT) if entry.is_file() and entry.suffix == ".py"}
    unexpected = sorted(found_files - _ALLOWED_MODULES)
    missing_tests = sorted(name for name in _ALLOWED_MODULES - found_files if name.startswith("test_"))
    assert unexpected == [], (
        f"unexpected .py files in {_PACKAGE_ROOT.name}: {unexpected}; add to _ALLOWED_MODULES with rationale or remove"
    )
    assert missing_tests == [], (
        f"allowed test .py files missing from {_PACKAGE_ROOT.name}: {missing_tests}; "
        "remove stale _ALLOWED_MODULES entries or restore the files"
    )
