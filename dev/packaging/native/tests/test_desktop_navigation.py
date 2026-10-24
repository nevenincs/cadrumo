"""The desktop's navigation projection carries the whole register as the loader validated it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo_client.contracts.navigation import (
    NavigationRegisterError,
    NavigationSurface,
    load_navigation_register,
)

from .. import desktop_navigation
from ..desktop_navigation import NAVIGATION_OUTPUT, main, navigation_projection, render_navigation

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_projection_carries_every_element_kind_and_retired_id() -> None:
    register = load_navigation_register()
    projection = json.loads(render_navigation(register))
    assert [element["id"] for element in projection["elements"]] == [element.id for element in register.elements]
    for projected, element in zip(projection["elements"], register.elements, strict=True):
        assert projected == {
            "id": element.id,
            "parent": element.parent,
            "label": element.label,
            "keywords": element.keywords,
            "surfaces": [surface.value for surface in element.surfaces],
            "params": dict(element.params),
        }
    assert projection["kinds"] == [
        {"name": kind.name, "alphabet": kind.alphabet, "length": kind.length} for kind in register.kinds
    ]
    assert projection["retired"] == list(register.retired)
    assert projection["surfaces"] == ["gui", "tui"]
    assert projection["link"] == {
        "prefix": "cadrumo://view/",
        "max_length": 512,
        "max_segments": 4,
        "prefer_key": "prefer",
    }


def test_the_projection_keeps_each_surface_s_ids() -> None:
    register = load_navigation_register()
    projection = navigation_projection(register)
    elements = projection["elements"]
    assert isinstance(elements, list)
    for surface in NavigationSurface:
        projected = {element["id"] for element in elements if surface.value in element["surfaces"]}
        assert projected == register.ids_for(surface)


def test_generation_writes_stable_bytes(tmp_path: Path) -> None:
    output = tmp_path / NAVIGATION_OUTPUT
    assert main(["--output", str(output)]) == 0
    first = output.read_bytes()
    stamp = output.stat().st_mtime_ns
    assert main(["--output", str(output)]) == 0
    assert output.read_bytes() == first
    assert output.stat().st_mtime_ns == stamp
    assert first.decode("utf-8") == render_navigation(load_navigation_register())


def test_generation_refuses_another_file_name(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as refused:
        main(["--output", str(tmp_path / "elsewhere.json")])
    assert refused.value.code == 2
    assert not (tmp_path / "elsewhere.json").exists()


def test_a_register_the_loader_refuses_never_reaches_the_desktop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "navigation.toml"
    broken.write_text(
        'schema = 1\nretired = []\n[[element]]\nid = "Ledger"\nlabel = "a.b"\nkeywords = ""\nsurfaces = ["gui"]\n',
        encoding="utf-8",
    )
    with pytest.raises(NavigationRegisterError):
        load_navigation_register(broken)
    monkeypatch.setattr(desktop_navigation, "load_navigation_register", lambda: load_navigation_register(broken))
    output = tmp_path / NAVIGATION_OUTPUT
    with pytest.raises(SystemExit) as refused:
        main(["--output", str(output)])
    assert refused.value.code == 1
    assert not output.exists()
