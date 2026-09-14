"""A narrowed binding-signal scope is reported rather than measured as a zero.

Two populations can leave the binding signal without contributing a single row:
a modelo directory carrying no ``revisions/`` tree, and a Python scan root that
is not present under the measured repository root. Neither produces a finding,
because neither is a defect in a declaration -- but a silently smaller corpus
reads exactly like a clean one, and the counts the signal publishes would be a
measurement of a scope nobody stated. Each is emitted as a limitation instead,
so the report says which modelo and which tree it did not look at.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ..bindings import _python_binding_references, audit

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _limitations(payload: dict[str, object]) -> list[dict[str, object]]:
    limitations = payload["limitations"]
    assert isinstance(limitations, list)
    return [item for item in limitations if isinstance(item, dict)]


def _limitation_codes(payload: dict[str, object]) -> list[str]:
    return [str(item["code"]) for item in _limitations(payload)]


def test_missing_python_scan_root_is_reported_not_counted_as_no_references(tmp_path: Path) -> None:
    """A scan root that is not a directory narrows the scope and says so."""
    (tmp_path / "src" / "cadrumo").mkdir(parents=True)
    (tmp_path / "src" / "cadrumo" / "module.py").write_text(
        'BINDING = "m303-2024-iva-devengado"\n',
        encoding="utf-8",
    )

    rows, limitations = _python_binding_references(tmp_path, frozenset({"m303-2024-iva-devengado"}))

    assert [str(row["binding_id"]) for row in rows] == ["m303-2024-iva-devengado"]
    missing = [item for item in limitations if item["code"] == "PYTHON_BINDING_REFERENCE_ROOT_MISSING"]
    assert [item["path"] for item in missing] == ["dev/registry"]


def test_present_python_scan_roots_report_no_scope_limitation(tmp_path: Path) -> None:
    """The limitation is earned by an absent tree, not emitted unconditionally."""
    for relative in ("src/cadrumo", "dev/registry"):
        (tmp_path / relative).mkdir(parents=True)

    _rows, limitations = _python_binding_references(tmp_path, frozenset({"m303-2024-iva-devengado"}))

    assert [item["code"] for item in limitations] == []


def test_modelo_without_revisions_tree_is_reported_as_a_narrowed_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A modelo contributing no coordinate is named rather than quietly dropped."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    modelos = tmp_path / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
    (modelos / "303" / "revisions" / "2024").mkdir(parents=True)
    (modelos / "303" / "revisions" / "2024" / "revision.toml").write_text(
        '[revisions."2024"]\npredecessor = "none"\n',
        encoding="utf-8",
    )
    (modelos / "390").mkdir(parents=True)

    payload = audit(tmp_path)

    withheld = [item for item in _limitations(payload) if item["code"] == "MODELOS_WITHOUT_REVISIONS"]
    assert len(withheld) == 1
    assert withheld[0]["count"] == 1
    assert withheld[0]["items"] == ["src/cadrumo/_data/registry/aeat/modelos/390"]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    assert summary["modelos"] == 1


def test_every_modelo_carrying_revisions_earns_no_scope_limitation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The modelo limitation is falsifiable: a complete corpus does not raise it."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    modelos = tmp_path / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
    (modelos / "303" / "revisions" / "2024").mkdir(parents=True)
    (modelos / "303" / "revisions" / "2024" / "revision.toml").write_text(
        '[revisions."2024"]\npredecessor = "none"\n',
        encoding="utf-8",
    )

    payload = audit(tmp_path)

    assert "MODELOS_WITHOUT_REVISIONS" not in _limitation_codes(payload)
