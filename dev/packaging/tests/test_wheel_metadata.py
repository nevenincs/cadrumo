"""A wheel answers for itself only through exactly one core-metadata document."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from cadrumo.core.toml import load_toml
from dev._paths import REPO_ROOT
from dev.packaging.dependency_contract import (
    assert_wheel_metadata_matches_pyproject,
    pyproject_surfaces,
    wheel_metadata,
)
from dev.packaging.wheel_metadata import read_wheel_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("leak_optional", [False, True])
def test_shared_core_and_extra_names_preserve_both_metadata_rows(tmp_path: Path, leak_optional: bool) -> None:
    configuration = load_toml(REPO_ROOT / "pyproject.toml")["project"]
    surfaces = pyproject_surfaces(REPO_ROOT)
    assert "pywin32" in surfaces.project_names & surfaces.external_optional_names
    rows = ["Metadata-Version: 2.4", "Name: cadrumo", "Version: 1.0"]
    rows.extend(f"Requires-Dist: {requirement}" for requirement in configuration["dependencies"])
    for extra, requirements in configuration["optional-dependencies"].items():
        rows.append(f"Provides-Extra: {extra}")
        for requirement in requirements:
            dependency, separator, marker = requirement.partition(";")
            condition = f"({marker.strip()}) and " if separator else ""
            rows.append(f'Requires-Dist: {dependency.strip()}; {condition}extra == "{extra}"')
    if leak_optional:
        rows.append("Requires-Dist: google-auth")
    wheel = _wheel(
        tmp_path / "cadrumo-1.0-py3-none-any.whl", {"cadrumo-1.0.dist-info/METADATA": "\n".join(rows) + "\n"}
    )
    pywin32_rows = [row for row in wheel_metadata(wheel)[0] if row.lower().startswith("pywin32")]
    assert len(pywin32_rows) == 2
    assert sum('extra == "workbook-windows"' in row for row in pywin32_rows) == 1

    if leak_optional:
        with pytest.raises(SystemExit, match=r"optional dependencies leaked.*google-auth"):
            assert_wheel_metadata_matches_pyproject(REPO_ROOT, wheel)
    else:
        assert_wheel_metadata_matches_pyproject(REPO_ROOT, wheel)


def _wheel(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, mode="w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return path


def test_a_wheel_with_one_metadata_member_yields_its_fields(tmp_path: Path) -> None:
    wheel = _wheel(
        tmp_path / "pkg-1.0-py3-none-any.whl",
        {
            "pkg-1.0.dist-info/METADATA": (
                "Metadata-Version: 2.4\nName: pkg\nVersion: 1.0\nRequires-Dist: extra-dep\nProvides-Extra: Fancy\n"
            ),
            "pkg/__init__.py": "",
        },
    )

    metadata = read_wheel_metadata(wheel)

    assert (metadata.get("Name"), metadata.get("Version")) == ("pkg", "1.0")
    assert wheel_metadata(wheel) == (["extra-dep"], {"fancy"})


@pytest.mark.parametrize(
    "members",
    [
        {"pkg/__init__.py": ""},
        {
            "pkg-1.0.dist-info/METADATA": "Name: pkg\nVersion: 1.0\n",
            "other-2.0.dist-info/METADATA": "Name: other\nVersion: 2.0\n",
        },
    ],
    ids=["no-metadata", "two-metadata"],
)
def test_a_wheel_without_exactly_one_metadata_member_is_refused_by_every_reader(
    tmp_path: Path, members: dict[str, str]
) -> None:
    wheel = _wheel(tmp_path / "pkg-1.0-py3-none-any.whl", members)

    with pytest.raises(SystemExit, match="expected one wheel METADATA member"):
        read_wheel_metadata(wheel)
    with pytest.raises(SystemExit, match="expected one wheel METADATA member"):
        wheel_metadata(wheel)
