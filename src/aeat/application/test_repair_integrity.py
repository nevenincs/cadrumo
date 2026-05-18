"""Tests for the repair integrity + list subverb backends."""

from __future__ import annotations

from typing import Any

import pytest

from aeat.adapters.persistence.storage.sql.secure_objects import (
    SecureObjectNamespaceIntegrity,
)
from aeat.application.repair_integrity import (
    build_repair_integrity_report,
    build_repair_list_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


class _StubRepository:
    """In-memory stand-in for SecureObjectRepository."""

    def __init__(self, namespaces: dict[str, dict[str, Any]]) -> None:
        # namespaces: { ns_name: { "readable": int, "unreadable": int, "keys": [str, ...] } }
        self._namespaces = namespaces

    def list_namespaces(self) -> tuple[str, ...]:
        return tuple(sorted(self._namespaces.keys()))

    def probe_namespace_integrity(self, namespace: str) -> SecureObjectNamespaceIntegrity:
        data = self._namespaces.get(namespace, {"readable": 0, "unreadable": 0, "keys": []})
        return SecureObjectNamespaceIntegrity(
            namespace=namespace,
            readable=data["readable"],
            unreadable=data["unreadable"],
        )

    def list_keys(self, namespace: str) -> tuple[str, ...]:
        return tuple(self._namespaces.get(namespace, {"keys": []})["keys"])


class TestBuildIntegrityReport:
    def test_clean_install_reports_ok(self) -> None:
        repo = _StubRepository(
            {
                "aeat.workflow": {"readable": 5, "unreadable": 0, "keys": []},
                "aeat.profile.bucket": {"readable": 3, "unreadable": 0, "keys": []},
            },
        )
        report = build_repair_integrity_report(repository=repo)
        assert report.readable_total == 8
        assert report.unreadable_total == 0
        assert report.check.status == "ok"
        assert report.check.next_action is None or report.check.next_action == ""
        assert report.check.dead_end is None or report.check.dead_end == ""

    def test_undecryptable_rows_surface_fail_with_next_action(self) -> None:
        repo = _StubRepository(
            {
                "aeat.workflow": {"readable": 5, "unreadable": 2, "keys": []},
                "aeat.profile.bucket": {"readable": 3, "unreadable": 0, "keys": []},
            },
        )
        report = build_repair_integrity_report(repository=repo)
        assert report.unreadable_total == 2
        assert report.check.status == "fail"
        assert report.check.next_action == "aeat config repair quarantine --yes"

    def test_namespace_filter_restricts_scope(self) -> None:
        repo = _StubRepository(
            {
                "aeat.workflow": {"readable": 5, "unreadable": 2, "keys": []},
                "aeat.profile.bucket": {"readable": 3, "unreadable": 0, "keys": []},
            },
        )
        report = build_repair_integrity_report(repository=repo, namespace="aeat.profile.bucket")
        assert len(report.namespaces) == 1
        assert report.namespaces[0].namespace == "aeat.profile.bucket"
        assert report.unreadable_total == 0
        assert report.check.status == "ok"


class TestBuildListReport:
    def test_list_returns_all_keys_in_namespace(self) -> None:
        repo = _StubRepository(
            {
                "aeat.workflow": {
                    "readable": 3,
                    "unreadable": 0,
                    "keys": ["digest-a", "digest-b", "digest-c"],
                },
            },
        )
        report = build_repair_list_report(namespace="aeat.workflow", repository=repo)
        assert report.namespace == "aeat.workflow"
        assert report.rows_total == 3
        assert tuple(r.object_key_digest for r in report.rows) == (
            "digest-a",
            "digest-b",
            "digest-c",
        )
        assert report.integrity.readable == 3

    def test_list_filter_mode_reflects_flag_selection(self) -> None:
        repo = _StubRepository({"aeat.workflow": {"readable": 0, "unreadable": 0, "keys": []}})
        default = build_repair_list_report(namespace="aeat.workflow", repository=repo)
        assert default.filter_mode == "default"
        all_mode = build_repair_list_report(
            namespace="aeat.workflow",
            include_all=True,
            repository=repo,
        )
        assert all_mode.filter_mode == "all"
        unreadable_mode = build_repair_list_report(
            namespace="aeat.workflow",
            only_unreadable=True,
            repository=repo,
        )
        assert unreadable_mode.filter_mode == "unreadable"

    def test_list_refuses_when_both_flags_passed(self) -> None:
        repo = _StubRepository({"aeat.workflow": {"readable": 0, "unreadable": 0, "keys": []}})
        with pytest.raises(ValueError, match="cannot combine"):
            build_repair_list_report(
                namespace="aeat.workflow",
                include_all=True,
                only_unreadable=True,
                repository=repo,
            )

    def test_list_empty_namespace_returns_zero_rows(self) -> None:
        repo = _StubRepository({"empty.ns": {"readable": 0, "unreadable": 0, "keys": []}})
        report = build_repair_list_report(namespace="empty.ns", repository=repo)
        assert report.rows_total == 0
        assert report.rows == ()


class TestReportInvariants:
    def test_integrity_report_is_frozen(self) -> None:
        from pydantic import ValidationError

        repo = _StubRepository({"aeat.workflow": {"readable": 1, "unreadable": 0, "keys": []}})
        report = build_repair_integrity_report(repository=repo)
        with pytest.raises(ValidationError):
            report.readable_total = 99  # type: ignore[misc]
