"""Resolution arms of the published authority descriptor selector."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.resources.bundled_data import bundled_path
from .. import authority as authority_module
from ..authority import bundled_authority_descriptor_path
from ..errors import AuthorityDescriptorUnavailableError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESCRIPTOR_NAME = "authority.current.json"


def _published_descriptor(root: Path) -> Path:
    descriptor = root / _DESCRIPTOR_NAME
    descriptor.write_text("{}", encoding="utf-8")
    return descriptor


def test_configured_root_selects_its_own_descriptor(tmp_path: Path) -> None:
    descriptor = _published_descriptor(tmp_path)
    with override_settings(cadrumo_authority_root=tmp_path):
        assert bundled_authority_descriptor_path().resolve() == descriptor.resolve()


def test_unset_root_resolves_the_packaged_descriptor() -> None:
    with override_settings(cadrumo_authority_root=None):
        resolved = bundled_authority_descriptor_path()
    assert resolved == bundled_path("registry", "authority", _DESCRIPTOR_NAME)
    assert resolved.is_file()


def test_configured_root_without_a_descriptor_refuses_instead_of_falling_back(tmp_path: Path) -> None:
    with (
        override_settings(cadrumo_authority_root=tmp_path),
        pytest.raises(AuthorityDescriptorUnavailableError) as refusal,
    ):
        bundled_authority_descriptor_path()
    error = refusal.value
    assert error.authority_root_configured is True
    assert error.searched_path.resolve() == (tmp_path / _DESCRIPTOR_NAME).resolve()
    assert error.context is not None
    assert error.context["publish_command"] == "python -m dev.registry.pipeline publish-authority"


def test_absent_packaged_descriptor_refuses_when_no_root_is_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    absent = tmp_path / "packaged" / _DESCRIPTOR_NAME
    monkeypatch.setattr(authority_module, "_bundled_path", lambda *parts: absent)
    with override_settings(cadrumo_authority_root=None), pytest.raises(AuthorityDescriptorUnavailableError) as refusal:
        bundled_authority_descriptor_path()
    error = refusal.value
    assert error.authority_root_configured is False
    assert error.searched_path == absent
