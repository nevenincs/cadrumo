"""Live M349 invoice resolver tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from textual.widgets import Static

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from cadrumo.application.modelo.work_form_models import ModeloFormRepeatingBlock
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.operations.composition import OperationComposedServices
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.invoices.enums import PaymentStatus, resolve_iva_rate_slot
from cadrumo.domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition import build_calculation_action_ports
from cadrumo.entrypoints.tests.profile_persistence._dormant_resolver_live_support import (
    _T0,
    _T1,
    _revision,
    _seed_ready_profile,
)
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.components.theme import install_cadrumo_themes
from cadrumo.entrypoints.tui.modelo.lifecycle import ModeloWorkspaceLifecycleDoor
from cadrumo.entrypoints.tui.modelo.workbench.casilla_list import CasillaList, CasillaListEntry
from cadrumo.entrypoints.tui.modelo.workbench.grid import CasillaListRecords
from cadrumo.entrypoints.tui.modelo.workbench.installed import InstalledModeloWorkbench, WorkbenchRepositories
from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen
from cadrumo.entrypoints.tui.modelo.workbench.wording import does_not_apply_text

pytestmark = [pytest.mark.hex_entrypoint]

# Chain 3 — M349 invoices (collectible_invoice): PROVEN LIVE
# ---------------------------------------------------------------------------

_M349_BUCKET = "34900000-0000-4000-8000-000000000013"
_M349_REVISION = "2020-y-siguientes"
_M349_YEAR = 2026
_M349_IMPORTE_CASILLA: CasillaId = validated_casilla_id("decl.importe-operaciones")
_M349_IMPORTE_BINDING = "iva-349-declarante-importe-operaciones"
_M349_OPERADORES_CASILLA: CasillaId = validated_casilla_id("decl.numero-operadores")

# Three DISTINCT non-equal ISSUED intra-community supply bases (clave E) to three
# distinct EU operators, all issued inside 1T (Jan-Mar). decl.importe-operaciones
# (base_sum) must fold the three bases; decl.numero-operadores (count_distinct)
# must count the three distinct operators.
_M349_INVOICES: tuple[tuple[str, str, str, date, Decimal], ...] = (
    # (invoice_number, counterparty_country, counterparty_tax_id, issued_at, base_total)
    ("F-2026-001", "DE", "DE123456789", date(2026, 1, 15), Decimal("1000.00")),
    ("F-2026-002", "FR", "FR12345678901", date(2026, 2, 10), Decimal("2500.50")),
    ("F-2026-003", "IT", "IT12345678901", date(2026, 3, 5), Decimal("740.25")),
)
_M349_EXPECTED_IMPORTE = Decimal("1000.00") + Decimal("2500.50") + Decimal("740.25")  # 4240.75
_M349_EXPECTED_OPERADORES = Decimal("3")


@pytest.fixture
def m349_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_M349_BUCKET) as profile:
        _seed_ready_profile(profile.repository, bucket_id=_M349_BUCKET)
        yield profile.repository


def _intra_community_invoice(
    *,
    invoice_number: str,
    counterparty_country: str,
    counterparty_tax_id: str,
    issued_at: date,
    base_total: Decimal,
) -> Invoice:
    """Build one ISSUED INTRA_COMMUNITY_SUPPLY invoice (clave E) with a zero-rate line."""
    invoice_id = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id=counterparty_tax_id,
        currency="EUR",
        grand_total=base_total,
    )
    return Invoice(
        invoice_id=invoice_id,
        bucket_id=_M349_BUCKET,
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_name="EU Customer GmbH",
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country=counterparty_country,
        base_total=base_total,
        iva_total=Decimal("0"),
        grand_total=base_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Intra-community supply",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=resolve_iva_rate_slot(Decimal("0"), date.today()),
                iva_amount=Decimal("0"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=IvaCategory("intra_community_supply"),
    )


@pytest.fixture
def m349_calculated(
    m349_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> tuple[WorkUnit, CalculationRevision]:
    """E2E: real seeded intra-community invoices fold into M349 on the live path.

    Seeds three DISTINCT ISSUED INTRA_COMMUNITY_SUPPLY invoices (clave E) in 1T,
    then runs the live bucket-aggregation calculate. casilla
    decl.importe-operaciones must equal the summed bases and
    decl.numero-operadores must count the three distinct operators — proving the
    enrolled InvoiceCatalogueSourceResolver folds the real encrypted invoice
    catalogue through to the bound casillas.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=m349_objects)
    CalculationRevisionCatalogueRepository(objects=m349_objects)
    TransactionCatalogueRepository(bucket_id=_M349_BUCKET, objects=m349_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=m349_objects)

    invoices = tuple(
        _intra_community_invoice(
            invoice_number=number,
            counterparty_country=country,
            counterparty_tax_id=tax_id,
            issued_at=issued_at,
            base_total=base_total,
        )
        for number, country, tax_id, issued_at, base_total in _M349_INVOICES
    )
    invoice_repo.save(build_invoice_catalogue(invoices))

    # Non-vacuity: the casilla under test binds the invoice source, and the seeded
    # bases are distinct so a copy/contamination cannot satisfy the sum.
    revision = _revision("349", _M349_REVISION)
    importe_casilla = next(c for c in revision.casillas if c.id == _M349_IMPORTE_CASILLA)
    assert importe_casilla.binding == _M349_IMPORTE_BINDING
    assert any(str(b.source) == "collectible_invoice" and b.id == _M349_IMPORTE_BINDING for b in revision.bindings)
    assert len({base for *_, base in _M349_INVOICES}) == 3

    work_unit = create_work_unit(
        bucket_id=_M349_BUCKET,
        modelo="349",
        filing_year=_M349_YEAR,
        period=Period.from_year_and_code(_M349_YEAR, "1T"),
        revision_id=_M349_REVISION,
        ports=WorkLifecyclePorts(
            work_unit_repository=wu_repo, bucket_event_repository=BucketEventHistoryRepository(objects=m349_objects)
        ),
        clock=_T0,
        operation=operation,
    )
    with bundled_indexed_authority().operation() as operation:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=_M349_BUCKET, operation=operation),
            clock=_T1,
        )

    assert isinstance(result, BucketAggregationCalculationResult)
    folded_importe = Decimal(result.revision.casilla_values[_M349_IMPORTE_CASILLA])
    assert folded_importe == _M349_EXPECTED_IMPORTE, (
        f"M349 {_M349_IMPORTE_CASILLA} must fold the three seeded invoice bases "
        f"(sum {_M349_EXPECTED_IMPORTE}); got {folded_importe}"
    )
    folded_operadores = Decimal(result.revision.casilla_values[_M349_OPERADORES_CASILLA])
    assert folded_operadores == _M349_EXPECTED_OPERADORES, (
        f"M349 {_M349_OPERADORES_CASILLA} must count the three distinct operators; got {folded_operadores}"
    )
    # The invoice source is CLAIMED (resolver enrolled): no unhandled advisory.
    assert not any(
        diag.source_kind in {"collectible_invoice", "payable_invoice"} and diag.reason == "unhandled_binding_source"
        for diag in result.source_diagnostics
    )
    return work_unit, result.revision


