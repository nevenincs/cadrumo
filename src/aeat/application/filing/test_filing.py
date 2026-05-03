"""Unit tests for :mod:`aeat.application.filing`.

Covers the public draft-construction surface, the
:class:`Modelo130Builder` arithmetic, and the cross-cutting
:class:`FilingValidator` rules. Test doubles are real
Protocol-conforming pydantic models defined in
:mod:`aeat.application.filing.testing` — no mocks, patches, fakes, or
stubs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from . import (
    FilingApprovalStaleReason,
    FilingComputationError,
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValidationError,
    FilingBuilderError,
    FilingValidationFinding,
    FilingValidator,
    FilingValue,
    FilingValueKind,
    Modelo130Builder,
    apply_validation,
    approval_stale_reasons,
    approve_draft,
    build_draft,
    compute_draft_id,
    iter_findings,
    refresh_review_status,
    unapprove_draft,
    validate_draft,
)
from .testing import (
    SyntheticDeadlineChecker,
    SyntheticDeadlineStatus,
    SyntheticProfile,
    default_schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> SyntheticProfile:
    return SyntheticProfile(
        tax_id="12345678Z",
        display_name="Test Autónomo",
        applicable_modelos=("130",),
    )


def _clean_inputs() -> dict[str, object]:
    return {
        "01": Decimal("12500.00"),
        "02": Decimal("3500.00"),
        "05": Decimal("400.00"),
        "06": Decimal("0.00"),
    }


def _sample_raw_transaction(*, provider_id: str = "tx-1", description: str = "Software subscription") -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("-80.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="pytest",
        ),
        raw_fields={"Concepto": description},
    )


def _sample_transaction(*, provider_id: str = "tx-1") -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _sample_raw_transaction(provider_id=provider_id),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        }
    )


class TestModelo130Builder:
    """Verify the Modelo 130 builder against hand-calculated values."""

    def test_computed_casillas_match_hand_calculations(self) -> None:
        builder = Modelo130Builder()
        draft = builder.build(
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        by_id = {v.casilla_id: v for v in draft.values}
        # Apartado I — ordinary activity.
        assert by_id["03"].value == Decimal("9000.00")
        assert by_id["03"].kind is FilingValueKind.COMPUTED
        assert by_id["03"].formula_trace == ("01", "02")
        assert by_id["04"].value == Decimal("1800.0000")
        assert by_id["04"].formula_trace == ("03",)
        assert by_id["07"].value == Decimal("1400.0000")
        assert by_id["07"].formula_trace == ("04", "05", "06")

    def test_apartado_ii_to_v_casillas_match_hand_calculations(self) -> None:
        """Hand-calculations for the 12 apartado-II/III/IV/V casillas."""
        builder = Modelo130Builder()
        inputs = {
            "01": Decimal("12500"),
            "02": Decimal("3500"),
            "05": Decimal("400"),
            "06": Decimal("0"),
            # Apartado II — agrícola.
            "08": Decimal("5000"),  # volumen ingresos agraria
            "10": Decimal("30"),  # retenciones agraria
            # Apartado III.
            "13": Decimal("0"),  # minoración
            # Apartado IV.
            "15": Decimal("100"),  # deducción vivienda
            "16": Decimal("0"),  # arrastre
            # Apartado V.
            "18": Decimal("0"),  # ingreso previo
        }
        draft = builder.build(
            period="2026Q1",
            profile=_profile(),
            inputs=inputs,
            schema_provider=default_schema_provider(),
        )
        by_id = {v.casilla_id: v for v in draft.values}
        # 09 = 0.02 * 08 = 100.00
        assert by_id["09"].value == Decimal("100.00")
        assert by_id["09"].formula_trace == ("08",)
        # 11 = 09 - 10 = 100 - 30 = 70
        assert by_id["11"].value == Decimal("70")
        assert by_id["11"].formula_trace == ("09", "10")
        # 12 = max(0, 07 + 11) = max(0, 1400 + 70) = 1470
        assert by_id["12"].value == Decimal("1470")
        assert by_id["12"].formula_trace == ("07", "11")
        # 14 = 12 - 13 = 1470 - 0 = 1470
        assert by_id["14"].value == Decimal("1470")
        assert by_id["14"].formula_trace == ("12", "13")
        # 17 = 14 - 15 - 16 = 1470 - 100 - 0 = 1370
        assert by_id["17"].value == Decimal("1370")
        assert by_id["17"].formula_trace == ("14", "15", "16")
        # 19 = 17 - 18 = 1370 - 0 = 1370
        assert by_id["19"].value == Decimal("1370")
        assert by_id["19"].formula_trace == ("17", "18")

    def test_default_value_kind_when_input_missing(self) -> None:
        builder = Modelo130Builder()
        inputs = _clean_inputs()
        # Drop the optional-with-default casillas to exercise DEFAULT.
        del inputs["05"]
        del inputs["06"]
        draft = builder.build(
            period="2026Q1",
            profile=_profile(),
            inputs=inputs,
            schema_provider=default_schema_provider(),
        )
        by_id = {v.casilla_id: v for v in draft.values}
        assert by_id["05"].kind is FilingValueKind.DEFAULT
        assert by_id["05"].value == Decimal("0")

    def test_negative_pago_fraccionado_floors_at_zero(self) -> None:
        builder = Modelo130Builder()
        inputs = {
            "01": Decimal("100"),
            "02": Decimal("50"),
            # Bruto = 10; retenciones overshoot it → resultado clamps to 0.
            "05": Decimal("99999"),
            "06": Decimal("0"),
        }
        draft = builder.build(
            period="2026Q1",
            profile=_profile(),
            inputs=inputs,
            schema_provider=default_schema_provider(),
        )
        by_id = {v.casilla_id: v for v in draft.values}
        assert by_id["07"].value == Decimal("0")

    def test_unsupported_input_type_raises(self) -> None:
        builder = Modelo130Builder()
        inputs = _clean_inputs()
        inputs["01"] = object()  # type: ignore[assignment]
        with pytest.raises(FilingComputationError):
            builder.build(
                period="2026Q1",
                profile=_profile(),
                inputs=inputs,
                schema_provider=default_schema_provider(),
            )


class TestFilingValidator:
    """Verify the cross-cutting validator rules."""

    def _draft_with_value(self, value: FilingValue) -> FilingDraft:
        # Build a clean draft and substitute one value.
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        new_values = tuple(value if v.casilla_id == value.casilla_id else v for v in draft.values)
        return draft.model_copy(update={"values": new_values})

    def test_required_missing_emits_error(self) -> None:
        builder = Modelo130Builder()
        # Drop a required input that has no default (casilla 01).
        inputs = _clean_inputs()
        del inputs["01"]
        raw = builder.build(
            period="2026Q1",
            profile=_profile(),
            inputs=inputs,
            schema_provider=default_schema_provider(),
        )
        validator = FilingValidator(schema_provider=default_schema_provider())
        findings = validator.validate(raw)
        codes = {f.code for f in findings if f.severity is FilingFindingSeverity.ERROR}
        assert "casilla-required-missing" in codes

    def test_out_of_range_emits_error(self) -> None:
        bad = FilingValue(
            casilla_id="01",
            value=Decimal("-1"),
            kind=FilingValueKind.LITERAL,
            source="test",
            formula_trace=None,
        )
        draft = self._draft_with_value(bad)
        validator = FilingValidator(schema_provider=default_schema_provider())
        findings = validator.validate(draft)
        assert any(f.code == "casilla-out-of-range" for f in findings)

    def test_formula_divergence_emits_error(self) -> None:
        bad = FilingValue(
            casilla_id="03",
            value=Decimal("999"),
            kind=FilingValueKind.LITERAL,  # wrong kind for a formula casilla
            source="manual override",
            formula_trace=None,
        )
        draft = self._draft_with_value(bad)
        validator = FilingValidator(schema_provider=default_schema_provider())
        findings = validator.validate(draft)
        assert any(f.code == "formula-divergence" for f in findings)

    def test_deadline_checker_emits_error_when_overdue(self) -> None:
        checker = SyntheticDeadlineChecker(
            status=SyntheticDeadlineStatus(
                due_date=date(2026, 4, 20),
                is_overdue=True,
            )
        )
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
            deadline_checker=checker,
        )
        codes = {f.code for f in draft.findings}
        assert "filing-deadline-missed" in codes
        assert draft.status is FilingDraftStatus.DRAFT

    def test_clean_draft_promotes_to_ready_to_submit(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        assert draft.status is FilingDraftStatus.READY_TO_SUBMIT
        assert draft.findings == ()


class TestPublicAPI:
    """Tests for build_draft / validate_draft / iter_findings."""

    def test_build_draft_smoke(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        assert isinstance(draft, FilingDraft)
        assert draft.modelo == "130"
        assert draft.period == "2026Q1"
        assert draft.profile_tax_id == "12345678Z"
        assert draft.draft_id  # non-empty

    def test_json_round_trip_preserves_draft(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        roundtripped = FilingDraft.model_validate_json(draft.model_dump_json())
        assert roundtripped == draft

    def test_stable_draft_id_for_same_inputs(self) -> None:
        first = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        second = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        assert first.draft_id == second.draft_id

    def test_compute_draft_id_excludes_findings_and_status(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        recomputed = compute_draft_id(
            modelo=draft.modelo,
            period=draft.period,
            profile_tax_id=draft.profile_tax_id,
            schema_version=draft.schema_version,
            values=draft.values,
        )
        assert recomputed == draft.draft_id

    def test_validate_draft_preserves_id(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        refreshed = validate_draft(draft, schema_provider=default_schema_provider())
        assert refreshed.draft_id == draft.draft_id

    def test_validate_draft_preserves_approval_when_review_surface_is_unchanged(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        approved = approve_draft(
            draft,
            approved_by="kent",
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue(),
        )

        refreshed = validate_draft(approved, schema_provider=default_schema_provider())
        assert refreshed.status is FilingDraftStatus.APPROVED
        assert refreshed.approved_at == approved.approved_at
        assert refreshed.approved_by == approved.approved_by
        assert refreshed.review_checksum == approved.review_checksum
        assert refreshed.approval_basis == approved.approval_basis

    def test_validate_draft_marks_reviewed_draft_stale_when_validation_surface_changes(self) -> None:
        clean = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        approved = approve_draft(
            clean,
            approved_by="kent",
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue(),
        )
        tampered_values = tuple(
            FilingValue(
                casilla_id=value.casilla_id,
                value=Decimal("999"),
                kind=FilingValueKind.LITERAL,
                source="tampered",
                formula_trace=None,
            )
            if value.casilla_id == "03"
            else value
            for value in approved.values
        )
        tampered = approved.model_copy(update={"values": tampered_values})
        re_validated = validate_draft(tampered, schema_provider=default_schema_provider())
        assert re_validated.status is FilingDraftStatus.APPROVAL_STALE

    def test_iter_findings_threshold(self) -> None:
        finding_error = FilingValidationFinding(
            casilla_id=None,
            severity=FilingFindingSeverity.ERROR,
            code="x",
            message={"en": "x"},
        )
        finding_info = FilingValidationFinding(
            casilla_id=None,
            severity=FilingFindingSeverity.INFO,
            code="y",
            message={"en": "y"},
        )
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        ).model_copy(update={"findings": (finding_error, finding_info)})
        warnings_or_errors = list(iter_findings(draft, severity_at_least="WARNING"))
        assert finding_error in warnings_or_errors
        assert finding_info not in warnings_or_errors
        all_findings = list(iter_findings(draft, severity_at_least="INFO"))
        assert finding_info in all_findings
        with pytest.raises(FilingBuilderError):
            list(iter_findings(draft, severity_at_least="HUGE"))

    def test_fail_on_warning_raises(self) -> None:
        # Force a divergence by clobbering inputs with an out-of-range value.
        inputs = _clean_inputs()
        inputs["01"] = Decimal("-1")
        with pytest.raises(FilingValidationError):
            build_draft(
                modelo="130",
                period="2026Q1",
                profile=_profile(),
                inputs=inputs,
                schema_provider=default_schema_provider(),
                fail_on_warning=True,
            )

    def test_apply_validation_status_promotion(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        promoted = apply_validation(draft, ())
        assert promoted.status is FilingDraftStatus.READY_TO_SUBMIT

    def test_approve_round_trip_persists_review_metadata(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        approved = approve_draft(
            draft,
            approved_by="kent",
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue(),
        )
        assert approved.status is FilingDraftStatus.APPROVED
        assert approved.approved_at is not None
        assert approved.approved_by == "kent"
        assert approved.review_checksum is not None
        assert approved.approval_basis is not None

        restored = FilingDraft.model_validate_json(approved.model_dump_json())
        refreshed = refresh_review_status(
            restored,
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue(),
        )
        assert refreshed.status is FilingDraftStatus.APPROVED
        assert refreshed.approval_basis == approved.approval_basis

    def test_transaction_catalogue_change_marks_approved_draft_stale(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        approved = approve_draft(
            draft,
            approved_by="kent",
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue(),
        )
        changed_catalogue = TransactionCatalogue.from_transactions([_sample_transaction()])

        stale = refresh_review_status(
            approved,
            schema_provider=default_schema_provider(),
            transaction_catalogue=changed_catalogue,
        )
        reasons = approval_stale_reasons(
            approved,
            schema_provider=default_schema_provider(),
            transaction_catalogue=changed_catalogue,
        )

        assert stale.status is FilingDraftStatus.APPROVAL_STALE
        assert FilingApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED in reasons
        assert stale.approved_at == approved.approved_at
        assert stale.approved_by == approved.approved_by
        assert stale.review_checksum == approved.review_checksum

    def test_transaction_audit_metadata_does_not_create_false_stale_positive(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        transaction = _sample_transaction()
        approved = approve_draft(
            draft,
            approved_by="kent",
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue.from_transactions([transaction]),
        )
        audit_only_variant = transaction.model_copy(
            update={
                "classified_at": datetime(2026, 4, 18, 8, 0, tzinfo=UTC),
                "classified_by": "manual",
                "notes": "operator note only",
            }
        )

        refreshed = refresh_review_status(
            approved,
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue.from_transactions([audit_only_variant]),
        )
        assert refreshed.status is FilingDraftStatus.APPROVED

    def test_unapprove_restores_machine_ready_status(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        )
        approved = approve_draft(
            draft,
            approved_by="kent",
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue(),
        )

        unapproved = unapprove_draft(approved)
        assert unapproved.status is FilingDraftStatus.READY_TO_SUBMIT
        assert unapproved.approved_at is None
        assert unapproved.approved_by is None
        assert unapproved.review_checksum is None
        assert unapproved.approval_basis is None

    def test_refresh_review_status_preserves_downstream_statuses(self) -> None:
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=_profile(),
            inputs=_clean_inputs(),
            schema_provider=default_schema_provider(),
        ).model_copy(
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
            schema_provider=default_schema_provider(),
            transaction_catalogue=TransactionCatalogue(),
        )

        assert refreshed.status is FilingDraftStatus.SUBMITTED
        assert refreshed.approved_at is None
        assert refreshed.approved_by is None
        assert refreshed.review_checksum is None
