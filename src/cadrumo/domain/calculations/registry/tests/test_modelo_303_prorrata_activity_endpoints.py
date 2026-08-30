"""Official-source and canonical-owner proof for M303 prorrata activity rows."""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

import pytest

from .....core import (
    EstadoCasillaOficial,
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
    ProrrataActivityRowType,
    ProrrataRegisterRegime,
)
from .....core.modelo import Modelo
from .....core.i18n import tr
from .....core.resources import bundled_path
from .....domain.prorrata_register import ProrrataActivityRow, ProrrataRegister, ProrrataRegisterEntry
from .._validate import RegistryValidator
from ..corpus_catalogue import resolve_record_design_binary
from ..errors import RegistryValidationError
from ..export import clasificar_casillas_oficiales
from ..formula_initial_values import initial_value_casilla_ids, initial_values
from ..loader import load_catalogue_file
from ..m303_prorrata_activity_projection import project_m303_prorrata_activity_rows
from ..record_design import extract_record_design
from ..schema_input_kind import InputKind
from ..snapshot import build_snapshot
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
_NUMBERED_PROJECTION_ENDPOINTS = _ENDPOINTS | frozenset(str(number) for number in range(700, 736))
#: The projection kinds every supported M303 design epoch declares IDENTICALLY.
#: Measured across all six revisions, these six counts do not move.
#:
#: `m303_regimen_simplificado_fact` is deliberately NOT here: it is the one kind
#: that tracks the design epoch (38, 96, 100, 106 and 108 across the six
#: revisions), because AEAT's simplified-regime fact rows change with the form.
#: Its per-epoch count is pinned where it belongs -- the semantic-map census
#: states it for each epoch against that epoch's own map -- so repeating a
#: single number here could only be wrong for five of the six.
_INVARIANT_PROJECTION_KIND_COUNTS = {
    "m303_prorrata_activity": 25,
    "m303_differentiated_deduction": 36,
    "m303_regimen_simplificado_activity": 6,
    "m303_regimen_simplificado_module": 28,
    "m303_exonerado_390_activity": 12,
    "m303_exonerado_390_operaciones_terceros": 1,
}


def _projection_refs() -> tuple[M303ProrrataActivityProjectionRef, ...]:
    return tuple(
        M303ProrrataActivityProjectionRef(
            projection_kind="m303_prorrata_activity",
            slot=slot,
            field=field,
            casilla_id=str(500 + (slot - 1) * 5 + field_index),
        )
        for slot in range(1, 6)
        for field_index, field in enumerate(M303ProrrataActivityProjectionField)
    )


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
    sheet = next(item for item in extract_record_design(resolved.path).accept_partial() if item.name == "DP30305")
    source_fields = tuple(
        field
        for field in sheet.fields
        if (match := _CASILLA_TAG.search(field.description)) is not None and match.group(1) in _ENDPOINTS
    )
    source_casillas = tuple(
        match.group(1) for field in source_fields if (match := _CASILLA_TAG.search(field.description)) is not None
    )
    assert source_casillas == tuple(str(number) for number in range(500, 525))
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
    # Each of the 25 exports to exactly one DP30305 field -- the sheet this case
    # reads from the OFFICIAL BINARY above to derive the five-by-five grid. This
    # asserted they export nowhere, which contradicted that evidence once the
    # layouts were authored: a box AEAT prints on the record design belongs in
    # the fichero.
    assert all(len(casilla.export_refs) == 1 for casilla in endpoints)
    assert all("dp30305" in str(casilla.export_refs[0]).casefold() for casilla in endpoints)
    assert len({casilla.export_refs[0] for casilla in endpoints}) == len(endpoints)
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


