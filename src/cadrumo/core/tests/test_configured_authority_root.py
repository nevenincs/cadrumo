"""The registry authority root resolves without the storage root or the profile pointer.

The published authority is product data. Locating it has to keep working on a
machine whose storage refuses to resolve -- one that still carries retired
``aeat`` state -- while every storage and profile access keeps refusing there.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from pathlib import Path

import pytest

from ..config import Settings, configured_authority_root, load_settings, override_settings
from ..config_state_root import (
    FormerProductStateError,
    default_storage_root,
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


def _machine_beside_retired_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the live platform inputs at a data root that sits beside retired ``aeat`` state.

    Every platform's user-data variable is redirected, so the live resolver lands
    on the fabricated root wherever the test runs, and the storage-root variable
    is removed so the platform default -- the path that refuses -- is the one
    resolved.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "platform-data"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "platform-data"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv(_STORAGE_ROOT_ENV, raising=False)
    retired = platform_user_data_root(live_state_root_inputs()).parent / "aeat"
    retired.mkdir(parents=True)
    (retired / "custody-marker.bin").write_bytes(_RETIRED_MARKER)
    return retired


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


def test_the_authority_root_resolves_beside_retired_state_while_storage_and_profile_refuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the product's own registry location is readable on a retired-state machine.

    The settings construction every storage and profile access goes through
    derives the storage root and reads the active-profile pointer; both refuse
    here. The authority root is read without either, and the retired state is
    left exactly as it was found.
    """
    retired = _machine_beside_retired_state(tmp_path, monkeypatch)
    published = tmp_path / "published-authority"
    monkeypatch.setenv(_AUTHORITY_ROOT_ENV, str(published))

    assert _outside_every_override(configured_authority_root) == published.resolve()

    with pytest.raises(FormerProductStateError, match="will not read, move, re-key, delete, or adopt"):
        _outside_every_override(load_settings)
    with pytest.raises(FormerProductStateError):
        default_storage_root()

    assert sorted(entry.name for entry in retired.iterdir()) == ["custody-marker.bin"]
    assert (retired / "custody-marker.bin").read_bytes() == _RETIRED_MARKER
