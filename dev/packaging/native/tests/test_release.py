"""Release claims must agree with expectations supplied outside the package."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from ..release import verify_release

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    expected = {
        "target": "linux-aarch64",
        "platform": "linux-aarch64",
        "abi": 1,
        "python": "3.13.11",
        "version": "1.2.3",
        "channel": "preview",
        "cohort": ["app", "data"],
    }
    manifest = {
        "build": {key: expected[key] for key in ("target", "python", "version", "channel")},
        "layout": {"platform": "linux-aarch64", "abi": 1},
        "python": "3.13.11",
        "distributions": {"app": "1.2.3", "data": "1.2.3"},
    }
    return manifest, expected


def test_valid_release_matches_external_expectations() -> None:
    manifest, expected = _inputs()
    verify_release(manifest, expected)


@pytest.mark.parametrize("field", ["target", "python", "version", "channel"])
def test_self_consistent_package_cannot_replace_expected_release(field: str) -> None:
    manifest, expected = _inputs()
    original = deepcopy(expected)
    manifest["build"][field] = "other"
    with pytest.raises(ValueError, match=f"release {field}"):
        verify_release(manifest, expected)
    assert expected == original


@pytest.mark.parametrize("defect", ["missing", "mixed", "abi", "platform", "python"])
def test_companions_and_layout_are_bound_to_the_release(defect: str) -> None:
    manifest, expected = _inputs()
    if defect == "missing":
        del manifest["distributions"]["data"]
    elif defect == "mixed":
        manifest["distributions"]["data"] = "1.2.2"
    elif defect == "python":
        manifest["python"] = "3.13.15"
    else:
        manifest["layout"][defect] = 2 if defect == "abi" else "linux-x86-64"
    with pytest.raises(ValueError):
        verify_release(manifest, expected)
