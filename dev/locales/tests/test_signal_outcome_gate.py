"""The locale gate fails on blocking findings only and keeps advisory findings visible."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .. import _signal as signal_module
from .. import cli as cli_module
from .. import signal_discovery as discovery_module
from ..cli import app
from ..manager import LocaleManager
from ..signal_report import is_advisory_finding, signal_outcome

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ADVISORY: dict[str, object] = {
    "classification": "advisory",
    "kind": "docs_translation_invariant_echo",
    "message_id": "Cadrumo",
}
_BLOCKING: dict[str, object] = {
    "classification": "blocking",
    "kind": "docs_translation_source_echo",
    "message_id": "Save",
}


_PARALLEL_COUNTERS = (
    "parallel_localization_declarations",
    "invalid_data_files",
    "docs_extraction_failures",
    "docs_source_drift_pages",
    "docs_translation_source_echo",
    "docs_orphan_catalogue_files",
    "docs_missing_catalogue_files",
    "docs_generated_source_failures",
)


def _clean_parallel_inventory(
    repository: Path, *, spelling_values: dict[str, dict[str, str]] | None = None
) -> tuple[dict[str, object], list[dict[str, object]]]:
    return dict.fromkeys(_PARALLEL_COUNTERS, 0), []


def _clean_spelling(
    required_keys: set[str],
    locale_leaves: dict[str, dict[str, object]],
    repository: Path,
    *,
    additional_values: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[tuple[str, str], tuple[str, ...]], dict[str, object], list[dict[str, object]]]:
    return {}, {"spelling_tool_failures": 0, "spelling_unknown_cells": 0}, []


@pytest.fixture
def clean_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocaleManager:
    """A manager whose real audit finds nothing, so injected findings are the only variable."""
    source = tmp_path / "source"
    source.mkdir()
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "en.yml").write_text("{}\n", encoding="utf-8")
    manager = LocaleManager(source, locales)
    monkeypatch.setattr(manager, "get_codebase_keys", lambda: set())
    monkeypatch.setattr(manager, "get_codebase_namespaces", lambda: set())
    monkeypatch.setattr(discovery_module, "dynamic_key_families", lambda markers: ({}, ()))
    # The environment-bound producers (document tree, pinned dictionaries) are held at
    # their clean state so the classification gate is the only variable under test.
    monkeypatch.setattr(signal_module, "parallel_localization_inventory", _clean_parallel_inventory)
    monkeypatch.setattr(signal_module, "spellcheck_catalogues", _clean_spelling)
    monkeypatch.setattr(
        cli_module, "locale_signal", lambda manager: signal_module.locale_signal(manager, repository=tmp_path)
    )
    return manager


def _inject_parallel_findings(monkeypatch: pytest.MonkeyPatch, findings: list[dict[str, object]]) -> None:
    """Add producer findings after the clean inventory so the real gate classifies them."""

    def inventory(
        repository: Path, *, spelling_values: dict[str, dict[str, str]] | None = None
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        counts, real = _clean_parallel_inventory(repository, spelling_values=spelling_values)
        return counts, [*real, *findings]

    monkeypatch.setattr(signal_module, "parallel_localization_inventory", inventory)


def _section(payload: Mapping[str, object], key: str) -> dict[str, object]:
    """Narrow one JSON object member to an object, failing loudly on any other shape."""
    value = payload[key]
    assert isinstance(value, dict)
    return {str(name): member for name, member in value.items()}


def _detail_findings(payload: Mapping[str, object]) -> list[object]:
    """Narrow the detail findings member to a list."""
    findings = _section(payload, "details")["findings"]
    assert isinstance(findings, list)
    return [finding for finding in findings]


def _status_exit(manager: LocaleManager, *, check: bool) -> tuple[int, dict[str, object]]:
    args = ["status", "--json", *(["--check"] if check else [])]
    result = CliRunner().invoke(app, args, obj=manager)
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, dict)
    return result.exit_code, {str(name): member for name, member in parsed.items()}


def test_clean_audit_is_complete_and_passes(clean_manager: LocaleManager, tmp_path: Path) -> None:
    payload = signal_module.locale_signal(clean_manager, repository=tmp_path)

    assert payload["outcome"] == "complete"
    assert payload["details"]["findings"] == []
    assert _status_exit(clean_manager, check=True)[0] == 0


def test_advisory_only_findings_pass_the_check_and_stay_visible(
    clean_manager: LocaleManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _inject_parallel_findings(monkeypatch, [_ADVISORY, {**_ADVISORY, "message_id": "Modelo"}])

    code, payload = _status_exit(clean_manager, check=True)

    assert code == 0
    assert payload["outcome"] == "advisory"
    assert _section(payload, "details")["findings"] == [_ADVISORY, {**_ADVISORY, "message_id": "Modelo"}]
    assert _section(payload, "summary")["findings"] == {"blocking": 0, "advisory": 2, "total": 2}
    assert "2 advisory findings" in str(payload["headline"])
    assert "No blocking" in str(payload["headline"])


def test_blocking_finding_fails_the_check(clean_manager: LocaleManager, monkeypatch: pytest.MonkeyPatch) -> None:
    _inject_parallel_findings(monkeypatch, [_BLOCKING])

    code, payload = _status_exit(clean_manager, check=True)

    assert code == 1
    assert payload["outcome"] == "backlog"


def test_mixed_findings_fail_the_check_and_retain_the_advisory_ones(
    clean_manager: LocaleManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _inject_parallel_findings(monkeypatch, [_ADVISORY, _BLOCKING])

    code, payload = _status_exit(clean_manager, check=True)

    assert code == 1
    assert payload["outcome"] == "backlog"
    assert _section(payload, "summary")["findings"] == {"blocking": 1, "advisory": 1, "total": 2}
    assert _ADVISORY in _detail_findings(payload)
    assert "1 advisory findings are retained separately" in str(payload["headline"])


@pytest.mark.parametrize(
    "finding",
    [
        {"kind": "unclassified_kind"},
        {"classification": "warning", "kind": "unknown_classification"},
        {"classification": None, "kind": "null_classification"},
        {"classification": "Advisory", "kind": "case_variant"},
    ],
    ids=["missing", "unknown", "none", "case-variant"],
)
def test_missing_or_unknown_classification_still_blocks(
    clean_manager: LocaleManager, monkeypatch: pytest.MonkeyPatch, finding: dict[str, object]
) -> None:
    _inject_parallel_findings(monkeypatch, [_ADVISORY, finding])

    code, payload = _status_exit(clean_manager, check=True)

    assert code == 1
    assert payload["outcome"] == "backlog"


def test_status_without_check_exits_zero_for_every_outcome(
    clean_manager: LocaleManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _inject_parallel_findings(monkeypatch, [_BLOCKING])

    code, payload = _status_exit(clean_manager, check=False)

    assert code == 0
    assert payload["outcome"] == "backlog"


def test_open_inventory_blocks_even_when_no_finding_names_it() -> None:
    assert signal_outcome([], unsettled_inventory_or_cells=True) == "backlog"
    assert signal_outcome([_ADVISORY], unsettled_inventory_or_cells=True) == "backlog"
    assert signal_outcome([_ADVISORY], unsettled_inventory_or_cells=False) == "advisory"
    assert signal_outcome([], unsettled_inventory_or_cells=False) == "complete"


def test_only_the_exact_advisory_classification_is_non_gating() -> None:
    cases: list[tuple[dict[str, object], bool]] = [
        (_ADVISORY, True),
        (_BLOCKING, False),
        ({}, False),
        ({"classification": "ADVISORY"}, False),
    ]
    for finding, expected in cases:
        assert is_advisory_finding(finding) is expected


def test_unready_cells_gate_through_the_real_matrix(
    clean_manager: LocaleManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A translation cell that is not ready gates through the real matrix, not only through findings."""
    (tmp_path / "locales" / "en.yml").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(clean_manager, "get_codebase_keys", lambda: {"cli.save"})

    payload = signal_module.locale_signal(clean_manager, repository=tmp_path)

    assert payload["outcome"] == "backlog"
    assert payload["details"]["backlog"]
    assert any(not is_advisory_finding(finding) for finding in payload["details"]["findings"])
