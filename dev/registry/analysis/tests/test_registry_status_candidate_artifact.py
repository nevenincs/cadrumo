"""An explicit health descriptor owns both currency and runtime admission."""

from collections import Counter
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path

from .. import registry_status

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def artifact_axes(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Isolate artifact selection from the unrelated source/target census."""
    selected: list[Path] = []

    def currency(descriptor: Path, *_args: object) -> tuple[str, None, None]:
        selected.append(descriptor)
        return "current", None, None

    monkeypatch.setattr(registry_status, "_collect_registry_validity", lambda *_args: (None, True))
    monkeypatch.setattr(registry_status, "_collect_oracle_status", lambda *_args: True)
    monkeypatch.setattr(registry_status, "_collect_target_axis", lambda *_args: (False, Counter(), ()))
    monkeypatch.setattr(registry_status, "_collect_authority_currency", currency)
    return selected


def test_corrupt_candidate_fails_even_with_loadable_active_authority(
    tmp_path: Path,
    artifact_axes: list[Path],
) -> None:
    """A healthy default cannot lend its loadability to a malformed candidate."""
    active = registry_status.collect_registry_status()
    assert active.loadable
    candidate = tmp_path / "authority.current.json"
    candidate.write_text("{}", encoding="utf-8")
    assessed = registry_status.collect_registry_status(authority_descriptor=candidate)
    assert not assessed.loadable
    assert artifact_axes[-1] == candidate
    assert any(detail.startswith("LOADABLE:") for detail in assessed.details)


def test_valid_selected_artifact_does_not_load_a_missing_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_axes: list[Path],
) -> None:
    """The caller's candidate remains usable while the default is unavailable."""
    selected = bundled_authority_descriptor_path()
    monkeypatch.setattr(registry_status, "bundled_authority_descriptor_path", lambda: tmp_path / "missing.json")
    assert not registry_status.collect_registry_status().loadable
    assessed = registry_status.collect_registry_status(authority_descriptor=selected)
    assert assessed.loadable
    assert artifact_axes[-1] == selected
