"""The registry authority root resolves without the storage root or the profile pointer.

The published authority is product data. Its configured location resolves
independently of project storage and unrelated old platform state.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from pathlib import Path

import pytest

from ..config import Settings, configured_authority_root, override_settings
from ..config_state_root import (
    live_state_root_inputs,
    platform_user_data_root,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AUTHORITY_ROOT_ENV = "CADRUMO_AUTHORITY_ROOT"
_STORAGE_ROOT_ENV = "CADRUMO_LOCAL_STORAGE_ROOT"
_RETIRED_MARKER = b"retired-aeat-state-must-remain"


def _outside_every_override[T](read: Callable[[], T]) -> T:
    """Run ``read`` in an empty context, where no settings override is installed.

    That is the state a fresh process starts in, and the only state in which
    the process environment, rather than an override, answers.
    """
    return contextvars.Context().run(read)


def test_an_absolute_environment_value_is_the_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    published = tmp_path / "published-authority"
    monkeypatch.setenv(_AUTHORITY_ROOT_ENV, str(published))
    assert _outside_every_override(configured_authority_root) == published.resolve()


def test_a_relative_environment_value_anchors_under_the_platform_data_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relative value lands beside the product's data, never under the process cwd."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "platform-data"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "platform-data"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv(_AUTHORITY_ROOT_ENV, "relative-authority")
    expected = (platform_user_data_root(live_state_root_inputs()) / "relative-authority").resolve()
    assert _outside_every_override(configured_authority_root) == expected


@pytest.mark.parametrize("value", [None, ""], ids=["unset", "empty"])
def test_an_unset_or_empty_variable_selects_the_packaged_authority(
    value: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty variable is unset, so the packaged authority is the one resolved."""
    if value is None:
        monkeypatch.delenv(_AUTHORITY_ROOT_ENV, raising=False)
    else:
        monkeypatch.setenv(_AUTHORITY_ROOT_ENV, value)
    assert _outside_every_override(configured_authority_root) is None


@pytest.mark.parametrize("value", [None, "", "relative-authority", "absolute"])
def test_the_reader_and_the_full_settings_model_agree(
    value: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both readers parse the one field declaration, so no value can split them."""
    if value is None:
        monkeypatch.delenv(_AUTHORITY_ROOT_ENV, raising=False)
    else:
        monkeypatch.setenv(_AUTHORITY_ROOT_ENV, str(tmp_path / "published") if value == "absolute" else value)
    assert _outside_every_override(configured_authority_root) == Settings().cadrumo_authority_root


def test_an_override_block_answers_inside_its_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_AUTHORITY_ROOT_ENV, str(tmp_path / "ambient"))
    overridden = tmp_path / "overridden"
    with override_settings(cadrumo_authority_root=overridden):
        assert configured_authority_root() == overridden.resolve()
    with override_settings(cadrumo_authority_root=None):
        assert configured_authority_root() is None


def test_authority_and_project_storage_ignore_unrelated_retired_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unrelated old platform state neither relocates nor blocks project-owned storage."""
    retired = tmp_path / "aeat"
    retired.mkdir()
    (retired / "custody-marker.bin").write_bytes(_RETIRED_MARKER)
    storage = tmp_path / "project-storage"
    published = tmp_path / "published-authority"
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(storage))
    monkeypatch.delenv(_STORAGE_ROOT_ENV, raising=False)
    monkeypatch.setenv(_AUTHORITY_ROOT_ENV, str(published))
    assert _outside_every_override(configured_authority_root) == published.resolve()
    assert Settings().cadrumo_local_storage_root == storage
    assert sorted(entry.name for entry in retired.iterdir()) == ["custody-marker.bin"]
    assert (retired / "custody-marker.bin").read_bytes() == _RETIRED_MARKER