@pytest.mark.unit
def test_m349_importe_operaciones_folds_seeded_invoices_on_live_calculate(
    m349_calculated: tuple[WorkUnit, CalculationRevision],
) -> None:
    _, revision = m349_calculated
    assert revision.casilla_values[_M349_IMPORTE_CASILLA] == _M349_EXPECTED_IMPORTE
    assert len(revision.detail_rows) == 3


def _installed(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation, unit: WorkUnit
) -> InstalledModeloWorkbench:
    def door(calculation_revision_id: str | None, verification_report_id: str | None) -> ModeloWorkspaceLifecycleDoor:
        # Read-only acceptance never submits an operation. The production door
        # and installed reader still perform their normal admission/load paths.
        return ModeloWorkspaceLifecycleDoor(
            services=cast(OperationComposedServices, object()),
            work_unit_id=unit.work_unit_id,
            calculation_revision_id=calculation_revision_id,
            verification_report_id=verification_report_id,
        )

    return InstalledModeloWorkbench(
        bucket_id=unit.bucket_id,
        declaration=DeclarationsWorkspaceDeclarationRefV1(
            work_unit_id=unit.work_unit_id,
            modelo=unit.modelo,
            filing_year=unit.filing_year,
            period=unit.period,
            state=unit.state,
            has_current_calculation=True,
            has_current_filing=False,
        ),
        operation=operation,
        repositories=WorkbenchRepositories(
            work_units=WorkUnitCatalogueRepository(objects=objects),
            calculations=CalculationRevisionCatalogueRepository(objects=objects),
            verifications=VerificationReportCatalogueRepository(objects=objects),
        ),
        door=door,
    )


@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.unit
def test_real_encrypted_calculation_rows_reach_the_installed_form(
    m349_objects: SecureObjectRepository,
    m349_calculated: tuple[WorkUnit, CalculationRevision],
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> None:
    unit, calculated = m349_calculated
    stored = CalculationRevisionCatalogueRepository(objects=m349_objects).load().get(calculated.calculation_revision_id)
    assert stored is not None and stored.detail_rows == calculated.detail_rows
    assert "detail_rows" in stored.model_fields_set
    form = _installed(m349_objects, operation, unit).load(language).form
    block = next(
        block
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock) and block.id == "modelo-349-operador"
    )
    assert block.rows_known and tuple(row.index for row in block.rows) == (1, 2, 3)
    amounts = [dict(zip(block.column_casilla_ids, row.values, strict=True))["op.base-imponible"] for row in block.rows]
    assert amounts == [item[-1] for item in _M349_INVOICES]
    assert sum(value for value in amounts if isinstance(value, Decimal)) == _M349_EXPECTED_IMPORTE
    assert form.calculation_revision_id == calculated.calculation_revision_id


