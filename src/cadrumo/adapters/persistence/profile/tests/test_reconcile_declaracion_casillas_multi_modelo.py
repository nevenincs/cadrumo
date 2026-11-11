"""Real-behavior tests for casilla-level declaración reconcile enrollment.

Extends the coverage :mod:`test_reconcile_declaracion_casillas` established for
Modelo 130 to the five modelos enrolled under
:data:`cadrumo.application.modelo.reconciliation.DECLARATION_RECONCILE_ROLE`
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
the ``reconcile_parsed_declaracion`` application service directly with a synthetically
constructed
:class:`~cadrumo.adapters.inbound.declaracion.InboundDeclaracionObservation`,
mirroring the pattern ``test_reconcile_declaracion_casillas.py`` uses for
Modelo 130. The synthetic fixture data is declared ``synthetic_generated``
(not derived from a real AEAT filing) per the fixture-provenance discipline.
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
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    filing_grade_exercises,
    filing_year_envelope,
    newest_authored_edition,
)
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
_M100_YEAR = newest_authored_edition("100")
_HORIZON = filing_year_envelope().horizon
_CLOCK = datetime(_HORIZON, 4, 20, tzinfo=UTC)
_persist_filed_revision = partial(persist_filed_revision, clock=_CLOCK)
_synthetic_declaracion = partial(synthetic_declaracion, tax_id=_PROFILE_TAX_ID)


# Seeded through a detached WorkflowState, never a repository read: the
# capsule publishes by an atomic no-replace rename onto ``buckets/<profile-id>``,
# which a workflow-state repository construction would otherwise materialise
# first and collide with.
_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="33333333-3333-4333-8333-333333333333",
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
        source_ref=f"test://declaracion-{work_unit.modelo}",
        actor="operator",
        declaracion=declaracion,
        operation=operation,
    )


# --- Modelo 100 (IRPF annual): printed Renta casilla ids --------------------


def test_modelo_100_pagos_fraccionados_mismatch_is_caught_as_typed_casilla_diff(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """M100 0604 must reconcile against the annual pagos-fraccionados credit.

    The persisted revision represents the annual declaration after the four
    Modelo 130 quarters have folded into casilla 0604. A filed declaración that
    prints a different 0604 must surface a typed casilla mismatch rather than
    an identity-only reconcile success.
    """
    work_unit = seed_active_work_unit(modelo="100", filing_year=_M100_YEAR, period="0A", operation=authority_operation)
    _persist_filed_revision(work_unit, casilla_values={"0604": Decimal("1520.00")})

    report = _reconcile(
        work_unit,
        # One M130 quarter short against the already-folded annual credit.
        _synthetic_declaracion(work_unit, values={"0604": Decimal("1140.00")}, operation=authority_operation),
        operation=authority_operation,
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
    assert f"aeat-dr-100-{_M100_YEAR}-dictionary" in diff.source_refs


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
            _HORIZON,
            "1T",
            {"27": Decimal("1000.00"), "45": Decimal("400.00"), "iva.resultado": Decimal("600.00")},
            id="303",
        ),
        pytest.param(
            "390",
            filing_grade_exercises("390")[-1],
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
            _HORIZON,
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
    authority_operation: PinnedAuthorityOperation,
) -> None:
    work_unit = seed_active_work_unit(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        operation=authority_operation,
    )
    _persist_filed_revision(work_unit, casilla_values=casilla_values)

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(work_unit, values=casilla_values, operation=authority_operation),
        operation=authority_operation,
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs


# --- Modelo 303 (IVA autoliquidación): compound iva.* casilla ids -----------


def test_modelo_303_value_mismatch_is_caught_as_typed_casilla_diff(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A filed casilla value that differs from the computed revision is
    CAUGHT and represented as a typed ``casilla`` diff — not a silent
    identity ``matches``."""
    work_unit = seed_active_work_unit(
        modelo="303",
        filing_year=_HORIZON,
        period="1T",
        operation=authority_operation,
    )
    _persist_filed_revision(
        work_unit,
        casilla_values={"27": Decimal("1000.00"), "45": Decimal("400.00"), "iva.resultado": Decimal("600.00")},
    )

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={"27": Decimal("1000.00"), "45": Decimal("400.00"), "iva.resultado": Decimal("650.00")},
            operation=authority_operation,
        ),
        operation=authority_operation,
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


def test_modelo_390_missing_casilla_is_caught_as_typed_casilla_diff(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A casilla the computed revision resolved but the declaración omitted
    is MISSING_IN_FILED, not a silent skip."""
    work_unit = seed_active_work_unit(
        modelo="390",
        filing_year=filing_grade_exercises("390")[-1],
        period="0A",
        operation=authority_operation,
    )
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
            operation=authority_operation,
        ),
        operation=authority_operation,
    )

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    casilla_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.CASILLA]
    assert len(casilla_diffs) == 1
    diff = casilla_diffs[0]
    assert diff.field_name == "iva.anual.resultado-regimen-general"
    assert diff.kind == "casilla_missing_in_filed"


# --- Modelo 111 (retenciones e ingresos a cuenta trimestral): "01".."30" ----


def test_modelo_111_matching_declaracion_reconciles_clean(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    work_unit = seed_active_work_unit(
        modelo="111",
        filing_year=_HORIZON,
        period="1T",
        operation=authority_operation,
    )
    _persist_filed_revision(work_unit, casilla_values={"28": Decimal("3200.00"), "30": Decimal("3200.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={"28": Decimal("3200.00"), "30": Decimal("3200.00")},
            operation=authority_operation,
        ),
        operation=authority_operation,
    )

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs


def test_modelo_111_value_mismatch_is_caught_as_typed_casilla_diff(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    work_unit = seed_active_work_unit(
        modelo="111",
        filing_year=_HORIZON,
        period="1T",
        operation=authority_operation,
    )
    _persist_filed_revision(work_unit, casilla_values={"28": Decimal("3200.00"), "30": Decimal("3200.00")})

    report = _reconcile(
        work_unit,
        _synthetic_declaracion(
            work_unit,
            values={"28": Decimal("3200.00"), "30": Decimal("3250.00")},
            operation=authority_operation,
        ),
        operation=authority_operation,
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


def test_modelo_190_value_mismatch_is_caught_as_typed_casilla_diff(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    work_unit = seed_active_work_unit(
        modelo="190",
        filing_year=_HORIZON,
        period="0A",
        operation=authority_operation,
    )
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
            operation=authority_operation,
        ),
        operation=authority_operation,
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
