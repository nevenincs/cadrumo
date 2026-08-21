"""Modelo 190 registry behaviour for annual Modelo 111 monetary links and withholding count."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.aggregation import RetencionClave
from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .....tests.registry_observations import registry_grounded_modelo_observation
from .. import (
    RegistryValidator,
    WithholdingObservation,
    build_snapshot,
    calculate_registry_snapshot,
    relation_source_requirements,
    resolve_available_bound_inputs_by_casilla_id,
    resolve_relation_values_from_observations,
    resolve_withholding_binding_values,
)
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_WWW6_HOST = aeat_host("www6")
_DECL_TOTAL_PERCEPCIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.total-percepciones",
    surface="_DECL_TOTAL_PERCEPCIONES_CASILLA",
)
_DECL_PERCEPCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.percepciones-total",
    surface="_DECL_PERCEPCIONES_TOTAL_CASILLA",
)
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.retenciones-total",
    surface="_DECL_RETENCIONES_TOTAL_CASILLA",
)
_M111_IMPORTE_SOURCE_CASILLAS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(value, surface="_M111_IMPORTE_SOURCE_CASILLAS")
    for value in ("02", "05", "08", "11", "14", "17", "20", "23", "26")
)
_M111_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "28",
    surface="_M111_RETENCIONES_TOTAL_CASILLA",
)
_RETIRED_M111_PERCEPCIONES_SOURCE_CASILLAS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(value, surface="_RETIRED_M111_PERCEPCIONES_SOURCE_CASILLAS")
    for value in ("01", "04", "07", "10", "13", "16", "19", "22", "25")
)
_M190_PERCEPCIONES_BINDING = "modelo-190-percepciones-anual"


def _withholding_observation(source_id: str, nif: str, clave: str) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=source_id,
        perceptor_tax_id=nif,
        transaction_date=date(2025, 6, 1),
        clave=RetencionClave(clave),
        percibido_dinerario=Decimal("1000"),
        retencion_practicada=Decimal("190"),
    )


def test_modelo_190_guidance_and_layout_sources_are_separated() -> None:
    modelo, catalogues = _committed_modelo("190")
    instructions = catalogues.sources["aeat-modelo-190-instructions-2025"]

    assert "aeat-modelo-190-instructions-2025" in modelo.source_refs
    assert instructions.evidence_tier == "official_source_guidance"
    assert instructions.authority == "aeat"
    assert instructions.kind == "manual_pdf"
    assert (bundled_path() / instructions.corpus_path).is_file()
    assert catalogues.sources["aeat-dr-190-2025"].evidence_tier == "layout_authority"
    assert catalogues.sources["boe-modelo-190-2025-form"].evidence_tier == "layout_authority"
    assert catalogues.sources["boe-modelo-190-2025-amendment"].evidence_tier == "layout_authority"
    # Every revision, rather than one named id. The id pinned here stopped
    # existing when modelo 190's span was split into "2024" and
    # "2025-y-siguientes", and the lookup raised before reaching any assertion --
    # so the separation this test exists to prove went unchecked in BOTH.
    checked = 0
    for revision in modelo.revisions.values():
        for formula in revision.formulas:
            for citation in formula.source_citations:
                assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"
                checked += 1
        for binding in revision.bindings:
            for citation in binding.source_citations:
                assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"
                checked += 1
    assert checked, "no formula or binding citation was checked, so this proves nothing"


def test_modelo_190_validates_and_gates_workflow_surfaces_through_snapshot() -> None:
    modelo, catalogues = _committed_modelo("190")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period="0A",
    )

    assert snapshot.revision.orden_aplicabilidad == (
        "orden-eha-3127-2009:art-1",
        "orden-hac-1431-2025:art-2",
    )
    construct = snapshot.revision.constructs[0]
    linked_surfaces = {
        link.surface for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    # "verification" is deliberately absent. It is NOT a member of
    # ApplicationLink.surface -- the Literal admits calculation, filing, review,
    # approval, reconciliation, export, deadline, portal, extractor, workflow,
    # communication and payer_delivery -- so no registry data can declare it,
    # and none does: zero across every bundled modelo. Asserting it here was not
    # a data gap waiting to be filled but an expectation the schema forbids, and
    # it could never have passed. If a verification surface is wanted, that is a
    # schema decision with its own grounding, not something this test can imply.
    assert {
        "calculation",
        "filing",
        "deadline",
        "review",
        "approval",
        "reconciliation",
        "extractor",
        "portal",
        "workflow",
    } <= linked_surfaces


@pytest.mark.parametrize(
    ("ejercicio", "window_id", "expected"),
    [
        (2024, "modelo-190-2024-0a", (2025, "2024 0A", date(2025, 1, 1), date(2025, 1, 31))),
        (2026, "modelo-190-2025-0a", (2026, "2025 0A", date(2026, 1, 1), date(2026, 1, 31))),
    ],
)
def test_modelo_190_annual_deadline_is_grounded_to_current_revision(
    ejercicio: int, window_id: str, expected: tuple[int, str, date, date]
) -> None:
    """Each filing year resolves the revision that declares ITS deadline window.

    Written when modelo 190 held both windows in one revision, this asserted a
    construct referencing both and a revision declaring both. The span was later
    split into "2024" and "2025-y-siguientes", which moved each window into the
    revision it governs -- the windows did not change, and neither did their
    dates, but the single-revision expectation could no longer hold.

    Parametrising over the two filing years keeps every window, date and
    grounding reference asserted while letting the registry declare each where
    it belongs. A future split moves a window between revisions without making
    this test wrong.
    """
    modelo, catalogues = _committed_modelo("190")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=ejercicio,
        period="0A",
    )
    revision = snapshot.revision
    construct = revision.constructs[0]
    windows = {window.id: window for window in revision.deadline_windows}
    schedule = next(item for item in revision.filing_schedules if item.id == "modelo-190-anual")
    deadline_link = next(item for item in revision.application_links if item.id == "modelo-190-deadline")

    assert deadline_link.surface == "deadline"
    assert deadline_link.consumer == "cadrumo.domain.deadlines"
    assert deadline_link.requires_snapshot is True
    assert catalogues.legal["rd-439-2007:art-108"].evidence_tier == "legal_authority"
    assert catalogues.legal["orden-eha-3127-2009:art-1"].evidence_tier == "legal_authority"
    assert catalogues.sources["aeat-modelo-190-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-190-2025-form"].evidence_tier == "layout_authority"

    assert construct.deadline_windows == (window_id,)
    assert construct.filing_schedules == ("modelo-190-anual",)
    assert schedule.period_kind == "annual"
    assert schedule.periods == ("0A",)
    assert schedule.legal_refs == ("rd-439-2007:art-108", "orden-eha-3127-2009:art-1")
    assert schedule.source_refs == ("aeat-modelo-190-procedure", "boe-modelo-190-2025-form")

    assert set(windows) == {window_id}
    window = windows[window_id]
    expected_filing_year, expected_period, opens_on, closes_on = expected
    assert window.filing_year == expected_filing_year
    assert str(window.period) == expected_period
    assert window.period_kind == "annual"
    assert window.opens_on == opens_on
    assert window.closes_on == closes_on
    assert window.legal_refs == ("rd-439-2007:art-108", "orden-eha-3127-2009:art-1")
    assert window.source_refs == ("aeat-modelo-190-procedure", "boe-modelo-190-2025-form")


def test_modelo_190_filed_declarations_read_allows_live_register_host() -> None:
    modelo, _ = _committed_modelo("190")
    declared = [
        ref
        for revision in modelo.revisions.values()
        for ref in revision.live_cross_references
        if ref.id == "modelo-190-filed-declarations-read"
    ]

    assert declared, "no revision declares the filed-declarations read surface"
    for filed_read in declared:
        assert filed_read.surface == "authenticated_read_surface"
        assert filed_read.requires_authentication is True
        assert filed_read.requires_aeat_authorization is True
        assert filed_read.synthetic_data_allowed is False
        assert _WWW6_HOST in filed_read.allowed_hosts
        assert set(filed_read.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}


def test_modelo_190_relations_resolve_against_modelo_111_registry() -> None:
    snapshot = _committed_snapshot("190", 2025, "0A")
    snapshot_111 = _committed_snapshot("111", 2025, "1T")

    modelo_111_outputs = {casilla.id for casilla in snapshot_111.revision.casillas}
    relation_source_casilla_ids = {relation.source_casilla_id for relation in snapshot.revision.relations}
    assert relation_source_casilla_ids <= modelo_111_outputs
    assert relation_source_casilla_ids.isdisjoint(_RETIRED_M111_PERCEPCIONES_SOURCE_CASILLAS)
    expected_relation_source_casilla_ids = (*_M111_IMPORTE_SOURCE_CASILLAS, _M111_RETENCIONES_TOTAL_CASILLA)
    assert tuple(sorted(relation_source_casilla_ids)) == expected_relation_source_casilla_ids
    assert {tuple(relation.source_periods) for relation in snapshot.revision.relations} == {("1T", "2T", "3T", "4T")}


def test_modelo_190_calculation_aggregates_modelo_111_quarterly_observations() -> None:
    snapshot = _committed_snapshot("190", 2025, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    source_values: dict[CasillaId, tuple[Decimal, ...]] = {
        _M111_IMPORTE_SOURCE_CASILLAS[0]: (Decimal("1000"), Decimal("2000"), Decimal("1500"), Decimal("2500")),
        _M111_IMPORTE_SOURCE_CASILLAS[1]: (Decimal("100"), Decimal("0"), Decimal("0"), Decimal("50")),
        _M111_IMPORTE_SOURCE_CASILLAS[2]: (Decimal("800"), Decimal("900"), Decimal("850"), Decimal("950")),
        _M111_IMPORTE_SOURCE_CASILLAS[3]: (Decimal("120"), Decimal("0"), Decimal("0"), Decimal("0")),
        _M111_IMPORTE_SOURCE_CASILLAS[4]: (Decimal("200"), Decimal("0"), Decimal("300"), Decimal("0")),
        _M111_IMPORTE_SOURCE_CASILLAS[5]: (Decimal("0"), Decimal("80"), Decimal("0"), Decimal("0")),
        _M111_IMPORTE_SOURCE_CASILLAS[6]: (Decimal("0"), Decimal("0"), Decimal("250"), Decimal("0")),
        _M111_IMPORTE_SOURCE_CASILLAS[7]: (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("75")),
        _M111_IMPORTE_SOURCE_CASILLAS[8]: (Decimal("400"), Decimal("0"), Decimal("0"), Decimal("0")),
        _M111_RETENCIONES_TOTAL_CASILLA: (Decimal("190"), Decimal("210"), Decimal("175.25"), Decimal("225.75")),
    }
    observed_by_period: dict[str, dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        source_casilla_id = requirement.source_casilla_ids[0]
        if source_casilla_id not in source_values:
            raise AssertionError(f"unexpected Modelo 190 relation source casilla {source_casilla_id}")
        for index, period in enumerate(requirement.periods):
            observed_by_period.setdefault(period, {})[source_casilla_id] = source_values[source_casilla_id][index]
    observations = tuple(
        registry_grounded_modelo_observation(
            modelo="111",
            filing_year=2025,
            period=period,
            casilla_values=casilla_values,
        )
        for period, casilla_values in sorted(observed_by_period.items())
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2025,
        period="0A",
    )

    # Assert binding wiring: relation_values must be populated for the
    # casillas the 190 relations source from 111.
    assert relation_values, "relation_values must be non-empty after resolving 111 observations"

    expected_percepciones_total = sum(
        (sum(source_values[casilla_id], Decimal("0")) for casilla_id in _M111_IMPORTE_SOURCE_CASILLAS),
        Decimal("0"),
    )
    expected_retenciones_total = sum(source_values[_M111_RETENCIONES_TOTAL_CASILLA], Decimal("0"))
    withholding_values = resolve_withholding_binding_values(
        snapshot.revision,
        (
            _withholding_observation("m190-1", "11111111H", "A"),
            _withholding_observation("m190-1-repeat", "11111111H", "A"),
            _withholding_observation("m190-2", "11111111H", "G"),
            _withholding_observation("m190-3", "22222222J", "A"),
        ),
    )
    assert withholding_values[_M190_PERCEPCIONES_BINDING] == Decimal("3")

    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, withholding_values),
        date_context={"filing_period": date(2025, 12, 31)},
        binding_values=withholding_values,
        relation_values=relation_values,
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert _DECL_TOTAL_PERCEPCIONES_CASILLA not in entries
    assert _DECL_TOTAL_PERCEPCIONES_CASILLA in result.values, "perceptores aggregation casilla must be computed"
    assert _DECL_PERCEPCIONES_TOTAL_CASILLA in result.values, "percepciones aggregation casilla must be computed"
    assert _DECL_RETENCIONES_TOTAL_CASILLA in result.values, "retenciones aggregation casilla must be computed"
    assert result.values[_DECL_TOTAL_PERCEPCIONES_CASILLA] == Decimal("3")
    assert result.values[_DECL_PERCEPCIONES_TOTAL_CASILLA] == expected_percepciones_total
    assert result.values[_DECL_RETENCIONES_TOTAL_CASILLA] == expected_retenciones_total
