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

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..binding_signal.consumer_audit import python_binding_references
from ..binding_signal.sources import collect_raw_inventory
from ..bindings import audit, main

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION = str(filing_year_envelope().horizon)


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

    rows, limitations = python_binding_references(tmp_path, frozenset({"m303-2024-iva-devengado"}))

    assert [str(row["binding_id"]) for row in rows] == ["m303-2024-iva-devengado"]
    missing = [item for item in limitations if item["code"] == "PYTHON_BINDING_REFERENCE_ROOT_MISSING"]
    assert [item["path"] for item in missing] == ["dev/registry"]


def test_present_python_scan_roots_report_no_scope_limitation(tmp_path: Path) -> None:
    """The limitation is earned by an absent tree, not emitted unconditionally."""
    for relative in ("src/cadrumo", "dev/registry"):
        (tmp_path / relative).mkdir(parents=True)

    _rows, limitations = python_binding_references(tmp_path, frozenset({"m303-2024-iva-devengado"}))

    assert [item["code"] for item in limitations] == []


def _modelos_root(tmp_path: Path) -> Path:
    return tmp_path / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"


def test_modelo_without_revisions_tree_is_named_in_the_raw_inventory(tmp_path: Path) -> None:
    """A modelo contributing no coordinate is named rather than quietly dropped."""
    modelos = _modelos_root(tmp_path)
    (modelos / "303" / "revisions" / _REVISION).mkdir(parents=True)
    (modelos / "390").mkdir(parents=True)

    inventory = collect_raw_inventory(tmp_path, modelos, None)

    assert inventory.modelos_without_revisions == ["src/cadrumo/_data/registry/aeat/modelos/390"]
    assert set(inventory.revisions) == {("303", _REVISION)}


def test_every_modelo_carrying_revisions_is_not_named_as_withheld(tmp_path: Path) -> None:
    """The modelo limitation is falsifiable: a complete corpus does not raise it."""
    modelos = _modelos_root(tmp_path)
    (modelos / "303" / "revisions" / _REVISION).mkdir(parents=True)

    inventory = collect_raw_inventory(tmp_path, modelos, None)

    assert inventory.modelos_without_revisions == []


def test_an_unloadable_registry_is_a_processing_error_not_a_raw_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Raw delta files omit inherited bindings, so a loader failure must not degrade into measuring them."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    revision = _modelos_root(tmp_path) / "303" / "revisions" / _REVISION
    (revision / "bindings").mkdir(parents=True)
    (revision / "revision.toml").write_text(f'[revisions."{_REVISION}"]\npredecessor = "none"\n', encoding="utf-8")
    (revision / "bindings" / "0001-declarations.toml").write_text(
        f'[[revisions."{_REVISION}".bindings]]\nid = "modelo-303-synthetic-binding"\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="orphan modelo directory"):
        audit(tmp_path)

    monkeypatch.setattr(sys, "argv", ["bindings", "--root", str(tmp_path), "--output", str(tmp_path / "out.json")])
    assert main() == 2
    assert "processing_error" in capsys.readouterr().out
    assert not (tmp_path / "out.json").exists()
