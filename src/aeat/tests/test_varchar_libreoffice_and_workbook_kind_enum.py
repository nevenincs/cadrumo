"""Runtime contracts for secure-object hash columns and workbook parity vocabulary."""

from __future__ import annotations

from enum import StrEnum

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from ..adapters.persistence.storage.sql import SecureObjectRow, ensure_quarantine_table
from ..domain.calculations.registry import WorkbookKind, WorkbookRunnerAvailability

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SECURE_OBJECT_HASH_COLUMNS: tuple[str, ...] = (
    "revision_id",
    "previous_revision_id",
    "previous_payload_hash",
    "payload_hash",
    "ciphertext_hash",
)

_WORKBOOK_KIND_VALUES: frozenset[str] = frozenset(
    {
        "formula_form",
        "record_design_layout",
        "validation_hints",
        "static_layout",
        "unsupported_binary_xls",
        "unreadable",
    },
)


def test_secure_object_hash_columns_are_reflected_as_fixed_length_varchar() -> None:
    """The live secure_objects table exposes fixed-width revision/hash metadata."""
    engine = create_engine("sqlite:///:memory:")
    SecureObjectRow.__table__.create(engine)

    reflected = {column["name"]: column["type"] for column in inspect(engine).get_columns("secure_objects")}

    assert {name: reflected[name].length for name in _SECURE_OBJECT_HASH_COLUMNS} == {
        name: 64 for name in _SECURE_OBJECT_HASH_COLUMNS
    }


def test_secure_object_quarantine_preserves_fixed_length_hash_columns() -> None:
    """The quarantine archive mirrors the fixed-width hash metadata contract."""
    engine = create_engine("sqlite:///:memory:")

    ensure_quarantine_table(engine)

    reflected = {
        column["name"]: column["type"] for column in inspect(engine).get_columns("secure_objects_quarantine")
    }
    assert {name: reflected[name].length for name in _SECURE_OBJECT_HASH_COLUMNS} == {
        name: 64 for name in _SECURE_OBJECT_HASH_COLUMNS
    }


def test_workbook_kind_public_enum_exposes_closed_classification_vocabulary() -> None:
    """Workbook reports expose a closed StrEnum vocabulary to callers."""
    assert issubclass(WorkbookKind, StrEnum)
    assert frozenset(member.value for member in WorkbookKind) == _WORKBOOK_KIND_VALUES
    assert {member.value: str(member) for member in WorkbookKind} == {
        value: value for value in _WORKBOOK_KIND_VALUES
    }


def test_workbook_runner_availability_accepts_only_declared_engines() -> None:
    """Runner availability records validate the public engine vocabulary."""
    libreoffice = WorkbookRunnerAvailability(
        status="available",
        engine="libreoffice-headless",
        executable="soffice",
        detail="LibreOffice executable found for local workbook recalculation",
    )
    excel = WorkbookRunnerAvailability(
        status="available",
        engine="excel-com",
        executable="{00024500-0000-0000-C000-000000000046}",
        detail="Excel COM automation is registered for local read-only workbook recalculation",
    )

    assert libreoffice.engine == "libreoffice-headless"
    assert excel.engine == "excel-com"
    with pytest.raises(ValidationError):
        WorkbookRunnerAvailability(
            status="available",
            engine="libreoffice",
            executable="libreoffice",
            detail="unsupported short engine name",
        )
