"""Official-source and canonical-owner proof for M303 prorrata activity rows."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from .....core import ProrrataActivityRowType, ProrrataRegisterRegime
from .....core.resources import bundled_path
from .....domain.prorrata_register import ProrrataActivityRow, ProrrataRegister, ProrrataRegisterEntry
from .. import (
    InputKind,
    RegistryValidationError,
    build_snapshot,
    extract_record_design,
    initial_value_casilla_ids,
    load_catalogue_file,
    project_m303_prorrata_activity_rows,
    resolve_record_design_binary,
)
from .._formula_initial_values import initial_values
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ENDPOINTS = frozenset(str(number) for number in range(500, 525))
_DESIGNS = (
    ("2023", "aeat-dr-303-2023", 2023, "2023", "4T", 3),
    ("2024-hasta-08-y-2t", "aeat-dr-303-2024-early", 2024, "2024-early", "2T", 3),
    ("2024-desde-09-y-3t", "aeat-dr-303-2024-late", 2024, "2024-late", "4T", 3),
    ("2025", "aeat-dr-303-2025", 2025, "2025", "4T", 3),
    ("2026-y-siguientes", "aeat-dr-303-2026", 2026, "2026", "4T", 4),
)
_FIELD_NAMES = (
    "cnae",
    "operaciones-total",
    "operaciones-con-derecho",
    "tipo",
    "porcentaje",
)
_OFFICIAL_TYPE_CODES = ("An", "N", "N", "An", "Num")
_CASILLA_TAG = re.compile(r"\[(5\d{2})\]")


@pytest.mark.parametrize(
    ("revision_id", "source_ref", "filing_year", "design_epoch", "period", "cnae_width"),
    _DESIGNS,
)
def test_real_dp30305_binary_and_registry_define_exact_five_by_five_projection_endpoints(
    revision_id: str,
    source_ref: str,
    filing_year: int,
    design_epoch: str,
    period: str,
    cnae_width: int,
) -> None:
    """Every source epoch proves its own box, slot, width, and endpoint data."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )
    sheet = next(item for item in extract_record_design(resolved.path) if item.name == "DP30305")
    source_fields = tuple(
        field
        for field in sheet.fields
        if (match := _CASILLA_TAG.search(field.description)) is not None and match.group(1) in _ENDPOINTS
    )
    assert tuple(_CASILLA_TAG.search(field.description).group(1) for field in source_fields) == tuple(
        str(number) for number in range(500, 525)
    )
    assert tuple(field.type_code for field in source_fields) == _OFFICIAL_TYPE_CODES * 5
    assert tuple(field.length for field in source_fields) == (cnae_width, 17, 17, 1, 5) * 5
    expected_offsets = (
        (
            13,
            16,
            33,
            50,
            51,
            56,
            59,
            76,
            93,
            94,
            99,
            102,
            119,
            136,
            137,
            142,
            145,
            162,
            179,
            180,
            185,
            188,
            205,
            222,
            223,
        )
        if cnae_width == 3
        else (
            13,
            17,
            34,
            51,
            52,
            57,
            61,
            78,
            95,
            96,
            101,
            105,
            122,
            139,
            140,
            145,
            149,
            166,
            183,
            184,
            189,
            193,
            210,
            227,
            228,
        )
    )
    assert tuple(field.offset for field in source_fields) == expected_offsets

    modelo, registry_catalogues = _committed_modelo("303")
    revision = build_snapshot(
        modelo,
        registry_catalogues,
        source_root=source_root,
        filing_year=filing_year,
        period=period,
    ).revision
    assert revision.id == revision_id
    endpoints = tuple(
        casilla for casilla in revision.casillas if tuple(casilla.section[:3]) == ("iva", "prorrata", "actividad")
    )
    assert frozenset(str(casilla.id) for casilla in endpoints) == _ENDPOINTS
    assert len(endpoints) == 25
    assert all(casilla.input_kind is InputKind.PROJECTION_ONLY for casilla in endpoints)
    assert all(
        casilla.formula is None and casilla.binding is None and not casilla.alternate_bindings for casilla in endpoints
    )
    assert all(not casilla.export_refs for casilla in endpoints)
    assert all(
        frozenset(str(ref) for ref in casilla.source_refs) == {source_ref, "aeat-modelo-303-procedure"}
        for casilla in endpoints
    )
    cnae_endpoints = tuple(casilla for casilla in endpoints if casilla.section[-1] == "cnae")
    assert len(cnae_endpoints) == 5
    assert all(
        casilla.constraints is not None and casilla.constraints.max_length == cnae_width for casilla in cnae_endpoints
    )


def test_projection_only_endpoints_reject_direct_input_and_are_not_zero_seeded() -> None:
    """No numbered row endpoint can resurrect the deleted scalar/manual path."""
    modelo, catalogues = _committed_modelo("303")
    revision = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="4T",
    ).revision
    assert _ENDPOINTS.isdisjoint(set(initial_value_casilla_ids(revision)))

    with pytest.raises(RegistryValidationError, match="projection-only registry casillas cannot be supplied"):
        initial_values(
            revision,
            inputs={"500": Decimal("1")},
            binding_values={},
            target_period="4T",
        )


def test_typed_register_rows_project_to_only_their_deterministic_fixed_slots() -> None:
    """The canonical child collection is the sole value authority for 500-524."""
    modelo, catalogues = _committed_modelo("303")
    revision = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="4T",
    ).revision
    rows = tuple(
        ProrrataActivityRow(
            ejercicio=2025,
            activity_id=f"activity-{slot}",
            slot=slot,
            cnae_code=f"{470 + slot}",
            operaciones_total=Decimal(f"{slot}000.00"),
            operaciones_con_derecho=Decimal(f"{slot}00.00"),
            prorrata_type=ProrrataActivityRowType.GENERAL,
            percentage=Decimal(f"{slot}0.00"),
            evidence_reference=f"operator-evidence:activity-{slot}",
        )
        for slot in (5, 3, 1, 4, 2)
    )
    register = ProrrataRegister(
        entries=(ProrrataRegisterEntry(ejercicio=2025, regime=ProrrataRegisterRegime.GENERAL),),
        activity_rows=rows,
    )

    projection = project_m303_prorrata_activity_rows(revision, register=register, ejercicio=2025)

    assert tuple(item.slot for item in projection) == (1, 2, 3, 4, 5)
    assert tuple(
        (str(endpoint.casilla_id), endpoint.value) for item in projection for endpoint in item.endpoint_values()
    ) == tuple(
        (str(500 + (slot - 1) * 5 + field_index), value)
        for slot in range(1, 6)
        for field_index, value in enumerate(
            (
                f"{470 + slot}",
                Decimal(f"{slot}000.00"),
                Decimal(f"{slot}00.00"),
                "G",
                Decimal(f"{slot}0.00"),
            ),
        )
    )
