"""Real-behavior tests for casilla-level filed-declaración reconciliation (Modelo 130).

These lock the ``reconcile-declaration-casillas`` contract: a filed declaración
PDF is compared casilla-by-casilla against the
persisted computed :class:`~CalculationRevision`, not only
at the header / total level. Modelo 130 is the first modelo enrolled in
:data:`cadrumo.application.modelo.reconciliation._DECLARATION_CASILLA_RECONCILE_MODELOS`
because its ``declaracion_pdf`` extraction profile targets registry casilla ids
``"01"``..``"19"`` directly.

Real-PDF declaración extraction (the ``bbox_anchored`` pdfplumber word-position
primitive) is Tier-R and out of scope here (tracked separately alongside the
remaining not-yet-enrolled modelos). This suite tests
the ``_reconcile_parsed_declaracion`` seam directly with a synthetically
constructed :class:`~cadrumo.adapters.inbound.declaracion.InboundDeclaracionObservation`
— the same seam-testing pattern ``test_reconcile_value_comparison.py`` uses for
the justificante-total reconcile (a synthetic :class:`~cadrumo.domain.justificante.Justificante`
built via ``model_copy``), applied here to the declaración side. The synthetic
fixture data is declared ``synthetic_generated`` (not derived from a real AEAT
filing) per the fixture-provenance discipline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.inbound.declaracion import InboundDeclaracionObservation, TemplateRevision
from ....adapters.inbound.pdf import ExtractedCasilla
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....core.casilla_id import validated_casilla_id
from ....core.time import now
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.registry_observations import registry_grounded_observations
from ...workflow.persistence import workflow_state_repository
from ..reconciliation import (
    ReconciliationDeclaracionSourceUnsupportedError,
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
_MODELO_130 = "130"
_FILING_YEAR = 2026
_PERIOD = "1T"


# Seeded through a detached WorkflowState, never a repository read: the
# capsule publishes by an atomic no-replace rename onto ``buckets/<profile-id>``,
# which a workflow-state repository construction would otherwise materialise
# first and collide with.
_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="22222222-2222-4222-8222-222222222222",
    profile_overrides={"identity.tax_id": _PROFILE_TAX_ID},
)


def _seed_work_unit(
    *,
    modelo: str = _MODELO_130,
    filing_year: int = _FILING_YEAR,
    period: str = _PERIOD,
    snapshot_grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> WorkUnit:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    typed_period = Period.from_year_and_code(filing_year, period)
    # Seed the real law-determined revision id (mirrors
    # test_reconcile_value_comparison.py) so the snapshot resolver's D1 identity
    # assertion holds and the casilla compare actually runs.
    revision_id = (
        bundled_authority()
        .snapshot(
            modelo,
            filing_year=filing_year,
            period=typed_period.registry_token,
            grade=snapshot_grade,
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
    modelo: str | None = None,
    ejercicio: str | None = None,
    period: Period | None = None,
    extraction_profile_provisional: bool = False,
    snapshot_grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> InboundDeclaracionObservation:
    """Build a synthetic, in-memory declaración observation for Modelo 130.

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
        grade=snapshot_grade,
    )
    return InboundDeclaracionObservation(
        modelo=modelo or str(work_unit.modelo),
        ejercicio=ejercicio or str(work_unit.filing_year),
        period=period or work_unit.period,
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
        extraction_profile_id=f"modelo-{modelo or str(work_unit.modelo)}-declaracion-pdf",
        extraction_profile_provisional=extraction_profile_provisional,
        source_pdf_path=Path("synthetic/declaracion-130.pdf"),
        source_pdf_sha256="0" * 64,
        parsed_at=now(),
    )


def _reconcile(work_unit: WorkUnit, declaracion: InboundDeclaracionObservation):
    return _reconcile_parsed_declaracion(
        work_unit=work_unit,
        source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
        source_ref="test://declaracion-130",
        actor="operator",
        declaracion=declaracion,
    )


def test_filed_declaracion_matching_computed_revision_reconciles_clean() -> None:
    work_unit = _seed_work_unit()
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00"), "19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"03": Decimal("5000.00"), "19": Decimal("900.00")}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs
    assert "extraction_profile_provisional" not in {a.code for a in report.advisories}


