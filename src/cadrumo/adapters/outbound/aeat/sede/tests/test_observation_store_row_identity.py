"""A decrypted Sede row must be the row that was asked for.

Both observation families derive their natural key from identity fields the
payload itself carries, but nothing re-derived it after decryption: ``load_*``
validated only the envelope's class and version, and ``list_*`` not even a key.
A valid payload re-encrypted under another row's key was returned as that row,
so custody consumers would associate filing evidence with the wrong
declaration, or a wallet balance with the wrong period — with no error
anywhere, because every layer beneath answered correctly about the row it was
handed.

``load_artefact`` had the same shape one level down: it parsed the requested
SHA-256 out of the storage reference and returned the row's bytes without
hashing them, so a content address nothing re-checks was only a lookup key.

Each tamper re-encrypts a GENUINE payload under another row's associated data,
which is what a substituted row looks like: the AAD, the schema version, the
sensitivity class and the envelope all still agree, so only an identity check
at this boundary can catch it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ......core.config import Settings
from ......core.period import Period
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from .....persistence.storage.secure_object_namespaces import (
    AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE,
    AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE,
    AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE,
)
from .....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ..errors import SedeValidationError
from ..iva_compensation_wallet_parsing import WALLET_URL
from ..observation_store import FiledDeclaracionObservationStore
from ..schema import (
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)
from .observation_store_support import declaration_pdf_artefact, filed_declaration_observation
from .wallet_observation_inventory import list_iva_wallet_observations

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_EJERCICIO = newest_authored_edition("100")
_WALLET_YEAR = filing_year_envelope().horizon
_BUCKET_ID = "d0ab4fce-5ade-4781-9880-7a851f2bf2e1"  # was 'sede-row-identity'
_AEAT = Settings.external_constants().aeat
_COTEJO_DOCUMENT_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.cotejo_document}"


def _wallet(target_year: int, captured_at: datetime) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif="12345678Z",
        authenticated_identity="12345678Z",
        target_year=target_year,
        target_period=Period.from_year_and_code(target_year, "1T"),
        rows=(
            IvaCompensationWalletRow(
                generation_year=target_year - 1,
                generation_period=Period.from_year_and_code(target_year - 1, "4T"),
                pending_amount=Decimal("1234.56"),
            ),
        ),
        total_pending=Decimal("1234.56"),
        source_url=AnyHttpUrl(WALLET_URL),
        captured_at=captured_at,
    )


def _rows(engine, namespace: str) -> list[tuple[object, bytes, bytes]]:
    """Return ``(row, aad, plaintext)`` for every row in ``namespace``."""
    from sqlalchemy import select

    from .....persistence.storage.crypto.encrypted_columns import (
        decrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from .....persistence.storage.sql.session import session_scope
    from .....persistence.storage.sql.tables import secure_objects_table

    with session_scope(engine) as session:
        found = []
        for row in session.execute(select(secure_objects_table).where(secure_objects_table.c.namespace == namespace)):
            aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            found.append((row.id, aad, decrypt_secure_object_payload(bytes(row.payload), associated_data=aad)))
        return found


def _substitute(engine, namespace: str, *, victim_marker: str, donor_marker: str) -> None:
    """Re-encrypt the donor row's genuine plaintext under the victim row's identity.

    Rows are told apart by a marker in their decrypted payload rather than by a
    predicate on ``object_key``: that column is a hashed-lookup type, so its
    stored bytes are a digest and a raw-bytes WHERE clause is not a narrower
    query but a different one.
    """
    from sqlalchemy import update

    from .....persistence.storage.crypto.encrypted_columns import encrypt_secure_object_payload
    from .....persistence.storage.sql.session import session_scope
    from .....persistence.storage.sql.tables import secure_objects_table

    rows = _rows(engine, namespace)
    donor = next(plaintext for _, _, plaintext in rows if donor_marker in plaintext.decode("utf-8"))
    victim_id = next(row_id for row_id, _, plaintext in rows if victim_marker in plaintext.decode("utf-8"))
    victim_aad = next(aad for row_id, aad, _ in rows if row_id == victim_id)

    with session_scope(engine) as session:
        session.execute(
            update(secure_objects_table)
            .where(secure_objects_table.c.id == victim_id)
            .values(payload=encrypt_secure_object_payload(donor, associated_data=victim_aad)),
        )


def test_a_filed_observation_under_a_foreign_row_is_refused_on_targeted_load(tmp_path: Path) -> None:
    """The targeted lookup refuses instead of answering with the other declaration."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        artefact = declaration_pdf_artefact(b"%PDF-1.7 A")
        path_a = store.persist_observation(filed_declaration_observation(artefact, expediente_id="202310013522456T"))
        store.persist_observation(filed_declaration_observation(artefact, expediente_id="202410013522999B"))

        _substitute(
            profile.repository._engine,
            AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace,
            victim_marker="202310013522456T",
            donor_marker="202410013522999B",
        )

        with pytest.raises(SedeValidationError):
            store.load_observation(path_a)


