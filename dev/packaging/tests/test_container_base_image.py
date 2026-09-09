"""Behavioral checks for the canonical container base-image declaration."""

from __future__ import annotations

import pytest

from .._base_image import dockerfile_path, linux_base_image

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SUPPORTED_DISTRIBUTIONS = ("trixie", "bookworm")


def test_dockerfile_builds_from_its_declared_base_image() -> None:
    declared = linux_base_image()
    dockerfile = dockerfile_path()

    assert declared
    assert dockerfile.is_file()
    assert "FROM ${PYTHON_BASE_IMAGE}" in dockerfile.read_text(encoding="utf-8")


def test_declared_base_image_pins_the_distribution() -> None:
    declared = linux_base_image()

    assert any(distribution in declared for distribution in _SUPPORTED_DISTRIBUTIONS), (
        f"{declared!r} does not pin a supported Debian distribution"
    )
