"""Unit tests for :func:`aeat.status._cache_key.make_cache_key`."""

from __future__ import annotations

from datetime import date

import pytest

from ._cache_key import make_cache_key
from ._models import AeatStatusKind

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def test_stable_across_param_order() -> None:
    key1 = make_cache_key(
        tax_id="X1234567L",
        surface=AeatStatusKind.EXPEDIENTE,
        params={"since": date(2025, 1, 1), "year": 2025},
    )
    key2 = make_cache_key(
        tax_id="X1234567L",
        surface=AeatStatusKind.EXPEDIENTE,
        params={"year": 2025, "since": date(2025, 1, 1)},
    )
    assert key1 == key2


def test_none_params_ignored() -> None:
    key1 = make_cache_key(tax_id="X1234567L", surface=AeatStatusKind.EXPEDIENTE, params=None)
    key2 = make_cache_key(
        tax_id="X1234567L",
        surface=AeatStatusKind.EXPEDIENTE,
        params={"since": None},
    )
    assert key1 == key2


def test_different_tax_ids_collide_never() -> None:
    key1 = make_cache_key(tax_id="X1234567L", surface=AeatStatusKind.EXPEDIENTE)
    key2 = make_cache_key(tax_id="Y9876543M", surface=AeatStatusKind.EXPEDIENTE)
    assert key1 != key2


def test_different_surfaces_collide_never() -> None:
    key1 = make_cache_key(tax_id="X1234567L", surface=AeatStatusKind.EXPEDIENTE)
    key2 = make_cache_key(tax_id="X1234567L", surface=AeatStatusKind.DEVOLUCION)
    assert key1 != key2


def test_different_base_urls_collide_never() -> None:
    key1 = make_cache_key(
        tax_id="X1234567L",
        surface=AeatStatusKind.EXPEDIENTE,
        base_url="https://sede.agenciatributaria.gob.es",
    )
    key2 = make_cache_key(
        tax_id="X1234567L",
        surface=AeatStatusKind.EXPEDIENTE,
        base_url="https://sede.preprod.agenciatributaria.gob.es",
    )
    assert key1 != key2


def test_key_shape() -> None:
    key = make_cache_key(tax_id="X1234567L", surface=AeatStatusKind.EXPEDIENTE)
    assert len(key) == 16
    assert all(ch in "0123456789abcdef" for ch in key)
