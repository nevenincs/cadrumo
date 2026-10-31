"""Mach-O relocation leaves a receipt-pinned vendor runtime as shipped."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ...command_execution import run_command
from ..agent_runtime import STAGED_RECEIPT_NAME, STAGED_RUNTIME_TREES
from ..platforms.macos import _require_relocatable_as_shipped, _split_vendor_images

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SYSTEM = {"/usr/lib/libSystem.B.dylib"}
_FLOOR = (99, 0, 0, 0)


def test_images_beside_a_runtime_receipt_are_vendor_owned_and_the_rest_are_relocated(tmp_path: Path) -> None:
    runtime = tmp_path / "lib/cadrumo"
    (runtime / "node/bin").mkdir(parents=True)
    (runtime / STAGED_RECEIPT_NAME).write_text("{}", encoding="utf-8")
    node = runtime / "node/bin/node"
    assert STAGED_RUNTIME_TREES == ("node", "node_modules")
    extension = tmp_path / "lib/cadrumo/native/module.so"
    extension.parent.mkdir(parents=True)
    node.write_bytes(b"")
    extension.write_bytes(b"")
    assert _split_vendor_images([node, extension], tmp_path) == ([node], [extension])
    assert _split_vendor_images([node, extension], tmp_path / "lib/cadrumo/native") == ([], [node, extension])


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires the native macOS toolchain")
def test_a_vendor_image_must_need_no_rewrite_to_ship_pinned(tmp_path: Path) -> None:
    source = tmp_path / "main.c"
    source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    plain = tmp_path / "plain"
    with_rpath = tmp_path / "with_rpath"
    for output, extra in ((plain, []), (with_rpath, ["-Wl,-rpath,/opt/ambient"])):
        built = run_command(["/usr/bin/cc", "-arch", "arm64", *extra, "-o", str(output), str(source)], cwd=tmp_path)
        assert built.returncode == 0, built.stderr
    before = plain.read_bytes()
    _require_relocatable_as_shipped(plain, _FLOOR, _SYSTEM)
    assert plain.read_bytes() == before
    with pytest.raises(ValueError, match="cannot ship as pinned"):
        _require_relocatable_as_shipped(with_rpath, _FLOOR, _SYSTEM)
    with pytest.raises(ValueError, match="cannot ship as pinned"):
        _require_relocatable_as_shipped(plain, _FLOOR, set())
    with pytest.raises(ValueError, match="deployment floor"):
        _require_relocatable_as_shipped(plain, (1, 0, 0, 0), _SYSTEM)
