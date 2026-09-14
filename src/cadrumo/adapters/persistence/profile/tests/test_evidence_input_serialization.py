"""Serialization refusal tests for in-memory evidence bytes."""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic_core import PydanticSerializationError

from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.evidence_input import EvidenceInput, resolve_purchase_invoice_evidence_input
from cadrumo.application.ledger.evidence_input_ports import EvidenceInputPorts
from cadrumo.core.config import Settings

from ._evidence_input_test_support import (
    _added_record,
    evidence_input_ports,
    isolated_settings,
    pdf_file,
    secure_objects,
)
from ._evidence_input_test_support import runtime_profile as runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
__all__ = ["evidence_input_ports", "isolated_settings", "pdf_file", "runtime_profile", "secure_objects"]


def test_evidence_input_refuses_persistence(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
    evidence_input_ports: EvidenceInputPorts,
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    resolved = resolve_purchase_invoice_evidence_input(
        record,
        store=AttachmentStore(objects=secure_objects),
        ports=evidence_input_ports,
    )

    with pytest.raises(NotImplementedError):
        resolved.model_dump()
    with pytest.raises(NotImplementedError):
        resolved.model_dump_json()
    with pytest.raises(NotImplementedError):
        dict(resolved)
    with pytest.raises(NotImplementedError):
        pickle.dumps(resolved)


def test_nested_serialization_cannot_leak_evidence_bytes(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
    evidence_input_ports: EvidenceInputPorts,
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    resolved = resolve_purchase_invoice_evidence_input(
        record,
        store=AttachmentStore(objects=secure_objects),
        ports=evidence_input_ports,
    )

    class _Wrapper(BaseModel):
        ev: EvidenceInput

    wrapper = _Wrapper(ev=resolved)
    with pytest.raises(PydanticSerializationError):
        wrapper.model_dump()
    with pytest.raises(PydanticSerializationError):
        wrapper.model_dump_json()
