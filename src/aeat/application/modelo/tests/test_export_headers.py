"""Export header composition tests for Modelo revisions."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.deadlines import TaxpayerProfile
from ....domain.deadlines._models import EntityType, IVARegime, LegalEntityForm, ModeloIVAProfile, RefundAccount
from ....domain.modelos._calculation_revision import CalculationRevisionState
from .._export import ModeloExportError, compose_export_headers
from ._export_test_support import (
    _M303_RESULT_CASILLA,
    _SPANISH_IBAN,
    _load_seeded_work_unit_and_revision,
    _profile,
    _seed_profile,
    _seed_revision,
    _snapshot_ref,
    isolated_backend_context,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_backend_context(tmp_path):
        yield


def test_compose_export_headers_emits_devolucion_for_redeme_negative_303(isolated_backend: None) -> None:
    """End-to-end through the real header composition: a REDEME company's negative
    Modelo 303 (monthly period) composes a fichero with Tipo de declaración "D"
    (solicitud de devolución); an otherwise-identical ordinary company composes "C"
    (a compensar). The only difference is the REDEME enrolment on the passed profile.
    """
    bucket_id = _seed_profile(profile_overrides={"identity.surnames": "Redeme", "identity.name": "Company"})
    work_unit_id, revision_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="02",
        casilla_values={_M303_RESULT_CASILLA: Decimal("-210.00")},
    )
    work_unit, revision = _load_seeded_work_unit_and_revision(work_unit_id, revision_id)

    period = Period.from_year_and_code(2026, "02")
    redeme = TaxpayerProfile(
        tax_id="redemecompany",
        iva_regime=IVARegime.GENERAL,
        # A refund disposition needs a refund account on file; without it the
        # composer refuses (ModeloRefundAccountMissingError) rather than emitting
        # an empty DID block.
        iva=ModeloIVAProfile(redeme_enrolled=True, refund_account=RefundAccount(iban=_SPANISH_IBAN)),
    )

    headers_redeme = compose_export_headers(
        work_unit=work_unit, revision=revision, workflow_profile=redeme, period=period
    )
    headers_ordinary = compose_export_headers(
        work_unit=work_unit, revision=revision, workflow_profile=_profile(), period=period
    )

    # The REDEME company's negative period is a refund "D"; the ordinary company's
    # identical negative period carries forward "C" (regression control).
    assert headers_redeme["declaration_type"] == "D"
    assert headers_ordinary["declaration_type"] == "C"
    # REDEME byte: "1" for the enrolled filer, "2" for the ordinary one.
    assert headers_redeme["redeme"] == "1"
    assert headers_ordinary["redeme"] == "2"
    assert headers_ordinary["full_name"] == "Redeme Company"
    # The refund composer emitted the DID block for the REDEME refund; the ordinary
    # compensación carries no DID fields.
    assert headers_redeme["iban"] == _SPANISH_IBAN
    assert headers_redeme["sepa_marca"] == "1"
    assert "iban" not in headers_ordinary


def test_export_headers_use_typed_instalment_period_dates(isolated_backend: None) -> None:
    bucket_id = _seed_profile(profile_overrides={"identity.surnames": "Test Surnames", "identity.name": "Test Name"})
    work_unit_id, calculation_revision_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="202",
        filing_year=2026,
        period="2P",
    )
    work_unit, revision = _load_seeded_work_unit_and_revision(work_unit_id, calculation_revision_id)

    headers = compose_export_headers(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=_profile(),
        period=Period.from_year_and_code(2026, "2P"),
    )

    assert headers["fecha_inicio_periodo"] == "01102026"
    assert headers["fecha_fin_periodo"] == "31102026"
    assert headers["devengo_start_date"] == "01102026"


def test_modelo_202_legal_entity_exports_company_name_in_razon_social_slot(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    from ....application.filing import build_runtime_schema_provider, export_draft
    from ....domain.filing import ModeloDraft
    from ....domain.submission._protocols import ModeloDraftStatus

    company_name = "Rocio Ferrer Administracion Sociedad Limitada"
    tax_id = "B12345674"
    bucket_id = _seed_profile(
        tax_id=tax_id,
        profile_overrides={
            "identity.legal_name": company_name,
            "identity.name": company_name,
            "identity.surnames": "Rocio Ferrer",
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "taxpayer_type.irpf_income_categories": "",
            "irpf.estimation_regime": "",
        },
    )
    work_unit_id, revision_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="202",
        filing_year=2026,
        period="1P",
    )
    work_unit, revision = _load_seeded_work_unit_and_revision(work_unit_id, revision_id)
    period = Period.from_year_and_code(2026, "1P")
    workflow_profile = TaxpayerProfile(
        tax_id=tax_id,
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        incn_prior_12_months=Decimal("500000"),
        new_entity_first_two_profit_periods=False,
    )

    headers = compose_export_headers(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        period=period,
    )

    assert headers["surnames"] == company_name
    assert headers["name"] == ""

    provider = build_runtime_schema_provider(filing_year=2026, period=period, modelos=("202",))
    subview = provider.get_subview("202")
    draft = ModeloDraft(
        draft_id="d" + "2" * 63,
        modelo="202",
        period=period,
        profile_tax_id=tax_id,
        subject_tax_id=tax_id,
        snapshot_ref=_snapshot_ref(modelo="202", period=period, revision_id=work_unit.revision_id),
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=datetime(2026, 6, 28, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 28, 10, 0, tzinfo=UTC),
        schema_version=subview.schema_version,
    )

    output_path = tmp_path / "modelo-202-legal-entity.txt"
    receipt = export_draft(draft, output_path=output_path, headers=headers, schema_provider=provider)
    text = output_path.read_bytes().decode("latin-1")

    assert receipt.byte_size == len(output_path.read_bytes())
    page_start = text.index("<T20201000>")
    assert text[page_start + 22 : page_start + 82].rstrip() == company_name
    assert text[page_start + 82 : page_start + 102] == " " * 20


def test_modelo_202_legal_entity_export_requires_legal_name(isolated_backend: None) -> None:
    tax_id = "B12345674"
    bucket_id = _seed_profile(
        tax_id=tax_id,
        profile_overrides={
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "taxpayer_type.irpf_income_categories": "",
            "irpf.estimation_regime": "",
        },
    )
    work_unit_id, revision_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="202",
        filing_year=2026,
        period="1P",
    )
    work_unit, revision = _load_seeded_work_unit_and_revision(work_unit_id, revision_id)

    with pytest.raises(ModeloExportError) as exc_info:
        compose_export_headers(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=TaxpayerProfile(
                tax_id=tax_id,
                entity_type=EntityType.LEGAL_ENTITY,
                legal_entity_form=LegalEntityForm.SL,
                iva_regime=IVARegime.GENERAL,
                incn_prior_12_months=Decimal("500000"),
                new_entity_first_two_profit_periods=False,
            ),
            period=Period.from_year_and_code(2026, "1P"),
        )

    assert exc_info.value.context == {"missing": ["identity.legal_name"]}
