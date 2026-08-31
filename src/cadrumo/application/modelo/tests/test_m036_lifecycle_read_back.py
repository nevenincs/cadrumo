"""Real-runtime read-back tests for the M036 declaration list / view surface.

Authority: the operator-surface decision D7 (read-back
baseline guarantee).

Drives the production persistence + read path end to end: a real bucket
runtime, real encrypted ``SecureObjectRepository`` write, real
``SecureSnapshotRepository`` enumeration / resolution.  Records an alta + a
modificacion + a baja, then asserts ``list_m036_declarations`` returns all
three with their persisted fields and ``read_m036_declaration`` returns the
exact recorded record (strict equality on the typed record, every defaultable
field populated non-default — a real ``sede_justificante`` and ``note``).  An
empty bucket lists clean; an unknown id refuses.  An anti-tautology proof
shows a record absent from storage is absent from the list.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ....domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ....tests.secure_sql import isolated_runtime_profile
from .._m036_lifecycle import (
    M036DeclarationCommand,
    M036DeclarationResult,
    list_m036_declarations,
    read_m036_declaration,
    record_m036_declaration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "30303030-3030-4030-8030-303030303030"


def _command(
    *,
    event_kind: CensoModeloEventKind,
    declared_on: date,
    justificante: str | None = None,
    note: str | None = None,
) -> M036DeclarationCommand:
    return M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=event_kind,
        declared_on=declared_on,
        sede_justificante=justificante,
        note=note,
    )


def test_list_returns_every_recorded_declaration(tmp_path: Path) -> None:
    """alta + modificacion + baja all surface in list with their persisted fields."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        alta = record_m036_declaration(
            _command(
                event_kind=CensoModeloEventKind.ALTA,
                declared_on=date(2026, 1, 10),
                justificante="ACUSE-ALTA-1",
                note="Initial registration",
            ),
            bucket_id=runtime.bucket_id,
        )
        modificacion = record_m036_declaration(
            _command(
                event_kind=CensoModeloEventKind.MODIFICACION,
                declared_on=date(2026, 3, 15),
                justificante="ACUSE-MOD-1",
                note="Domicilio fiscal update",
            ),
            bucket_id=runtime.bucket_id,
        )
        baja = record_m036_declaration(
            _command(
                event_kind=CensoModeloEventKind.BAJA,
                declared_on=date(2026, 12, 31),
                justificante="ACUSE-BAJA-1",
                note="Deregistration",
            ),
            bucket_id=runtime.bucket_id,
        )

        declarations = list_m036_declarations(bucket_id=runtime.bucket_id)

    assert all(isinstance(declaration, M036DeclarationResult) for declaration in declarations)
    by_id = {declaration.declaration_id: declaration for declaration in declarations}
    assert set(by_id) == {alta.declaration_id, modificacion.declaration_id, baja.declaration_id}
    assert {declaration.event_kind for declaration in declarations} == {
        CensoModeloEventKind.ALTA,
        CensoModeloEventKind.MODIFICACION,
        CensoModeloEventKind.BAJA,
    }
    # Every persisted field round-trips through the encrypted store.
    assert by_id[modificacion.declaration_id].sede_justificante == "ACUSE-MOD-1"
    assert by_id[modificacion.declaration_id].note == "Domicilio fiscal update"
    assert by_id[modificacion.declaration_id].declared_on == date(2026, 3, 15)


def test_view_returns_exact_recorded_record_strict_equality(tmp_path: Path) -> None:
    """read_m036_declaration returns the exact persisted record (strict equality).

    Every defaultable field is populated non-default (a real
    ``sede_justificante`` and ``note``) per the roundtrip discipline, so a
    save-drops-field / load-re-defaults-field regression cannot hide behind a
    default value.

    A ``modificacion`` amends an existing registration, so this records the
    requisite alta first — the sequence guard refuses a bare ``modificacion``
    with nothing on record.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        record_m036_declaration(
            _command(event_kind=CensoModeloEventKind.ALTA, declared_on=date(2026, 1, 1)),
            bucket_id=runtime.bucket_id,
        )
        recorded = record_m036_declaration(
            _command(
                event_kind=CensoModeloEventKind.MODIFICACION,
                declared_on=date(2026, 5, 20),
                justificante="ACUSE-RB-EXACT",
                note="Read-back exact-equality probe",
            ),
            bucket_id=runtime.bucket_id,
        )

        viewed = read_m036_declaration(recorded.declaration_id, bucket_id=runtime.bucket_id)

    assert viewed == recorded
    assert viewed.sede_justificante == "ACUSE-RB-EXACT"
    assert viewed.note == "Read-back exact-equality probe"
    assert viewed.declared_on == date(2026, 5, 20)
    assert viewed.recorded_at == recorded.recorded_at


def test_view_resolves_unambiguous_prefix(tmp_path: Path) -> None:
    """A unique prefix of the declaration id resolves to the single record."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        recorded = record_m036_declaration(
            _command(
                event_kind=CensoModeloEventKind.ALTA,
                declared_on=date(2026, 2, 2),
                justificante="ACUSE-PREFIX",
                note="Prefix-resolution probe",
            ),
            bucket_id=runtime.bucket_id,
        )

        viewed = read_m036_declaration(recorded.declaration_id[:12], bucket_id=runtime.bucket_id)

    assert viewed == recorded


def test_view_unknown_id_refuses(tmp_path: Path) -> None:
    """An id matching no recorded declaration raises the not-found error."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        record_m036_declaration(
            _command(event_kind=CensoModeloEventKind.ALTA, declared_on=date(2026, 6, 1)),
            bucket_id=runtime.bucket_id,
        )

        with pytest.raises(KeyError):
            read_m036_declaration("f" * 64, bucket_id=runtime.bucket_id)


def test_list_on_empty_bucket_returns_clean_empty(tmp_path: Path) -> None:
    """An untouched bucket lists no declarations — a clean empty, not an error."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        declarations = list_m036_declarations(bucket_id=runtime.bucket_id)

    assert declarations == ()


def test_anti_tautology_unrecorded_declaration_absent_from_list(tmp_path: Path) -> None:
    """A declaration that was never recorded is absent from list and refuses on view.

    Anti-tautology proof: derive the id a record *would* have without
    persisting it, then assert the list omits it and the view of it refuses.
    If this passed with an unrecorded record present, every read-back test in
    the suite would be tautological.
    """
    from .._m036_lifecycle import derive_m036_declaration_id

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        recorded = record_m036_declaration(
            _command(
                event_kind=CensoModeloEventKind.ALTA,
                declared_on=date(2026, 4, 4),
                justificante="ACUSE-PRESENT",
                note="present",
            ),
            bucket_id=runtime.bucket_id,
        )
        never_recorded_id = derive_m036_declaration_id(
            profile_id=_PROFILE_ID,
            event_kind=CensoModeloEventKind.BAJA,
            declared_on=date(2027, 1, 1),
            sede_justificante="ACUSE-NEVER",
        )

        declarations = list_m036_declarations(bucket_id=runtime.bucket_id)
        listed_ids = {declaration.declaration_id for declaration in declarations}

        assert recorded.declaration_id in listed_ids
        assert never_recorded_id not in listed_ids
        with pytest.raises(KeyError):
            read_m036_declaration(never_recorded_id, bucket_id=runtime.bucket_id)