@pytest.mark.parametrize(
    ("revision_id", "source_ref", "filing_year", "_design_epoch", "period", "_cnae_width"),
    _DESIGNS,
)
def test_real_m303_revision_owns_the_complete_grounded_projection_declaration_matrix(
    revision_id: str,
    source_ref: str,
    filing_year: int,
    _design_epoch: str,
    period: str,
    _cnae_width: int,
) -> None:
    """Each supported record-design epoch declares every typed endpoint once."""
    modelo, catalogues = _committed_modelo("303")
    revision = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
    ).revision

    assert revision.id == revision_id
    # Whether this revision carries an export layout is incidental to the
    # projection-endpoint matrix asserted below, and it stopped being true when
    # the campaign authored modelo 303's layouts.
    measured = Counter(str(declaration.projection_ref.projection_kind) for declaration in revision.projection_endpoints)
    assert {kind: measured[kind] for kind in _INVARIANT_PROJECTION_KIND_COUNTS} == _INVARIANT_PROJECTION_KIND_COUNTS
    # The one epoch-tracking kind is asserted present and non-empty rather than
    # counted; the census owns its per-epoch figure.
    assert measured["m303_regimen_simplificado_fact"] > 0
    assert set(measured) == set(_INVARIANT_PROJECTION_KIND_COUNTS) | {"m303_regimen_simplificado_fact"}
    # Every declaration is a distinct endpoint: a duplicated projection_ref would
    # leave the counts identical while two slots claimed one home.
    assert len({declaration.projection_ref for declaration in revision.projection_endpoints}) == len(
        revision.projection_endpoints
    )
    # Grounding is per FAMILY, and the split follows the projection kind exactly
    # (verified 1:1 on every revision). This asserted the procedural pair on all
    # declarations, which the simplified-regime endpoints have since outgrown --
    # they now cite the articles that ESTABLISH the regimen simplificado plus the
    # annual Orden that fixes its modules, which is stronger grounding than the
    # procedural pair, not weaker.
    for declaration in revision.projection_endpoints:
        kind = str(declaration.projection_ref.projection_kind)
        if "regimen_simplificado" in kind:
            assert declaration.legal_refs == ("ley-37-1992:art-122", "ley-37-1992:art-123"), kind
            # The design ref plus the year's modulos Orden.
            assert source_ref in declaration.source_refs, kind
            assert len(declaration.source_refs) == 2, declaration.source_refs
        else:
            assert declaration.legal_refs == ("rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"), kind
            assert declaration.source_refs == (source_ref,), kind
    numbered = frozenset(
        str(casilla_id)
        for declaration in revision.projection_endpoints
        if (
            casilla_id := declaration.projection_ref.casilla_id
            if hasattr(declaration.projection_ref, "casilla_id")
            else None
        )
        is not None
    )
    assert numbered == _NUMBERED_PROJECTION_ENDPOINTS
    assert all(
        next(casilla for casilla in revision.casillas if casilla.id == casilla_id).input_kind
        is InputKind.PROJECTION_ONLY
        for casilla_id in numbered
    )
    statuses = clasificar_casillas_oficiales(revision)
    assert all(statuses[casilla_id] is EstadoCasillaOficial.ADDRESSED for casilla_id in numbered)


def test_m303_projection_declaration_refuses_a_foreign_revision_record_design_source() -> None:
    """A mutation cannot transplant a 2025 endpoint declaration into the 2026 revision."""
    modelo, catalogues = _committed_modelo("303")
    revision = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="4T",
    ).revision
    foreign = revision.projection_endpoints[0].model_copy(update={"source_refs": ("aeat-dr-303-2025",)})
    revised = revision.model_copy(update={"projection_endpoints": (foreign, *revision.projection_endpoints[1:])})
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: revised}})

    with pytest.raises(RegistryValidationError, match="outside the selected revision authority"):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_m303_projection_declaration_matrix_cannot_be_deleted_before_snapshot_construction() -> None:
    """All real 2025 projection-only casillas require their revision declaration matrix."""
    modelo, catalogues = _committed_modelo("303")
    revision = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="4T",
    ).revision
    # Non-empty, not a tally: this gate's value is the REFUSAL below, and the
    # only thing the pre-state must establish is that there is a matrix to
    # delete. The pinned 108 was a moment -- the 2025 revision declares 216 now.
    assert revision.projection_endpoints
    deleted = revision.model_copy(update={"projection_endpoints": ()})
    mutated_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: deleted}})

    with pytest.raises(
        RegistryValidationError, match="projection_only casillas lack revision-owned projection declarations"
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)
    with pytest.raises(
        RegistryValidationError, match="projection_only casillas lack revision-owned projection declarations"
    ):
        build_snapshot(
            mutated_modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period="4T",
        )


