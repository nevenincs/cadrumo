"""Development entry points refuse an unpublished authority root by name.

The published authority is generated output kept outside the packaged tree, so
a fresh clone has no authority at all until it is published. Every development
path that reaches it must say so, and say which variable selects it, rather
than surfacing the bare file error of whichever path it happened to open.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry import authority as authority_module
from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path
from cadrumo.domain.calculations.registry.errors import (
    AuthorityDescriptorUnavailableError,
    RegistryValidationError,
)

from ..pipeline.authority_publication import authority_publication_destination

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def unpublished_authority_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An authority directory nobody has published into, with no cached owner.

    The process-shared authority owner is reset because a cached one would
    answer from the generation this checkout already holds.
    """
    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", None)
    return tmp_path


def test_reading_an_unpublished_root_names_the_absent_descriptor(unpublished_authority_root: Path) -> None:
    """A read refuses with the typed error, not the open() failure beneath it."""
    with (
        override_settings(cadrumo_authority_root=unpublished_authority_root),
        pytest.raises(AuthorityDescriptorUnavailableError) as refusal,
    ):
        bundled_authority_descriptor_path()

    assert not isinstance(refusal.value, FileNotFoundError)
    assert "authority.current.json" in str(refusal.value)


def test_publishing_without_a_configured_root_refuses_and_names_the_variable() -> None:
    """The publisher stops rather than guessing, and says what to set.

    Resolving the destination through the descriptor selector would make the
    publisher depend on its own output: the selector refuses a directory
    holding no descriptor, so a first publication could never create the one
    that would have made the selector succeed.
    """
    with (
        override_settings(cadrumo_authority_root=None),
        pytest.raises(RegistryValidationError) as refusal,
    ):
        authority_publication_destination()

    assert "CADRUMO_AUTHORITY_ROOT" in str(refusal.value)


def test_publishing_into_an_empty_root_resolves_it_rather_than_refusing(
    unpublished_authority_root: Path,
) -> None:
    """A configured root needs no descriptor yet; that is the bootstrap case."""
    with override_settings(cadrumo_authority_root=unpublished_authority_root):
        assert authority_publication_destination() == unpublished_authority_root
