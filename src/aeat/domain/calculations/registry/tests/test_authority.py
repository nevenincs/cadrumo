"""Tests for the centralized validated registry authority."""

from __future__ import annotations

import hashlib
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....core import Period
from .....core.resources import bundled_path, resources
from .. import (
    CasillaId,
    RegistrySnapshotError,
    RegistryValidationError,
    ValidatedRegistryAuthority,
    calculate_registry_snapshot,
    validated_casilla_id,
)
from .._loader import _collect_registry_tree_fingerprints, clear_fingerprint_cache

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_LEGACY_AUTHORITY_CACHE_SCHEMA_VERSION = "casilla-reference-ambiguity-v2"
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M130_CARRY_FORWARD_CASILLA: CasillaId = validated_casilla_id("15", surface="_M130_CARRY_FORWARD_CASILLA")
_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_CASILLA")


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
            _M130_INGRESOS_CASILLA: Decimal("10000.00"),
            _M130_GASTOS_CASILLA: Decimal("4000.00"),
            _M130_RETENCIONES_CASILLA: Decimal("50.00"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("5000.00"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("20.00"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("5.00"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("100.00"),
        },
        # 1T cannot have a same-ejercicio prior-quarter saldo seed;
        # the M130 carry-forward selector returns no anchor for 1T.
        # C15 is computed from that zero carry-forward binding and the
        # positive C14 cap, not supplied as a fictional non-zero seed.
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("9500.00"),
        },
        date_context={"filing_period": date(2026, 4, 20)},
    )

    assert _M130_RESULTADO_CASILLA in result.values
    assert {entry.target_casilla_id for entry in result.entries} >= {_M130_RESULTADO_CASILLA}
    casilla_15 = next(obs for obs in result.observations if obs.casilla_id == _M130_CARRY_FORWARD_CASILLA)
    assert casilla_15.value == Decimal("0")
    assert casilla_15.formula_id == "modelo-130-resultados-negativos-anteriores-cap"
    assert casilla_15.absent_by_design is False


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

    assert [window.period for _, _, window in windows] == [
        Period.from_year_and_code(2026, "1T"),
        Period.from_year_and_code(2026, "2T"),
        Period.from_year_and_code(2026, "3T"),
        Period.from_year_and_code(2026, "4T"),
    ]
    assert [window.closes_on for _, _, window in windows] == sorted(window.closes_on for _, _, window in windows)


_MINIMAL_CATALOGUE_TOML = """\
[legal."test-ley-001:art-1"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/test/test-ley-001.html#a1"
document_id = "BOE-T-001"
article = "1"
permalink = "https://example.com/test"
effective_from = 2025-01-01
review_status = "reviewed"

[sources."test-source-001"]
evidence_tier = "layout_authority"
authority = "aeat"
kind = "record_design"
corpus_path = "corpus/test/test-source-001.pdf"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2025-01-01
source_url = "https://example.com/test-source"
review_status = "reviewed"
"""

_MINIMAL_MANIFEST_TOML = """\
[modelo]
id = "999"
title = "Cache invalidation test modelo"
official_name = "Cache invalidation test modelo"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""

_MINIMAL_REVISION_TOML_TEMPLATE = """\
[revisions."2025"]
label = "{label}"
valid_from = 2025-01-01
period_selector = {{ year_from = 2025, periods = ["0A"] }}
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
orden_aplicabilidad = ["test-ley-001:art-1"]

[[revisions."2025".application_links]]
id = "test-filing-link"
surface = "filing"
consumer = "cli.app"
requires_snapshot = true
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]

[[revisions."2025".casillas]]
id = "01"
number = "01"
label = "Test casilla"
section = ["test"]
data_type = "integer"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]

[[revisions."2025".workbook_parity_refs]]
id = "test-workbook-001"
workbook_source = "test-source-001"
fixture_id = "test-fixture-001"
formula_coverage = "record_design_layout"
runner_required = false
tolerance = "0.00"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""


def test_authority_cache_invalidates_when_fragmented_revision_changes(tmp_path: Path) -> None:
    """Authority caching must track recursive revision fragment fingerprints."""

    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    legal_dir.mkdir(parents=True)
    corpus_file = tmp_path / "corpus" / "test" / "test-source-001.pdf"
    corpus_file.parent.mkdir(parents=True)
    corpus_file.write_bytes(b"x" * 1000)

    (legal_dir / "catalogue.toml").write_text(_MINIMAL_CATALOGUE_TOML, encoding="utf-8")
    (registry_root / "modelos" / "999" / "manifest.toml").write_text(_MINIMAL_MANIFEST_TOML, encoding="utf-8")

    revision_path = revision_dir / "revision.toml"
    revision_path.write_text(_MINIMAL_REVISION_TOML_TEMPLATE.format(label="before"), encoding="utf-8")

    first = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    revision_path.write_text(_MINIMAL_REVISION_TOML_TEMPLATE.format(label="after cache invalidation"), encoding="utf-8")

    from .._loader import clear_fingerprint_cache

    clear_fingerprint_cache()
    second = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)

    assert first is not second
    assert first.modelo("999").revisions["2025"].label == "before"
    assert second.modelo("999").revisions["2025"].label == "after cache invalidation"


