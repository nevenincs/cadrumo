"""Serialization refusal tests for in-memory evidence bytes."""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic_core import PydanticSerializationError

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ..evidence_input import EvidenceInput, resolve_purchase_invoice_evidence_input
from ._evidence_input_test_support import _added_record, pdf_file
from ._evidence_input_test_support import runtime_profile as runtime_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "pdf_file", "runtime_profile", "secure_objects"]


def test_evidence_input_refuses_persistence(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    resolved = resolve_purchase_invoice_evidence_input(record, store=AttachmentStore(objects=secure_objects))

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
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    resolved = resolve_purchase_invoice_evidence_input(record, store=AttachmentStore(objects=secure_objects))

    class _Wrapper(BaseModel):
        ev: EvidenceInput

    wrapper = _Wrapper(ev=resolved)
    with pytest.raises(PydanticSerializationError):
        wrapper.model_dump()
    with pytest.raises(PydanticSerializationError):
        wrapper.model_dump_json()
