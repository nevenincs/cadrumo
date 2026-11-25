"""Real-behavior tests for casilla-level filed-declaración reconciliation (Modelo 130).

These lock the ``reconcile-declaration-casillas`` contract: a filed declaración
PDF is compared casilla-by-casilla against the
persisted computed :class:`~CalculationRevision`, not only
at the header / total level. Modelo 130 is the first modelo enrolled under
:data:`cadrumo.application.modelo.reconciliation.DECLARATION_RECONCILE_ROLE`
because its ``declaracion_pdf`` extraction profile targets registry casilla ids
``"01"``..``"19"`` directly.

Real-PDF declaración extraction (the ``bbox_anchored`` pdfplumber word-position
primitive) is Tier-R and out of scope here (tracked separately alongside the
remaining not-yet-enrolled modelos). This suite tests
the ``reconcile_parsed_declaracion`` application service directly with a synthetically
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
from functools import partial

import pytest

from cadrumo.adapters.inbound.declaracion.schema import InboundDeclaracionObservation
from cadrumo.adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    active_profile_isolated_backend_fixture,
)
from cadrumo.application.modelo.reconciliation_comparison import ReconciliationDeclaracionSourceUnsupportedError
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.work_unit import WorkUnit

from .....application.modelo.reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from .....application.modelo.reconciliation_records import ModeloReconciliationDiffKind, ModeloReconciliationVerdict
from .reconciliation_persist_support import (
    persist_filed_revision,
    reconcile_parsed_declaracion,
    seed_active_work_unit,
    synthetic_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_TAX_ID = "00000000T"
_CLOCK = datetime(2026, 4, 20, tzinfo=UTC)
_MODELO_130 = "130"
_FILING_YEAR = 2026
_PERIOD = "1T"
_seed_work_unit = partial(seed_active_work_unit, modelo=_MODELO_130, filing_year=_FILING_YEAR, period=_PERIOD)
_persist_filed_revision = partial(persist_filed_revision, clock=_CLOCK)
_synthetic_declaracion = partial(synthetic_declaracion, tax_id=_PROFILE_TAX_ID)


# Seeded through a detached WorkflowState, never a repository read: the
# capsule publishes by an atomic no-replace rename onto ``buckets/<profile-id>``,
# which a workflow-state repository construction would otherwise materialise
# first and collide with.
_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="22222222-2222-4222-8222-222222222222",
    profile_overrides={"identity.tax_id": _PROFILE_TAX_ID},
)


def _reconcile(
    work_unit: WorkUnit,
    declaracion: InboundDeclaracionObservation,
    *,
    operation: PinnedAuthorityOperation,
):
    return reconcile_parsed_declaracion(
        work_unit=work_unit,
        source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
        source_ref="test://declaracion-130",
        actor="operator",
        declaracion=declaracion,
        operation=operation,
    )


def test_filed_declaracion_matching_computed_revision_reconciles_clean(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    work_unit = _seed_work_unit(operation=authority_operation)
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00"), "19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={"03": Decimal("5000.00"), "19": Decimal("900.00")},
            operation=authority_operation,
        ),
        operation=authority_operation,
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs
    assert "extraction_profile_provisional" not in {a.code for a in report.advisories}


def test_provisional_extraction_profile_surfaces_non_blocking_advisory(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A declaración parsed through a ``provisional_pending_specimen`` profile
    discloses that its layout is unconfirmed rather than silently presenting
    bbox-anchored values as verified (no-silent-under-declaration)."""
    work_unit = _seed_work_unit(operation=authority_operation)
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00"), "19": Decimal("900.00")})
    snapshot = authority_operation.snapshot(
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
            operation=authority_operation,
            extraction_profile_provisional=profile.provisional_pending_specimen,
        ),
        operation=authority_operation,
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