def test_provisional_extraction_profile_surfaces_non_blocking_advisory() -> None:
    """A declaración parsed through a ``provisional_pending_specimen`` profile
    discloses that its layout is unconfirmed rather than silently presenting
    bbox-anchored values as verified (no-silent-under-declaration)."""
    work_unit = _seed_work_unit()
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00"), "19": Decimal("900.00")})
    snapshot = bundled_authority().snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    profile = snapshot.extraction_profiles["modelo-130-declaracion-pdf"]
    assert profile.provisional_pending_specimen is True

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={"03": Decimal("5000.00"), "19": Decimal("900.00")},
            extraction_profile_provisional=profile.provisional_pending_specimen,
        ),
    )

    # The advisory is non-blocking: identity and casillas still match.
    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    provisional_advisories = [a for a in report.advisories if a.code == "extraction_profile_provisional"]
    assert len(provisional_advisories) == 1
    advisory = provisional_advisories[0]
    assert advisory.context["modelo"] == str(work_unit.modelo)
    assert advisory.context["extraction_profile_id"] == profile.id
    assert "has no real AEAT specimen confirming its printed layout" in advisory.message
    assert "manually verify the extracted casilla values" in advisory.message


def test_filed_declaracion_value_mismatch_is_caught_as_typed_casilla_diff() -> None:
    """A filed casilla value that differs from the computed revision is CAUGHT
    and represented as a typed ``casilla`` diff with legal grounding — not a
    silent identity ``matches``."""
    work_unit = _seed_work_unit()
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00"), "19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"03": Decimal("5000.00"), "19": Decimal("950.00")}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "19"
    assert diff.kind == "casilla_value_mismatch"
    assert diff.work_unit_value == "900.00"
    assert diff.evidence_value == "950.00"
    # Provenance rides the divergence (aeat-calculation-grounding): casilla 19
    # is grounded in the M130 extraction profile / verification expectation refs.
    assert diff.legal_refs
    assert diff.source_refs


def test_filed_declaracion_missing_casilla_is_caught_as_typed_casilla_diff() -> None:
    """A casilla the computed revision resolved but the declaración omitted
    is MISSING_IN_FILED, not a silent skip."""
    work_unit = _seed_work_unit()
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00"), "19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"03": Decimal("5000.00")}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "19"
    assert diff.kind == "casilla_missing_in_filed"
    assert diff.work_unit_value == "900.00"
    assert diff.evidence_value == ""


def test_filed_declaracion_extra_casilla_is_caught_as_typed_casilla_diff() -> None:
    """A casilla the declaración prints but the computed revision never
    resolved is EXTRA_IN_FILED."""
    work_unit = _seed_work_unit()
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"03": Decimal("5000.00"), "19": Decimal("900.00")}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "19"
    assert diff.kind == "casilla_extra_in_filed"
    assert diff.work_unit_value == ""
    assert diff.evidence_value == "900.00"


def test_filed_declaracion_divergence_within_tolerance_does_not_flag() -> None:
    """The registry tolerance (0.01) is honoured: a one-cent gap is clean."""
    work_unit = _seed_work_unit()
    _persist_filed_revision(work_unit, casilla_values={"19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"19": Decimal("900.01")}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs


def test_no_persisted_revision_surfaces_advisory_not_false_green() -> None:
    work_unit = _seed_work_unit()
    # No revision persisted.

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"19": Decimal("900.00")}),
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    codes = {a.code for a in report.advisories}
    assert "totals_not_reconciled" in codes
    reasons = {a.context.get("reason") for a in report.advisories if a.code == "totals_not_reconciled"}
    assert "no_persisted_revision" in reasons


def test_header_mismatch_and_casilla_mismatch_both_surface_together() -> None:
    """A declaración that diverges on BOTH the header and a casilla value
    surfaces both diff kinds in one report — neither shadows the other."""
    work_unit = _seed_work_unit()
    _persist_filed_revision(work_unit, casilla_values={"19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"19": Decimal("950.00")}, tax_id="12345678Z"),
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    header_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.HEADER_FIELD]
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert any(d.field_name == "tax_id" for d in header_diffs)
    assert any(d.field_name == "19" for d in casilla_diffs)


def test_unenrolled_modelo_refuses_casilla_level_declaration_reconcile() -> None:
    """Modelo 200 declares no ``declaracion_pdf`` extraction profile at all and
    is not enrolled in casilla-level declaración reconcile; the private seam
    itself refuses cleanly (defence in depth alongside the public
    ``modelo_reconcile`` pre-check)."""
    work_unit = _seed_work_unit(
        modelo="200",
        filing_year=_FILING_YEAR,
        period="0A",
        snapshot_grade=RegistryAuthorityGrade.CALCULATION,
    )

    with pytest.raises(ReconciliationDeclaracionSourceUnsupportedError):
        _reconcile(
            work_unit,
            _synthetic_declaracion(
                work_unit,
                values={"00552": Decimal("100.00")},
                modelo="200",
                snapshot_grade=RegistryAuthorityGrade.CALCULATION,
            ),
        )
