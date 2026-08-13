"""Strict roundtrip across the encrypted JustificanteRepository boundary.

:class:`JustificanteRepository` persists :class:`Justificante` receipts at
``SensitivityClass.AUDIT``. A justificante is the artefact that proves a
modelo was filed, so a field silently dropped on save or silently re-defaulted
on load destroys filing evidence without surfacing anything.

The fixture sets **every defaultable field to a non-default value** — all four
of them (``ejercicio``, ``presentation_id``, ``total_a_ingresar``,
``total_a_devolver``). A save-drops / load-re-defaults regression is invisible
when a fixture leaves an optional field at its default, because the reloaded
default equals the saved default and strict equality still holds.

The two negative tests are the anti-tautology proofs that keep the equality
witness honest: corrupting the persisted CSV to a value outside the canonical
8-32 uppercase-alphanumeric bound must be refused at load, and deleting an
optional amount from the persisted envelope must surface as strict inequality
rather than a quietly re-defaulted ``None``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError
from sqlalchemy import select

from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.storage.crypto import (
    decrypt_secure_object_payload,
    encrypt_secure_object_payload,
    secure_object_payload_aad,
)
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....core import Period
from ....tests.secure_sql import isolated_runtime_profile
from .._schema import Justificante

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIOD = Period.from_year_and_code(2025, "1T")
_CSV = "ABCD12345678EFGH"
_PRESENTED_AT = datetime(2026, 4, 18, 11, 5, 0, tzinfo=UTC)
_PARSED_AT = datetime(2026, 4, 18, 11, 7, 30, tzinfo=UTC)
_SOURCE_SHA256 = "3f" * 32
_VERIFICATION_URL = "https://sede.agenciatributaria.gob.es/cotejo/ABCD12345678EFGH"
_SOURCE_PDF_PATH = Path("justificantes/303-2025-1T-ABCD.pdf")

_DEFAULTABLE_FIELDS: frozenset[str] = frozenset(
    {
        "ejercicio",
        "presentation_id",
        "total_a_ingresar",
        "total_a_devolver",
    }
)
"""The receipt's optional fields, every one populated non-default below.

Pinned as a literal set rather than derived from ``model_fields`` so that a new
optional field added to :class:`Justificante` without a non-default fixture
value fails :func:`test_every_defaultable_field_is_populated_non_default`
instead of silently widening the set the roundtrip believes it covers.
"""


def _populated_justificante() -> Justificante:
    """Build a receipt with every defaultable field carrying a non-default value.

    ``total_a_ingresar`` and ``total_a_devolver`` are both populated. A real
    receipt prints one or the other, but the schema constrains neither, and the
    purpose here is to give the strict-equality witness signal on both slots.
    """

    return Justificante(
        csv=_CSV,
        modelo="303",
        ejercicio="2025",
        period=_PERIOD,
        presentation_id="3032512345678",
        presented_at=_PRESENTED_AT,
        tax_id="12345678Z",
        total_a_ingresar=Decimal("1234.56"),
        total_a_devolver=Decimal("78.90"),
        verification_url=AnyHttpUrl(_VERIFICATION_URL),
        source_pdf_path=_SOURCE_PDF_PATH,
        source_pdf_sha256=_SOURCE_SHA256,
        parsed_at=_PARSED_AT,
    )


def test_every_defaultable_field_is_populated_non_default() -> None:
    """The fixture leaves no optional field at its schema default.

    Guards the roundtrip below: an optional field left at its default cannot
    distinguish "the boundary carried the value" from "the boundary dropped it
    and the loader re-defaulted it", so the equality assertion would be
    tautological for that field.
    """

    optional_fields = {name for name, info in Justificante.model_fields.items() if not info.is_required()}
    assert optional_fields == _DEFAULTABLE_FIELDS, (
        f"Justificante's optional-field set moved to {sorted(optional_fields)}; "
        f"the roundtrip fixture pins {sorted(_DEFAULTABLE_FIELDS)}. Populate the "
        f"new field non-default in _populated_justificante and add it here."
    )

    receipt = _populated_justificante()
    for name in sorted(_DEFAULTABLE_FIELDS):
        default = Justificante.model_fields[name].get_default(call_default_factory=True)
        assert getattr(receipt, name) != default, (
            f"fixture leaves {name!r} at its default {default!r}; the strict-equality roundtrip is blind to that field"
        )


def test_populated_justificante_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """A fully-populated receipt roundtrips strictly across AUDIT-class storage."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _populated_justificante()
        JustificanteRepository().save(original)

        loaded = JustificanteRepository().load(_CSV)

        assert loaded is not None
        assert loaded == original
        assert loaded.csv == _CSV
        assert loaded.ejercicio == "2025"
        assert loaded.presentation_id == "3032512345678"
        assert loaded.total_a_ingresar == Decimal("1234.56")
        assert loaded.total_a_devolver == Decimal("78.90")
        assert loaded.period == _PERIOD
        assert loaded.period.filing_year == 2025
        assert loaded.presented_at == _PRESENTED_AT
        assert loaded.parsed_at == _PARSED_AT
        assert loaded.source_pdf_path == _SOURCE_PDF_PATH
        assert loaded.source_pdf_sha256 == _SOURCE_SHA256