def test_filed_declaracion_value_mismatch_is_caught_as_typed_casilla_diff(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A filed casilla value that differs from the computed revision is CAUGHT
    and represented as a typed ``casilla`` diff with legal grounding — not a
    silent identity ``matches``."""
    work_unit = _seed_work_unit(operation=authority_operation)
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00"), "19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={"03": Decimal("5000.00"), "19": Decimal("950.00")},
            operation=authority_operation,
        ),
        operation=authority_operation,
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


def test_filed_declaracion_missing_casilla_is_caught_as_typed_casilla_diff(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A casilla the computed revision resolved but the declaración omitted
    is MISSING_IN_FILED, not a silent skip."""
    work_unit = _seed_work_unit(operation=authority_operation)
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00"), "19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"03": Decimal("5000.00")}, operation=authority_operation),
        operation=authority_operation,
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "19"
    assert diff.kind == "casilla_missing_in_filed"
    assert diff.work_unit_value == "900.00"
    assert diff.evidence_value == ""


def test_filed_declaracion_extra_casilla_is_caught_as_typed_casilla_diff(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A casilla the declaración prints but the computed revision never
    resolved is EXTRA_IN_FILED."""
    work_unit = _seed_work_unit(operation=authority_operation)
    _persist_filed_revision(work_unit, casilla_values={"03": Decimal("5000.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={"03": Decimal("5000.00"), "19": Decimal("900.00")},
            operation=authority_operation,
        ),
        operation=authority_operation,
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "19"
    assert diff.kind == "casilla_extra_in_filed"
    assert diff.work_unit_value == ""
    assert diff.evidence_value == "900.00"


def test_filed_declaracion_divergence_within_tolerance_does_not_flag(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The registry tolerance (0.01) is honoured: a one-cent gap is clean."""
    work_unit = _seed_work_unit(operation=authority_operation)
    _persist_filed_revision(work_unit, casilla_values={"19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"19": Decimal("900.01")}, operation=authority_operation),
        operation=authority_operation,
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs


def test_no_persisted_revision_surfaces_advisory_not_false_green(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    work_unit = _seed_work_unit(operation=authority_operation)
    # No revision persisted.

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values={"19": Decimal("900.00")}, operation=authority_operation),
        operation=authority_operation,
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    codes = {a.code for a in report.advisories}
    assert "totals_not_reconciled" in codes
    reasons = {a.context.get("reason") for a in report.advisories if a.code == "totals_not_reconciled"}
    assert "no_persisted_revision" in reasons


def test_header_mismatch_and_casilla_mismatch_both_surface_together(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A declaración that diverges on BOTH the header and a casilla value
    surfaces both diff kinds in one report — neither shadows the other."""
    work_unit = _seed_work_unit(operation=authority_operation)
    _persist_filed_revision(work_unit, casilla_values={"19": Decimal("900.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={"19": Decimal("950.00")},
            operation=authority_operation,
            tax_id="12345678Z",
        ),
        operation=authority_operation,
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    header_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.HEADER_FIELD]
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert any(d.field_name == "tax_id" for d in header_diffs)
    assert any(d.field_name == "19" for d in casilla_diffs)


def test_unenrolled_modelo_refuses_casilla_level_declaration_reconcile(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 200 declares no ``declaracion_pdf`` extraction profile at all and
    is not enrolled in casilla-level declaración reconcile; the private seam
    itself refuses cleanly (defence in depth alongside the public
    ``modelo_reconcile`` pre-check)."""
    work_unit = _seed_work_unit(
        modelo="200",
        filing_year=_FILING_YEAR,
        period="0A",
        snapshot_grade=RegistryAuthorityGrade.CALCULATION,
        operation=authority_operation,
    )

    with pytest.raises(ReconciliationDeclaracionSourceUnsupportedError):
        _reconcile(
            work_unit,
            _synthetic_declaracion(
                work_unit,
                values={"00552": Decimal("100.00")},
                operation=authority_operation,
                modelo="200",
                snapshot_grade=RegistryAuthorityGrade.CALCULATION,
            ),
            operation=authority_operation,
        )
