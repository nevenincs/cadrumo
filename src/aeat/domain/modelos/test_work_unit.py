"""Schema + behaviour tests for the modelo work-unit domain types.

These tests cover the deterministic content-addressing of
``work_unit_id``, the strict / frozen schema invariants on
``WorkUnit``, the catalogue's key-matches-record contract, and the
application-layer lifecycle actions (``create_work_unit``,
``list_work_units``, ``get_work_unit``, ``rename_work_unit``).

The action tests inject a purely in-memory fake repository so the
service layer is exercised without a SQL backend.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from aeat.application.modelo import (
    WorkUnitNotFoundError,
    create_work_unit,
    get_work_unit,
    list_work_units,
    rename_work_unit,
)
from aeat.domain.modelos._errors import ModeloValidationError
from aeat.domain.modelos._repository import remove_work_unit, upsert_work_unit
from aeat.domain.modelos._work_unit import (
    WorkUnit,
    WorkUnitCatalogue,
    derive_work_unit_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


class _InMemoryWorkUnitRepository:
    """Fake repository that stores a catalogue in process memory.

    The application services accept any object that exposes
    ``load`` and ``save`` matching the
    :class:`WorkUnitCatalogueRepository` contract. This stub
    implements just enough to drive the action layer without a
    SQL backend.
    """

    def __init__(self, *, initial: WorkUnitCatalogue | None = None) -> None:
        self._catalogue = initial or WorkUnitCatalogue()
        self.save_calls = 0

    def load(self) -> WorkUnitCatalogue:
        return self._catalogue

    def save(self, catalogue: WorkUnitCatalogue) -> None:
        self._catalogue = catalogue
        self.save_calls += 1


# ---------------------------------------------------------------------------
# derive_work_unit_id
# ---------------------------------------------------------------------------


def test_derive_work_unit_id_is_64_char_lowercase_hex() -> None:
    """The derived id shares the catalogue-key shape used elsewhere
    in the project: exactly 64 lowercase hex characters."""

    wid = derive_work_unit_id(
        bucket_id="default",
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="2009-y-siguientes",
    )
    assert len(wid) == 64
    assert all(ch in "0123456789abcdef" for ch in wid)


def test_derive_work_unit_id_is_deterministic() -> None:
    """Two identical inputs always produce the same identifier."""

    args: dict[str, Any] = {
        "bucket_id": "default",
        "modelo": "303",
        "filing_year": 2026,
        "period": "Q1",
        "revision_id": "2009-y-siguientes",
    }
    assert derive_work_unit_id(**args) == derive_work_unit_id(**args)


def test_derive_work_unit_id_distinguishes_buckets() -> None:
    """Different buckets produce different identifiers even when the
    other four axes match — bucket scope is part of the content-
    addressing key."""

    base: dict[str, Any] = {
        "modelo": "303",
        "filing_year": 2026,
        "period": "Q1",
        "revision_id": "2009-y-siguientes",
    }
    a = derive_work_unit_id(bucket_id="bucket-A", **base)
    b = derive_work_unit_id(bucket_id="bucket-B", **base)
    assert a != b


def test_derive_work_unit_id_normalises_case_on_modelo_and_period() -> None:
    """``modelo`` and ``period`` are normalised to uppercase before
    hashing so ``\"303\"`` and ``\"303\"`` (or ``\"q1\"`` and
    ``\"Q1\"``) hash to the same id."""

    canonical = derive_work_unit_id(
        bucket_id="default",
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="2009-y-siguientes",
    )
    lower_period = derive_work_unit_id(
        bucket_id="default",
        modelo="303",
        filing_year=2026,
        period="q1",
        revision_id="2009-y-siguientes",
    )
    assert canonical == lower_period


# ---------------------------------------------------------------------------
# WorkUnit schema
# ---------------------------------------------------------------------------


def _build_unit(**overrides: Any) -> WorkUnit:
    bucket_id = overrides.pop("bucket_id", "default")
    modelo = overrides.pop("modelo", "303")
    filing_year = overrides.pop("filing_year", 2026)
    period = overrides.pop("period", "Q1")
    revision_id = overrides.pop("revision_id", "2009-y-siguientes")
    wid = overrides.pop(
        "work_unit_id",
        derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
    )
    return WorkUnit(
        work_unit_id=wid,
        bucket_id=bucket_id,
        modelo=modelo,  # type: ignore[arg-type]
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=overrides.pop("name", "303-2026-Q1"),
        created_at=overrides.pop("created_at", _T0),
        updated_at=overrides.pop("updated_at", _T0),
    )


