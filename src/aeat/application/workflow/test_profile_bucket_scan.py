"""Real-behavior tests for profile-bucket manifest scanning."""

from __future__ import annotations

import ast
import inspect
import logging
from pathlib import Path
from types import ModuleType

import pytest

from . import _profile_bucket_scan
from ._profile_bucket_scan import list_profile_bucket_scan_issues, list_profile_buckets

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_FORBIDDEN_RUNTIME_BOUNDARY_REFERENCES = frozenset(
    {
        "BucketEventHistoryRepository",
        "SecureObjectRepository",
        "UserProfileLifecycleRepository",
        "UserProfileSnapshotRepository",
        "active_bucket_id_or_raise",
        "activate_master_key_provider",
        "get_master_key_provider",
        "inspect_bucket_storage_runtime",
        "profile_storage_session",
        "workflow_state_repository",
    }
)


def test_profile_bucket_scan_reports_malformed_manifest_without_live_surface_leak(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bucket_dir = tmp_path / "buckets" / "operator"
    bucket_dir.mkdir(parents=True)
    (bucket_dir / "manifest.toml").write_text("bucket_id = [\n", encoding="utf-8")

    with caplog.at_level(logging.DEBUG, logger="aeat.application.workflow._profile_bucket_scan"):
        pointers = list_profile_buckets(root=tmp_path)

    issues = list_profile_bucket_scan_issues(root=tmp_path)

    assert pointers == {}
    assert len(issues) == 1
    assert issues[0].bucket_id == "operator"
    assert issues[0].reason.startswith("TOMLDecodeError:")
    assert "skipping unreadable bucket manifest bucket_id=operator" in caplog.text


def test_profile_bucket_scan_stays_read_only_manifest_discovery_adapter() -> None:
    seen = _module_imported_and_referenced_names(_profile_bucket_scan)

    assert _FORBIDDEN_RUNTIME_BOUNDARY_REFERENCES.isdisjoint(seen)


def _module_imported_and_referenced_names(module: ModuleType) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.update(alias.name.split("."))
                names.add(alias.asname or alias.name.rsplit(".", maxsplit=1)[-1])
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                names.update(node.module.split("."))
            for alias in node.names:
                names.add(alias.name)
                if alias.asname is not None:
                    names.add(alias.asname)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names
