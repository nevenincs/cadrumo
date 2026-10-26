"""Publication acceptance for held readers and atomic generation cutover."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority

from ..pipeline.authority_publication import install_validated_authority_database
from ._authority_generation_support import publishable_artifact

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain, pytest.mark.windows_only]


def test_held_reader_finishes_across_atomic_descriptor_cutover(tmp_path: Path) -> None:
    first = install_validated_authority_database(
        publishable_artifact("first"), destination=tmp_path, require_current=lambda: None
    )
    authority = IndexedRegistryAuthority(tmp_path / "authority.current.json")
    try:
        with authority.operation() as held:
            assert held.profile_schema().title == "Profile schema first"
            second = install_validated_authority_database(
                publishable_artifact("second"),
                destination=tmp_path,
                require_current=lambda: None,
            )
            assert second.database != first.database
            assert held.profile_schema().title == "Profile schema first"
            with authority.operation() as current:
                assert current.profile_schema().title == "Profile schema second"
    finally:
        authority.close()


def test_retired_database_cleanup_is_deferred_until_held_reader_closes(tmp_path: Path) -> None:
    """A held generation survives cutover and is retired by a later publication."""
    first = install_validated_authority_database(
        publishable_artifact("first"), destination=tmp_path, require_current=lambda: None
    )
    authority = IndexedRegistryAuthority(tmp_path / "authority.current.json")
    first_path = tmp_path / first.database
    try:
        with authority.operation() as held:
            second = install_validated_authority_database(
                publishable_artifact("second"),
                destination=tmp_path,
                require_current=lambda: None,
            )
            assert held.profile_schema().title == "Profile schema first"
            assert first_path.is_file()
    finally:
        authority.close()

    third = install_validated_authority_database(
        publishable_artifact("third"), destination=tmp_path, require_current=lambda: None
    )
    assert not first_path.exists()
    assert not (tmp_path / second.database).exists()
    assert (tmp_path / third.database).is_file()
