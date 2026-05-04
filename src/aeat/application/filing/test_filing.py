"""Application filing API tests at the registry hard-cut boundary."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ...core.i18n import Translatable
from ...domain.transactions import TransactionCatalogue
from . import (
    SCHEMA_VERSION_DEFAULT,
    CasillaCollection,
    CasillaSchema,
    CasillaSchemaProvider,
    FilingBuilderError,
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValidationFinding,
    FilingValidator,
    FilingValueKind,
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    compute_draft_id,
    iter_findings,
    refresh_review_status,
    validate_draft,
)
from .testing import (
    SyntheticDeadlineChecker,
    SyntheticDeadlineStatus,
    SyntheticProfile,
    synthesize_filing_draft,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> SyntheticProfile:
    return SyntheticProfile(
        tax_id="12345678Z",
        display_name="Registry boundary test",
        applicable_modelos=("130",),
    )


def _draft() -> FilingDraft:
    return synthesize_filing_draft(
        modelo="130",
        period="2026Q1",
        casilla_values={"01": Decimal("12500.00"), "02": Decimal("3500.00")},
        status=FilingDraftStatus.DRAFT,
        profile_tax_id="12345678Z",
    )


@dataclass(frozen=True, slots=True)
class _TestCasillaSchema:
    id: str
    value_type: str = "decimal"
    required: bool = False
    formula_inputs: tuple[str, ...] = ()
    min_value: float | int | None = None
    max_value: float | int | None = None
    default: object | None = None


@dataclass(frozen=True, slots=True)
class _TestCasillaCollection:
    casillas: tuple[CasillaSchema, ...] = ()
    schema_version: str = SCHEMA_VERSION_DEFAULT

    def __iter__(self) -> object:
        return iter(self.casillas)

    def get(self, casilla_id: str) -> CasillaSchema | None:
        for casilla in self.casillas:
            if casilla.id == casilla_id:
                return casilla
        return None

    def all(self) -> Sequence[CasillaSchema]:
        return self.casillas


@dataclass(frozen=True, slots=True)
class _TestSchemaProvider:
    collection: CasillaCollection

    def get_collection(self, modelo: str) -> CasillaCollection:
        del modelo
        return self.collection


def _schema_provider(
    *casillas: CasillaSchema,
    schema_version: str = SCHEMA_VERSION_DEFAULT,
) -> CasillaSchemaProvider:
    return _TestSchemaProvider(_TestCasillaCollection(casillas=casillas, schema_version=schema_version))


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
            "13": Decimal("0"),
            "15": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        schema_provider=build_runtime_schema_provider(),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert draft.status is FilingDraftStatus.READY_TO_SUBMIT
    assert draft.schema_version == "registry:130:2019-y-siguientes"
    assert values["19"].value == Decimal("880.00")
    assert values["19"].kind is FilingValueKind.COMPUTED
    assert values["19"].formula_trace == ("17", "18")


def test_validate_draft_preserves_id_without_builder_dispatch() -> None:
    draft = _draft()
    refreshed = validate_draft(draft, schema_provider=_schema_provider())
    assert refreshed.draft_id == draft.draft_id


def test_validator_reports_schema_version_mismatch_without_model_specific_schema() -> None:
    draft = _draft()
    findings = FilingValidator(schema_provider=_schema_provider(schema_version="registry-test-v2")).validate(draft)
    assert any(f.code == "filing-schema-version-mismatch" for f in findings)


def test_validator_reports_required_missing_without_model_specific_schema() -> None:
    draft = synthesize_filing_draft(
        modelo="TEST",
        period="2026Q1",
        casilla_values={},
        status=FilingDraftStatus.DRAFT,
        profile_tax_id="12345678Z",
    )
    findings = FilingValidator(
        schema_provider=_schema_provider(_TestCasillaSchema(id="required", required=True))
    ).validate(draft)
    assert any(f.code == "casilla-required-missing" and f.casilla_id == "required" for f in findings)


def test_validator_reports_range_violation_without_model_specific_schema() -> None:
    draft = synthesize_filing_draft(
        modelo="TEST",
        period="2026Q1",
        casilla_values={"bounded": Decimal("-1")},
        status=FilingDraftStatus.DRAFT,
        profile_tax_id="12345678Z",
    )
    findings = FilingValidator(
        schema_provider=_schema_provider(_TestCasillaSchema(id="bounded", min_value=0))
    ).validate(draft)
    assert any(f.code == "casilla-out-of-range" and f.casilla_id == "bounded" for f in findings)


def test_validator_reports_formula_divergence_without_model_specific_schema() -> None:
    draft = synthesize_filing_draft(
        modelo="TEST",
        period="2026Q1",
        casilla_values={"computed": Decimal("10")},
        status=FilingDraftStatus.DRAFT,
        profile_tax_id="12345678Z",
    )
    findings = FilingValidator(
        schema_provider=_schema_provider(_TestCasillaSchema(id="computed", formula_inputs=("input-a", "input-b")))
    ).validate(draft)
    assert any(f.code == "formula-divergence" and f.casilla_id == "computed" for f in findings)


def test_compute_draft_id_excludes_findings_and_status() -> None:
    draft = _draft()
    recomputed = compute_draft_id(
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        schema_version=draft.schema_version,
        values=draft.values,
    )
    assert recomputed == draft.draft_id


def test_iter_findings_threshold() -> None:
    finding_error = FilingValidationFinding(
        casilla_id=None,
        severity=FilingFindingSeverity.ERROR,
        code="x",
        message=Translatable("translation"),
    )
    finding_info = FilingValidationFinding(
        casilla_id=None,
        severity=FilingFindingSeverity.INFO,
        code="y",
        message=Translatable("translation"),
    )
    draft = _draft().model_copy(update={"findings": (finding_error, finding_info)})
    warnings_or_errors = list(iter_findings(draft, severity_at_least="WARNING"))
    assert finding_error in warnings_or_errors
    assert finding_info not in warnings_or_errors
    assert finding_info in list(iter_findings(draft, severity_at_least="INFO"))
    with pytest.raises(FilingBuilderError):
        list(iter_findings(draft, severity_at_least="HUGE"))


def test_approve_draft_uses_registry_schema_fingerprint() -> None:
    schema_provider = build_runtime_schema_provider()
    draft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=_profile(),
        inputs={"01": Decimal("100"), "02": Decimal("25")},
        schema_provider=schema_provider,
    )

    approved = approve_draft(
        draft,
        approved_by="kent",
        schema_provider=schema_provider,
        transaction_catalogue=TransactionCatalogue(),
    )

    assert approved.status is FilingDraftStatus.APPROVED
    assert approved.approval_basis is not None
    assert approved.approval_basis.schema_formula_fingerprint
    assert approved.review_checksum is not None


def test_refresh_review_status_preserves_submitted_status_but_clears_stale_approval() -> None:
    draft = _draft().model_copy(
        update={
            "status": FilingDraftStatus.SUBMITTED,
            "approved_at": datetime(2026, 4, 18, 8, 0, tzinfo=UTC),
            "approved_by": "kent",
            "review_checksum": "a" * 64,
            "approval_basis": None,
        }
    )
    refreshed = refresh_review_status(
        draft,
        schema_provider=_schema_provider(),
        transaction_catalogue=TransactionCatalogue(),
    )
    assert refreshed.status is FilingDraftStatus.SUBMITTED
    assert refreshed.approved_at is None
    assert refreshed.approved_by is None
    assert refreshed.review_checksum is None


def test_deadline_validator_still_reports_overdue_status() -> None:
    findings = FilingValidator(
        schema_provider=_schema_provider(),
        deadline_checker=SyntheticDeadlineChecker(
            status=SyntheticDeadlineStatus(
                due_date=date(2026, 4, 20),
                is_overdue=True,
            )
        ),
    ).validate(_draft())
    assert any(f.code == "filing-deadline-missed" for f in findings)
