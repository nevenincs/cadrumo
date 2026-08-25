"""Application filing API tests at the registry boundary."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.errors import BaseSeverity
from ....core.i18n import Translatable as tr
from ....core.resources import resources
from ....domain.filing import (
    CasillaSchemaProvider,
    ModeloBuilderError,
    ModeloDraft,
    ModeloDraftError,
    ModeloValidationFinding,
    ModeloValidator,
    ModeloValueKind,
    compute_modelo_draft_id,
)
from ....domain.invoices import InvoiceCatalogue
from ....domain.submission import ModeloDraftStatus
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    ModeloCalculateError,
    _binding_provenance,
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    compute_current_approval_basis,
    empty_prior_filing_observations_fingerprint,
    empty_profile_activity_fingerprint,
    iter_findings,
    refresh_review_status,
    validate_draft,
)
from ..conftest import _BUCKET_ID
from ..runtime import ModeloOperatorProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The isolated capsule predates every filing this module drafts.
_PROFILE_SEEDED_AT = datetime(2025, 1, 6, 9, 0, 0, tzinfo=UTC)

_PERIOD = Period.from_year_and_code(2026, "1T")


_M130_CASILLA_01: CasillaId = validated_casilla_id("01", surface="test_filing.casilla")
_M130_CASILLA_02: CasillaId = validated_casilla_id("02", surface="test_filing.casilla")
_M130_CASILLA_05: CasillaId = validated_casilla_id("05", surface="test_filing.casilla")
_M130_CASILLA_06: CasillaId = validated_casilla_id("06", surface="test_filing.casilla")
_M130_CASILLA_08: CasillaId = validated_casilla_id("08", surface="test_filing.casilla")
_M130_CASILLA_10: CasillaId = validated_casilla_id("10", surface="test_filing.casilla")
_M130_CASILLA_16: CasillaId = validated_casilla_id("16", surface="test_filing.casilla")
_M130_CASILLA_17: CasillaId = validated_casilla_id("17", surface="test_filing.casilla")
_M130_CASILLA_18: CasillaId = validated_casilla_id("18", surface="test_filing.casilla")
_M130_CASILLA_19: CasillaId = validated_casilla_id("19", surface="test_filing.casilla")
_M130_RESULT_TRACE: tuple[CasillaId, ...] = (_M130_CASILLA_17, _M130_CASILLA_18)
_UNKNOWN_CASILLA: CasillaId = validated_casilla_id("unknown.casilla", surface="test_filing.casilla")

_M111_CASILLA_03: CasillaId = validated_casilla_id("03", surface="test_filing.casilla")
_M111_CASILLA_06: CasillaId = validated_casilla_id("06", surface="test_filing.casilla")
_M111_CASILLA_09: CasillaId = validated_casilla_id("09", surface="test_filing.casilla")
_M111_CASILLA_12: CasillaId = validated_casilla_id("12", surface="test_filing.casilla")
_M111_CASILLA_15: CasillaId = validated_casilla_id("15", surface="test_filing.casilla")
_M111_CASILLA_18: CasillaId = validated_casilla_id("18", surface="test_filing.casilla")
_M111_CASILLA_21: CasillaId = validated_casilla_id("21", surface="test_filing.casilla")
_M111_CASILLA_24: CasillaId = validated_casilla_id("24", surface="test_filing.casilla")
_M111_CASILLA_27: CasillaId = validated_casilla_id("27", surface="test_filing.casilla")
_M111_CASILLA_28: CasillaId = validated_casilla_id("28", surface="test_filing.casilla")
_M111_CASILLA_29: CasillaId = validated_casilla_id("29", surface="test_filing.casilla")
_M111_CASILLA_30: CasillaId = validated_casilla_id("30", surface="test_filing.casilla")
_M111_CASILLA_28_TRACE: tuple[CasillaId, ...] = (
    _M111_CASILLA_03,
    _M111_CASILLA_06,
    _M111_CASILLA_09,
    _M111_CASILLA_12,
    _M111_CASILLA_15,
    _M111_CASILLA_18,
    _M111_CASILLA_21,
    _M111_CASILLA_24,
    _M111_CASILLA_27,
)
_M111_CASILLA_30_TRACE: tuple[CasillaId, ...] = (_M111_CASILLA_28, _M111_CASILLA_29)

_M115_CASILLA_01: CasillaId = validated_casilla_id("01", surface="test_filing.casilla")
_M115_CASILLA_02: CasillaId = validated_casilla_id("02", surface="test_filing.casilla")
_M115_CASILLA_03: CasillaId = validated_casilla_id("03", surface="test_filing.casilla")
_M115_CASILLA_04: CasillaId = validated_casilla_id("04", surface="test_filing.casilla")
_M115_CASILLA_05: CasillaId = validated_casilla_id("05", surface="test_filing.casilla")
_M115_CASILLA_03_TRACE: tuple[CasillaId, ...] = (_M115_CASILLA_02,)
_M115_CASILLA_05_TRACE: tuple[CasillaId, ...] = (_M115_CASILLA_03, _M115_CASILLA_04)

_M123_CASILLA_01: CasillaId = validated_casilla_id("01", surface="test_filing.casilla")
_M123_CASILLA_02: CasillaId = validated_casilla_id("02", surface="test_filing.casilla")
_M123_CASILLA_03: CasillaId = validated_casilla_id("03", surface="test_filing.casilla")
_M123_CASILLA_04: CasillaId = validated_casilla_id("04", surface="test_filing.casilla")
_M123_CASILLA_05: CasillaId = validated_casilla_id("05", surface="test_filing.casilla")
_M123_CASILLA_06: CasillaId = validated_casilla_id("06", surface="test_filing.casilla")
_M123_CASILLA_07: CasillaId = validated_casilla_id("07", surface="test_filing.casilla")
_M123_CASILLA_08: CasillaId = validated_casilla_id("08", surface="test_filing.casilla")
_M123_CASILLA_09: CasillaId = validated_casilla_id("09", surface="test_filing.casilla")
_M123_CASILLA_10: CasillaId = validated_casilla_id("10", surface="test_filing.casilla")
_M123_CASILLA_11: CasillaId = validated_casilla_id("11", surface="test_filing.casilla")
_M123_CASILLA_12: CasillaId = validated_casilla_id("12", surface="test_filing.casilla")
_M123_CASILLA_13: CasillaId = validated_casilla_id("13", surface="test_filing.casilla")
_M123_CASILLA_14: CasillaId = validated_casilla_id("14", surface="test_filing.casilla")
_M123_CASILLA_03_TRACE: tuple[CasillaId, ...] = (_M123_CASILLA_01, _M123_CASILLA_02)
_M123_CASILLA_06_TRACE: tuple[CasillaId, ...] = (_M123_CASILLA_04, _M123_CASILLA_05)
_M123_CASILLA_09_TRACE: tuple[CasillaId, ...] = (_M123_CASILLA_07, _M123_CASILLA_08)
_M123_CASILLA_12_TRACE: tuple[CasillaId, ...] = (_M123_CASILLA_09, _M123_CASILLA_11)
_M123_CASILLA_14_TRACE: tuple[CasillaId, ...] = (_M123_CASILLA_12, _M123_CASILLA_13)

_M131_CASILLA_03: CasillaId = validated_casilla_id("03", surface="test_filing.casilla")
_M131_CASILLA_05: CasillaId = validated_casilla_id("05", surface="test_filing.casilla")
_M131_CASILLA_08: CasillaId = validated_casilla_id("08", surface="test_filing.casilla")
_M131_CASILLA_09: CasillaId = validated_casilla_id("09", surface="test_filing.casilla")
_M131_CASILLA_12: CasillaId = validated_casilla_id("12", surface="test_filing.casilla")
_M131_CASILLA_14: CasillaId = validated_casilla_id("14", surface="test_filing.casilla")
_M131_CASILLA_15: CasillaId = validated_casilla_id("15", surface="test_filing.casilla")


def _profile() -> ModeloOperatorProfile:
    return ModeloOperatorProfile(
        tax_id="12345678Z",
        display_name="Registry boundary test",
    )


@cache
def _schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",), filing_year=_PERIOD.filing_year, period=_PERIOD)


@cache
def _modelo_130_unscoped_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",))


@cache
def _unscoped_schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider()


@cache
def _period_schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(filing_year=_PERIOD.filing_year, period=_PERIOD)


def _draft(
    schema_provider: CasillaSchemaProvider | None = None,
    *,
    retenciones: Decimal = Decimal("100"),
) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M130_CASILLA_01: Decimal("12500.00"),
            _M130_CASILLA_02: Decimal("3500.00"),
            _M130_CASILLA_05: Decimal("250"),
            _M130_CASILLA_06: retenciones,
            _M130_CASILLA_08: Decimal("2000"),
            _M130_CASILLA_10: Decimal("10"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            _M130_CASILLA_16: Decimal("0"),
            _M130_CASILLA_18: Decimal("0"),
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
        provider_transaction_id=provider_id,
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
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )


def test_build_draft_uses_registry_snapshot_for_modelo_130() -> None:
    draft = build_draft(
        modelo="130",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M130_CASILLA_01: Decimal("10000"),
            _M130_CASILLA_02: Decimal("4000"),
            _M130_CASILLA_05: Decimal("250"),
            _M130_CASILLA_06: Decimal("100"),
            _M130_CASILLA_08: Decimal("2000"),
            _M130_CASILLA_10: Decimal("10"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            _M130_CASILLA_16: Decimal("0"),
            _M130_CASILLA_18: Decimal("0"),
        },
        schema_provider=_modelo_130_unscoped_provider(),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == "registry:130:2019-y-siguientes"
    assert _M130_CASILLA_19 in values
    assert values[_M130_CASILLA_19].kind is ModeloValueKind.COMPUTED
    assert values[_M130_CASILLA_19].formula_trace_casilla_ids == _M130_RESULT_TRACE


def test_build_draft_blocks_negative_modelo_130_retenciones() -> None:
    """Registry C06 non-negativity prevents a filing-ready Modelo 130 draft."""
    draft = _draft(retenciones=Decimal("-100"))

    assert draft.status is ModeloDraftStatus.BORRADOR
    assert any(
        finding.code == "casilla-out-of-range" and finding.casilla_id == _M130_CASILLA_06 for finding in draft.findings
    )


def test_binding_provenance_rejects_empty_registry_refs() -> None:
    """A bound filing value cannot be projected from an ungrounded binding definition."""

    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
    binding = next(item for item in snapshot.revision.bindings if item.legal_refs and item.source_refs)
    source, legal_refs, source_refs = _binding_provenance(binding)
    assert source == binding.source
    assert legal_refs == tuple(binding.legal_refs)
    assert source_refs == tuple(binding.source_refs)

    for corrupted in (
        binding.model_copy(update={"legal_refs": ()}),
        binding.model_copy(update={"source_refs": ()}),
    ):
        with pytest.raises(ModeloBuilderError) as provenance_error:
            _binding_provenance(corrupted)
        assert (
            provenance_error.value.translated_message
            == "application.filing.build_draft.errors.binding_provenance_missing"
        )


def test_build_draft_uses_registry_snapshot_for_modelo_111() -> None:
    draft = build_draft(
        modelo="111",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M111_CASILLA_03: Decimal("180.25"),
            _M111_CASILLA_06: Decimal("12.10"),
            _M111_CASILLA_09: Decimal("300.00"),
            _M111_CASILLA_12: Decimal("14.40"),
            _M111_CASILLA_15: Decimal("25.00"),
            _M111_CASILLA_18: Decimal("0.50"),
            _M111_CASILLA_21: Decimal("7.00"),
            _M111_CASILLA_24: Decimal("8.00"),
            _M111_CASILLA_27: Decimal("9.00"),
            _M111_CASILLA_29: Decimal("40.00"),
        },
        schema_provider=_unscoped_schema_provider(),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == "registry:111:2019-y-siguientes"
    assert {_M111_CASILLA_28, _M111_CASILLA_30} <= set(values)
    assert values[_M111_CASILLA_28].kind is ModeloValueKind.COMPUTED
    assert values[_M111_CASILLA_28].formula_trace_casilla_ids == _M111_CASILLA_28_TRACE
    assert values[_M111_CASILLA_30].formula_trace_casilla_ids == _M111_CASILLA_30_TRACE


def test_build_draft_blocks_negative_modelo_111_retenciones() -> None:
    """Registry C06 non-negativity prevents a filing-ready Modelo 111 draft."""
    draft = build_draft(
        modelo="111",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M111_CASILLA_03: Decimal("180.25"),
            _M111_CASILLA_06: Decimal("-12.10"),
            _M111_CASILLA_09: Decimal("300.00"),
            _M111_CASILLA_12: Decimal("14.40"),
            _M111_CASILLA_15: Decimal("25.00"),
            _M111_CASILLA_18: Decimal("0.50"),
            _M111_CASILLA_21: Decimal("7.00"),
            _M111_CASILLA_24: Decimal("8.00"),
            _M111_CASILLA_27: Decimal("9.00"),
            _M111_CASILLA_29: Decimal("40.00"),
        },
        schema_provider=_unscoped_schema_provider(),
    )

    assert draft.status is ModeloDraftStatus.BORRADOR
    assert any(
        finding.code == "casilla-out-of-range" and finding.casilla_id == _M111_CASILLA_06 for finding in draft.findings
    )


def test_build_draft_uses_registry_snapshot_for_modelo_115() -> None:
    draft = build_draft(
        modelo="115",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M115_CASILLA_01: Decimal("1"),
            _M115_CASILLA_02: Decimal("1250.50"),
            _M115_CASILLA_04: Decimal("10.00"),
        },
        schema_provider=_unscoped_schema_provider(),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == "registry:115:2019-y-siguientes"
    assert {_M115_CASILLA_03, _M115_CASILLA_05} <= set(values)
    assert values[_M115_CASILLA_03].kind is ModeloValueKind.COMPUTED
    assert values[_M115_CASILLA_03].formula_trace_casilla_ids == _M115_CASILLA_03_TRACE
    assert values[_M115_CASILLA_05].formula_trace_casilla_ids == _M115_CASILLA_05_TRACE


def test_build_draft_uses_registry_snapshot_for_modelo_123() -> None:
    snapshot = resources().modelos.authority.snapshot("123", filing_year=2026, period="1T", on=date(2026, 4, 1))
    draft = build_draft(
        modelo="123",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M123_CASILLA_01: Decimal("2"),
            _M123_CASILLA_02: Decimal("3"),
            _M123_CASILLA_04: Decimal("1000.25"),
            _M123_CASILLA_05: Decimal("200.75"),
            _M123_CASILLA_07: Decimal("190.05"),
            _M123_CASILLA_08: Decimal("38.14"),
            _M123_CASILLA_10: Decimal("0"),
            _M123_CASILLA_11: Decimal("7.50"),
            _M123_CASILLA_13: Decimal("12.25"),
        },
        schema_provider=_unscoped_schema_provider(),
    )

    values = {value.casilla_id: value for value in draft.values}
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == f"registry:123:{snapshot.revision.id}"
    assert {_M123_CASILLA_03, _M123_CASILLA_06, _M123_CASILLA_09, _M123_CASILLA_12, _M123_CASILLA_14} <= set(values)
    assert values[_M123_CASILLA_03].formula_trace_casilla_ids == _M123_CASILLA_03_TRACE
    assert values[_M123_CASILLA_06].formula_trace_casilla_ids == _M123_CASILLA_06_TRACE
    assert values[_M123_CASILLA_09].formula_trace_casilla_ids == _M123_CASILLA_09_TRACE
    assert values[_M123_CASILLA_12].formula_trace_casilla_ids == _M123_CASILLA_12_TRACE
    assert values[_M123_CASILLA_14].formula_trace_casilla_ids == _M123_CASILLA_14_TRACE


def test_build_draft_preserves_modelo_131_structured_binding_values() -> None:
    draft = build_draft(
        modelo="131",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M131_CASILLA_03: Decimal("1000"),
            _M131_CASILLA_05: Decimal("500"),
            _M131_CASILLA_08: Decimal("0"),
            _M131_CASILLA_09: Decimal("0"),
            "modelo-131-2026-resultados-negativos-anteriores": Decimal("0"),
            _M131_CASILLA_12: Decimal("0"),
            _M131_CASILLA_14: Decimal("0"),
            "modelo-131.dpa.013-016.epigrafe-iae": "722",
            "modelo-131.dpa.031-032.vehiculos-afectos": "2",
            "modelo-131.did.012-045.iban": "ES9121000418450200051332",
        },
        schema_provider=_period_schema_provider(),
    )

    values = {value.casilla_id: value for value in draft.values}
    binding_values = {value.binding_id: value.value for value in draft.binding_values}

    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert draft.schema_version == "registry:131:2026"
    assert _M131_CASILLA_15 in values
    assert binding_values["modelo-131.dpa.013-016.epigrafe-iae"] == "722"
    assert binding_values["modelo-131.dpa.031-032.vehiculos-afectos"] == 2
    assert binding_values["modelo-131.did.012-045.iban"] == "ES9121000418450200051332"


def test_build_draft_preserves_modelo_131_repeating_activity_binding_values() -> None:
    draft = build_draft(
        modelo="131",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M131_CASILLA_03: Decimal("1000"),
            _M131_CASILLA_05: Decimal("500"),
            "modelo-131.dpa.013-016.epigrafe-iae": ["722", "845"],
            "modelo-131.dpa.031-032.vehiculos-afectos": {"1": "2", "2": "3"},
        },
        schema_provider=_period_schema_provider(),
    )

    rows = {(value.binding_id, value.row_index): value.value for value in draft.binding_values}

    assert rows[("modelo-131.dpa.013-016.epigrafe-iae", 1)] == "722"
    assert rows[("modelo-131.dpa.013-016.epigrafe-iae", 2)] == "845"
    assert rows[("modelo-131.dpa.031-032.vehiculos-afectos", 1)] == 2
    assert rows[("modelo-131.dpa.031-032.vehiculos-afectos", 2)] == 3


def test_build_draft_preserves_modelo_131_page_one_structured_binding_values() -> None:
    draft = build_draft(
        modelo="131",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M131_CASILLA_03: Decimal("1000"),
            _M131_CASILLA_05: Decimal("500"),
            "modelo-131.page1.109-109.discapacidad-33": "yes",
            "modelo-131.page1.110-113.actividad-1-epigrafe": "722",
            "modelo-131.page1.114-130.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.page1.131-135.actividad-1-porcentaje": Decimal("2"),
            "modelo-131.page1.692-692.declaracion-complementaria": "no",
            "modelo-131.page1.693-705.justificante-anterior": "1234567890123",
        },
        schema_provider=_period_schema_provider(),
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
        value.model_copy(update={"formula_trace_casilla_ids": (_M130_CASILLA_01,)})
        if value.casilla_id == _M130_CASILLA_19
        else value
        for value in draft.values
    )
    divergent = draft.model_copy(update={"values": values})
    findings = ModeloValidator(schema_provider=schema_provider).validate(divergent)
    assert any(f.code == "formula-divergence" and f.casilla_id == _M130_CASILLA_19 for f in findings)


def test_validator_reports_unknown_casilla_id_against_registry_schema() -> None:
    schema_provider = _schema_provider()
    draft = _draft(schema_provider)
    unknown_value = draft.values[0].model_copy(update={"casilla_id": _UNKNOWN_CASILLA})
    mutated = draft.model_copy(update={"values": (*draft.values, unknown_value)})

    findings = ModeloValidator(schema_provider=schema_provider).validate(mutated)

    assert any(f.code == "casilla-unknown" and f.casilla_id == _UNKNOWN_CASILLA for f in findings)


def test_compute_draft_id_excludes_findings_and_status() -> None:
    draft = _draft()
    recomputed = compute_modelo_draft_id(
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        snapshot_ref=draft.snapshot_ref,
        values=draft.values,
        binding_values=draft.binding_values,
    )
    assert recomputed == draft.draft_id


def test_compute_draft_id_uses_snapshot_ref_not_schema_version() -> None:
    draft = _draft()
    schema_mutated = draft.model_copy(update={"schema_version": f"{draft.schema_version}:changed"})
    snapshot_mutated_ref = draft.snapshot_ref.model_copy(
        update={"revision_id": f"{draft.snapshot_ref.revision_id}-changed"},
    )
    schema_mutated_id = compute_modelo_draft_id(
        modelo=schema_mutated.modelo,
        period=schema_mutated.period,
        profile_tax_id=schema_mutated.profile_tax_id,
        snapshot_ref=schema_mutated.snapshot_ref,
        values=schema_mutated.values,
        binding_values=schema_mutated.binding_values,
    )
    snapshot_mutated_id = compute_modelo_draft_id(
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        snapshot_ref=snapshot_mutated_ref,
        values=draft.values,
        binding_values=draft.binding_values,
    )

    assert schema_mutated_id == draft.draft_id
    assert snapshot_mutated_id != draft.draft_id


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
    with pytest.raises(ModeloCalculateError) as severity_error:
        list(iter_findings(draft, severity_at_least="HUGE"))
    assert severity_error.value.translated_message == "application.filing.errors.unknown_severity_threshold"


def test_approve_draft_uses_registry_schema_fingerprint() -> None:
    schema_provider = _unscoped_schema_provider()
    draft = build_draft(
        modelo="130",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M130_CASILLA_01: Decimal("100"),
            _M130_CASILLA_02: Decimal("25"),
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
        invoice_catalogue=InvoiceCatalogue(),
        prior_filing_observations_fingerprint=empty_prior_filing_observations_fingerprint(),
        profile_activity_fingerprint=empty_profile_activity_fingerprint(),
    )

    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.approval_basis is not None
    assert approved.approval_basis.schema_formula_fingerprint
    assert approved.review_checksum is not None


def test_approval_basis_reloads_persisted_transaction_catalogue(tmp_path: Path) -> None:
    """Both fingerprints are SELF-LOADED, from a capsule that still has its record row.

    The module-scoped runtime is truncated before every test, which also
    removes the capsule's one current profile-record row -- a state no
    published capsule reaches, and one the record loader is right to refuse.
    Entering a fresh runtime here gives the self-load a real capsule to read,
    so the profile fingerprint is loaded rather than supplied and the
    transaction-catalogue reload stays the subject under test.
    """
    schema_provider = _schema_provider()
    draft = _draft(schema_provider)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        # The published capsule's revision-one record is factless, so its
        # projection digests to the EMPTY constant and could not be told apart
        # from a supplied empty fingerprint. Seeding real facts through the
        # production replacement door gives the self-load something distinctive
        # to digest, which is what makes the assertion below discriminating.
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
                created_at=_PROFILE_SEEDED_AT,
                updated_at=_PROFILE_SEEDED_AT,
            ),
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)

        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        provider_id="first-catalogue-row",
                        amount=Decimal("80.00"),
                        description="First persisted catalogue row",
                    ),
                ),
            ),
        )
        first_basis = compute_current_approval_basis(
            draft,
            bucket_id=profile.bucket_id,
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
                ),
            ),
        )
        second_basis = compute_current_approval_basis(
            draft,
            bucket_id=profile.bucket_id,
            schema_provider=schema_provider,
        )

    assert first_basis.transaction_catalogue_fingerprint != second_basis.transaction_catalogue_fingerprint
    # The self-load actually ran: a real capsule's projection digest is not the
    # empty-projection constant the supplied-value shortcut would have produced.
    assert first_basis.profile_activity_fingerprint == second_basis.profile_activity_fingerprint
    assert first_basis.profile_activity_fingerprint != empty_profile_activity_fingerprint()


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
    schema_provider = _unscoped_schema_provider()
    draft = build_draft(
        modelo="111",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M111_CASILLA_03: Decimal("180.25"),
            _M111_CASILLA_06: Decimal("12.10"),
            _M111_CASILLA_09: Decimal("300.00"),
            _M111_CASILLA_12: Decimal("14.40"),
            _M111_CASILLA_15: Decimal("25.00"),
            _M111_CASILLA_18: Decimal("0.50"),
            _M111_CASILLA_21: Decimal("7.00"),
            _M111_CASILLA_24: Decimal("8.00"),
            _M111_CASILLA_27: Decimal("9.00"),
            _M111_CASILLA_29: Decimal("40.00"),
        },
        schema_provider=schema_provider,
    )

    approved = approve_draft(
        draft,
        bucket_id="test",
        approved_by="registry",
        schema_provider=schema_provider,
        transaction_catalogue=TransactionCatalogue(),
        invoice_catalogue=InvoiceCatalogue(),
        prior_filing_observations_fingerprint=empty_prior_filing_observations_fingerprint(),
        profile_activity_fingerprint=empty_profile_activity_fingerprint(),
    )

    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.schema_version == "registry:111:2019-y-siguientes"
    assert approved.approval_basis is not None
    assert approved.approval_basis.schema_formula_fingerprint


def test_approve_modelo_115_draft_uses_registry_schema_fingerprint() -> None:
    schema_provider = _unscoped_schema_provider()
    draft = build_draft(
        modelo="115",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M115_CASILLA_01: Decimal("1"),
            _M115_CASILLA_02: Decimal("1250.50"),
            _M115_CASILLA_04: Decimal("10.00"),
        },
        schema_provider=schema_provider,
    )

    approved = approve_draft(
        draft,
        bucket_id="test",
        approved_by="registry",
        schema_provider=schema_provider,
        transaction_catalogue=TransactionCatalogue(),
        invoice_catalogue=InvoiceCatalogue(),
        prior_filing_observations_fingerprint=empty_prior_filing_observations_fingerprint(),
        profile_activity_fingerprint=empty_profile_activity_fingerprint(),
    )

    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.schema_version == "registry:115:2019-y-siguientes"
    assert approved.approval_basis is not None
    assert approved.approval_basis.schema_formula_fingerprint


def test_approve_modelo_123_draft_uses_registry_schema_fingerprint() -> None:
    snapshot = resources().modelos.authority.snapshot("123", filing_year=2026, period="1T", on=date(2026, 4, 1))
    schema_provider = _unscoped_schema_provider()
    draft = build_draft(
        modelo="123",
        period=_PERIOD,
        profile=_profile(),
        inputs={
            _M123_CASILLA_01: Decimal("2"),
            _M123_CASILLA_02: Decimal("3"),
            _M123_CASILLA_04: Decimal("1000.25"),
            _M123_CASILLA_05: Decimal("200.75"),
            _M123_CASILLA_07: Decimal("190.05"),
            _M123_CASILLA_08: Decimal("38.14"),
            _M123_CASILLA_10: Decimal("0"),
            _M123_CASILLA_11: Decimal("7.50"),
            _M123_CASILLA_13: Decimal("12.25"),
        },
        schema_provider=schema_provider,
    )

    approved = approve_draft(
        draft,
        bucket_id="test",
        approved_by="registry",
        schema_provider=schema_provider,
        transaction_catalogue=TransactionCatalogue(),
        invoice_catalogue=InvoiceCatalogue(),
        prior_filing_observations_fingerprint=empty_prior_filing_observations_fingerprint(),
        profile_activity_fingerprint=empty_profile_activity_fingerprint(),
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
    context = exc_info.value.context
    assert context is not None
    context = dict(context)
    assert context["codes"] == ("filing-schema-version-mismatch",)
    assert context["modelo"] == "130"
    assert context["finding_count"] == 1


def test_approve_draft_rejects_formula_trace_mismatch() -> None:
    schema_provider = _schema_provider()
    values = tuple(
        value.model_copy(update={"formula_trace_casilla_ids": (_M130_CASILLA_01,)})
        if value.casilla_id == _M130_CASILLA_19
        else value
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
    context = exc_info.value.context
    assert context is not None
    context = dict(context)
    assert context["codes"] == ("formula-divergence",)
    assert context["modelo"] == "130"
    assert context["finding_count"] == 1


def test_refresh_review_status_preserves_submitted_status_but_clears_stale_approval() -> None:
    schema_provider = _schema_provider()
    draft = _draft(schema_provider).model_copy(
        update={
            "status": ModeloDraftStatus.PRESENTADA,
            "approved_at": datetime(2026, 4, 18, 8, 0, tzinfo=UTC),
            "approved_by": "operator",
            "review_checksum": "a" * 64,
            "approval_basis": None,
        },
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
