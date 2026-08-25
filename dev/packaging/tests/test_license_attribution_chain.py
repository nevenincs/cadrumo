"""Packaging gate for the Apache §4(d) attribution chain.

Every distribution this repository publishes — the root ``cadrumo`` runtime
wheel and the two ``cadrumo-data-*`` corpus companions — must ship the Apache
LICENSE text and the project ``NOTICE`` attribution file inside its artifacts
(``.dist-info/licenses/`` in wheels, the root of the sdist). The mechanism is
the explicit PEP 639 ``license-files`` declaration in each ``pyproject.toml``;
this gate pins the declaration and the presence of the referenced files so a
future edit cannot silently drop the attribution chain back to hatchling's
implicit glob defaults.

The companion NOTICE files additionally scope the Apache-2.0 licence to the
project's packaging and derived works — never the underlying official AEAT/BOE
documents — so this gate also asserts that scoping statement survives.
"""

from __future__ import annotations

import tomllib

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT

_PROJECT_DIRS = {
    "cadrumo": _REPO_ROOT,
    "cadrumo-data-manuals": _REPO_ROOT / "packaging" / "cadrumo_data_manuals",
    "cadrumo-data-official": _REPO_ROOT / "packaging" / "cadrumo_data_official",
}


@pytest.mark.parametrize("distribution", sorted(_PROJECT_DIRS))
def test_distribution_declares_and_carries_the_attribution_chain(distribution: str) -> None:
    """Each published distribution declares license-files = LICENSE + NOTICE and ships both."""
    project_dir = _PROJECT_DIRS[distribution]
    pyproject = tomllib.loads((project_dir / "pyproject.toml").read_text(encoding="utf-8"))
    declared = pyproject["project"].get("license-files")
    assert declared == ["LICENSE", "NOTICE"], (
        f"{distribution} pyproject must declare license-files = ['LICENSE', 'NOTICE'] "
        "so the wheel/sdist carry the Apache 4(d) attribution chain explicitly"
    )
    for name in declared:
        target = project_dir / name
        assert target.is_file(), f"{target} is declared in license-files but missing on disk"
        assert target.stat().st_size > 0, f"{target} is empty"


@pytest.mark.parametrize(
    "companion",
    ("cadrumo_data_manuals", "cadrumo_data_official"),
)
def test_companion_notice_scopes_the_licence_off_official_documents(companion: str) -> None:
    """The corpus companions' NOTICE must scope Apache-2.0 to packaging, never the official texts."""
    notice = (_REPO_ROOT / "packaging" / companion / "NOTICE").read_text(encoding="utf-8")
    assert "Neve Nincs" in notice
    assert "Ley 37/2007" in notice
    assert "does not" in notice and "relicense" in notice
    assert "NOT affiliated" in notice
