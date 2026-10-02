"""Native setup command projections; real installation belongs to its adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from .. import gnome_login_observer

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("action", "existing", "expected"),
    [
        ("inspect", False, "absent"),
        ("inspect", True, "installed"),
        ("install", False, "already_installed"),
        ("install", True, "created"),
    ],
)
def test_native_setup_reports_only_the_exact_installation_outcome(
    action: str,
    existing: bool,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        gnome_login_observer,
        "sys",
        SimpleNamespace(
            platform="linux",
            stdout=gnome_login_observer.sys.stdout,
            stderr=gnome_login_observer.sys.stderr,
        ),
    )
    calls: list[str] = []

    def inspect() -> bool:
        calls.append("inspect")
        return existing

    def install() -> bool:
        calls.append("install")
        return existing

    monkeypatch.setattr(gnome_login_observer, "inspect_gnome_login_producer", inspect)
    monkeypatch.setattr(gnome_login_observer, "install_gnome_login_producer", install)
    assert gnome_login_observer.run([action]) == 0
    output = capsys.readouterr()
    assert output.out == expected + "\n" and output.err == ""
    assert calls == [action]


@pytest.mark.parametrize("platform_name", ["win32", "darwin"])
def test_unsupported_host_refuses_before_native_setup(
    platform_name: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        gnome_login_observer,
        "sys",
        SimpleNamespace(
            platform=platform_name,
            stdout=gnome_login_observer.sys.stdout,
            stderr=gnome_login_observer.sys.stderr,
        ),
    )

    def forbidden() -> bool:
        pytest.fail("unsupported host reached native installation")

    monkeypatch.setattr(gnome_login_observer, "install_gnome_login_producer", forbidden)
    assert gnome_login_observer.run(["install"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err == RuntimeRefusalCode.UNAVAILABLE.value + "\n"


@pytest.mark.parametrize("native_failure", [False, True])
def test_native_setup_refusal_does_not_print_paths_or_claim_installation(
    native_failure: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        gnome_login_observer,
        "sys",
        SimpleNamespace(
            platform="linux",
            stdout=gnome_login_observer.sys.stdout,
            stderr=gnome_login_observer.sys.stderr,
        ),
    )

    def refuse() -> bool:
        if native_failure:
            raise OSError("private-path-or-host-details")
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)

    monkeypatch.setattr(gnome_login_observer, "install_gnome_login_producer", refuse)
    assert gnome_login_observer.run(["install"]) == 2
    output = capsys.readouterr()
    expected = RuntimeRefusalCode.UNAVAILABLE if native_failure else RuntimeRefusalCode.PEER_UNTRUSTED
    assert output.out == "" and output.err == expected.value + "\n"
