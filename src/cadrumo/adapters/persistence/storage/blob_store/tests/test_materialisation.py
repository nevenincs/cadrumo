"""Tests for the route-canonical :class:`SecretStore` factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from ......core.config import Settings
from .._materialisation import get_secret_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_secret_store_factory_caches_each_explicit_route_independently(tmp_path: Path) -> None:
    """A second Settings route never inherits the first route's cached store."""
    settings_a = Settings(
        cadrumo_secret_store_dir=tmp_path / "root-a" / "secrets",
        cadrumo_blob_store_dir=tmp_path / "root-a" / "blobs",
    )
    settings_b = Settings(
        cadrumo_secret_store_dir=tmp_path / "root-b" / "secrets",
        cadrumo_blob_store_dir=tmp_path / "root-b" / "blobs",
    )
    settings_c = Settings(
        cadrumo_secret_store_dir=settings_a.cadrumo_secret_store_dir,
        cadrumo_blob_store_dir=tmp_path / "root-c" / "blobs",
    )
    store_a = get_secret_store(settings=settings_a)
    store_b = get_secret_store(settings=settings_b)
    store_c = get_secret_store(settings=settings_c)

    assert store_a is get_secret_store(settings=settings_a)
    assert store_b is get_secret_store(settings=settings_b)
    assert store_a is not store_b
    assert store_a is not store_c
    assert store_a.store_dir == settings_a.cadrumo_secret_store_dir
    assert store_b.store_dir == settings_b.cadrumo_secret_store_dir
    assert store_c.store_dir == settings_c.cadrumo_secret_store_dir
