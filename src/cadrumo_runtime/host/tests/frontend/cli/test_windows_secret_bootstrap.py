"""The AEAT host parses inherited channels and retains descriptor cleanup."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

from cadrumo_client.commands import windows_secret_channels
from cadrumo_runtime.host.frontend.cli import bootstrap, windows_secret_bootstrap

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("isolated", "arguments", "message"),
    (
        (False, ["--profile-handle", "17", "--", "--version"], "requires isolated Python"),
        (True, ["--profile-handle", "17"], "command tail is required"),
        (True, ["--", "--version"], "at least one inherited HANDLE"),
        (True, ["--profile-handle", "invalid", "--", "--version"], "invalid int value"),
    ),
)
def test_parser_refuses_invalid_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated: bool,
    arguments: list[str],
    message: str,
) -> None:
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=isolated))
    monkeypatch.setattr(sys, "argv", ["bootstrap", *arguments])
    with pytest.raises(SystemExit) as caught:
        windows_secret_bootstrap.main()
    assert caught.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize("failure", [None, "dispatch", "import"])
def test_parser_dispatches_channels_and_closes_owned_descriptors(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    reader, writer = os.pipe()
    adopted: list[int] = []

    def adopt(handle: int, *, writable: bool = False) -> int:
        assert handle == 17
        assert not writable
        descriptor = os.dup(reader)
        adopted.append(descriptor)
        return descriptor

    def dispatch() -> None:
        assert len(adopted) == 1  # The same profile/leaf HANDLE is adopted once.
        descriptor = adopted[0]
        assert sys.argv == [
            "aeat",
            "--profile-secrets-fd",
            str(descriptor),
            "config",
            "profile",
            "history",
            "--secrets-fd",
            str(descriptor),
        ]
        assert os.read(descriptor, 6) == b"secret"
        if failure == "dispatch":
            raise RuntimeError("dispatch failed")

    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=True))
    monkeypatch.setattr(
        sys,
        "argv",
        ["bootstrap", "--profile-handle", "17", "--secrets-handle", "17", "--", "config", "profile", "history"],
    )
    # Replace only OS HANDLE adoption; parser, argv construction and cleanup run for real.
    monkeypatch.setattr(windows_secret_channels, "descriptor_from_inherited_handle", adopt)
    monkeypatch.setattr(bootstrap, "main", dispatch)
    if failure == "import":
        monkeypatch.setitem(sys.modules, bootstrap.__name__, None)
    try:
        os.write(writer, b"secret")
        if failure == "dispatch":
            with pytest.raises(RuntimeError, match="dispatch failed"):
                windows_secret_bootstrap.main()
        elif failure == "import":
            with pytest.raises(ModuleNotFoundError):
                windows_secret_bootstrap.main()
        else:
            windows_secret_bootstrap.main()
        assert len(adopted) == 1
        with pytest.raises(OSError):
            os.fstat(adopted[0])
    finally:
        windows_secret_channels.close_secret_descriptors(adopted)
        os.close(reader)
        os.close(writer)