def test_work_unit_is_strict_frozen_and_rejects_extras() -> None:
    """``model_config = strict / frozen / extra='forbid'`` — extras
    fail validation; mutation after construction raises."""

    unit = _build_unit()
    with pytest.raises(ValidationError):
        WorkUnit(
            work_unit_id=unit.work_unit_id,
            bucket_id=unit.bucket_id,
            modelo="303",  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
            filing_year=2026,
            period="Q1",
            revision_id="2009-y-siguientes",
            name="303-2026-Q1",
            created_at=_T0,
            updated_at=_T0,
            unknown_axis="extra-value",  # type: ignore[call-arg]  # ty: ignore[unknown-argument]
        )
    with pytest.raises(ValidationError):
        unit.name = "renamed"  # type: ignore[misc]


def test_work_unit_rejects_id_that_does_not_match_derivation() -> None:
    """The content-addressing invariant: a persisted
    ``work_unit_id`` that disagrees with the deterministic
    derivation is refused by the schema."""

    with pytest.raises(ValidationError) as exc:
        _build_unit(work_unit_id="0" * 64)
    assert "does not match the derived id" in str(exc.value)


def test_work_unit_rejects_updated_before_created() -> None:
    """``updated_at`` must not precede ``created_at``."""

    earlier = _T0
    later = datetime(2026, 1, 16, 12, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        _build_unit(created_at=later, updated_at=earlier)


# ---------------------------------------------------------------------------
# WorkUnitCatalogue
# ---------------------------------------------------------------------------


def test_catalogue_rejects_key_record_mismatch() -> None:
    unit = _build_unit()
    bad_key = "f" * 64
    with pytest.raises(ValidationError):
        WorkUnitCatalogue(work_units={bad_key: unit})


def test_catalogue_from_work_units_rejects_duplicate_ids() -> None:
    """Building a catalogue from an iterable with two records under
    the same id fails fast."""

    unit = _build_unit()
    with pytest.raises(ModeloValidationError):
        WorkUnitCatalogue.from_work_units((unit, unit))


def test_upsert_returns_a_new_catalogue_and_leaves_original_unchanged() -> None:
    unit = _build_unit()
    catalogue = WorkUnitCatalogue()
    updated = upsert_work_unit(catalogue, unit)
    assert len(catalogue) == 0
    assert len(updated) == 1
    assert updated.get(unit.work_unit_id) is unit


def test_remove_returns_value_equal_catalogue_when_id_is_absent() -> None:
    catalogue = WorkUnitCatalogue()
    same = remove_work_unit(catalogue, "missing-id")
    assert same == catalogue


# ---------------------------------------------------------------------------
# Application actions — create_work_unit is idempotent
# ---------------------------------------------------------------------------


def test_create_work_unit_is_idempotent_on_the_four_axis_key() -> None:
    """Two ``create_work_unit`` calls with the same four-axis key
    return the same record without producing duplicates."""

    repo = _InMemoryWorkUnitRepository()
    first = create_work_unit(
        bucket_id="default",
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="2009-y-siguientes",
        repository=repo,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        clock=_T0,
    )
    second = create_work_unit(
        bucket_id="default",
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="2009-y-siguientes",
        name="ignored-because-already-exists",
        repository=repo,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        clock=_T0,
    )
    assert first.work_unit_id == second.work_unit_id
    assert second.name == first.name  # rename is the dedicated mutation
    assert repo.save_calls == 1  # second call is a no-op


def test_create_work_unit_uses_default_name_when_no_name_supplied() -> None:
    repo = _InMemoryWorkUnitRepository()
    unit = create_work_unit(
        bucket_id="default",
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="2009-y-siguientes",
        repository=repo,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        clock=_T0,
    )
    assert unit.name == "303-2026-Q1"


def test_create_work_unit_honours_explicit_name() -> None:
    repo = _InMemoryWorkUnitRepository()
    unit = create_work_unit(
        bucket_id="default",
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="2009-y-siguientes",
        name="renta-q1-2026-draft",
        repository=repo,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        clock=_T0,
    )
    assert unit.name == "renta-q1-2026-draft"


# ---------------------------------------------------------------------------
# Application actions — list / get / rename
# ---------------------------------------------------------------------------


def test_list_work_units_sorts_by_bucket_year_modelo_period() -> None:
    repo = _InMemoryWorkUnitRepository()
    for bucket, modelo, year, period in (
        ("bucket-B", "303", 2026, "Q1"),
        ("bucket-A", "303", 2026, "Q2"),
        ("bucket-A", "130", 2026, "Q1"),
    ):
        create_work_unit(
            bucket_id=bucket,
            modelo=modelo,
            filing_year=year,
            period=period,
            revision_id="rev",
            repository=repo,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
            clock=_T0,
        )
    units = list_work_units(repository=repo)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    keys = tuple((u.bucket_id, str(u.modelo), u.period) for u in units)
    assert keys == (
        ("bucket-A", "130", "Q1"),
        ("bucket-A", "303", "Q2"),
        ("bucket-B", "303", "Q1"),
    )


def test_list_work_units_filters_by_bucket_id() -> None:
    repo = _InMemoryWorkUnitRepository()
    create_work_unit(
        bucket_id="bucket-A",
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="rev",
        repository=repo,  # ty: ignore[invalid-argument-type]
        clock=_T0,  # type: ignore[arg-type]
    )
    create_work_unit(
        bucket_id="bucket-B",
        modelo="303",
        filing_year=2026,
        period="Q2",
        revision_id="rev",
        repository=repo,  # ty: ignore[invalid-argument-type]
        clock=_T0,  # type: ignore[arg-type]
    )
    only_a = list_work_units(bucket_id="bucket-A", repository=repo)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    assert len(only_a) == 1
    assert only_a[0].bucket_id == "bucket-A"


def test_get_work_unit_raises_when_id_is_absent() -> None:
    repo = _InMemoryWorkUnitRepository()
    with pytest.raises(WorkUnitNotFoundError):
        get_work_unit("missing", repository=repo)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


def test_rename_work_unit_preserves_work_unit_id_and_bumps_updated_at() -> None:
    repo = _InMemoryWorkUnitRepository()
    original = create_work_unit(
        bucket_id="default",
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="rev",
        repository=repo,  # ty: ignore[invalid-argument-type]
        clock=_T0,  # type: ignore[arg-type]
    )
    later = datetime(2026, 2, 1, 12, 0, 0, tzinfo=UTC)
    renamed = rename_work_unit(
        original.work_unit_id,
        "renta-q1-2026-final",
        repository=repo,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        clock=later,
    )
    assert renamed.work_unit_id == original.work_unit_id
    assert renamed.name == "renta-q1-2026-final"
    assert renamed.updated_at == later
    assert renamed.created_at == original.created_at


def test_rename_work_unit_raises_when_id_is_absent() -> None:
    repo = _InMemoryWorkUnitRepository()
    with pytest.raises(WorkUnitNotFoundError):
        rename_work_unit("missing", "ignored", repository=repo)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


# ---------------------------------------------------------------------------
# Boundary regression guards
# ---------------------------------------------------------------------------


def test_no_parallel_work_unit_model_outside_canonical_module() -> None:
    """``WorkUnit`` lives in ``aeat.domain.modelos._work_unit``. Any
    other module that declares a Pydantic class named
    ``WorkUnit`` competes with the canonical surface."""

    from pathlib import Path

    from aeat.core.paths import PROJECT_ROOT

    source_root = PROJECT_ROOT / "src" / "aeat"
    canonical = source_root / "domain" / "modelos" / "_work_unit.py"
    forbidden = "class WorkUnit("
    offenders: list[Path] = []
    for py_file in source_root.rglob("*.py"):
        if py_file == canonical:
            continue
        if py_file.name.startswith("test_"):
            continue
        if forbidden in py_file.read_text(encoding="utf-8"):
            offenders.append(py_file)
    assert offenders == [], f"Parallel WorkUnit class outside the canonical module: {[str(p) for p in offenders]}"


def test_no_parallel_work_unit_storage_namespace() -> None:
    """The work-unit catalogue persists under the
    ``aeat.domain.modelos.work_units`` namespace. Any other
    module referencing a competing namespace string is a shadow
    storage location."""

    from pathlib import Path

    from aeat.core.paths import PROJECT_ROOT

    source_root = PROJECT_ROOT / "src" / "aeat"
    canonical = source_root / "domain" / "modelos" / "_repository.py"
    forbidden_namespace = '"aeat.domain.modelos.work_units"'
    offenders: list[Path] = []
    for py_file in source_root.rglob("*.py"):
        if py_file == canonical:
            continue
        if py_file.name.startswith("test_"):
            continue
        if forbidden_namespace in py_file.read_text(encoding="utf-8"):
            offenders.append(py_file)
    assert offenders == [], (
        f"Parallel work-unit storage namespace outside the canonical repository: {[str(p) for p in offenders]}"
    )
