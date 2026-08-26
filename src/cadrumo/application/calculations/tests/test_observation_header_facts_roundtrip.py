"""Typed diseño header facts survive the encrypted observation boundary.

AEAT states some filing elections as HEADER fields in its diseño de registro
rather than as casillas -- the tipo de declaración, the sin-actividad and REDEME
markers. Those facts were being parsed out of the fichero at capture and then
dropped before storage, because the persisted provenance was assembled from a
fixed key set and copied exactly one key off the raw observation. The evidence
existed at capture and was gone by the time anything could read it, which is
worse than never reading it: the capture looked complete.

``source_headers`` is therefore a typed field on the persisted payload rather
than more entries in the flat ``source_metadata`` map. A flat string pair cannot
carry the record-design locator that makes a header fact auditable back to the
bytes, and a fixed-key projection cannot carry a key nobody named.

Real adapters throughout: real master-key provider, real SQLite engine, real
serializer, through ``isolated_runtime_profile``. Nothing here is stubbed --
a mock returning what the assertion expects would prove only that the assertion
was written.

See Also:
    :class:`~core.ObservedHeaderFact`
        The typed fact, and where its value-coverage limit is recorded.
    :class:`~application.calculations.ObservationEnvelopePayload`
        The persisted payload that now carries the facts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from cadrumo.domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation

from ....adapters.persistence.storage.sql import SecureObjectRow
from ....core import CasillaId, ObservedHeaderFact, Period, validated_casilla_id
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from .._observations_repository import (
    CalculationObservationRepository,
    ObservationEnvelopePayload,
    member_observation_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 5, 28, 11, 35, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")


_IVA_RESULTADO: CasillaId = validated_casilla_id("iva.resultado", surface="header facts roundtrip")


def _observation() -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id=_IVA_RESULTADO,
                value=Decimal("12345.67"),
                formula_id=None,
                operand_refs=(),
                operand_casilla_refs=(),
                operand_values=(),
                legal_refs=("ley-37-1992:art-21",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
    )


def _header_facts() -> tuple[ObservedHeaderFact, ...]:
    """Three facts spanning the shapes a real fichero produces.

    Two one-byte election flags and one multi-character token, each with a
    distinct record and offset in its locator, so a projection that collapsed
    facts onto one key or reused one locator cannot pass.
    """
    return (
        ObservedHeaderFact(
            header_key="declaration_type",
            value="C",
            source_artefact_kind="submitted_file",
            source_locator="modelo-303-fichero-boe:modelo-303-page-01:modelo-303-declaration-type:13:1",
        ),
        ObservedHeaderFact(
            header_key="sin_actividad",
            value="X",
            source_artefact_kind="submitted_file",
            source_locator="modelo-303-fichero-boe:modelo-303-page-01:modelo-303-sin-actividad:391:1",
        ),
        ObservedHeaderFact(
            header_key="program_version",
            value="A001",
            source_artefact_kind="submitted_file",
            source_locator="modelo-303-fichero-boe:modelo-303-page-01:modelo-303-program-version:100:4",
        ),
    )


def _save(repo: CalculationObservationRepository) -> ObservationEnvelopePayload:
    """Persist with EVERY defaultable payload field set non-default.

    ``member_nif``, ``source_metadata`` and ``source_headers`` all default, so a
    fixture that left any of them at its default could not distinguish "the
    field roundtripped" from "the field was dropped and re-defaulted to the same
    value the fixture happened to use".

    Setting ``member_nif`` widens the storage key, so the read goes through the
    member key rather than ``load_observation``, which only addresses the
    single-filer key. Reading back under the widened key is itself part of what
    this fixture establishes: a payload saved as a member row and read as a
    single-filer row would come back as ``None``.
    """
    repo.save(
        repo.prepare_observation_envelope(
            _observation(),
            source_kind="aeat_sede_justificante",
            captured_at=_CAPTURED_AT,
            member_nif="B12345678",
            source_metadata={"aeat_register_status": "ALTA", "aeat_expediente_id": "202530300000001Z"},
            source_headers=_header_facts(),
        )
    )
    loaded = repo.load(member_observation_key("303", _PERIOD, "B12345678"))
    assert loaded is not None, "the observation did not come back at all"
    return loaded


def test_header_facts_survive_the_encrypted_observation_roundtrip(tmp_path: Path) -> None:
    """Strict equality across the boundary, provenance included.

    Asserted as whole-tuple equality rather than field-by-field: a partial
    comparison is how a dropped ``source_locator`` survives review, and the
    locator is the field that makes the fact auditable rather than merely
    present.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()

        loaded = _save(repo)

        assert loaded.source_headers == _header_facts()
        assert loaded.member_nif == "B12345678"
        assert loaded.source_metadata == {
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "202530300000001Z",
        }
        # The typed channel and the flat map stay separate concerns: a header
        # fact must not have been smuggled into source_metadata on the way.
        assert not any(key.startswith("aeat_declaration_type") for key in loaded.source_metadata)


def test_a_header_fact_stripped_of_its_locator_refuses_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof, refusal arm: the typed row is strictly required.

    Deletes ``source_locator`` from one persisted fact inside the encrypted
    envelope and asserts the load refuses. Without this, every equality
    assertion above could be passing over a boundary that silently reconstructs
    whatever it cannot read.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository()
        _save(repo)

        object_key = member_observation_key("303", _PERIOD, "B12345678")
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == CalculationObservationRepository.namespace,
            SecureObjectRow.object_key == object_key,
        )

        def mutate(envelope):
            facts = envelope["payload"]["source_headers"]
            assert facts and facts[0]["source_locator"], (
                "the fixture did not serialise a locator, so this proof would pass over a broken boundary"
            )
            del facts[0]["source_locator"]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        with pytest.raises(ValidationError, match="source_locator"):
            repo.load(member_observation_key("303", _PERIOD, "B12345678"))


def test_dropping_the_whole_header_channel_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology proof, inequality arm -- and it documents a real asymmetry.

    ``source_headers`` defaults to an empty tuple, because most producers
    legitimately have no diseño headers: an app filing and an operator-entered
    row have none, and requiring the field would refuse them. That default is
    correct and it has a consequence worth stating rather than discovering: a
    payload that loses the whole channel does NOT raise, it re-defaults to
    empty. So the detection available here is strict inequality, not refusal,
    and this test pins exactly that -- which is the honest form of the
    save-drops-field / load-re-defaults-field regression for a defaultable
    field.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository()
        saved = _save(repo)
        assert saved.source_headers, "nothing was stored, so the deletion below would prove nothing"

        object_key = member_observation_key("303", _PERIOD, "B12345678")
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == CalculationObservationRepository.namespace,
            SecureObjectRow.object_key == object_key,
        )

        def mutate(envelope):
            del envelope["payload"]["source_headers"]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        reloaded = repo.load(member_observation_key("303", _PERIOD, "B12345678"))

        assert reloaded is not None
        assert reloaded.source_headers == (), "the channel was not actually dropped, so this proves nothing"
        assert reloaded != saved, "a lost header channel compared equal, so every roundtrip here is tautological"
