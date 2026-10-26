"""Windows resources retain the build sequence and each build type's display version."""

from pathlib import Path

import pytest

from ...build_stamp import BuildStamp
from ..windows import _version_resource

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_version_resources_carry_the_sequence_and_the_display_version_of_each_type(tmp_path: Path) -> None:
    stamp = BuildStamp("2026101903", 412, "2026-10-19T08:30:00Z")
    resource = _version_resource(tmp_path, "0,6,0,412", "0.6.0", stamp, '"Publisher\\0"', '"Host\\0"')
    assert "FILEVERSION 0,6,0,412" in resource
    assert "PRODUCTVERSION 0,6,0,412" in resource
    debug, release = resource[resource.index("#if CADRUMO_BUILD_DEBUG") : resource.index("#endif\n   VALUE")].split(
        "#else"
    )
    assert 'VALUE "FileVersion", "0.6.0+2026101903.debug\\0"' in debug
    assert 'VALUE "BuildType", "debug\\0"' in debug
    assert 'VALUE "FileVersion", "0.6.0+2026101903\\0"' in release
    assert 'VALUE "BuildType", "release\\0"' in release
    assert 'VALUE "BuildId", "2026101903\\0"' in resource
    assert 'VALUE "ProductVersion", "0.6.0\\0"' in resource
    assert 'VALUE "BuildDate", "2026-10-19T08:30:00Z\\0"' in resource
