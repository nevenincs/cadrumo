"""An operator-stored value at the derived Art. 58 path wins over the computation.

Modelo 100 casilla 0513 (``irpf_minimo_descendientes_estatal``) is
``input_kind = computed``: the Art. 58/61 LIRPF aggregate is derived at calculate
time from the profile's ``renta_family.descendiente.{n}.*`` facts by
:func:`~application.modelo._profile_binding.inject_derived_minimo_descendientes_facts`.

The profile schema nevertheless ALSO declares
``renta_family.descendientes_minimos_aggregate_{year}`` as an ordinary writable
decimal field, so the operator write door accepts a value at the derived path.
That value is indexed unconditionally by ``_profile_fact_index`` before the
injector runs, and the injector declines to overwrite a key already present, so
the stored value reaches casilla 0513 and the law computation never happens --
with no diagnostic, no notice, and no refusal anywhere on the path.

These tests PIN THAT CURRENT BEHAVIOUR as a defect, so they pass at HEAD and are
expected to be inverted by the later work that closes the override channel. They
are not an endorsement of it.

Non-tautological by construction: nothing here recomputes an Art. 58 formula or
asserts a hand-derived euro figure. The discriminating comparison is between two
runs of the SAME production calculate entry point over the SAME descendant facts,
differing in exactly one way -- whether a sentinel is stored at the derived path.
The sentinel is chosen at import time and the control run's computed figure is
measured at runtime; the test asserts up front that the two differ, so an
assertion that the sentinel reached 0513 cannot be satisfied by the computation
coincidentally producing the same number.

Real adapters throughout: a real encrypted storage root, the real profile
registration and write doors (:func:`register_active_profile` via
:func:`register_minimal_profile`, then :func:`set_active_field`), the resident
registry authority, and the real bucket-aggregation calculate action
(:func:`calculate_modelo_revision_from_bucket_aggregation`) resolving its
repositories from the active bucket exactly as production does. Nothing is
monkeypatched -- in particular the source-resolver mesh is built as a tuple at
call time, so a patched module attribute would not be observed by it anyway.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import BindingId, CasillaId, validated_casilla_id
from ....domain.contribuyente import DescendantInfo, descendant_facts_from_list
from ....domain.user_profile import UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...user_profile import (
    UserProfileLifecycleRepository,
    profile_create_storage_span,
    record_to_path_values,
    set_active_field,
)
from ...workflow import workflow_state_repository
from .. import calculate_modelo_revision_from_bucket_aggregation, create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "51300000-0000-4000-8000-000000000513"
_YEAR = 2024
_PERIOD_CODE = "0A"
_T0 = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)

#: The estatal Art. 58/61 aggregate casilla the derived path feeds.
_ESTATAL_CASILLA = "0513"

#: The derived aggregate path the schema declares as a writable decimal field.
_DERIVED_PATH = f"renta_family.descendientes_minimos_aggregate_{_YEAR}"

#: A distinctive value no Art. 58 tranche arithmetic can produce: the registry
#: tranche amounts and the menor-3 supplement are all whole hundreds of euros,
#: and every eligibility split is a halving, so no combination lands on a
#: sub-euro remainder of 0.37. The test still asserts sentinel != computed at
#: runtime rather than relying on this reasoning alone.
_SENTINEL = Decimal("4321.37")

#: Two descendants born well before the filing year, both living with the
#: taxpayer: an unambiguously Art. 58.1-eligible pair that produces a non-zero
#: estatal aggregate the sentinel has to visibly displace.
_DESCENDANTS = (
    DescendantInfo(birth_date=date(2010, 3, 4)),
    DescendantInfo(birth_date=date(2014, 9, 18)),
)

#: The single binding the M100 estimación-directa régimen predicate needs set for
#: the annual revision to reach the mínimo casillas at all.
_ESTIMACION_DIRECTA_NORMAL: BindingId = f"renta-{_YEAR}-modelo-100-estimacion-directa-es-normal"

#: Sources the live mesh resolves from bucket state. Bindings owned by these are
#: left to the mesh; everything else is zero-defaulted so the calculation reaches
#: 0513 rather than failing on an unrelated unresolved slot.
_MESH_OWNED_SOURCES = frozenset(
    {
        "profile",
        "relation_prefill",
        "ledger_renta_income_aggregation",
        "ledger_renta_gastos_estimacion_directa_aggregation",
        "ledger_iva_aggregation",
        "ledger_oss_aggregation",
        "collectible_invoice",
        "payable_invoice",
    },
)


#: Profile-sourced bindings this profile leaves unresolved and that the M100
#: formula chain nonetheless requires a value for. They are unrelated to the
#: Art. 58 aggregate under test and are supplied as caller zeros -- exactly as
#: the sibling engine test does -- so the calculation reaches casilla 0513. The
#: two mínimo bindings are deliberately NOT in this set: caller-supplying either
#: would decide the very question the probe asks.
_UNRELATED_PROFILE_BINDINGS: tuple[BindingId, ...] = (
    f"renta-{_YEAR}-profile-guarderia-gastos-reales",
    f"renta-{_YEAR}-profile-cotizaciones-ss-madre",
    f"renta-{_YEAR}-profile-descendientes-menores-3",
)


def _casilla_id(value: str) -> CasillaId:
    return validated_casilla_id(value, surface="test_derived_aggregate_override_real_path.casilla")


def _non_mesh_zero_bindings() -> dict[BindingId, Decimal]:
    """Zero-default every M100 binding the live bucket mesh does not own."""
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_PERIOD_CODE)
    values: dict[BindingId, Decimal] = {
        binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.source not in _MESH_OWNED_SOURCES
    }
    values[_ESTIMACION_DIRECTA_NORMAL] = Decimal("1")
    values.update(dict.fromkeys(_UNRELATED_PROFILE_BINDINGS, Decimal("0")))
    return values


@pytest.fixture
def _active_profile(tmp_path: Path) -> Iterator[None]:
    """A real active profile carrying two Art. 58-eligible descendants.

    Registered through the production registration door, so the descendant facts
    are stored exactly as ``config profile descendiente add`` would store them.
    """
    overrides = dict(descendant_facts_from_list(_DESCENDANTS))
    # The surrounding renta facts the M100 annual revision needs to evaluate at
    # all. None of them touches the Art. 58 aggregate; they exist so the
    # calculation reaches casilla 0513 rather than refusing earlier.
    overrides["tax_residence.ccaa"] = "cataluna"
    overrides["filing_export.declaration_type"] = "1"
    overrides["renta_taxpayer.birth_date"] = "1978-05-11"
    overrides["renta_taxpayer.marital_status"] = "1"
    overrides["renta_family.minor_children_in_unit"] = "false"
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=_BUCKET,
                display_name="derived override probe",
                overrides=overrides,
            ),
        )
        yield


def _calculate_estatal_minimo() -> Decimal:
    """Run the real M100/2024/0A calculate action and return casilla 0513.

    Every repository is left to default, so the action resolves the active
    bucket through the same path production takes.
    """
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_PERIOD_CODE)
    work_unit = create_work_unit(
        bucket_id=_BUCKET,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD_CODE),
        revision_id=snapshot.revision.id,
        clock=_T0,
    )
    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        binding_values=_non_mesh_zero_bindings(),
        clock=_T0,
    )
    return Decimal(revision.casilla_values[_casilla_id(_ESTATAL_CASILLA)])


def _store_sentinel_at_derived_path() -> None:
    """Write the sentinel through the real single-field operator write door."""
    workflow_state_repository().update(
        lambda state: set_active_field(
            state,
            UserProfileFact(path=_DERIVED_PATH, value=_SENTINEL),
        ),
    )


@pytest.mark.usefixtures("_active_profile")
def test_operator_write_door_accepts_a_value_at_the_derived_aggregate_path() -> None:
    """The write door stores a value at the derived path without any refusal.

    This is the reachability half of the defect: the schema declares the derived
    aggregate as an ordinary editable decimal field, so nothing between the
    operator and storage judges the path illegitimate. A later Step makes this
    write raise; when it does, this test is the one to invert.
    """
    _store_sentinel_at_derived_path()

    record = UserProfileLifecycleRepository(bucket_id=_BUCKET).load(_BUCKET)
    stored = record_to_path_values(record)

    assert _DERIVED_PATH in stored, (
        f"the write door was expected to store {_DERIVED_PATH!r}; "
        f"if it now refuses, this defect is closed and the test must be inverted"
    )
    assert Decimal(str(stored[_DERIVED_PATH])) == _SENTINEL


@pytest.mark.usefixtures("_active_profile")
def test_stored_derived_aggregate_suppresses_the_art_58_computation() -> None:
    """A stored value at the derived path reaches casilla 0513 instead of the law.

    Two runs of the same production calculate entry point over the same two
    eligible descendants. The only difference is the stored sentinel, so the
    change in 0513 is attributable to it and to nothing else.
    """
    computed = _calculate_estatal_minimo()

    # Control: the descendants really do drive a non-zero Art. 58 aggregate, so
    # the second run has something to visibly displace. Without this the
    # override assertion could pass against a computation that was already
    # producing nothing.
    assert computed > Decimal("0"), (
        "the two declared descendants must produce a non-zero Art. 58 aggregate for this probe to discriminate"
    )
    # The assertion below cannot be satisfied by coincidence.
    assert computed != _SENTINEL

    _store_sentinel_at_derived_path()
    overridden = _calculate_estatal_minimo()

    assert overridden == _SENTINEL, (
        f"casilla {_ESTATAL_CASILLA} resolved to {overridden} rather than the stored "
        f"{_SENTINEL}; if the Art. 58 computation now wins, the override channel is "
        f"closed and this test must be inverted"
    )
    assert overridden != computed
