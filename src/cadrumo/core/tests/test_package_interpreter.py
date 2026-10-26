"""Children of a Cadrumo-hosted interpreter re-enter the hosting binary's interpreter role."""

from __future__ import annotations

import sys

import pytest

from cadrumo.core.package_interpreter import ROLE_IMAGE_OPTION, interpreter_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_an_interpreter_the_binary_does_not_host_starts_its_own_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    assert interpreter_command() == (sys.executable,)
    monkeypatch.setattr(sys, "_xoptions", {ROLE_IMAGE_OPTION: True}, raising=False)
    assert interpreter_command() == (sys.executable,)


def test_a_hosted_interpreter_starts_the_binary_in_its_interpreter_role(monkeypatch: pytest.MonkeyPatch) -> None:
    image = r"C:\Program Files\Cadrumo\cadrumo.exe"
    monkeypatch.setattr(sys, "_xoptions", {ROLE_IMAGE_OPTION: image}, raising=False)
    assert interpreter_command() == (image, "--role", "python")
