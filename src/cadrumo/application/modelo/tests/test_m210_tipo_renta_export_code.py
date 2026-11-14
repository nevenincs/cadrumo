"""A Modelo 210 export writes the official tipo de renta code the return declared, never the rate concept.

The calculation keys its rate on the registry's conceptual token (``general``),
while the design's tipo de renta field holds the two-character official code the
operator declared. Codes share a concept (01 and 03 are both ``general``), so the
export writes the code the calculation revision retained, checked against the
one registry projection from code to concept, and refuses a revision that
retained none rather than guess one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.filing_producer_key import FilingProducerKey
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from ....domain.calculations.registry.irnr_tipo_renta import m210_tipo_renta_code_projection
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.filing.schema import ModeloDraft, ModeloDraftStatus
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.errors import ModeloError
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...filing.export import render_filing_layout
from ...filing.export_producer import filing_producer_values
from ...filing.export_verification import mismatched_casilla_ids
from ...filing.runtime import RegistrySchemaAccessor
from ...filing.tests.export_support import _field_slice, _general_ingreso_producer_snapshot, export_schema_provider
from ..export_preparation import build_revision_export_draft

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "210"
_ANNUAL = "0A"
_TIPO_RENTA = validated_casilla_id("tipo_renta")
_CLOCK = datetime(1980, 7, 9, tzinfo=UTC)
_PROJECTED_YEAR = "errors.snapshot.filing_year_projected"


def _provider(filing_year: int) -> RegistrySchemaAccessor:
    return export_schema_provider(filing_year=filing_year, period=_ANNUAL, modelos=(_MODELO,))


def _exported_years() -> tuple[int, ...]:
    """The supported years with an edition of their own, the only ones an export reaches."""
    support = published_supported_filing_years()
    assert support is not None
    years: list[int] = []
    for year in sorted(support.years):
        try:
            published_snapshot(_MODELO, filing_year=year, period=_ANNUAL)
            _provider(year)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        except RegistryValidationError as refused:
            if refused.translated_message != _PROJECTED_YEAR:
                raise
            continue
        years.append(year)
    return tuple(years)


def _codes_sharing_a_concept() -> tuple[str, str]:
    """Two official codes the registry projects to one rate concept, read from the projection itself."""
    by_concept: dict[str, list[str]] = {}
    for code, concept in sorted(m210_tipo_renta_code_projection().items()):
        by_concept.setdefault(concept.value, []).append(code)
    first, second = next(codes for codes in by_concept.values() if len(codes) > 1)[:2]
    return first, second


def _work_unit(filing_year: int) -> WorkUnit:
    bucket_id = "m210-tipo-renta-export"
    period = Period.from_year_and_code(filing_year, _ANNUAL)
    revision_id = _provider(filing_year).get_snapshot(_MODELO).revision.id
    modelo = ModeloCode(_MODELO)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo=modelo, filing_year=filing_year, period=period, revision_id=revision_id
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{filing_year}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _revision(work_unit: WorkUnit, *, code: str | None) -> CalculationRevision:
    concept = m210_tipo_renta_code_projection()[code].value if code is not None else "general"
    inputs = {_TIPO_RENTA: concept, validated_casilla_id("rendimientos_integros"): "1000.00"}
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=inputs,
            binding_overrides={},
            casilla_values={},
            m210_official_tipo_renta_code=code,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=_MODELO,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=_ANNUAL,
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=inputs,
        binding_overrides={},
        casilla_values={},
        m210_official_tipo_renta_code=code,
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _draft(filing_year: int, code: str | None, operation: PinnedAuthorityOperation) -> ModeloDraft:
    work_unit = _work_unit(filing_year)
    draft = build_revision_export_draft(
        work_unit=work_unit,
        revision=_revision(work_unit, code=code),
        workflow_profile=TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime("GENERAL")),
        period=work_unit.period,
        schema_provider=_provider(filing_year),
        operation=operation,
    )
    return draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _rendered(filing_year: int, draft: ModeloDraft) -> bytes:
    snapshot = _provider(filing_year).get_snapshot(_MODELO)
    producer_snapshot = _general_ingreso_producer_snapshot(_MODELO)
    headers = {
        **filing_producer_values(producer_snapshot),
        FilingProducerKey.IRNR_DECLARACION_TIPO: "N",
        FilingProducerKey.IRNR_DECLARANTE_FULL_NAME: "Ana Prueba",
        FilingProducerKey.IRNR_DECLARANTE_TAX_ID: "12345678Z",
    }
    return render_filing_layout(
        snapshot.revision.export_layouts[0],
        registry_snapshot=snapshot,
        draft=draft,
        headers=headers,
        producer_snapshot=producer_snapshot,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
    )


def _tipo_renta_slice(filing_year: int) -> slice:
    layout = _provider(filing_year).get_snapshot(_MODELO).revision.export_layouts[0]
    record, field = next(
        (record, field) for record in layout.records for field in record.fields if field.casilla_id == _TIPO_RENTA
    )
    return _field_slice(layout, record.id, field.id)


def test_some_supported_year_exports_the_tipo_de_renta() -> None:
    assert _exported_years()


@pytest.mark.parametrize("year", _exported_years())
@pytest.mark.parametrize("which", [0, 1])
def test_the_export_writes_the_official_code_the_revision_retained(
    year: int, which: int, operation: PinnedAuthorityOperation
) -> None:
    code = _codes_sharing_a_concept()[which]
    draft = _draft(year, code, operation)

    payload = _rendered(year, draft)

    assert payload[_tipo_renta_slice(year)] == code.encode("ascii"), year
    provider = _provider(year)
    layout = provider.get_subview(_MODELO).export_layouts[0]
    mismatched, checked = mismatched_casilla_ids(layout, draft=draft, payload=payload, schema_provider=provider)
    assert _TIPO_RENTA in checked, year
    assert _TIPO_RENTA not in mismatched, year


@pytest.mark.parametrize("year", _exported_years())
def test_a_revision_that_retained_no_official_code_is_refused(year: int, operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ModeloError) as refused:
        _draft(year, None, operation)

    assert (refused.value.context or {}).get("casilla_id") == _TIPO_RENTA, year


def test_the_codes_under_test_share_one_rate_concept() -> None:
    first, second = _codes_sharing_a_concept()
    projection = m210_tipo_renta_code_projection()
    assert first != second
    assert projection[first] == projection[second]
    assert Decimal(len(first)) == Decimal(len(second))
