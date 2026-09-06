"""Packaging gate for the Apache §4(d) attribution chain.

Every distribution this repository publishes — the root ``cadrumo`` runtime
wheel and the two ``cadrumo-data-*`` corpus companions — must ship the Apache
LICENSE text and the project ``NOTICE`` attribution file inside its artifacts
(``.dist-info/licenses/`` in wheels, the root of the sdist). The mechanism is
the explicit PEP 639 ``license-files`` declaration in each ``pyproject.toml``;
this gate pins the declaration, and reads the referenced files, so a future edit
cannot silently drop the attribution chain back to hatchling's implicit glob
defaults. Presence is not the claim: an empty or placeholder LICENSE satisfies
existence while shipping no licence at all, so the Apache text is compared
byte-for-byte across the three distributions and its operative clauses are
pinned, and every NOTICE is read for the attribution it must carry.

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


_APACHE_OPERATIVE_CLAUSES = (
    "Apache License",
    "Version 2.0, January 2004",
    "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
    "You must give any other recipients of the Work",
    "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND",
)


def test_every_distribution_ships_the_same_verbatim_apache_licence_text() -> None:
    """The LICENSE each distribution ships is the Apache-2.0 text, byte-identical everywhere."""
    canonical = (_REPO_ROOT / "LICENSE").read_bytes()
    for clause in _APACHE_OPERATIVE_CLAUSES:
        assert clause in canonical.decode("utf-8"), (
            f"the root LICENSE is missing the operative Apache-2.0 clause {clause!r}; "
            "a present-but-empty or placeholder LICENSE ships no licence at all"
        )
    for distribution, project_dir in sorted(_PROJECT_DIRS.items()):
        shipped = (project_dir / "LICENSE").read_bytes()
        assert shipped == canonical, (
            f"{distribution} ships a LICENSE that differs from the root Apache-2.0 text "
            f"({len(shipped)} bytes vs {len(canonical)}); every distribution must carry "
            "the same verbatim licence"
        )


def test_root_notice_carries_the_project_attribution() -> None:
    """The root NOTICE must carry the Apache 4(d) attribution, not merely exist."""
    notice = (_REPO_ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "Copyright 2026 Neve Nincs" in notice
    assert "Apache License, Version 2.0" in notice
    assert "NOT affiliated" in notice
    assert "Agencia Estatal de" in notice
    assert "THIRD_PARTY_NOTICES.md" in notice
