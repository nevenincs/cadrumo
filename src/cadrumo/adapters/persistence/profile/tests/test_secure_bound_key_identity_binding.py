"""A secure-bound row's key and its payload's identity are one fact.

``SecureBoundRepository.save`` derives the SQL object key from the payload
itself, via ``extract_identifier`` -- for a justificante, the AEAT CSV. The two
are therefore two encodings of one fact, but nothing on the read path checked
that, so a row written under a different key returned its payload unremarked:
``load("CSV-B")`` handed back the record whose own ``csv`` is ``"CSV-A"``.

That is a quiet wrong answer rather than a loud failure. The returned object
describes itself truthfully and validates cleanly; it simply is not the record
that was asked for. A caller resolving a receipt by CSV -- to attach evidence
to a filing, or to answer "was this presented?" -- gets another taxpayer
artefact with no signal that anything is amiss.

``load`` now compares the payload's own identity with the key it was looked up
under and raises rather than returning ``None``: the row exists, and reporting
it absent would hide a real inconsistency behind an ordinary miss.

Real active profile, real SQLite, real AES-GCM. The mis-keyed row is written
through the substrate's own writer rather than by editing bytes, so it is a
genuinely well-formed row that differs only in the key it is filed under.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from .....core import Period
from .....domain.justificante import Justificante
from .....tests.aeat_literal_fixtures import justificante_wlpl_cotejo_url
from .....tests.secure_sql import isolated_runtime_profile
from ....persistence.storage import SecureObjectRowIdentityError
from ..justificante import JustificanteRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PRESENTED_AT = datetime(2026, 5, 27, 11, 15, 0, tzinfo=UTC)
_CSV_A = "AAAA11112222BBBB"
_CSV_B = "CCCC33334444DDDD"


def _justificante(csv: str) -> Justificante:
    return Justificante(
        csv=csv,
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        ejercicio="2025",
        presentation_id="PRES-2025-001-XYZ",
        presented_at=_PRESENTED_AT,
        tax_id="12345678Z",
        total_a_ingresar=Decimal("12345.67"),
        total_a_devolver=None,
        verification_url=AnyHttpUrl(justificante_wlpl_cotejo_url(csv)),
        source_pdf_path=Path("justificantes/303-2025-1T-AAAA.pdf"),
        source_pdf_sha256="a" * 64,
        parsed_at=_PRESENTED_AT,
    )


def _save_under_foreign_key(repository: JustificanteRepository, payload: Justificante, *, object_key: str) -> None:
    """Persist ``payload`` under ``object_key`` instead of its own identity.

    Written through the substrate's real writer with the repository's real
    envelope, so the row is well-formed in every respect except the key it is
    filed under -- isolating the key/payload binding as the only thing under
    test.
    """
    _, envelope = repository._identified_envelope(payload)
    repository._objects.save(
        namespace=repository.namespace,
        object_key=object_key,
        classification=repository.sensitivity,
        schema_version=repository.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )


def test_a_correctly_keyed_record_round_trips(tmp_path: Path) -> None:
    """Positive control: the ordinary save/load cycle is untouched.

    Every refusal below is only evidence against this. It also proves the
    comparison is not simply always-failing, which a naive identity check
    written against the wrong field would be.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        repository.save(record)

        assert repository.load(_CSV_A) == record
        assert repository.list_csvs() == (_CSV_A,)


def test_loading_a_mis_keyed_row_refuses_instead_of_returning_another_record(tmp_path: Path) -> None:
    """The discriminating case: asking for B must not yield A.

    Before the binding this returned the CSV-A record, so a caller resolving
    a receipt by CSV received a different artefact entirely and had no signal.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        _save_under_foreign_key(repository, record, object_key=_CSV_B)

        with pytest.raises(SecureObjectRowIdentityError):
            repository.load(_CSV_B)


def test_a_mis_keyed_row_is_absent_under_its_own_identity(tmp_path: Path) -> None:
    """The record is unreachable by its true CSV, which is the honest answer.

    Pins the other half of the inconsistency: the row is filed under B, so a
    lookup by A finds nothing. Distinguishing "absent" here from "refused"
    above is what shows the refusal is about the key/payload disagreement
    rather than about the record being unreadable in general.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        _save_under_foreign_key(repository, record, object_key=_CSV_B)

        assert repository.load(_CSV_A) is None


def test_verified_iteration_refuses_the_same_row(tmp_path: Path) -> None:
    """Lookup and verified enumeration reach the same verdict.

    The two surfaces previously disagreed -- lookup returned the record while
    enumeration reported its true identity -- so asserting them together is
    what establishes one invariant rather than two independent checks.
    """
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        _save_under_foreign_key(repository, record, object_key=_CSV_B)

        with pytest.raises(SecureObjectRowIdentityError):
            list(repository.iter_verified_records())


def test_a_correctly_keyed_row_survives_verified_iteration(tmp_path: Path) -> None:
    """Positive control for the enumeration half."""
    record = _justificante(_CSV_A)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = JustificanteRepository()
        repository.save(record)

        assert list(repository.iter_verified_records()) == [record]
