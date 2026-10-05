"""Hermetic write and check behavior for generated form layout fragments."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormLayoutDefinition,
    FormLayoutSeedSource,
    FormPlacementDefinition,
    FormPlacementKind,
    FormUnplacedReason,
)
from dev.registry.form_layout import cli as form_layout_cli
from dev.registry.form_layout.generator import LayoutGeneration
from dev.registry.form_layout.serialization import form_layout_fragment_path, render_form_layout_toml

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _layout() -> FormLayoutDefinition:
    return FormLayoutDefinition(
        id="form-layout",
        revision_id="2025",
        seed_source=FormLayoutSeedSource.AUTHORED,
        generator_version=1,
        source_state_digest="0" * 64,
        placements=(
            FormPlacementDefinition(
                casilla_id="001",
                kind=FormPlacementKind.UNPLACED,
                unplaced_reason=FormUnplacedReason.NO_OFFICIAL_ANCHOR,
            ),
        ),
    )


def _synthetic_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    outcome: LayoutGeneration,
) -> tuple[Path, Path]:
    modelo = SimpleNamespace(id="123")
    catalogues = SimpleNamespace(sources={})
    monkeypatch.setattr(form_layout_cli, "load_registry_tree", lambda _root: ((modelo,), catalogues))
    monkeypatch.setattr(
        form_layout_cli,
        "generate_modelo_layouts",
        lambda _modelo, *, sources, data_root: {outcome.revision_id: outcome},
    )
    return tmp_path / "registry", tmp_path / "data"


def test_check_reports_generated_bytes_without_writing_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _layout()
    registry_root, data_root = _synthetic_generation(
        monkeypatch,
        tmp_path,
        LayoutGeneration("123", "2025", layout),
    )
    revision_root = registry_root / "modelos" / "123" / "revisions" / "2025"
    revision_root.mkdir(parents=True)
    path = form_layout_fragment_path(revision_root)
    expected_text = render_form_layout_toml("2025", layout)

    changed, undeclared = form_layout_cli.synchronise_form_layouts(registry_root, data_root, check=True)

    assert changed == [path.as_posix()]
    assert undeclared == []
    assert not path.exists()

    changed, undeclared = form_layout_cli.synchronise_form_layouts(registry_root, data_root)

    assert changed == [path.as_posix()]
    assert undeclared == []
    assert path.read_text(encoding="utf-8") == expected_text


def test_check_preserves_undeclared_fragment_and_write_removes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry_root, data_root = _synthetic_generation(
        monkeypatch,
        tmp_path,
        LayoutGeneration("123", "2025", None, failure="no official anchor"),
    )
    path = form_layout_fragment_path(registry_root / "modelos" / "123" / "revisions" / "2025")
    path.parent.mkdir(parents=True)
    path.write_text("stale generated fragment\n", encoding="utf-8")

    changed, undeclared = form_layout_cli.synchronise_form_layouts(registry_root, data_root, check=True)

    assert changed == [path.as_posix()]
    assert undeclared == ["123 2025: no official anchor"]
    assert path.read_text(encoding="utf-8") == "stale generated fragment\n"

    changed, undeclared = form_layout_cli.synchronise_form_layouts(registry_root, data_root)

    assert changed == [path.as_posix()]
    assert undeclared == ["123 2025: no official anchor"]
    assert not path.exists()
    assert not path.parent.exists()


@pytest.mark.parametrize("check", [True, False])
@pytest.mark.parametrize(
    "outcome",
    [
        LayoutGeneration("123", "2025", _layout()),
        LayoutGeneration("123", "2025", None, failure="no official anchor"),
    ],
)
def test_a_fragment_the_generator_does_not_own_is_refused_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: LayoutGeneration, check: bool
) -> None:
    registry_root, data_root = _synthetic_generation(monkeypatch, tmp_path, outcome)
    path = form_layout_fragment_path(registry_root / "modelos" / "123" / "revisions" / "2025")
    path.parent.mkdir(parents=True)
    foreign = path.parent / "0001-complete-edition.toml"
    foreign_text = render_form_layout_toml("2025", _layout())
    foreign.write_text(foreign_text, encoding="utf-8", newline="\n")

    with pytest.raises(RegistryValidationError, match=r"0001-complete-edition\.toml"):
        form_layout_cli.synchronise_form_layouts(registry_root, data_root, check=check)

    assert [entry.name for entry in path.parent.iterdir()] == [foreign.name]
    assert foreign.read_text(encoding="utf-8") == foreign_text
