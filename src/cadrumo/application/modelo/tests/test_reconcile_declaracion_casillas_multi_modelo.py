"""Real-behavior tests for casilla-level declaración reconcile enrollment.

Extends the coverage :mod:`test_reconcile_declaracion_casillas` established for
Modelo 130 to the five modelos enrolled in
:data:`cadrumo.application.modelo.reconciliation._DECLARATION_CASILLA_RECONCILE_MODELOS`
in the same slice: Modelo 100 (IRPF annual, printed Renta casilla ids), Modelo
303 (IVA autoliquidación, compound ``iva.*`` primitive/result casilla ids),
Modelo 390 (IVA resumen anual, compound ``iva.anual.*`` ids), Modelo 111
(retenciones e ingresos a cuenta trimestral, printed AEAT box numbers
``"01"``..``"30"``), and Modelo 190 (resumen anual de retenciones, compound
``decl.*`` summary ids).

Each modelo's ``declaracion_pdf`` extraction profile has been confirmed (by
reading the registry TOML alongside
:meth:`~cadrumo.domain.calculations.registry.RegistrySnapshot.verification_policy`)
to target the exact casilla-id vocabulary its verification expectations
reconcile — the same parity Modelo 130 established first. Real-PDF
``bbox_anchored``/``named_label`` extraction stays Tier-R and out of scope
here (tracked separately); this suite tests the
``_reconcile_parsed_declaracion`` seam directly with a synthetically
constructed
:class:`~cadrumo.adapters.inbound.declaracion.InboundDeclaracionObservation`,
mirroring the pattern ``test_reconcile_declaracion_casillas.py`` uses for
Modelo 130. The synthetic fixture data is declared ``synthetic_generated``
(not derived from a real AEAT filing) per the fixture-provenance discipline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef

from ....adapters.inbound.declaracion import InboundDeclaracionObservation, TemplateRevision
from ....adapters.inbound.pdf import ExtractedCasilla
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period, validated_casilla_id
from ....core.time import now
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.registry_observations import registry_grounded_observations
from ..reconciliation import (
    _reconcile_parsed_declaracion,
)
from ..reconciliation_records import (
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_TAX_ID = "00000000T"
_CLOCK = datetime(2026, 4, 20, tzinfo=UTC)


# Seeded through a detached WorkflowState, never a repository read: the
# capsule publishes by an atomic no-replace rename onto ``buckets/<profile-id>``,
# which a workflow-state repository construction would otherwise materialise
# first and collide with.
_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="33333333-3333-4333-8333-333333333333",
    profile_overrides={"identity.tax_id": _PROFILE_TAX_ID},
)


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> WorkUnit:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    typed_period = Period.from_year_and_code(filing_year, period)
    # Seed the real law-determined revision id (mirrors
    # test_reconcile_declaracion_casillas.py) so the snapshot resolver's D1
    # identity assertion holds and the casilla compare actually runs.
    revision_id = (
        bundled_authority()
        .snapshot(
            modelo,
            filing_year=filing_year,
            period=typed_period.registry_token,
        )
        .revision.id
    )
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit


def _persist_filed_revision(work_unit: WorkUnit, *, casilla_values: dict[str, Decimal]) -> None:
    validated_values = {validated_casilla_id(k, surface="test"): v for k, v in casilla_values.items()}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=validated_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repo = CalculationRevisionCatalogueRepository()
    repo.save(
        upsert_calculation_revision(
            repo.load(),
            CalculationRevision(
                calculation_revision_id=revision_id,
                work_unit_id=work_unit.work_unit_id,
                state=CalculationRevisionState.PRESENTADO,
                casilla_values=validated_values,
                observations=registry_grounded_observations(
                    modelo=str(work_unit.modelo),
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                    casilla_values=validated_values,
                ),
                created_at=_CLOCK,
                updated_at=_CLOCK,
                verified_at=_CLOCK,
                verified_by="test",
                filed_at=_CLOCK,
                filed_by="test",
                filing_instance_evidence=None,
                source_provenance=(),
            ),
        ),
    )


def _synthetic_declaracion(
    work_unit: WorkUnit,
    *,
    values: dict[str, Decimal],
    tax_id: str = _PROFILE_TAX_ID,
) -> InboundDeclaracionObservation:
    """Build a synthetic, in-memory declaración observation for ``work_unit``'s modelo.

    Bypasses real PDF extraction entirely (declared ``synthetic_generated``
    provenance): constructs the same typed
    :class:`~cadrumo.adapters.inbound.declaracion.InboundDeclaracionObservation`
    the parser would return, with an explicit registry snapshot ref matching
    the seeded work unit's law-determined revision.
    """
    snapshot = bundled_authority().snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    return InboundDeclaracionObservation(
        modelo=str(work_unit.modelo),
        ejercicio=str(work_unit.filing_year),
        period=work_unit.period,
        tax_id=tax_id,
        template_revision=TemplateRevision(
            modelo=str(work_unit.modelo),
            año=work_unit.filing_year,
            revision=snapshot.revision.id,
            detected_from="explicit_override",
        ),
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            modelo_year=snapshot.filing_year,
            period=snapshot.period,
        ),
        values=tuple(
            ExtractedCasilla(
                casilla_id=validated_casilla_id(casilla_id, surface="test"),
                printed_value=value,
                source_page=1,
                source_bbox=None,
                extraction_confidence=1.0,
            )
            for casilla_id, value in values.items()
        ),
        warnings=(),
        extraction_profile_id=f"modelo-{work_unit.modelo}-declaracion-pdf",
        extraction_profile_provisional=False,
        source_pdf_path=Path(f"synthetic/declaracion-{work_unit.modelo}.pdf"),
        source_pdf_sha256="0" * 64,
        parsed_at=now(),
    )


def _reconcile(work_unit: WorkUnit, declaracion: InboundDeclaracionObservation):
    return _reconcile_parsed_declaracion(
        work_unit=work_unit,
        source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
        source_ref=f"test://declaracion-{work_unit.modelo}",
        actor="operator",
        declaracion=declaracion,
    )


# --- Modelo 100 (IRPF annual): printed Renta casilla ids --------------------


def test_modelo_100_pagos_fraccionados_mismatch_is_caught_as_typed_casilla_diff() -> None:
    """M100 0604 must reconcile against the annual pagos-fraccionados credit.

    The persisted revision represents the annual declaration after the four
    Modelo 130 quarters have folded into casilla 0604. A filed declaración that
    prints a different 0604 must surface a typed casilla mismatch rather than
    an identity-only reconcile success.
    """
    work_unit = _seed_work_unit(modelo="100", filing_year=2024, period="0A")
    _persist_filed_revision(work_unit, casilla_values={"0604": Decimal("1520.00")})

    report = _reconcile(
        work_unit,
        # One M130 quarter short against the already-folded annual credit.
        _synthetic_declaracion(work_unit, values={"0604": Decimal("1140.00")}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "0604"
    assert diff.kind == "casilla_value_mismatch"
    assert diff.work_unit_value == "1520.00"
    assert diff.evidence_value == "1140.00"
    assert {"ley-35-2006:art-99", "rd-439-2007:art-109", "rd-439-2007:art-110"} <= set(diff.legal_refs)
    assert "aeat-dr-100-2024-dictionary" in diff.source_refs


# --- Cross-modelo matching declaración reconciles clean (303/390/190) -------
#
# One shared body across modelos with genuinely different casilla-id shapes:
# 303/390 use compound ``iva.*`` primitive/result ids, 190 uses compound
# ``decl.*`` summary ids. Each row's vocabulary is preserved verbatim as
# distinct parameter data — that shape difference IS the coverage.


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "casilla_values"),
    [
        pytest.param(
            "303",
            2026,
            "1T",
            {"27": Decimal("1000.00"), "45": Decimal("400.00"), "iva.resultado": Decimal("600.00")},
            id="303",
        ),
        pytest.param(
            "390",
            2025,
            "0A",
            {
                "iva.anual.cuota-devengada-total": Decimal("88416.00"),
                "iva.anual.cuota-deducible-total": Decimal("68202.00"),
                "iva.anual.resultado-regimen-general": Decimal("20214.00"),
            },
            id="390",
        ),
        pytest.param(
            "190",
            2025,
            "0A",
            {
                "decl.total-percepciones": Decimal("12.00"),
                "decl.percepciones-total": Decimal("48000.00"),
                "decl.retenciones-total": Decimal("7200.00"),
            },
            id="190",
        ),
    ],
)
def test_matching_declaracion_reconciles_clean(
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: dict[str, Decimal],
) -> None:
    work_unit = _seed_work_unit(modelo=modelo, filing_year=filing_year, period=period)
    _persist_filed_revision(work_unit, casilla_values=casilla_values)

    report = _reconcile(work_unit, _synthetic_declaracion(work_unit, values=casilla_values))

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs


# --- Modelo 303 (IVA autoliquidación): compound iva.* casilla ids -----------


def test_modelo_303_value_mismatch_is_caught_as_typed_casilla_diff() -> None:
    """A filed casilla value that differs from the computed revision is
    CAUGHT and represented as a typed ``casilla`` diff — not a silent
    identity ``matches``."""
    work_unit = _seed_work_unit(modelo="303", filing_year=2026, period="1T")
    _persist_filed_revision(
        work_unit,
        casilla_values={"27": Decimal("1000.00"), "45": Decimal("400.00"), "iva.resultado": Decimal("600.00")},
    )

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={"27": Decimal("1000.00"), "45": Decimal("400.00"), "iva.resultado": Decimal("650.00")},
        ),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "iva.resultado"
    assert diff.kind == "casilla_value_mismatch"
    assert diff.work_unit_value == "600.00"
    assert diff.evidence_value == "650.00"
    assert diff.legal_refs
    assert diff.source_refs


# --- Modelo 390 (IVA resumen anual): compound iva.anual.* casilla ids -------


def test_modelo_390_missing_casilla_is_caught_as_typed_casilla_diff() -> None:
    """A casilla the computed revision resolved but the declaración omitted
    is MISSING_IN_FILED, not a silent skip."""
    work_unit = _seed_work_unit(modelo="390", filing_year=2025, period="0A")
    _persist_filed_revision(
        work_unit,
        casilla_values={
            "iva.anual.cuota-devengada-total": Decimal("88416.00"),
            "iva.anual.cuota-deducible-total": Decimal("68202.00"),
            "iva.anual.resultado-regimen-general": Decimal("20214.00"),
        },
    )

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={
                "iva.anual.cuota-devengada-total": Decimal("88416.00"),
                "iva.anual.cuota-deducible-total": Decimal("68202.00"),
            },
        ),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "iva.anual.resultado-regimen-general"
    assert diff.kind == "casilla_missing_in_filed"


# --- Modelo 111 (retenciones e ingresos a cuenta trimestral): "01".."30" ----


def test_modelo_111_matching_declaracion_reconciles_clean() -> None:
    work_unit = _seed_work_unit(modelo="111", filing_year=2026, period="1T")
    _persist_filed_revision(work_unit, casilla_values={"28": Decimal("3200.00"), "30": Decimal("3200.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"28": Decimal("3200.00"), "30": Decimal("3200.00")}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs


def test_modelo_111_value_mismatch_is_caught_as_typed_casilla_diff() -> None:
    work_unit = _seed_work_unit(modelo="111", filing_year=2026, period="1T")
    _persist_filed_revision(work_unit, casilla_values={"28": Decimal("3200.00"), "30": Decimal("3200.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"28": Decimal("3200.00"), "30": Decimal("3250.00")}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "30"
    assert diff.kind == "casilla_value_mismatch"
    assert diff.work_unit_value == "3200.00"
    assert diff.evidence_value == "3250.00"
    assert diff.legal_refs
    assert diff.source_refs


# --- Modelo 190 (resumen anual de retenciones): compound decl.* ids --------


def test_modelo_190_value_mismatch_is_caught_as_typed_casilla_diff() -> None:
    work_unit = _seed_work_unit(modelo="190", filing_year=2025, period="0A")
    _persist_filed_revision(
        work_unit,
        casilla_values={
            "decl.total-percepciones": Decimal("12.00"),
            "decl.percepciones-total": Decimal("48000.00"),
            "decl.retenciones-total": Decimal("7200.00"),
        },
    )

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={
                "decl.total-percepciones": Decimal("12.00"),
                "decl.percepciones-total": Decimal("48000.00"),
                "decl.retenciones-total": Decimal("7000.00"),
            },
        ),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "decl.retenciones-total"
    assert diff.kind == "casilla_value_mismatch"
    assert diff.work_unit_value == "7200.00"
    assert diff.evidence_value == "7000.00"
    assert diff.legal_refs
    assert diff.source_refs
