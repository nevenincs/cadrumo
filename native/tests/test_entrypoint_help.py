"""Native entrypoint help admission accepts each command's actual root format."""

from __future__ import annotations

import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

AEAT_HELP = """CADRUMO - flujo local con la Agencia Estatal de Administración Tributaria
Familias de comandos
  aeat config  Perfiles y sesión
  aeat app     Trabajo fiscal
Opciones
  --profile-secrets-stdin
  --profile-secrets-fd FD
  --profile-auth-method {password|api-key}
  --profile-credential-ref UUID
"""


def _verify(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, output: str, returncode: int = 0) -> None:
    scope: dict[str, Any] = runpy.run_path(str(Path(__file__).with_name("entrypoint_smoke.py")))
    verify = scope["verify_entrypoints"]
    monkeypatch.setitem(verify.__globals__, "declared_entrypoints", lambda *_: (SimpleNamespace(name=name),))
    monkeypatch.setattr(scope["importlib"].metadata, "distribution", lambda _: object())

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if command != [str(tmp_path / "bin" / f"{name}.exe"), "--help"]:
            pytest.fail("Help must execute the selected packaged image")
        if kwargs["cwd"] != tmp_path or kwargs["encoding"] != "utf-8" or kwargs["check"] is not False:
            pytest.fail("Help must preserve packaged cwd, UTF-8 decoding and explicit exit admission")
        return subprocess.CompletedProcess(command, returncode, output, "")

    monkeypatch.setattr(scope["subprocess"], "run", run)
    verify(tmp_path, {name}, "bin", ".exe")


@pytest.mark.parametrize(
    ("name", "output"),
    [
        ("aeat", AEAT_HELP),
        ("cadrumo-runtime", "usage: cadrumo-runtime [-h] --supervised\n"),
        ("cadrumo-mcp", "usage: cadrumo-mcp [-h]\n"),
    ],
)
def test_canonical_root_help_dispatches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, output: str
) -> None:
    """Accept localized AEAT root help and the two named argparse entrypoints."""
    _verify(monkeypatch, tmp_path, name, output)


@pytest.mark.parametrize(
    ("name", "output", "returncode"),
    [
        ("aeat", "", 0),
        ("aeat", "Cadrumo 0.5.1\n", 0),
        ("aeat", AEAT_HELP.split("--profile-auth-method")[0], 0),
        ("aeat", "usage: cadrumo-runtime [-h]\n", 0),
        ("aeat", AEAT_HELP, 2),
        ("cadrumo-runtime", "usage: cadrumo-mcp [-h]\n", 0),
        ("cadrumo-mcp", AEAT_HELP, 0),
        ("cadrumo-mcp", "0.5.1\n", 0),
    ],
)
def test_wrong_empty_truncated_or_failed_help_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, output: str, returncode: int
) -> None:
    """Reject version fallback, incomplete roots, another command's help and failed dispatch."""
    with pytest.raises(AssertionError, match="did not dispatch help"):
        _verify(monkeypatch, tmp_path, name, output, returncode)