def test_real_layoutless_revision_without_projection_only_casillas_needs_no_declarations() -> None:
    """The completeness gate is scoped to the canonical projection-only capability."""
    modelo, catalogues = _committed_modelo("130")
    revision = modelo.revisions["2019-y-siguientes"]

    # The claim is about PROJECTION-ONLY capability, not about layouts: a
    # revision with no projection-only casilla needs no declarations whether or
    # not it exports. Modelo 130 was chosen as a layoutless subject and the
    # campaign has since authored its export layout, so asserting the absence
    # asserted the state of the campaign rather than the property.
    assert revision.projection_endpoints == ()
    assert all(casilla.input_kind is not InputKind.PROJECTION_ONLY for casilla in revision.casillas)
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_typed_register_rows_project_to_only_their_deterministic_fixed_slots() -> None:
    """The canonical child collection is the sole value authority for 500-524."""
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
        entries=(
            ProrrataRegisterEntry(ejercicio=2025, regime=ProrrataRegisterRegime.GENERAL, especial_transition=None),
        ),
        activity_rows=rows,
    )

    projection = project_m303_prorrata_activity_rows(
        projection_refs=_projection_refs(),
        register=register,
        ejercicio=2025,
    )

    assert tuple(item.slot for item in projection) == (1, 2, 3, 4, 5)
    assert tuple(
        (str(endpoint.projection_ref.casilla_id), endpoint.value)
        for item in projection
        for endpoint in item.endpoint_values()
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


def _general_register(ejercicio: int, *, slots: tuple[int, ...]) -> ProrrataRegister:
    rows = tuple(
        ProrrataActivityRow(
            ejercicio=ejercicio,
            activity_id=f"activity-{slot}",
            slot=slot,
            cnae_code=f"{470 + slot}",
            operaciones_total=Decimal(f"{slot}000.00"),
            operaciones_con_derecho=Decimal(f"{slot}00.00"),
            prorrata_type=ProrrataActivityRowType.GENERAL,
            percentage=Decimal(f"{slot}0.00"),
            evidence_reference=f"operator-evidence:activity-{slot}",
        )
        for slot in slots
    )
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(ejercicio=ejercicio, regime=ProrrataRegisterRegime.GENERAL, especial_transition=None),
        ),
        activity_rows=rows,
    )


def test_incomplete_ejercicio_refuses_with_the_typed_localised_operator_facing_refusal() -> None:
    """A partial DP30305 activity-row collection must fail before it can mask an under-declaration.

    Only 3 of the 5 official slots are recorded for an applicable ejercicio,
    so the live export-path projector must refuse rather than silently
    emit a thin endpoint set.
    """
    register = _general_register(2025, slots=(1, 2, 3))

    with pytest.raises(RegistryValidationError) as excinfo:
        project_m303_prorrata_activity_rows(
            projection_refs=_projection_refs(),
            register=register,
            ejercicio=2025,
        )

    error = excinfo.value
    assert error.translated_message == "application.filing.m303_prorrata_activity_rows.errors.activity_rows_incomplete"
    assert error.context == {
        "modelo": Modelo.M303.value,
        "filing_year": 2025,
        "required_slot_first": 1,
        "required_slot_last": 5,
    }
    for locale in ("en", "es", "ca", "hu"):
        rendered = tr(error.translated_message, locale=locale)
        assert rendered != error.translated_message, (
            f"locale key {error.translated_message!r} is absent from the {locale!r} catalogue"
        )
        assert rendered


def test_complete_ejercicio_is_not_refused_by_the_activity_rows_completeness_gate() -> None:
    """Five recorded slots project cleanly -- a guard that refuses everything is broken too."""
    register = _general_register(2025, slots=(1, 2, 3, 4, 5))

    projection = project_m303_prorrata_activity_rows(
        projection_refs=_projection_refs(),
        register=register,
        ejercicio=2025,
    )

    assert tuple(item.slot for item in projection) == (1, 2, 3, 4, 5)
