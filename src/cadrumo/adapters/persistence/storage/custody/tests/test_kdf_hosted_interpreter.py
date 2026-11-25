"""A KDF child of a Cadrumo-hosted interpreter runs the hosting binary's interpreter role."""

from __future__ import annotations

import sys

import pytest

from cadrumo.core.package_interpreter import ROLE_IMAGE_OPTION, isolated_interpreter_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_a_hosted_kdf_child_runs_the_binary_interpreter_role_without_site(monkeypatch: pytest.MonkeyPatch) -> None:
    image = r"C:\Program Files\Cadrumo\cadrumo.exe"
    monkeypatch.setattr(sys, "_xoptions", {ROLE_IMAGE_OPTION: image}, raising=False)
    assert isolated_interpreter_command() == (image, "--role", "python", "-S")