def test_justificante_iteration_surfaces_the_persisted_receipt(tmp_path: Path) -> None:
    """The CSV is the natural key, so listing and iteration find the saved receipt."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _populated_justificante()
        JustificanteRepository().save(original)

        repo = JustificanteRepository()
        assert repo.list_csvs() == (_CSV,)
        assert tuple(repo.iter_justificantes()) == (original,)


def test_justificante_corrupted_csv_is_refused_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: an out-of-bound persisted CSV must not load.

    The persisted CSV is replaced with ``"AB-CD"`` — short of the canonical
    8-character floor and carrying a separator the character class refuses —
    then the record is re-encrypted under the same associated data and read back
    through the production load path.

    A CSV that fails the canonical bound on disk is corruption: nothing in this
    application can write one, and the value is what AEAT's cotejo endpoint is
    handed to re-serve the document. If the load path accepted it, the retyped
    field would be decorative and every justificante roundtrip in the suite
    would be tautological.
    """

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_justificante()
        JustificanteRepository().save(original)

        with session_scope(profile.repository._engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == JustificanteRepository.namespace,
                SecureObjectRow.object_key == _CSV,
            )
            row = session.execute(stmt).scalar_one()
            aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            envelope = json.loads(
                decrypt_secure_object_payload(bytes(row.payload), associated_data=aad).decode("utf-8")
            )
            assert envelope["payload"]["csv"] == _CSV, (
                "fixture must serialise the csv onto the envelope payload for this proof to have signal"
            )
            envelope["payload"]["csv"] = "AB-CD"
            row.payload = encrypt_secure_object_payload(json.dumps(envelope).encode("utf-8"), associated_data=aad)

        try:
            mutated = JustificanteRepository().load(_CSV)
        except ValidationError:
            return
        assert mutated != original, (
            "anti-tautology proof failed: an out-of-bound CSV persisted on disk "
            "loaded without refusal and compared equal to the original. The "
            "justificante boundary does not enforce the canonical CSV shape and "
            "every justificante roundtrip in the suite is suspect."
        )


def test_justificante_dropped_optional_amount_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: a deleted optional amount must not re-default silently.

    ``total_a_ingresar`` is deleted from the persisted envelope. It is optional,
    so the loader will happily re-default it to ``None`` rather than raise — and
    that is precisely the save-drops-field regression the strict-equality
    witness exists to catch. The reloaded record must therefore compare
    strictly unequal to the original.
    """

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_justificante()
        JustificanteRepository().save(original)

        with session_scope(profile.repository._engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == JustificanteRepository.namespace,
                SecureObjectRow.object_key == _CSV,
            )
            row = session.execute(stmt).scalar_one()
            aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            envelope = json.loads(
                decrypt_secure_object_payload(bytes(row.payload), associated_data=aad).decode("utf-8")
            )
            assert envelope["payload"].get("total_a_ingresar") is not None, (
                "fixture must serialise a non-default total_a_ingresar for this proof to have signal"
            )
            del envelope["payload"]["total_a_ingresar"]
            row.payload = encrypt_secure_object_payload(json.dumps(envelope).encode("utf-8"), associated_data=aad)

        try:
            mutated = JustificanteRepository().load(_CSV)
        except ValidationError:
            return
        assert mutated != original, (
            "anti-tautology proof failed: deleting total_a_ingresar from the "
            "persisted envelope did NOT surface on load. An optional field can "
            "be dropped on save and silently re-defaulted on read, so every "
            "justificante roundtrip in the suite is suspect."
        )
