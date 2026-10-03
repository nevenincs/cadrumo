"""A wheel answers for itself only through exactly one core-metadata document."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from dev.packaging.dependency_contract import wheel_metadata
from dev.packaging.wheel_metadata import read_wheel_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


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
