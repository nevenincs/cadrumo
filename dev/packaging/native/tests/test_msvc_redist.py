"""The pinned MSVC toolset's runtime libraries are found by its version line, hashed and checked before staging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..assembly_staging import program_redistributable
from ..hashing import digest
from ..msvc_redist import REQUIRED_LIBRARIES, MsvcRedistError, locate_msvc_redist, main, redist_record, verified_redist

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _crt(root: Path, version: str, *, omit: tuple[str, ...] = (), folder: str = "Microsoft.VC143.CRT") -> Path:
    directory = root / "VC/Redist/MSVC" / version / "x64" / folder
    directory.mkdir(parents=True)
    for name in REQUIRED_LIBRARIES:
        if name not in omit:
            (directory / name).write_bytes(f"{version} {name}".encode())
    return directory


def test_the_newest_build_of_the_toolsets_line_is_selected_and_other_lines_are_ignored(tmp_path: Path) -> None:
    _crt(tmp_path, "14.43.35001")
    older = _crt(tmp_path, "14.44.35112")
    newest = _crt(tmp_path, "14.44.35999")
    _crt(tmp_path, "14.45.40000")
    (tmp_path / "VC/Redist/MSVC/v143").mkdir()

    selected = locate_msvc_redist(tmp_path, "14.44.35207")

    assert selected == newest
    assert selected != older


def test_a_folder_missing_one_of_the_three_libraries_is_a_typed_error_that_names_it(tmp_path: Path) -> None:
    _crt(tmp_path, "14.44.35112", omit=("vcruntime140_1.dll",))

    with pytest.raises(MsvcRedistError, match=r"lacks vcruntime140_1\.dll"):
        locate_msvc_redist(tmp_path, "14.44.35207")


def test_a_toolset_with_no_redistributable_of_its_line_is_refused(tmp_path: Path) -> None:
    _crt(tmp_path, "14.43.35001")

    with pytest.raises(MsvcRedistError, match=r"MSVC 14\.44 line"):
        locate_msvc_redist(tmp_path, "14.44.35207")
    with pytest.raises(MsvcRedistError, match=r"not major\.minor\.build"):
        locate_msvc_redist(tmp_path, "latest")


def test_the_record_hashes_each_library_and_assembly_accepts_it(tmp_path: Path) -> None:
    directory = _crt(tmp_path, "14.44.35112")

    record = redist_record(tmp_path, "14.44.35207")
    staged = verified_redist(json.loads(json.dumps(record)))

    assert record["directory"] == directory.as_posix()
    assert record["sha256"] == {name: digest(directory / name) for name in REQUIRED_LIBRARIES}
    assert staged == {name: directory / name for name in REQUIRED_LIBRARIES}


def test_assembly_refuses_a_library_changed_or_removed_after_configure(tmp_path: Path) -> None:
    directory = _crt(tmp_path, "14.44.35112")
    record = redist_record(tmp_path, "14.44.35207")
    (directory / "msvcp140.dll").write_bytes(b"replaced")

    with pytest.raises(MsvcRedistError, match=r"differs from its configured digests \(msvcp140\.dll\)"):
        verified_redist(record)

    (directory / "vcruntime140.dll").unlink()
    with pytest.raises(MsvcRedistError, match=r"lacks vcruntime140\.dll"):
        verified_redist(record)


def test_only_a_windows_assembly_takes_the_redistributable_and_it_must_have_been_configured(tmp_path: Path) -> None:
    directory = _crt(tmp_path, "14.44.35112")
    configured = {"build_toolchain": {"msvc_redist": redist_record(tmp_path, "14.44.35207")}}

    assert program_redistributable({"backend": "linux"}, {}) is None
    assert program_redistributable({"backend": "windows"}, configured) == {
        name: directory / name for name in REQUIRED_LIBRARIES
    }
    with pytest.raises(MsvcRedistError, match="records no MSVC redistributable"):
        program_redistributable({"backend": "windows"}, {"build_toolchain": {}})


@pytest.mark.parametrize("record", [None, "text", {"directory": "relative", "sha256": {}}, {"directory": "/x"}])
def test_assembly_refuses_an_absent_or_malformed_record(record: object) -> None:
    with pytest.raises(MsvcRedistError, match="reconfigure CMake"):
        verified_redist(record)


def test_the_command_prints_the_record_or_refuses(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _crt(tmp_path, "14.44.35112")

    assert main(["--visual-studio", str(tmp_path), "--msvc-version", "14.44.35207"]) == 0
    assert sorted(json.loads(capsys.readouterr().out)["sha256"]) == sorted(REQUIRED_LIBRARIES)
    assert main(["--visual-studio", str(tmp_path), "--msvc-version", "14.45.1"]) == 1
    assert "msvc-redist:" in capsys.readouterr().err
