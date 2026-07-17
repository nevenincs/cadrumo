"""Workflow-engine tests over production authorities only.

The end-to-end engine path is exercised by the modelo verification and filing
suites through ``build_revision_workflow_engine``.  This module keeps the
workflow package's local witnesses focused on boundaries that can be exercised
without inventing collaborator behaviour: the dependency direction, the shared
registry-backed deadline schedule, and registered error-envelope metadata.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from ....application.state_projection import build_pending_obligations
from ....core.errors import ErrorCategory, build_error_envelope
from ....domain.deadlines import DeadlineEngine, IVARegime, TaxpayerProfile, compute_obligation_schedule
from .. import _engine as engine_module
from .._errors import UnhandledWorkflowError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_workflow_engine_avoids_outbound_adapter_imports() -> None:
    """The application engine must not bind an outbound AEAT adapter module."""
    bound_outbound_modules = {
        name: value.__name__
        for name, value in vars(engine_module).items()
        if inspect.ismodule(value) and value.__name__.startswith("cadrumo.adapters.outbound.aeat")
    }

    assert bound_outbound_modules == {}


def test_workflow_deadline_gate_and_projection_share_the_production_schedule() -> None:
    """Both consumers expose the exact rows emitted by the deadline authority."""
    profile = TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    today = date(2026, 4, 12)

    schedule = compute_obligation_schedule(DeadlineEngine(), profile, today=today)
    authority_rows = {
        (obligation.modelo, obligation.period, obligation.opens_on, obligation.closes_on, obligation.status)
        for obligation in schedule.obligations
    }
    projection_rows = {
        (obligation.modelo, obligation.period, obligation.opens_on, obligation.closes_on, obligation.status)
        for obligation in build_pending_obligations(profile, today=today)
    }

    assert authority_rows
    assert projection_rows == authority_rows


@pytest.mark.parametrize(
    "exc",
    (
        ValueError("bad value"),
        TypeError("wrong type"),
        KeyError("missing"),
        RuntimeError("boom"),
        AttributeError("no attr"),
    ),
)
def test_unhandled_workflow_error_uses_the_registered_envelope(exc: Exception) -> None:
    """A real workflow error resolves through the central envelope registry."""
    error = UnhandledWorkflowError(
        f"COMPUTING_DEADLINES raised {type(exc).__name__}: {exc}",
        context={
            "stage": "COMPUTING_DEADLINES",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
    )
    error.__cause__ = exc

    envelope = build_error_envelope(error)

    assert envelope.code == "INTERNAL_WORKFLOW_UNHANDLED"
    assert envelope.category == ErrorCategory.INTERNAL.value
    assert envelope.retryable is False
    assert envelope.context is not None
    assert envelope.context["stage"] == "COMPUTING_DEADLINES"
    assert envelope.context["error_type"] == type(exc).__name__
