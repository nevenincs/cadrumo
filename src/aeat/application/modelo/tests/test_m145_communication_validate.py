"""Real-runtime validation tests for Modelo 145 local communication records.

See Also:
    :mod:`~application.modelo._m145_communication_records`
        Backend validation service under test.
    :func:`~application.modelo.validate_m145_communication_record`
        Public facade validator exercised by this module.
    :class:`~application.modelo.M145CommunicationValidationIssueKind`
        Typed validation issue vocabulary asserted for malformed records.
    :class:`~domain.calculations.registry.CasillaDefinition`
        Registry casilla definitions that drive required-field validation.
    :class:`~domain.calculations.registry.ModeloRevision`
        Active Modelo 145 revision whose legal and source refs are preserved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import CasillaDefinition, casillas_by_id
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    M145CommunicationCreateCommand,
    M145CommunicationValidationIssueKind,
    create_m145_communication_record,
    validate_m145_communication_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _field_values() -> dict[str, str]:
    return {
        "perceptor.nif": "12345678Z",
        "perceptor.primer-apellido": "Garcia",
        "perceptor.segundo-apellido": "Lopez",
        "perceptor.nombre": "Ana",
        "perceptor.anio-nacimiento": "1981",
    }


def _snapshot_casillas() -> dict[str, CasillaDefinition]:
    snapshot = resources().modelos.authority.snapshot("145", filing_year=2026, period="comunicacion")
    return casillas_by_id(snapshot.revision)


def _casilla_for_data_type(data_type: str) -> CasillaDefinition:
    for casilla in sorted(_snapshot_casillas().values(), key=lambda item: item.id):
        if casilla.data_type == data_type:
            return casilla
    raise AssertionError(f"Modelo 145 registry declares no casilla with data_type={data_type!r}")


def test_validate_m145_communication_record_accepts_registry_backed_required_fields(tmp_path: Path) -> None:
    snapshot = resources().modelos.authority.snapshot("145", filing_year=2026, period="comunicacion")

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
            bucket_id=runtime.bucket_id,
        )
        result = validate_m145_communication_record(record.communication_record_id[:12], bucket_id=runtime.bucket_id)

    assert result.valid is True
    assert result.issue_count == 0
    assert result.issues == ()
    assert result.communication_record_id == record.communication_record_id
    assert result.revision_id == snapshot.revision.id
    assert result.legal_refs == tuple(sorted(str(ref) for ref in snapshot.revision.legal_refs))
    assert result.source_refs == tuple(sorted(str(ref) for ref in snapshot.revision.source_refs))


def test_validate_m145_communication_record_reports_missing_required_casilla_with_registry_refs(
    tmp_path: Path,
) -> None:
    casillas = _snapshot_casillas()
    missing = next(casilla for casilla in sorted(casillas.values(), key=lambda item: item.id) if casilla.required)
    values = _field_values()
    values.pop(missing.id)

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=values),
            bucket_id=runtime.bucket_id,
        )
        result = validate_m145_communication_record(record.communication_record_id, bucket_id=runtime.bucket_id)

    issue = next(issue for issue in result.issues if issue.kind is M145CommunicationValidationIssueKind.MISSING_REQUIRED)
    assert result.valid is False
    assert issue.casilla_id == missing.id
    assert issue.data_type == missing.data_type
    assert issue.legal_refs == tuple(str(ref) for ref in missing.legal_refs)
    assert issue.source_refs == tuple(str(ref) for ref in missing.source_refs)


@pytest.mark.parametrize(
    ("data_type", "invalid_value"),
    (
        ("date", "2026/01/31"),
        ("integer", "1.5"),
        ("money", "not-money"),
        ("nif", "not-a-nif"),
        ("year", "19X1"),
    ),
)
def test_validate_m145_communication_record_reports_registry_data_type_failures(
    tmp_path: Path,
    data_type: str,
    invalid_value: str,
) -> None:
    casilla = _casilla_for_data_type(data_type)
    values = _field_values()
    values[casilla.id] = invalid_value

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=values),
            bucket_id=runtime.bucket_id,
        )
        result = validate_m145_communication_record(record.communication_record_id, bucket_id=runtime.bucket_id)

    issue = next(
        issue
        for issue in result.issues
        if issue.kind is M145CommunicationValidationIssueKind.INVALID_VALUE and issue.casilla_id == casilla.id
    )
    assert result.valid is False
    assert issue.data_type == data_type
    assert issue.legal_refs == tuple(str(ref) for ref in casilla.legal_refs)
    assert issue.source_refs == tuple(str(ref) for ref in casilla.source_refs)