def test_a_filed_observation_under_a_foreign_row_is_refused_on_enumeration(tmp_path: Path) -> None:
    """Enumeration refuses too — the wider of the two doors.

    A consumer that lists rather than looks up would otherwise carry the
    substituted evidence with no key ever compared.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        artefact = declaration_pdf_artefact(b"%PDF-1.7 A")
        store.persist_observation(filed_declaration_observation(artefact, expediente_id="202310013522456T"))
        store.persist_observation(filed_declaration_observation(artefact, expediente_id="202410013522999B"))

        _substitute(
            profile.repository._engine,
            AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace,
            victim_marker="202310013522456T",
            donor_marker="202410013522999B",
        )

        with pytest.raises(SedeValidationError):
            store.list_observations()


def test_a_wallet_observation_under_a_foreign_row_is_refused(tmp_path: Path) -> None:
    """The wallet family carries the same guard, keyed on its own identity fields.

    A wallet balance read against the wrong target period is a wrong number in
    a filing, not a mislabelled record.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        path_a = store.persist_iva_wallet_observation(
            _wallet(_WALLET_YEAR, datetime(_WALLET_YEAR, 4, 1, 9, 0, tzinfo=UTC))
        )
        store.persist_iva_wallet_observation(
            _wallet(_WALLET_YEAR - 1, datetime(_WALLET_YEAR - 1, 4, 1, 9, 0, tzinfo=UTC))
        )

        _substitute(
            profile.repository._engine,
            AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE.namespace,
            victim_marker=f'"target_year":{_WALLET_YEAR}',
            donor_marker=f'"target_year":{_WALLET_YEAR - 1}',
        )

        with pytest.raises(SedeValidationError):
            store.load_iva_wallet_observation(path_a)
        with pytest.raises(SedeValidationError):
            list_iva_wallet_observations(store)


def test_the_substituted_row_really_holds_a_valid_foreign_payload(tmp_path: Path) -> None:
    """The tamper's positive control.

    Without it the refusals above could be earned by a corrupted payload
    failing to parse, proving the pre-existing envelope guards rather than the
    new identity check. Here the substituted bytes are a complete, parseable
    envelope for the OTHER row.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        artefact = declaration_pdf_artefact(b"%PDF-1.7 A")
        store.persist_observation(filed_declaration_observation(artefact, expediente_id="202310013522456T"))
        store.persist_observation(filed_declaration_observation(artefact, expediente_id="202410013522999B"))

        _substitute(
            profile.repository._engine,
            AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace,
            victim_marker="202310013522456T",
            donor_marker="202410013522999B",
        )

        payloads = [
            json.loads(plaintext.decode("utf-8"))
            for _, _, plaintext in _rows(
                profile.repository._engine,
                AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE.namespace,
            )
        ]
        expedientes = sorted(payload["payload"]["expediente_id"] for payload in payloads)

        # Both rows now decode cleanly, and both to the SAME declaration:
        # the victim row no longer holds its own.
        assert expedientes == ["202410013522999B", "202410013522999B"]


def test_an_untampered_store_still_loads_and_lists(tmp_path: Path) -> None:
    """The binding must not turn every legitimate read into a refusal."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        artefact = declaration_pdf_artefact(b"%PDF-1.7 A")
        observation = filed_declaration_observation(artefact, expediente_id="202310013522456T")
        wallet = _wallet(_WALLET_YEAR, datetime(_WALLET_YEAR, 4, 1, 9, 0, tzinfo=UTC))

        path = store.persist_observation(observation)
        wallet_path = store.persist_iva_wallet_observation(wallet)

        assert store.load_observation(path) == observation
        assert store.list_observations() == (observation,)
        assert store.load_iva_wallet_observation(wallet_path) == wallet
        assert list_iva_wallet_observations(store) == (wallet,)


def test_an_artefact_whose_bytes_do_not_match_its_reference_is_refused(tmp_path: Path) -> None:
    """A content address nothing re-checks is only a lookup key.

    ``persist_artefact`` verifies the digest on the way in, but the row can be
    overwritten afterwards under the same key; the read then returned bytes
    that did not hash to the reference it was asked for. This is AEAT filing
    evidence, so bytes that cannot re-derive their own address cannot defend a
    figure whatever they contain.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        body_a = b"%PDF-1.7 body A"
        body_b = b"%PDF-1.7 body B, a different filing entirely"
        key = ("100", _EJERCICIO, Period.from_year_and_code(_EJERCICIO, "0A"), "202310013522456T")
        ref_a = store.persist_artefact(key, declaration_pdf_artefact(body_a), body_a).storage_ref
        assert ref_a is not None
        store.persist_artefact(key, declaration_pdf_artefact(body_b), body_b)

        _substitute(
            profile.repository._engine,
            AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.namespace,
            victim_marker="body A",
            donor_marker="body B",
        )

        # The row under ref A now holds B's genuine bytes: intact, decryptable,
        # and exactly what the pre-fix read returned. Nothing but the re-hash
        # stands between the caller and the wrong evidence.
        stored = [
            plaintext
            for _, _, plaintext in _rows(
                profile.repository._engine,
                AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE.namespace,
            )
        ]
        assert stored.count(body_b) == 2
        assert body_a not in stored

        with pytest.raises(SedeValidationError):
            store.load_artefact(ref_a)


def test_an_untampered_artefact_still_loads(tmp_path: Path) -> None:
    """The re-hash must not refuse a genuine artefact."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        body = b"%PDF-1.7 body A"
        key = ("100", _EJERCICIO, Period.from_year_and_code(_EJERCICIO, "0A"), "202310013522456T")
        ref = store.persist_artefact(key, declaration_pdf_artefact(body), body).storage_ref
        assert ref is not None

        assert store.load_artefact(ref) == body