@pytest.mark.unit
def test_explicit_empty_and_omitted_legacy_detail_channels_survive_real_encrypted_reload(
    m349_objects: SecureObjectRepository,
    m349_calculated: tuple[WorkUnit, CalculationRevision],
    operation: PinnedAuthorityOperation,
) -> None:
    unit, _ = m349_calculated
    InvoiceCatalogueRepository(objects=m349_objects).save(build_invoice_catalogue(()))
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        unit.work_unit_id,
        ports=build_calculation_action_ports(bucket_id=_M349_BUCKET, operation=operation),
        clock=_T1,
    )
    assert result.revision.detail_rows == ()
    repository = CalculationRevisionCatalogueRepository(objects=m349_objects)
    catalogue = repository.load()
    head = catalogue.get(result.revision.calculation_revision_id)
    assert head is not None and "detail_rows" in head.model_fields_set
    before = _installed(m349_objects, operation, unit).load(OutputLanguage.EN).form
    blocks = [
        block
        for page in before.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
    ]
    assert blocks and all(block.rows_known and not block.rows for block in blocks)

    write = repository.to_secure_object_write(catalogue)
    payload = json.loads(write.payload)
    del payload["payload"]["revisions"][head.calculation_revision_id]["detail_rows"]
    m349_objects.save_many((write.model_copy(update={"payload": json.dumps(payload).encode("utf-8")}),))
    legacy = repository.load().get(head.calculation_revision_id)
    assert legacy is not None and "detail_rows" not in legacy.model_fields_set
    assert legacy.calculation_revision_id == head.calculation_revision_id
    after = _installed(m349_objects, operation, unit).load(OutputLanguage.EN).form
    blocks = [
        block
        for page in after.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
    ]
    assert blocks and all(not block.rows_known and not block.rows for block in blocks)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
@pytest.mark.parametrize("appearance", ("dark", "light"))
async def test_installed_saved_records_are_read_only_visible_content_in_each_terminal_layout(
    m349_objects: SecureObjectRepository,
    m349_calculated: tuple[WorkUnit, CalculationRevision],
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
    size: tuple[int, int],
    appearance: str,
) -> None:
    unit, calculated = m349_calculated
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(_installed(m349_objects, operation, unit))
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            install_cadrumo_themes(app, appearance=appearance)
            await app.workers.wait_for_complete()
            await pilot.pause()
            await pilot.press("]")
            await pilot.pause()
            listing = screen.query_one(CasillaList)
            records = [item for item in listing.items if isinstance(item, CasillaListRecords)]
            assert len(records) == 1 and len(records[0].rows) == 3
            assert not any(isinstance(item, CasillaListEntry) for item in listing.items)
            assert listing.highlighted is None
            assert screen._empty_listing_note() is None
            heading = str(screen.query_one("#wb-page", Static).render())
            help_text = str(screen.query_one("#wb-help", Static).render())
            assert tr("tui.modelo.workbench.filter.empty") not in heading
            assert tr("tui.modelo.workbench.filter.empty_next", page="") not in heading
            assert does_not_apply_text(unit.period) not in heading
            assert tr("tui.modelo.workbench.help.empty") not in help_text
            assert tr("tui.modelo.workbench.grid.records_read_only") in help_text
            assert all(
                widget.region.right <= size[0] and widget.region.bottom <= size[1]
                for widget in (listing, screen.query_one("#wb-page", Static))
            )
            assert listing.scrollable_content_region.width <= listing.region.width
            assert not listing.show_horizontal_scrollbar
            drawn: dict[int, str] = {}
            for offset in range(0, listing.max_scroll_y + listing.size.height, max(listing.size.height - 1, 1)):
                listing.scroll_to(y=offset, animate=False)
                await pilot.pause()
                for y in range(listing.size.height):
                    drawn[int(listing.scroll_y) + y] = listing.render_line(y).text
            rendered_rows = "\n".join(line for _, line in sorted(drawn.items()))
            assert "EU Customer GmbH" in " ".join(rendered_rows.split())
            for identifier in ("123456789", "12345678901"):
                assert identifier in rendered_rows
            for column_heading in records[0].headings:
                assert " ".join(column_heading.split()) in " ".join(rendered_rows.split())
            assert listing.focus_address(("casilla", "op.base-imponible"))
            assert listing.highlighted is None
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen is screen
            listing.scroll_end(animate=False)
            await pilot.pause()
            assert listing.scroll_y == listing.max_scroll_y
            assert screen.form is not None and screen.form.calculation_revision_id == calculated.calculation_revision_id


# ---------------------------------------------------------------------------
