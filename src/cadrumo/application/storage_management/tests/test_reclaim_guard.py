"""Real-filesystem behaviour for aggregate storage-area reclaim."""

from __future__ import annotations

import pytest

from ....core import STORAGE_TAXONOMY, StorageArea, StorageScope, storage_path
from ....core.config import override_settings
from ..errors import StorageReclaimRefusedError, StorageReclaimUnconfirmedError
from .._service import RECLAIMABLE_LIFECYCLES, reclaim_storage_area

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _area_targets(area: StorageArea):
    return tuple(
        category
        for category, location in STORAGE_TAXONOMY.items()
        if location.grouping.value == area.value
        and location.scope is StorageScope.ROOT
        and location.lifecycle in RECLAIMABLE_LIFECYCLES
    )


class TestDurableAreasRefuse:
    @pytest.mark.parametrize("area", [StorageArea.STATE, StorageArea.EXPORTS])
    def test_refusal_keeps_real_content_intact(self, area: StorageArea, tmp_path) -> None:
        category = next(
            member
            for member, location in STORAGE_TAXONOMY.items()
            if location.grouping.value == area.value and location.scope is StorageScope.ROOT
        )
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(category)
            target.mkdir(parents=True, exist_ok=True)
            marker = target / "operator-data.bin"
            marker.write_bytes(b"must survive")

            with pytest.raises(StorageReclaimRefusedError) as caught:
                reclaim_storage_area(area, confirmed=True)

        assert caught.value.area is area
        assert marker.read_bytes() == b"must survive"
        assert "durable state" in caught.value.reason


class TestRegenerableAreasProceed:
    @pytest.mark.parametrize("area", [StorageArea.LOGS, StorageArea.CACHE])
    def test_confirmed_reclaim_empties_every_derived_target(self, area: StorageArea, tmp_path) -> None:
        targets = _area_targets(area)
        assert targets, "the positive control needs at least one taxonomy-derived target"
        with override_settings(cadrumo_local_storage_root=tmp_path):
            markers = []
            for index, category in enumerate(targets):
                target = storage_path(category)
                target.mkdir(parents=True, exist_ok=True)
                marker = target / f"entry-{index}.bin"
                marker.write_bytes(b"regenerable")
                markers.append(marker)

            report = reclaim_storage_area(area, confirmed=True)

        assert report.area is area
        assert report.removed_entries
        assert not [marker for marker in markers if marker.exists()]

    def test_cache_reclaim_preserves_durable_cache_members(self, tmp_path) -> None:
        durable = next(
            category
            for category, location in STORAGE_TAXONOMY.items()
            if location.grouping.value == StorageArea.CACHE.value and location.lifecycle not in RECLAIMABLE_LIFECYCLES
        )
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(durable)
            target.mkdir(parents=True, exist_ok=True)
            marker = target / "durable.bin"
            marker.write_bytes(b"preserved")

            reclaim_storage_area(StorageArea.CACHE, confirmed=True)

        assert marker.read_bytes() == b"preserved"

    def test_unconfirmed_area_reclaim_deletes_nothing(self, tmp_path) -> None:
        category = _area_targets(StorageArea.LOGS)[0]
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(category)
            target.mkdir(parents=True, exist_ok=True)
            marker = target / "diagnostic.log"
            marker.write_bytes(b"still here")

            with pytest.raises(StorageReclaimUnconfirmedError) as caught:
                reclaim_storage_area(StorageArea.LOGS)

        assert caught.value.area is StorageArea.LOGS
        assert marker.read_bytes() == b"still here"
