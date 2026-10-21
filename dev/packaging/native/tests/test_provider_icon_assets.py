"""The desktop artwork projection follows the exact admitted wheel metadata."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote_to_bytes

import pytest

from ..provider_icon_assets import (
    ProviderIconGenerationError,
    generate,
    provider_icon_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MONO = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>'
_COLOR = b'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="1" cy="1" r="1"/></svg>'
_MODULE = b"""from enum import StrEnum
from importlib import resources

class IconVariant(StrEnum):
    MONO = "mono"
    COLOR = "color"

class Attribution:
    title = "Fixture artwork"
    url = "https://example.test/icons"
    pin = "fixture pin"
    licence = "Fixture License"
    notice = "Fixture notice"
    trademarks = "Fixture trademarks"

ICON_ATTRIBUTION = Attribution()

def icon_variants(key):
    if key != "fixture-mark":
        raise LookupError(key)
    return (IconVariant.MONO, IconVariant.COLOR)

def read_icon(key, variant):
    if key != "fixture-mark":
        raise LookupError(key)
    filename = "fixture-mark.svg" if variant is IconVariant.MONO else "fixture-mark-color.svg"
    return resources.files(__name__.rpartition(".")[0]).joinpath("icons", filename).read_bytes()
"""


def _wheel(
    path: Path,
    *,
    providers: object | None = None,
    extra_art: bool = False,
    include_art: bool = True,
) -> Path:
    if providers is None:
        providers = [{"id": "fixture-provider", "icon": "fixture-mark"}]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "cadrumo_agent/providers/provider_metadata.json",
            json.dumps({"providers": providers}),
        )
        archive.writestr("cadrumo_agent/providers/provider_icons.py", _MODULE)
        if include_art:
            archive.writestr("cadrumo_agent/providers/icons/fixture-mark.svg", _MONO)
            archive.writestr("cadrumo_agent/providers/icons/fixture-mark-color.svg", _COLOR)
        if extra_art:
            archive.writestr("cadrumo_agent/providers/icons/unlisted.svg", _MONO)
    return path


def test_wheel_metadata_and_icon_module_drive_stable_frontend_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel = _wheel(tmp_path / "agent.whl")
    controlled = tmp_path / "controlled-temporary"
    controlled.mkdir()
    ambient = tmp_path / "ambient-not-created"
    monkeypatch.setenv("CADRUMO_TEMP_DIR", str(controlled))
    monkeypatch.setattr(tempfile, "tempdir", str(ambient))

    document = provider_icon_document(wheel)

    assert list(document["providers"]) == ["fixture-provider"]
    variants = document["providers"]["fixture-provider"]
    assert unquote_to_bytes(variants["mono"].partition(",")[2]) == _MONO
    assert unquote_to_bytes(variants["color"].partition(",")[2]) == _COLOR
    assert document["attribution"] == {
        "title": "Fixture artwork",
        "url": "https://example.test/icons",
        "pin": "fixture pin",
        "licence": "Fixture License",
        "notice": "Fixture notice",
        "trademarks": "Fixture trademarks",
    }

    output = tmp_path / "generated/provider-icons.json"
    generate(wheel, output)
    first = output.read_bytes()
    generate(wheel, output)
    assert output.read_bytes() == first
    assert not list(controlled.iterdir())
    assert not ambient.exists()


def test_catalogue_provider_without_declared_art_uses_no_mark(tmp_path: Path) -> None:
    wheel = _wheel(
        tmp_path / "agent.whl",
        providers=[{"id": "fixture-provider", "icon": None}],
        include_art=False,
    )

    document = provider_icon_document(wheel)

    assert document["providers"] == {}
    assert document["attribution"]["title"] == "Fixture artwork"


@pytest.mark.parametrize(
    ("providers", "extra_art"),
    [
        ([{"id": "fixture-provider", "icon": "not-bundled"}], False),
        ([{"id": "fixture-provider", "icon": "fixture-mark"}], True),
        ([{"id": "fixture-provider"}], False),
        (
            [
                {"id": "fixture-provider", "icon": "fixture-mark"},
                {"id": "fixture-provider", "icon": "fixture-mark"},
            ],
            False,
        ),
        ([{"id": "bad/provider", "icon": "fixture-mark"}], False),
    ],
)
def test_incomplete_or_invalid_catalogue_refuses_generation(tmp_path: Path, providers: object, extra_art: bool) -> None:
    wheel = _wheel(tmp_path / "agent.whl", providers=providers, extra_art=extra_art)

    with pytest.raises(ProviderIconGenerationError):
        provider_icon_document(wheel)


def test_duplicate_wheel_member_is_refused(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path / "agent.whl")
    with pytest.warns(UserWarning, match="Duplicate name"), zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("cadrumo_agent/providers/provider_metadata.json", b'{"providers":[]}')

    with pytest.raises(ProviderIconGenerationError, match=r"one .* member"):
        provider_icon_document(wheel)
