"""Fitness probe for the on-host text reader: its real request, on a document it can check.

Presence and a one-token answer prove a model is loaded; they do not prove it
can do the text reader's job. A vision model configured in the text role loads,
answers ``ok``, and then spends the whole extraction answer budget without
producing anything the parser can read -- so every document refuses while every
readiness check passes.

This probe sends the text reader's own prompt, rendered by the same builder,
with the same answer budget and temperature the reader's requests inherit, over
the same local transport, and grounds the reply with the same parser and field
grounding. The document is synthetic and carries no identifier, so nothing
sensitive is sent and no taxpayer fact is involved. The model is fit when the
reply parses and the two values the probe checks ground to what the document
prints.

The probe calls the transport directly rather than through the caching client:
a fitness answer must come from the model now, never from a stored reply, and it
must run without an unlocked profile.
"""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal

import httpx

from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ....application.local_reader import RoleFitnessOutcome
from ....application.provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)
from ....core.config import Settings
from ....core.field_origin import FieldOrigin
from ....core.model_catalogue import ModelRole
from ....domain.calculations.registry.authority import bundled_indexed_authority
from .errors import LLMError
from .evidence_draft_text import build_text_field_extraction_prompt
from .invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response
from .providers.base import ProviderRequest
from .providers.local import LocalAdapter

__all__ = ["probe_text_extraction_fitness"]

_PROBE_INVOICE_NUMBER = "PROBE-0001"
_PROBE_TAXABLE_BASE = Decimal("100.00")
_PROBE_TRANSCRIPTION = (
    "FACTURA\n"
    f"Numero de factura: {_PROBE_INVOICE_NUMBER}\n"
    "Fecha de expedicion: 2026-01-15\n"
    "Concepto: Servicio de prueba\n"
    "Base imponible: 100.00 EUR\n"
    "Tipo IVA: 21%\n"
    "Cuota IVA: 21.00 EUR\n"
    "Total factura: 121.00 EUR\n"
)


def probe_text_extraction_fitness(model: str, settings: Settings) -> RoleFitnessOutcome:
    """Send the text reader's real request to ``model`` and judge whether its answer is usable.

    Never raises. A model still answering when the probe's timeout expires is
    reported ``timed_out`` under its own condition; any other transport failure
    is reported with ``transport_failed`` so the caller does not record it as the
    model's fitness.
    """
    budget = settings.cadrumo_llm_default_max_tokens
    with bundled_indexed_authority().operation() as operation:
        prompt = build_text_field_extraction_prompt(_PROBE_TRANSCRIPTION, operation=operation)
        request = ProviderRequest(
            request_id="role-fitness-probe",
            model=model,
            prompt=prompt,
            system=None,
            max_tokens=budget,
            temperature=settings.cadrumo_llm_default_temperature,
            timeout_s=settings.cadrumo_llm_default_timeout_s,
        )
        started = time.monotonic()
        try:
            completion = asyncio.run(
                LocalAdapter(timeout_s=settings.cadrumo_llm_default_timeout_s).complete(request),
            )
        except (LLMError, httpx.HTTPError) as exc:
            if _timed_out(exc):
                return _unfit(
                    model,
                    budget=budget,
                    started=started,
                    condition=ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_WITHIN_TIMEOUT,
                    facts={
                        "model": model,
                        "role": ModelRole.TEXT_EXTRACTION.value,
                        "answer_budget_tokens": budget,
                        "probe_timeout_s": settings.cadrumo_llm_default_timeout_s,
                    },
                    timed_out=True,
                )
            return _unfit(
                model,
                budget=budget,
                started=started,
                condition=ProvisioningPreconditionCondition.MODEL_READY,
                facts={"model": model, "role": ModelRole.TEXT_EXTRACTION.value, "probe_error_type": type(exc).__name__},
                transport_failed=True,
            )
        facts: dict[str, ProvisioningFactValue] = {
            "model": model,
            "role": ModelRole.TEXT_EXTRACTION.value,
            "answer_budget_tokens": budget,
            "output_tokens": completion.output_tokens,
        }
        try:
            parsed = parse_invoice_extraction_response(completion.text)
        except PurchaseInvoiceEvidenceInputError:
            return _unfit(
                model,
                budget=budget,
                started=started,
                condition=ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE,
                facts={**facts, "answer_parseable": False},
                output_tokens=completion.output_tokens,
            )
        draft = ground_extracted_fields(
            parsed,
            raw_text_length=len(_PROBE_TRANSCRIPTION),
            origin=FieldOrigin.TEXT_LAYER,
            operation=operation,
        )
    grounded = draft.invoice_number == _PROBE_INVOICE_NUMBER and draft.taxable_base == _PROBE_TAXABLE_BASE
    elapsed = int((time.monotonic() - started) * 1000)
    if not grounded:
        return _unfit(
            model,
            budget=budget,
            started=started,
            condition=ProvisioningPreconditionCondition.ROLE_MODEL_FIT_FOR_ROLE,
            facts={**facts, "answer_parseable": True, "probe_values_grounded": False},
            output_tokens=completion.output_tokens,
            answer_parseable=True,
        )
    return RoleFitnessOutcome(
        role=ModelRole.TEXT_EXTRACTION,
        model=model,
        fit=True,
        answer_parseable=True,
        grounded=True,
        output_tokens=completion.output_tokens,
        answer_budget_tokens=budget,
        elapsed_ms=elapsed,
        facts={**facts, "answer_parseable": True, "probe_values_grounded": True},
    )


def _timed_out(exc: BaseException) -> bool:
    """Return whether the request reached the model and ran past the probe's bound.

    A read timeout means the runtime accepted the request and the model was still
    answering, which is a fact about the model on this host. A refused or failed
    connection is not, so only the read and write phases count.
    """
    cause: BaseException | None = exc
    while cause is not None:
        if isinstance(cause, (httpx.ReadTimeout, httpx.WriteTimeout)):
            return True
        cause = cause.__cause__
    return False


def _unfit(
    model: str,
    *,
    budget: int,
    started: float,
    condition: ProvisioningPreconditionCondition,
    facts: dict[str, ProvisioningFactValue],
    output_tokens: int | None = None,
    answer_parseable: bool = False,
    timed_out: bool = False,
    transport_failed: bool = False,
) -> RoleFitnessOutcome:
    return RoleFitnessOutcome(
        role=ModelRole.TEXT_EXTRACTION,
        model=model,
        fit=False,
        answer_parseable=answer_parseable,
        timed_out=timed_out,
        transport_failed=transport_failed,
        output_tokens=output_tokens,
        answer_budget_tokens=budget,
        elapsed_ms=int((time.monotonic() - started) * 1000),
        facts=facts,
        precondition_verdict=provisioning_no_recovery_verdict(condition, facts=facts),
    )
