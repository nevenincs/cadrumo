"""Tests for the centralized validated registry authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.core.resources import bundled_path, resources

from . import RegistrySnapshotError, ValidatedRegistryAuthority, calculate_registry_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def test_authority_returns_cached_validated_snapshot_for_repeated_filing_context() -> None:
    authority = resources().modelos.authority

    first = authority.snapshot("130", filing_year=2026, period="1T")
    second = authority.snapshot("130", filing_year=2026, period="1T")

    assert first is second
    assert first.revision.period_selector.includes_year(2026)
    assert "1T" in first.revision.period_selector.periods


def test_authority_snapshot_runs_real_modelo_calculation() -> None:
    authority = resources().modelos.authority
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("10000.00"),
            "02": Decimal("4000.00"),
            "05": Decimal("100.00"),
            "06": Decimal("50.00"),
            "08": Decimal("5000.00"),
            "10": Decimal("20.00"),
            "16": Decimal("5.00"),
            "18": Decimal("100.00"),
        },
        # 1T cannot have a same-ejercicio prior-quarter saldo seed;
        # the M130 carry-forward selector returns no anchor for 1T
        # and the bound casilla materialises Decimal("0") with the
        # absent_by_design provenance marker. binding_values omits
        # the carry-forward binding to exercise the absent-by-design
        # path through the runtime, NOT a fictional non-zero seed.
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("9500.00"),
        },
        date_context={"filing_period": date(2026, 4, 20)},
    )

    assert "19" in result.values
    assert {entry.target for entry in result.entries} >= {"19"}
    casilla_15 = next(obs for obs in result.observations if obs.casilla_id == "15")
    assert casilla_15.value == Decimal("0")
    assert casilla_15.absent_by_design is True


def test_authority_snapshot_is_authority_owned_revision_projection() -> None:
    authority = ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=bundled_path())

    snapshot = authority.snapshot("130", filing_year=2026, period="1T")
    modelo = authority.modelo("130")

    assert snapshot.modelo is modelo
    assert snapshot.revision == modelo.revisions[snapshot.revision.id]
    assert authority.snapshot("130", filing_year=2026, period="1T") is snapshot
    assert "130" in authority._validated_modelos


def test_authority_rejects_unknown_modelo() -> None:
    authority = resources().modelos.authority

    with pytest.raises(RegistrySnapshotError, match="999"):
        authority.snapshot("999", filing_year=2026, period="1T")


def test_authority_deadline_windows_are_validated_and_sorted() -> None:
    authority = resources().modelos.authority

    windows = authority.deadline_windows(2026, modelos=("130",))

    assert [window.period for _, _, window in windows] == ["2026Q1", "2026Q2", "2026Q3", "2026Q4"]
    assert [window.closes_on for _, _, window in windows] == sorted(window.closes_on for _, _, window in windows)


def test_authority_cache_invalidates_when_fragmented_revision_changes(tmp_path: Path) -> None:
    """Authority caching must track recursive revision fragment fingerprints."""

    registry_root = tmp_path / "registry" / "aeat"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (registry_root / "modelos" / "999" / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Cache test"
official_name = "Cache test"
tax_domain = "test"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    revision_path = revision_dir / "revision.toml"
    revision_path.write_text(
        """
[revisions."2025"]
label = "before"
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )

    first = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    revision_path.write_text(
        """
[revisions."2025"]
label = "after cache invalidation"
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    second = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)

    assert first is not second
    assert first.modelo("999").revisions["2025"].label == "before"
    assert second.modelo("999").revisions["2025"].label == "after cache invalidation"