def test_authority_uses_fingerprint_backed_process_cache_and_invalidates(tmp_path: Path) -> None:
    """Authority loading may cache in-process, but changed registry files must invalidate it."""
    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    legal_dir.mkdir(parents=True)
    corpus_file = tmp_path / "corpus" / "test" / "test-source-001.pdf"
    corpus_file.parent.mkdir(parents=True)
    corpus_file.write_bytes(b"x" * 1000)

    (legal_dir / "catalogue.toml").write_text(_MINIMAL_CATALOGUE_TOML, encoding="utf-8")
    (registry_root / "modelos" / "999" / "manifest.toml").write_text(_MINIMAL_MANIFEST_TOML, encoding="utf-8")

    revision_path = revision_dir / "revision.toml"
    revision_path.write_text(_MINIMAL_REVISION_TOML_TEMPLATE.format(label="before"), encoding="utf-8")

    clear_fingerprint_cache()

    # Load 1: should run validation.
    auth1 = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    assert auth1._registry_validated is True

    # Load 2: same fingerprint returns the in-process cached authority.
    auth2 = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    assert auth2 is auth1

    # Modify file to invalidate cache
    revision_path.write_text(_MINIMAL_REVISION_TOML_TEMPLATE.format(label="after"), encoding="utf-8")
    clear_fingerprint_cache()

    # Load 3: changed fingerprint must build and validate a fresh authority.
    auth3 = ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    assert auth3._registry_validated is True
    assert auth3 is not auth1
    assert auth3.modelo("999").revisions["2025"].label == "after"


def test_authority_ignores_legacy_validated_marker_and_revalidates_ambiguity(tmp_path: Path) -> None:
    """A filesystem validation marker must not bypass casilla-reference guards."""

    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    legal_dir.mkdir(parents=True)
    corpus_file = tmp_path / "corpus" / "test" / "test-source-001.pdf"
    corpus_file.parent.mkdir(parents=True)
    corpus_file.write_bytes(b"x" * 1000)

    (legal_dir / "catalogue.toml").write_text(_MINIMAL_CATALOGUE_TOML, encoding="utf-8")
    (registry_root / "modelos" / "999" / "manifest.toml").write_text(_MINIMAL_MANIFEST_TOML, encoding="utf-8")

    ambiguous_revision = _MINIMAL_REVISION_TOML_TEMPLATE.format(label="ambiguous").replace(
        'number = "01"',
        'number = "99"',
        1,
    )
    ambiguous_revision += """\

[[revisions."2025".casillas]]
id = "DPX:01"
number = "01"
segmento = "DPX"
label = "Colliding display token"
section = ["test"]
data_type = "integer"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""
    (revision_dir / "revision.toml").write_text(ambiguous_revision, encoding="utf-8")

    clear_fingerprint_cache()
    fingerprints = _collect_registry_tree_fingerprints(registry_root)
    hasher = hashlib.sha256()
    hasher.update(_LEGACY_AUTHORITY_CACHE_SCHEMA_VERSION.encode("utf-8"))
    hasher.update(str(registry_root.resolve()).encode("utf-8"))
    hasher.update(str(tmp_path.resolve()).encode("utf-8"))
    for item in fingerprints:
        hasher.update(item[0].encode("utf-8"))
        hasher.update(str(item[1]).encode("utf-8"))
        hasher.update(str(item[2]).encode("utf-8"))
    stale_cache_path = Path(tempfile.gettempdir()) / f"aeat_registry_{hasher.hexdigest()}_validated.tmp"
    stale_cache_path.write_text("validated", encoding="utf-8")

    try:
        with pytest.raises(RegistryValidationError, match="casilla reference token '01' is ambiguous"):
            ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
    finally:
        stale_cache_path.unlink(missing_ok=True)


def test_authority_load_rejects_reused_number_with_bare_casilla_owner(tmp_path: Path) -> None:
    """A reused printed number with one bare-id owner must fail at authority load."""

    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    revision_dir = registry_root / "modelos" / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    legal_dir.mkdir(parents=True)
    corpus_file = tmp_path / "corpus" / "test" / "test-source-001.pdf"
    corpus_file.parent.mkdir(parents=True)
    corpus_file.write_bytes(b"x" * 1000)

    (legal_dir / "catalogue.toml").write_text(_MINIMAL_CATALOGUE_TOML, encoding="utf-8")
    (registry_root / "modelos" / "999" / "manifest.toml").write_text(_MINIMAL_MANIFEST_TOML, encoding="utf-8")

    ambiguous_revision = _MINIMAL_REVISION_TOML_TEMPLATE.format(label="ambiguous") + """\

[[revisions."2025".casillas]]
id = "DPX:01"
number = "01"
segmento = "DPX"
label = "Segment qualified owner"
section = ["test"]
data_type = "integer"
legal_refs = ["test-ley-001:art-1"]
source_refs = ["test-source-001"]
"""
    (revision_dir / "revision.toml").write_text(ambiguous_revision, encoding="utf-8")

    clear_fingerprint_cache()

    with pytest.raises(RegistryValidationError, match=r"ambiguous bare casilla ids \['01'\]"):
        ValidatedRegistryAuthority.load(registry_root, source_root=tmp_path)
