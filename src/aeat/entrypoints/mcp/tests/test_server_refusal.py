"""The MCP server refuses gracefully when the agent extra is not installed.

The refusal contract is tested directly via :func:`emit_missing_sdk_refusal`, so
the test is environment-independent (no skip) whether or not the MCP SDK happens
to be installed in the running environment.
"""

from __future__ import annotations

import pytest

from .._server import emit_missing_sdk_refusal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_missing_sdk_refusal_exits_non_zero_with_install_hint(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        emit_missing_sdk_refusal()
    assert exc.value.code == 3
    captured = capsys.readouterr()
    assert "aeat-cli[agent]" in captured.err
