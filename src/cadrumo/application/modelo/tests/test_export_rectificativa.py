"""Autoliquidación rectificativa export tests for Modelo 303.

Grounds :class:`CalculationRevisionAmendmentKind.RECTIFICATIVA` (LGT art. 120.4,
``ley-58-2003:art-120`` apartado 4, developed by RD 117/2024) end to end through
the real header composer and the real fichero-BOE renderer:

* a rectificativa revision validates through the domain model_validator;
* the header composer marks the page-3 ``autoliq_rectificativa`` indicator and
  leaves the complementaria checkbox untouched;
* a rectificativa that lowers the resultado to a refund carries the devolución
  IBAN through the shared DID block;
* the indicator renders as a single ``1`` byte at its declared page-3 position
  without overflowing the length-1 field.

No mocks: every path exercises the production composer, the registry snapshot,
and the fixed-width serialiser.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....core import Period
from ....domain.calculations.registry import CasillaId
from ....domain.deadlines import (
    IVARegime,
    ModeloIVAProfile,
    RefundAccount,
    TaxpayerProfile,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    ModeloValidationError,
    WorkUnit,
    derive_calculation_revision_id,
    upsert_calculation_revision,
)
from .._export import compose_export_headers
from ._export_test_support import (
    _M303_RESULT_CASILLA,
    _SPANISH_IBAN,
    _load_seeded_work_unit_and_revision,
    _profile,
    _seed_profile,
    _seed_revision,
    isolated_backend,  # noqa: F401 — pytest fixture
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# A 64-hex internal filing-record id standing in for the baseline the amendment
# supersedes. It is NOT the AEAT 13-digit justificante (that lives on the
# baseline's external evidence and is out of scope for the indicator wiring).
_PRIOR_FILING_RECORD_ID = "a" * 64

# Page-3 record open marker in the rendered 303 fichero: literal "<T" + "303" +
# "03000" + ">" (page-03-open / -modelo / -page / -close), contiguous at offsets
# 1..11 of the page-3 record.
_PAGE_03_MARKER = b"<T30303000>"

# 1-based offset of the ``autoliq_rectificativa`` header field within page 3
# (Modelo 303 2023-y-siguientes diseño de registros, aeat-dr-303-2025).
_AUTOLIQ_RECTIFICATIVA_OFFSET = 392


def _seed_amendment_revision(
    *,
    bucket_id: str,
    kind: CalculationRevisionAmendmentKind,
    casilla_values: dict[CasillaId, Decimal] | None = None,
    period: str = "1T",
    filing_year: int = 2026,
) -> tuple[WorkUnit, CalculationRevision]:
    """Seed a Modelo 303 revision and re-file it as a validated amendment.

    The base revision is content-addressed WITHOUT amendment metadata (the
    metadata is not part of the revision id), so re-constructing it with
    ``amendment_kind`` / ``amends_filing_record_id`` / ``amendment_reason``
    preserves the id and forces the domain model_validator to accept the
    amendment triple — proving a rectificativa validates.
    """
    work_unit_id, revision_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=filing_year,
        period=period,
        casilla_values=dict(casilla_values or {}),
    )
    work_unit, revision = _load_seeded_work_unit_and_revision(work_unit_id, revision_id)
    amendment = CalculationRevision(
        calculation_revision_id=revision.calculation_revision_id,
        work_unit_id=revision.work_unit_id,
        state=revision.state,
        created_at=revision.created_at,
        updated_at=revision.updated_at,
        input_values_by_casilla_id=revision.input_values_by_casilla_id,
        binding_overrides=revision.binding_overrides,
        casilla_values=revision.casilla_values,
        observations=revision.observations,
        verified_at=revision.verified_at,
        verified_by=revision.verified_by,
        amendment_kind=kind,
        amends_filing_record_id=_PRIOR_FILING_RECORD_ID,
        amendment_reason="IVA soportado deducible omitido en la autoliquidación original",
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), amendment))
    return work_unit, amendment


def _minimal_revision(
    *,
    amendment_kind: CalculationRevisionAmendmentKind | None = None,
    amends_filing_record_id: str | None = None,
    amendment_reason: str | None = None,
) -> CalculationRevision:
    """Build a registry-free revision with a valid content-addressed id."""
    now = datetime(2026, 6, 30, 10, 0, tzinfo=UTC)
    work_unit_id = "c" * 64
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=now,
        updated_at=now,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        observations=(),
        amendment_kind=amendment_kind,
        amends_filing_record_id=amends_filing_record_id,
        amendment_reason=amendment_reason,
    )


def test_rectificativa_revision_validates_with_full_amendment_triple() -> None:
    """A RECTIFICATIVA revision passes the domain model_validator with its full
    amendment triple (kind + baseline id + reason) all set. Registry-free."""
    rectificativa = _minimal_revision(
        amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
        amends_filing_record_id=_PRIOR_FILING_RECORD_ID,
        amendment_reason="IVA soportado deducible omitido en la autoliquidación original",
    )

    assert rectificativa.amendment_kind is CalculationRevisionAmendmentKind.RECTIFICATIVA
    assert rectificativa.amends_filing_record_id == _PRIOR_FILING_RECORD_ID
    assert rectificativa.amendment_reason


def test_rectificativa_partial_amendment_triple_is_rejected() -> None:
    """The all-set-or-all-None amendment invariant rejects a rectificativa that
    supplies only the kind without the baseline id and reason. Registry-free."""
    with pytest.raises((ModeloValidationError, ValueError)):
        _minimal_revision(amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA)


def test_rectificativa_marks_autoliq_indicator_not_complementaria(isolated_backend: None) -> None:  # noqa: F811
    """The header composer marks ``autoliq_rectificativa`` for a rectificativa and
    does NOT set the complementaria checkbox (distinct amendment surfaces)."""
    bucket_id = _seed_profile()
    work_unit, rectificativa = _seed_amendment_revision(
        bucket_id=bucket_id,
        kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
        casilla_values={_M303_RESULT_CASILLA: Decimal("120.00")},
    )

    headers = compose_export_headers(
        work_unit=work_unit,
        revision=rectificativa,
        workflow_profile=_profile(),
        period=Period.from_year_and_code(2026, "1T"),
    )

    assert headers["autoliq_rectificativa"] == "1"
    assert "complementaria" not in headers


def test_complementaria_control_does_not_mark_rectificativa(isolated_backend: None) -> None:  # noqa: F811
    """Regression control for the branch split: a complementaria sets the
    complementaria checkbox and never the rectificativa indicator."""
    bucket_id = _seed_profile()
    work_unit, complementaria = _seed_amendment_revision(
        bucket_id=bucket_id,
        kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        casilla_values={_M303_RESULT_CASILLA: Decimal("120.00")},
    )

    headers = compose_export_headers(
        work_unit=work_unit,
        revision=complementaria,
        workflow_profile=_profile(),
        period=Period.from_year_and_code(2026, "1T"),
    )

    assert headers["complementaria"] == "true"
    assert "autoliq_rectificativa" not in headers


def test_rectificativa_refund_carries_devolucion_iban(isolated_backend: None) -> None:  # noqa: F811
    """A rectificativa that lowers the resultado to a refund (REDEME monthly
    negative period) carries the devolución IBAN via the shared DID block AND the
    rectificativa indicator — the two markers are orthogonal."""
    bucket_id = _seed_profile(profile_overrides={"identity.surnames": "Redeme", "identity.name": "Company"})
    work_unit, rectificativa = _seed_amendment_revision(
        bucket_id=bucket_id,
        kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
        casilla_values={_M303_RESULT_CASILLA: Decimal("-210.00")},
        period="02",
    )
    redeme = TaxpayerProfile(
        tax_id="B66012345",
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(redeme_enrolled=True, refund_account=RefundAccount(iban=_SPANISH_IBAN)),
    )

    headers = compose_export_headers(
        work_unit=work_unit,
        revision=rectificativa,
        workflow_profile=redeme,
        period=Period.from_year_and_code(2026, "02"),
    )

    assert headers["declaration_type"] == "D"
    assert headers["autoliq_rectificativa"] == "1"
    assert headers["iban"] == _SPANISH_IBAN


def test_rectificativa_indicator_renders_in_fichero_page_3(isolated_backend: None, tmp_path: Path) -> None:  # noqa: F811
    """Export boundary: the rectificativa indicator renders as a single ``1``
    byte at its declared page-3 position in the real fichero-BOE, proving the
    length-1 field does not overflow."""
    from ....application.filing import (
        ModeloOperatorProfile,
        build_draft,
        build_runtime_schema_provider,
        export_draft,
    )
    from ....domain.calculations.registry import validated_casilla_id
    from ....domain.submission import ModeloDraftStatus

    tax_id = "B12345674"
    bucket_id = _seed_profile(tax_id=tax_id)
    period = Period.from_year_and_code(2026, "1T")
    work_unit, rectificativa = _seed_amendment_revision(
        bucket_id=bucket_id,
        kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
        casilla_values={},
        period="1T",
    )
    workflow_profile = TaxpayerProfile(tax_id=tax_id, iva_regime=IVARegime.GENERAL)

    headers = compose_export_headers(
        work_unit=work_unit,
        revision=rectificativa,
        workflow_profile=workflow_profile,
        period=period,
    )
    assert headers["autoliq_rectificativa"] == "1"

    provider = build_runtime_schema_provider(filing_year=2026, period=period, modelos=("303",))

    # Build a real draft through the calculation engine so the fichero-BOE
    # completeness gate has the full M303 result set on disk (the rectificativa
    # indicator wiring under test lives in the page-3 headers, not the value
    # records). A single grounded IVA repercutido general line drives the cuota
    # devengada / resultado chain, populating every computed result casilla.
    built = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id=tax_id, display_name="Rectificativa Export SL"),
        inputs={
            validated_casilla_id("07", surface="modelo 303 rectificativa export test"): Decimal("10000.00"),
            validated_casilla_id("iva.repercutido.general", surface="modelo 303 rectificativa export test"): Decimal(
                "2100.00"
            ),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    )
    draft = built.model_copy(update={"status": ModeloDraftStatus.APROBADO})

    output_path = tmp_path / "modelo-303-rectificativa.boe"
    export_draft(draft, output_path=output_path, headers=headers, schema_provider=provider)
    payload = output_path.read_bytes()

    page_start = payload.index(_PAGE_03_MARKER)
    indicator_pos = page_start + _AUTOLIQ_RECTIFICATIVA_OFFSET - 1
    assert payload[indicator_pos : indicator_pos + 1] == b"1"
