"""Installed-environment proof for the OFX optional-extra boundary."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ......core.optional_extras import OFX_EXTRA

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]

_BARE_CORE_PROBE = "\n".join(
    (
        "import json",
        "from pathlib import Path",
        "from cadrumo.adapters.inbound.financial.providers.ofx import OfxProvider",
        "from cadrumo.core.optional_extras import OFX_EXTRA, optional_extra_available",
        "assert not optional_extra_available(OFX_EXTRA)",
        "validation = OfxProvider().validate_source(Path(__import__('sys').argv[1]))",
        "print(json.dumps({'is_valid': validation.is_valid, 'extra': validation.unavailable_optional_extra, 'warnings': validation.warnings}))",
    ),
)


def test_a_bare_core_probe_miss_carries_machine_identity_not_install_prose(tmp_path: Path) -> None:
    """A real bare-core installation declines non-OFX input with typed facts."""
    source = tmp_path / "statement.csv"
    source.write_text("date,amount\n2026-01-01,10.00\n", encoding="utf-8")
    project_root = Path(__file__).parents[7]
    uv = shutil.which("uv")
    assert uv is not None

    try:
        probe = subprocess.run(  # noqa: S603 - resolved uv executable and every argument are test-owned constants.
            [
                uv,
                "run",
                "--isolated",
                "--locked",
                "--no-default-groups",
                "python",
                "-c",
                _BARE_CORE_PROBE,
                str(source),
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"bare-core OFX probe exceeded 90 seconds; stdout={exc.stdout!r} stderr={exc.stderr!r}",
        )

    assert probe.returncode == 0, f"stdout={probe.stdout}\nstderr={probe.stderr}"
    assert json.loads(probe.stdout) == {
        "is_valid": False,
        "extra": {
            "extra": OFX_EXTRA.extra,
            "import_name": OFX_EXTRA.import_name,
            "importable": False,
        },
        "warnings": [],
    }
