"""Tests for the committed Modelo 369 OSS/IOSS registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree
from ._record_design import extract_record_design_workbook
from ._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_FORBIDDEN_REMOTE_ACTIONS = frozenset(
    [
        "server-side-save",
        "signing",
        "presentation",
        "payment",
        "amendment",
        "cancellation",
        "document-submission",
        "declaration-submission",
    ]
)


def _load_modelo_369() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(m for m in modelos if m.id == "369")
    return modelo, catalogues


def test_modelo_369_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_369()
    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)


def test_modelo_369_metadata_matches_hac_610_2021() -> None:
    modelo, _ = _load_modelo_369()

    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "ad_hoc"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-hac-610-2021:art-1" in modelo.legal_refs
    assert "orden-hac-610-2021:art-2" in modelo.legal_refs
    assert "orden-hac-610-2021:art-3" in modelo.legal_refs
    assert "aeat-dr-369-2021" in modelo.source_refs
    assert "aeat-modelo-369-procedure" in modelo.source_refs


def test_modelo_369_revisions_split_exterior_union_importacion_periods() -> None:
    modelo, _ = _load_modelo_369()

    exterior = modelo.revisions["esquema-exterior"]
    union = modelo.revisions["esquema-union"]
    importacion = modelo.revisions["esquema-importacion"]

    assert exterior.valid_from == date(2021, 7, 1)
    assert exterior.period_selector.year_from == 2021
    assert exterior.period_selector.periods == ("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T")

    assert union.valid_from == date(2021, 7, 1)
    assert union.period_selector.year_from == 2021
    assert union.period_selector.periods == ("1T", "2T", "3T", "4T")

    assert importacion.valid_from == date(2021, 7, 1)
    assert importacion.period_selector.year_from == 2021
    assert importacion.period_selector.periods == (
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
    )


@pytest.mark.parametrize(
    ("period", "expected_revision"),
    [
        ("EXT-1T", "esquema-exterior"),
        ("1T", "esquema-union"),
        ("01", "esquema-importacion"),
    ],
)
def test_modelo_369_snapshot_selects_scheme_by_period(period: str, expected_revision: str) -> None:
    modelo, catalogues = _load_modelo_369()

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2025,
        period=period,
    )

    assert snapshot.revision.id == expected_revision


@pytest.mark.parametrize(
    ("period", "revision_id", "legal_ref"),
    [
        ("EXT-1T", "esquema-exterior", "ley-37-1992:art-163-octiesdecies"),
        ("1T", "esquema-union", "ley-37-1992:art-163-unvicies"),
        ("01", "esquema-importacion", "ley-37-1992:art-163-quinvicies"),
    ],
)
def test_modelo_369_snapshots_carry_scheme_authority(period: str, revision_id: str, legal_ref: str) -> None:
    modelo, catalogues = _load_modelo_369()

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2025,
        period=period,
        revision_id=revision_id,
    )

    assert "orden-hac-610-2021:art-1" in snapshot.legal
    assert "orden-hac-610-2021:art-2" in snapshot.legal
    assert "orden-hac-610-2021:art-3" in snapshot.legal
    assert legal_ref in snapshot.legal
    assert "aeat-dr-369-2021" in snapshot.sources
    assert "aeat-modelo-369-procedure" in snapshot.sources
    assert "boe-modelo-369-2021-form" in snapshot.sources


def test_modelo_369_filing_schedules_match_scheme_period_selectors() -> None:
    modelo, _ = _load_modelo_369()

    expected = {
        "esquema-exterior": ("quarterly", ("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T")),
        "esquema-union": ("quarterly", ("1T", "2T", "3T", "4T")),
        "esquema-importacion": (
            "monthly",
            ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"),
        ),
    }

    for revision_id, (period_kind, periods) in expected.items():
        revision = modelo.revisions[revision_id]
        assert len(revision.filing_schedules) == 1
        schedule = revision.filing_schedules[0]
        assert schedule.period_kind == period_kind
        assert schedule.periods == periods
        assert schedule.periods == revision.period_selector.periods
        assert "orden-hac-610-2021:art-2" in schedule.legal_refs
        assert "orden-hac-610-2021:art-3" in schedule.legal_refs


@pytest.mark.parametrize(
    ("revision_id", "window_id", "period", "opens_on", "closes_on"),
    [
        (
            "esquema-exterior",
            "modelo-369-exterior-2025-ext-1t",
            "2025-EXT-1T",
            date(2025, 4, 1),
            date(2025, 4, 30),
        ),
        (
            "esquema-exterior",
            "modelo-369-exterior-2025-ext-4t",
            "2025-EXT-4T",
            date(2026, 1, 1),
            date(2026, 1, 31),
        ),
        (
            "esquema-union",
            "modelo-369-union-2025-1t",
            "2025-1T",
            date(2025, 4, 1),
            date(2025, 4, 30),
        ),
        (
            "esquema-union",
            "modelo-369-union-2025-4t",
            "2025-4T",
            date(2026, 1, 1),
            date(2026, 1, 31),
        ),
        (
            "esquema-importacion",
            "modelo-369-importacion-2025-01",
            "2025-01",
            date(2025, 2, 1),
            date(2025, 2, 28),
        ),
        (
            "esquema-importacion",
            "modelo-369-importacion-2025-12",
            "2025-12",
            date(2026, 1, 1),
            date(2026, 1, 31),
        ),
        (
            "esquema-importacion",
            "modelo-369-importacion-2026-01",
            "2026-01",
            date(2026, 2, 1),
            date(2026, 2, 28),
        ),
    ],
)
def test_modelo_369_deadline_windows_close_last_day_next_natural_month(
    revision_id: str,
    window_id: str,
    period: str,
    opens_on: date,
    closes_on: date,
) -> None:
    modelo, _ = _load_modelo_369()
    revision = modelo.revisions[revision_id]
    windows = {w.id: w for w in revision.deadline_windows}

    window = windows[window_id]
    assert window.period == period
    assert window.opens_on == opens_on
    assert window.closes_on == closes_on
    assert "orden-hac-610-2021:art-3" in window.legal_refs


def test_modelo_369_live_cross_references_are_read_only() -> None:
    modelo, _ = _load_modelo_369()

    for revision in modelo.revisions.values():
        cross_refs = {ref.surface: ref for ref in revision.live_cross_references}

        static_ref = cross_refs["static_official_documentation"]
        assert static_ref.requires_authentication is False
        assert static_ref.synthetic_data_allowed is False
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(static_ref.forbidden_actions)

        filed_ref = cross_refs["authenticated_read_surface"]
        assert filed_ref.requires_authentication is True
        assert filed_ref.requires_aeat_authorization is True
        assert filed_ref.synthetic_data_allowed is False
        assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
        assert set(filed_ref.allowed_hosts) == {
            "www1.agenciatributaria.gob.es",
            "www6.agenciatributaria.gob.es",
        }
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(filed_ref.forbidden_actions)


def test_modelo_369_workbook_parity_refs_resolve_to_official_record_design() -> None:
    modelo, catalogues = _load_modelo_369()

    for revision in modelo.revisions.values():
        assert len(revision.workbook_parity_refs) == 1
        ref = revision.workbook_parity_refs[0]
        source = catalogues.sources[ref.workbook_source]

        assert ref.workbook_source == "aeat-dr-369-2021"
        assert ref.formula_coverage == "record_design_layout"
        assert ref.runner_required is False
        assert source.evidence_tier == "layout_authority"
        assert (PROJECT_ROOT / source.corpus_path).is_file()


def test_modelo_369_official_record_design_workbook_is_parseable() -> None:
    _, catalogues = _load_modelo_369()
    source = catalogues.sources["aeat-dr-369-2021"]

    sheets = extract_record_design_workbook(PROJECT_ROOT / source.corpus_path)
    by_name = {sheet.name: sheet for sheet in sheets}

    assert len(sheets) == 14
    assert sum(len(sheet.fields) for sheet in sheets) == 1515
    assert by_name["T3690 Estruc. gral"].fields[0].offset == 1
    assert by_name["T3690 Estruc. gral"].fields[0].length == 2
    assert by_name["T3690 Estruc. gral"].fields[0].content == 'Constante "<T"'
    assert by_name["T36900 Info Adicional"].total_positions == 110
    assert by_name["T36901 Ext"].total_positions == 1422
    assert by_name["T36904 Un"].fields[4].description == "Régimen"
    assert by_name["T36910 Imp"].fields[4].content == '"IMPO"'


def test_modelo_369_constructs_close_over_revision_members() -> None:
    modelo, _ = _load_modelo_369()

    for revision in modelo.revisions.values():
        assert len(revision.constructs) == 1
        construct = revision.constructs[0]

        assert construct.casillas == tuple(c.id for c in revision.casillas)
        assert construct.workbook_parity_refs == tuple(w.id for w in revision.workbook_parity_refs)
        assert construct.live_cross_references == tuple(r.id for r in revision.live_cross_references)
        assert construct.application_links == tuple(link.id for link in revision.application_links)
        assert construct.deadline_windows == tuple(w.id for w in revision.deadline_windows)
        assert construct.filing_schedules == tuple(s.id for s in revision.filing_schedules)


def test_modelo_369_each_revision_declares_at_least_one_oss_aggregation_binding() -> None:
    """Each Esquema revision must carry at least one ledger_oss_aggregation
    binding so the calculation chain has a substrate-grounded source for
    its destination-MS aggregations."""
    modelo, _ = _load_modelo_369()
    for revision_id in ("esquema-exterior", "esquema-union", "esquema-importacion"):
        revision = modelo.revisions[revision_id]
        oss_bindings = [
            binding
            for binding in revision.bindings
            if binding.source == "ledger_oss_aggregation"
        ]
        assert oss_bindings, f"{revision_id} declares no ledger_oss_aggregation bindings"


def test_modelo_369_esquema_union_demonstrator_bindings_resolve_end_to_end() -> None:
    """End-to-end smoke test: the runtime resolver returns the expected
    per-binding totals for a small ledger of substrate-classified
    Esquema Unión observations."""
    from decimal import Decimal

    from aeat.domain.calculations.registry._bindings import (
        OssIossLedgerObservation,
        resolve_ledger_oss_aggregation_binding_values,
    )
    from aeat.domain.vat import (
        EUMemberState,
        InvoiceDirection,
        OssIossRegime,
        TransactionKind,
        VATRateKind,
    )

    modelo, _ = _load_modelo_369()
    revision = modelo.revisions["esquema-union"]

    observations = [
        OssIossLedgerObservation(
            ledger_id="inv-de-services",
            transaction_date=date(2025, 6, 15),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=VATRateKind.GENERAL,
            invoice_direction=InvoiceDirection.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("1000"),
            iva_amount=Decimal("190"),
        ),
        OssIossLedgerObservation(
            ledger_id="inv-fr-services",
            transaction_date=date(2025, 6, 20),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.FR,
            rate_kind=VATRateKind.GENERAL,
            invoice_direction=InvoiceDirection.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("500"),
            iva_amount=Decimal("100"),
        ),
        OssIossLedgerObservation(
            ledger_id="inv-de-goods",
            transaction_date=date(2025, 7, 1),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=VATRateKind.GENERAL,
            invoice_direction=InvoiceDirection.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
            base_amount=Decimal("200"),
            iva_amount=Decimal("38"),
        ),
    ]

    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-369-union-de-services-21pct": Decimal("190"),
        "modelo-369-union-fr-services-21pct": Decimal("100"),
        "modelo-369-union-de-goods-distance-21pct": Decimal("38"),
    }


def test_modelo_369_esquema_importacion_ioss_binding_resolves_low_value_sale() -> None:
    """End-to-end smoke test for the IOSS Importación binding."""
    from decimal import Decimal

    from aeat.domain.calculations.registry._bindings import (
        OssIossLedgerObservation,
        resolve_ledger_oss_aggregation_binding_values,
    )
    from aeat.domain.vat import (
        EUMemberState,
        InvoiceDirection,
        OssIossRegime,
        TransactionKind,
        VATRateKind,
    )

    modelo, _ = _load_modelo_369()
    revision = modelo.revisions["esquema-importacion"]

    observations = [
        OssIossLedgerObservation(
            ledger_id=f"ioss-de-{idx}",
            transaction_date=date(2025, 6, idx),
            regime=OssIossRegime.IMPORT_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=VATRateKind.GENERAL,
            invoice_direction=InvoiceDirection.ISSUED,
            transaction_kind=TransactionKind.IOSS_DISTANCE_SALE_LOW_VALUE,
            base_amount=base,
            iva_amount=iva,
        )
        for idx, (base, iva) in enumerate(
            [
                (Decimal("80"), Decimal("15.20")),
                (Decimal("120"), Decimal("22.80")),
            ],
            start=1,
        )
    ]

    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-importacion-de-low-value-21pct": Decimal("38.00")}


def test_modelo_369_esquema_union_constructs_link_oss_bindings() -> None:
    """The Esquema Unión construct must include each ledger_oss_aggregation
    binding so downstream consumers see a complete construct envelope."""
    modelo, _ = _load_modelo_369()
    union = modelo.revisions["esquema-union"]
    construct = next(c for c in union.constructs if c.id == "modelo-369-esquema-union")
    assert "modelo-369-union-de-services-21pct" in construct.bindings
    assert "modelo-369-union-fr-services-21pct" in construct.bindings
    assert "modelo-369-union-de-goods-distance-21pct" in construct.bindings
