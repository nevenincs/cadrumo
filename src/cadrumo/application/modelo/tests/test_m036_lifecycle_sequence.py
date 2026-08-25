"""Real-runtime tests for the Modelo 036 alta / modificacion / baja ordering guard.

AEAT's 036 is event-triggered: a ``modificacion`` amends and a ``baja``
deregisters an existing declaration, so both require a prior ``alta`` on
record; ``baja`` is terminal, so nothing further may follow it. Drives the
production persistence path exactly as the sibling service tests do (a real
bucket runtime, real encrypted writes), so a passing refusal test proves the
guard fires against real storage, not a stand-in.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ....domain.modelos import Modelo036PriorAltaRequiredError, Modelo036TerminalStateError
from ....tests.secure_sql import isolated_runtime_profile
from .._m036_lifecycle import M036DeclarationCommand, list_m036_declarations, record_m036_declaration

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "31313131-3131-4131-8131-313131313131"


def _command(
    *,
    event_kind: CensoModeloEventKind,
    declared_on: date,
    justificante: str | None = None,
) -> M036DeclarationCommand:
    return M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=event_kind,
        declared_on=declared_on,
        sede_justificante=justificante,
    )


def test_alta_then_modificacion_is_accepted(tmp_path: Path) -> None:
    """A modificacion following its own prior alta is the ordinary, accepted case."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        alta = record_m036_declaration(
            _command(event_kind=CensoModeloEventKind.ALTA, declared_on=date(2026, 1, 10)),
            bucket_id=runtime.bucket_id,
        )
        modificacion = record_m036_declaration(
            _command(event_kind=CensoModeloEventKind.MODIFICACION, declared_on=date(2026, 3, 15)),
            bucket_id=runtime.bucket_id,
        )

        declarations = list_m036_declarations(bucket_id=runtime.bucket_id)

    assert {declaration.declaration_id for declaration in declarations} == {
        alta.declaration_id,
        modificacion.declaration_id,
    }


def test_modificacion_without_prior_alta_is_refused(tmp_path: Path) -> None:
    """A modificacion with nothing on record refuses, naming what's wrong."""
    command = _command(event_kind=CensoModeloEventKind.MODIFICACION, declared_on=date(2026, 3, 15))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        with pytest.raises(Modelo036PriorAltaRequiredError) as exc_info:
            record_m036_declaration(command, bucket_id=runtime.bucket_id)

        assert exc_info.value.context is not None
        assert exc_info.value.context["requested_event_kind"] == CensoModeloEventKind.MODIFICACION.value
        assert list_m036_declarations(bucket_id=runtime.bucket_id) == ()


def test_baja_without_prior_alta_is_refused(tmp_path: Path) -> None:
    """A baja with nothing on record refuses the same way a modificacion does."""
    command = _command(event_kind=CensoModeloEventKind.BAJA, declared_on=date(2026, 3, 15))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        with pytest.raises(Modelo036PriorAltaRequiredError):
            record_m036_declaration(command, bucket_id=runtime.bucket_id)

        assert list_m036_declarations(bucket_id=runtime.bucket_id) == ()


@pytest.mark.parametrize("event_kind", list(CensoModeloEventKind))
def test_anything_after_baja_is_refused(tmp_path: Path, event_kind: CensoModeloEventKind) -> None:
    """Baja is terminal: alta, modificacion, and baja itself are all refused after it."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        alta = record_m036_declaration(
            _command(event_kind=CensoModeloEventKind.ALTA, declared_on=date(2026, 1, 10)),
            bucket_id=runtime.bucket_id,
        )
        baja = record_m036_declaration(
            _command(event_kind=CensoModeloEventKind.BAJA, declared_on=date(2026, 6, 30)),
            bucket_id=runtime.bucket_id,
        )
        before = {declaration.declaration_id for declaration in list_m036_declarations(bucket_id=runtime.bucket_id)}
        assert before == {alta.declaration_id, baja.declaration_id}

        # A distinct declared_on than the baja's own, or the derived id would
        # collide with an already-recorded declaration and this would test
        # the idempotent-repeat exemption instead of the terminal-state gate.
        next_command = _command(event_kind=event_kind, declared_on=date(2026, 9, 1))
        with pytest.raises(Modelo036TerminalStateError) as exc_info:
            record_m036_declaration(next_command, bucket_id=runtime.bucket_id)

        assert exc_info.value.context is not None
        assert exc_info.value.context["prior_declaration_id"] == baja.declaration_id
        after = {declaration.declaration_id for declaration in list_m036_declarations(bucket_id=runtime.bucket_id)}

    # Nothing new landed: the refused attempt persisted exactly what was
    # there before it, no more.
    assert after == before


def test_a_refused_sequence_persists_nothing_and_emits_no_event(tmp_path: Path) -> None:
    """Anti-tautology: a refused declaration writes neither the record nor its audit event.

    Derives the id the refused command WOULD have produced and confirms it
    never reaches storage, mirroring the profile/bucket-mismatch guard's own
    anti-tautology proof — a guard placed after any write would leave a
    partial trace even though the call raised.
    """
    from .._m036_lifecycle import derive_m036_declaration_id

    refused_command = _command(event_kind=CensoModeloEventKind.BAJA, declared_on=date(2026, 6, 30))
    would_be_id = derive_m036_declaration_id(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.BAJA,
        declared_on=date(2026, 6, 30),
        sede_justificante=None,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        with pytest.raises(Modelo036PriorAltaRequiredError):
            record_m036_declaration(refused_command, bucket_id=runtime.bucket_id)

        listed_ids = {declaration.declaration_id for declaration in list_m036_declarations(bucket_id=runtime.bucket_id)}
        catalogue = BucketEventHistoryRepository().load()

    assert would_be_id not in listed_ids
    assert listed_ids == set()
    assert not any(event.object_id == would_be_id for event in catalogue.events.values())
    assert catalogue.events == {}


def test_an_identical_repeat_of_the_terminal_baja_stays_idempotent(tmp_path: Path) -> None:
    """A retry of the exact same baja tuple is a no-op replay, not a new transition.

    The content-addressed ``declaration_id`` makes any exact repeat
    idempotent by design (:func:`record_m036_declaration`'s own contract);
    the sequence guard must not turn that pre-existing idempotency into a
    refusal just because the repeated declaration happens to be a baja.
    """
    baja_command = _command(
        event_kind=CensoModeloEventKind.BAJA,
        declared_on=date(2026, 6, 30),
        justificante="ACUSE-BAJA-REPEAT",
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as runtime:
        record_m036_declaration(
            _command(event_kind=CensoModeloEventKind.ALTA, declared_on=date(2026, 1, 10)),
            bucket_id=runtime.bucket_id,
        )
        first = record_m036_declaration(baja_command, bucket_id=runtime.bucket_id)
        second = record_m036_declaration(baja_command, bucket_id=runtime.bucket_id)

    assert first.declaration_id == second.declaration_id
