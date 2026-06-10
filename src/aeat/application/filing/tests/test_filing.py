"""Application filing API tests at the registry boundary."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.errors import BaseSeverity
from ....core.i18n import Translatable as tr
from ....core.resources import resources
from ....domain.filing import ModeloDraftError
from ....domain.submission import ModeloDraftStatus
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from .. import (
    CasillaSchemaProvider,
    ModeloCalculateError,
    ModeloDraft,
    ModeloValidationFinding,
    ModeloValidator,
    ModeloValueKind,
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    compute_current_approval_basis,
    compute_modelo_draft_id,
    iter_findings,
    refresh_review_status,
    validate_draft,
)
from ..testing import (
    ModeloTestDeadlineChecker,
    ModeloTestDeadlineStatus,
    ModeloTestProfile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _profile() -> ModeloTestProfile:
    return ModeloTestProfile(
        tax_id="12345678Z",
        display_name="Registry boundary test",
    )


def _schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",), filing_year=2026, period="1T")


def _draft(schema_provider: CasillaSchemaProvider | None = None) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "01": Decimal("12500.00"),
            "02": Decimal("3500.00"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        schema_provider=schema_provider or _schema_provider(),
    )


def _transaction(
    *,
    provider_id: str,
    amount: Decimal,
    description: str,
) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(f"/bank/{provider_id}.csv"),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
        }
    )


def test_build_draft_uses_registry_snapshot_for_modelo_130() -> None:
    draft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        schema_provider=build_runtime_schema_provider(modelos=("130",)),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == "registry:130:2019-y-siguientes"
    assert "19" in values
    assert values["19"].kind is ModeloValueKind.COMPUTED
    assert values["19"].formula_trace == ("17", "18")


def test_build_draft_uses_registry_snapshot_for_modelo_111() -> None:
    draft = build_draft(
        modelo="111",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "03": Decimal("180.25"),
            "06": Decimal("12.10"),
            "09": Decimal("300.00"),
            "12": Decimal("14.40"),
            "15": Decimal("25.00"),
            "18": Decimal("0.50"),
            "21": Decimal("7.00"),
            "24": Decimal("8.00"),
            "27": Decimal("9.00"),
            "29": Decimal("40.00"),
        },
        schema_provider=build_runtime_schema_provider(),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == "registry:111:2019-y-siguientes"
    assert {"28", "30"} <= set(values)
    assert values["28"].kind is ModeloValueKind.COMPUTED
    assert values["28"].formula_trace == ("03", "06", "09", "12", "15", "18", "21", "24", "27")
    assert values["30"].formula_trace == ("28", "29")


def test_build_draft_uses_registry_snapshot_for_modelo_115() -> None:
    draft = build_draft(
        modelo="115",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "01": Decimal("1"),
            "02": Decimal("1250.50"),
            "04": Decimal("10.00"),
        },
        schema_provider=build_runtime_schema_provider(),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == "registry:115:2019-y-siguientes"
    assert {"03", "05"} <= set(values)
    assert values["03"].kind is ModeloValueKind.COMPUTED
    assert values["03"].formula_trace == ("02",)
    assert values["05"].formula_trace == ("03", "04")


def test_build_draft_uses_registry_snapshot_for_modelo_123() -> None:
    snapshot = resources().modelos.authority.snapshot("123", filing_year=2026, period="1T", on=date(2026, 4, 1))
    draft = build_draft(
        modelo="123",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "01": Decimal("2"),
            "02": Decimal("3"),
            "04": Decimal("1000.25"),
            "05": Decimal("200.75"),
            "07": Decimal("190.05"),
            "08": Decimal("38.14"),
            "10": Decimal("0"),
            "11": Decimal("7.50"),
            "13": Decimal("12.25"),
        },
        schema_provider=build_runtime_schema_provider(),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == f"registry:123:{snapshot.revision.id}"
    assert {"03", "06", "09", "12", "14"} <= set(values)
    assert values["03"].formula_trace == ("01", "02")
    assert values["06"].formula_trace == ("04", "05")
    assert values["09"].formula_trace == ("07", "08")
    assert values["12"].formula_trace == ("09", "11")
    assert values["14"].formula_trace == ("12", "13")


def test_build_draft_preserves_modelo_131_structured_binding_values() -> None:
    draft = build_draft(
        modelo="131",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "03": Decimal("1000"),
            "05": Decimal("500"),
            "08": Decimal("0"),
            "09": Decimal("0"),
            "modelo-131-2026-resultados-negativos-anteriores": Decimal("0"),
            "12": Decimal("0"),
            "14": Decimal("0"),
            "modelo-131.dpa.013-016.epigrafe-iae": "722",
            "modelo-131.dpa.031-032.vehiculos-afectos": "2",
            "modelo-131.did.012-045.iban": "ES9121000418450200051332",
        },
        schema_provider=build_runtime_schema_provider(filing_year=2026, period="1T"),
    )

    values = {value.casilla_id: value for value in draft.values}
    binding_values = {value.binding_id: value.value for value in draft.binding_values}

    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == "registry:131:2026"
    assert "15" in values
    assert binding_values["modelo-131.dpa.013-016.epigrafe-iae"] == "722"
    assert binding_values["modelo-131.dpa.031-032.vehiculos-afectos"] == 2
    assert binding_values["modelo-131.did.012-045.iban"] == "ES9121000418450200051332"


def test_build_draft_preserves_modelo_131_repeating_activity_binding_values() -> None:
    draft = build_draft(
        modelo="131",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "03": Decimal("1000"),
            "05": Decimal("500"),
            "modelo-131.dpa.013-016.epigrafe-iae": ["722", "845"],
            "modelo-131.dpa.031-032.vehiculos-afectos": {"1": "2", "2": "3"},
        },
        schema_provider=build_runtime_schema_provider(filing_year=2026, period="1T"),
    )

    rows = {(value.binding_id, value.row_index): value.value for value in draft.binding_values}

    assert rows[("modelo-131.dpa.013-016.epigrafe-iae", 1)] == "722"
    assert rows[("modelo-131.dpa.013-016.epigrafe-iae", 2)] == "845"
    assert rows[("modelo-131.dpa.031-032.vehiculos-afectos", 1)] == 2
    assert rows[("modelo-131.dpa.031-032.vehiculos-afectos", 2)] == 3


def test_build_draft_preserves_modelo_131_page_one_structured_binding_values() -> None:
    draft = build_draft(
        modelo="131",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "03": Decimal("1000"),
            "05": Decimal("500"),
            "modelo-131.page1.109-109.discapacidad-33": "yes",
            "modelo-131.page1.110-113.actividad-1-epigrafe": "722",
            "modelo-131.page1.114-130.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.page1.131-135.actividad-1-porcentaje": Decimal("2"),
            "modelo-131.page1.692-692.declaracion-complementaria": "no",
            "modelo-131.page1.693-705.justificante-anterior": "1234567890123",
        },
        schema_provider=build_runtime_schema_provider(filing_year=2026, period="1T"),
    )

    binding_values = {value.binding_id: value.value for value in draft.binding_values}

    assert binding_values["modelo-131.page1.109-109.discapacidad-33"] is True
    assert binding_values["modelo-131.page1.110-113.actividad-1-epigrafe"] == "722"
    assert binding_values["modelo-131.page1.114-130.actividad-1-rendimiento-neto"] == Decimal("1200.50")
    assert binding_values["modelo-131.page1.131-135.actividad-1-porcentaje"] == Decimal("2")
    assert binding_values["modelo-131.page1.692-692.declaracion-complementaria"] is False
    assert binding_values["modelo-131.page1.693-705.justificante-anterior"] == "1234567890123"


def test_validate_draft_preserves_id_without_builder_dispatch() -> None:
    schema_provider = _schema_provider()
    draft = _draft(schema_provider)
    refreshed = validate_draft(draft, bucket_id="test", schema_provider=schema_provider)
    assert refreshed.draft_id == draft.draft_id


def test_validator_reports_schema_version_mismatch_against_registry_schema() -> None:
    draft = _draft()
    stale = draft.model_copy(update={"schema_version": f"{draft.schema_version}:changed"})
    findings = ModeloValidator(schema_provider=_schema_provider()).validate(stale)
    assert any(f.code == "filing-schema-version-mismatch" for f in findings)


def test_validator_reports_formula_divergence_against_registry_formula_trace() -> None:
    schema_provider = _schema_provider()
    draft = _draft(schema_provider)
    values = tuple(
        value.model_copy(update={"formula_trace": ("01",)}) if value.casilla_id == "19" else value
        for value in draft.values
    )
    divergent = draft.model_copy(update={"values": values})
    findings = ModeloValidator(schema_provider=schema_provider).validate(divergent)
    assert any(f.code == "formula-divergence" and f.casilla_id == "19" for f in findings)


def test_compute_draft_id_excludes_findings_and_status() -> None:
    draft = _draft()
    recomputed = compute_modelo_draft_id(
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        schema_version=draft.schema_version,
        values=draft.values,
        binding_values=draft.binding_values,
    )
    assert recomputed == draft.draft_id


def test_iter_findings_threshold() -> None:
    finding_error = ModeloValidationFinding(
        casilla_id=None,
        severity=BaseSeverity.ERROR,
        code="x",
        message=tr("translation"),
    )
    finding_info = ModeloValidationFinding(
        casilla_id=None,
        severity=BaseSeverity.INFO,
        code="y",
        message=tr("translation"),
    )
    draft = _draft().model_copy(update={"findings": (finding_error, finding_info)})
    warnings_or_errors = list(iter_findings(draft, severity_at_least="WARNING"))
    assert finding_error in warnings_or_errors
    assert finding_info not in warnings_or_errors
    assert finding_info in list(iter_findings(draft, severity_at_least="INFO"))
    with pytest.raises(ModeloCalculateError, match=r"Unknown severity"):
        list(iter_findings(draft, severity_at_least="HUGE"))


def test_approve_draft_uses_registry_schema_fingerprint() -> None:
    schema_provider = build_runtime_schema_provider()
    draft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "01": Decimal("100"),
            "02": Decimal("25"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        schema_provider=schema_provider,
    )

    approved = approve_draft(
        draft,
        bucket_id="test",
        approved_by="operator",
        schema_provider=schema_provider,
        transaction_catalogue=TransactionCatalogue(),
    )

    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.approval_basis is not None
    assert approved.approval_basis.schema_formula_fingerprint
    assert approved.review_checksum is not None


def test_approval_basis_reloads_persisted_transaction_catalogue() -> None:
    schema_provider = _schema_provider()
    draft = _draft(schema_provider)
    repository = TransactionCatalogueRepository(bucket_id="filing-test")

    repository.save(
        TransactionCatalogue.from_transactions(
            (
                _transaction(
                    provider_id="first-catalogue-row",
                    amount=Decimal("80.00"),
                    description="First persisted catalogue row",
                ),
            )
        )
    )
    first_basis = compute_current_approval_basis(
        draft,
        bucket_id="filing-test",
        schema_provider=schema_provider,
    )

    repository.save(
        TransactionCatalogue.from_transactions(
            (
                _transaction(
                    provider_id="second-catalogue-row",
                    amount=Decimal("125.00"),
                    description="Second persisted catalogue row",
                ),
            )
        )
    )
    second_basis = compute_current_approval_basis(
        draft,
        bucket_id="filing-test",
        schema_provider=schema_provider,
    )

    assert first_basis.transaction_catalogue_fingerprint != second_basis.transaction_catalogue_fingerprint


def test_approve_draft_rejects_blank_approver_with_translated_message() -> None:
    schema_provider = _schema_provider()
    draft = _draft(schema_provider)

    with pytest.raises(ModeloDraftError) as exc_info:
        approve_draft(
            draft,
            bucket_id="test",
            approved_by="   ",
            schema_provider=schema_provider,
            transaction_catalogue=TransactionCatalogue(),
        )

    assert exc_info.value.translated_message == "application.filing.review.errors.approved_by_blank"


def test_approve_draft_rejects_unready_draft_with_translated_message() -> None:
    schema_provider = _schema_provider()
    finding = ModeloValidationFinding(
        casilla_id=None,
        severity=BaseSeverity.ERROR,
        code="approval-blocker",
        message=tr("translation"),
    )
    draft = _draft(schema_provider).model_copy(update={"findings": (finding,)})

    with pytest.raises(ModeloDraftError) as exc_info:
        approve_draft(
            draft,
            bucket_id="test",
            approved_by="operator",
            schema_provider=schema_provider,
            transaction_catalogue=TransactionCatalogue(),
        )

    assert exc_info.value.translated_message == "application.filing.review.errors.draft_not_ready"


def test_approve_modelo_111_draft_uses_registry_schema_fingerprint() -> None:
    schema_provider = build_runtime_schema_provider()
    draft = build_draft(
        modelo="111",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "03": Decimal("180.25"),
            "06": Decimal("12.10"),
            "09": Decimal("300.00"),
            "12": Decimal("14.40"),
            "15": Decimal("25.00"),
            "18": Decimal("0.50"),
            "21": Decimal("7.00"),
            "24": Decimal("8.00"),
            "27": Decimal("9.00"),
            "29": Decimal("40.00"),
        },
        schema_provider=schema_provider,
    )

    approved = approve_draft(
        draft,
        bucket_id="test",
        approved_by="registry",
        schema_provider=schema_provider,
        transaction_catalogue=TransactionCatalogue(),
    )

    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.schema_version == "registry:111:2019-y-siguientes"
    assert approved.approval_basis is not None
    assert approved.approval_basis.schema_formula_fingerprint


def test_approve_modelo_115_draft_uses_registry_schema_fingerprint() -> None:
    schema_provider = build_runtime_schema_provider()
    draft = build_draft(
        modelo="115",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "01": Decimal("1"),
            "02": Decimal("1250.50"),
            "04": Decimal("10.00"),
        },
        schema_provider=schema_provider,
    )

    approved = approve_draft(
        draft,
        bucket_id="test",
        approved_by="registry",
        schema_provider=schema_provider,
        transaction_catalogue=TransactionCatalogue(),
    )

    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.schema_version == "registry:115:2019-y-siguientes"
    assert approved.approval_basis is not None
    assert approved.approval_basis.schema_formula_fingerprint


def test_approve_modelo_123_draft_uses_registry_schema_fingerprint() -> None:
    snapshot = resources().modelos.authority.snapshot("123", filing_year=2026, period="1T", on=date(2026, 4, 1))
    schema_provider = build_runtime_schema_provider()
    draft = build_draft(
        modelo="123",
        period="2026Q1",
        profile=_profile(),
        inputs={
            "01": Decimal("2"),
            "02": Decimal("3"),
            "04": Decimal("1000.25"),
            "05": Decimal("200.75"),
            "07": Decimal("190.05"),
            "08": Decimal("38.14"),
            "10": Decimal("0"),
            "11": Decimal("7.50"),
            "13": Decimal("12.25"),
        },
        schema_provider=schema_provider,
    )

    approved = approve_draft(
        draft,
        bucket_id="test",
        approved_by="registry",
        schema_provider=schema_provider,
        transaction_catalogue=TransactionCatalogue(),
    )

    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.schema_version == f"registry:123:{snapshot.revision.id}"
    assert approved.approval_basis is not None
    assert approved.approval_basis.schema_formula_fingerprint


def test_approve_draft_rejects_schema_version_mismatch() -> None:
    schema_provider = _schema_provider()
    draft = _draft(schema_provider).model_copy(update={"schema_version": "registry:130:wrong-revision"})

    with pytest.raises(ModeloDraftError) as exc_info:
        approve_draft(
            draft,
            bucket_id="test",
            approved_by="operator",
            schema_provider=schema_provider,
            transaction_catalogue=TransactionCatalogue(),
        )
    assert exc_info.value.translated_message == "application.filing.review.errors.registry_review_mismatch"
    assert exc_info.value.context == {"codes": "filing-schema-version-mismatch"}


def test_approve_draft_rejects_formula_trace_mismatch() -> None:
    schema_provider = _schema_provider()
    values = tuple(
        value.model_copy(update={"formula_trace": ("01",)}) if value.casilla_id == "19" else value
        for value in _draft(schema_provider).values
    )
    draft = _draft(schema_provider).model_copy(update={"values": values})

    with pytest.raises(ModeloDraftError) as exc_info:
        approve_draft(
            draft,
            bucket_id="test",
            approved_by="operator",
            schema_provider=schema_provider,
            transaction_catalogue=TransactionCatalogue(),
        )
    assert exc_info.value.translated_message == "application.filing.review.errors.registry_review_mismatch"
    assert exc_info.value.context == {"codes": "formula-divergence"}


def test_refresh_review_status_preserves_submitted_status_but_clears_stale_approval() -> None:
    schema_provider = _schema_provider()
    draft = _draft(schema_provider).model_copy(
        update={
            "status": ModeloDraftStatus.PRESENTADA,
            "approved_at": datetime(2026, 4, 18, 8, 0, tzinfo=UTC),
            "approved_by": "operator",
            "review_checksum": "a" * 64,
            "approval_basis": None,
        }
    )
    refreshed = refresh_review_status(
        draft,
        bucket_id="test",
        schema_provider=schema_provider,
        transaction_catalogue=TransactionCatalogue(),
    )
    assert refreshed.status is ModeloDraftStatus.PRESENTADA
    assert refreshed.approved_at is None
    assert refreshed.approved_by is None
    assert refreshed.review_checksum is None


def test_deadline_validator_still_reports_overdue_status() -> None:
    findings = ModeloValidator(
        schema_provider=_schema_provider(),
        deadline_checker=ModeloTestDeadlineChecker(
            status=ModeloTestDeadlineStatus(
                due_date=date(2026, 4, 20),
                is_overdue=True,
            )
        ),
    ).validate(_draft())
    assert any(f.code == "filing-deadline-missed" for f in findings)
