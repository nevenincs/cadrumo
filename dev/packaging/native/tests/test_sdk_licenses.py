"""SDK notices retain embedded dependency licenses and reject escaping sources."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..assemble import stage_sdk_licenses

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_sdk_dependency_notices_ship_with_canonical_cpython_notice(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    licenses = sdk / "licenses"
    licenses.mkdir(parents=True)
    (licenses / "LICENSE.cpython.txt").write_text("CPython notice", encoding="utf-8")
    (licenses / "LICENSE.openssl.txt").write_text("OpenSSL notice", encoding="utf-8")
    package = tmp_path / "package"
    stage_sdk_licenses(
        package,
        sdk,
        {
            "sdk": {
                "license": "licenses/LICENSE.cpython.txt",
                "licenses": {"licenses": "docs/licenses/CPython-dependencies"},
            },
            "files": {"python_license": "docs/licenses/CPython.txt"},
        },
    )
    assert (package / "docs/licenses/CPython.txt").read_text(encoding="utf-8") == "CPython notice"
    assert (package / "docs/licenses/CPython-dependencies/LICENSE.openssl.txt").read_text(
        encoding="utf-8"
    ) == "OpenSSL notice"


@pytest.mark.parametrize("defect", ["source_escape", "destination_escape", "linked_source", "collision"])
def test_sdk_license_refuses_escaping_linked_or_colliding_copy(tmp_path: Path, defect: str) -> None:
    sdk = tmp_path / "sdk"
    sdk.mkdir()
    (sdk / "LICENSE").write_text("notice", encoding="utf-8")
    source = "../outside.txt" if defect == "source_escape" else "LICENSE"
    destination = "../outside.txt" if defect == "destination_escape" else "docs/CPython.txt"
    package = tmp_path / "package"
    if defect == "linked_source":
        (sdk / "linked").symlink_to(sdk, target_is_directory=True)
        source = "linked/LICENSE"
    if defect == "collision":
        (package / "docs").mkdir(parents=True)
        (package / "docs/CPython.txt").write_text("prior notice", encoding="utf-8")
    with pytest.raises((ValueError, FileExistsError)):
        stage_sdk_licenses(package, sdk, {"sdk": {"license": source}, "files": {"python_license": destination}})
    assert not (tmp_path / "outside.txt").exists()
