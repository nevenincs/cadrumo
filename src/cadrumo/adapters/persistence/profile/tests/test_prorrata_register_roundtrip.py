"""Strict roundtrip across the cross-period IVA prorrata register repo.

Persists :class:`ProrrataRegister` under
``cadrumo.persistence.profile.prorrata_register`` at ``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture populates every defaultable field across the register
with non-default values (a fully-settled carried entry carrying its provisional
percentage, provenance, source-observation identity, and definitive percentage
plus both volume inputs; a second AEAT-authorised especial entry carrying a
sector id and an authorisation reference). The save-drops-field /
load-re-defaults-field regression is caught by two probes: one corrupts a
persisted value and asserts the strict-equality witness surfaces the drift, one
deletes a required field and asserts the load path raises.

See Also:
    :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`
        Encrypted repository under test for save/load and upsert behaviour.
    :class:`~domain.prorrata_register.ProrrataRegister`
        Strict aggregate persisted as the profile-scoped secure-object payload.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Per-ejercicio register row whose defaultable fields are populated for
        the anti-tautology roundtrip.
    :func:`~tests.secure_sql.isolated_runtime_profile`
        Real SQLite + encrypted runtime profile used instead of mocks or
        shadow persistence.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pydantic
import pytest

from .....core import (
    ABSENT_SECURE_OBJECT_REVISION_ID,
    ProrrataActivityRowType,
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from .....core.external_constants import UTF_8_ENCODING
from .....domain.prorrata_register import (
    PRORRATA_REGISTER_SCHEMA_VERSION,
    ProrrataActivityRow,
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterError,
    SectorDefinition,
)
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ....persistence.storage.errors import SecureObjectRevisionConflictError, StorageValidationError
from ....persistence.storage.sql.engine import get_engine
from ..prorrata_register import ProrrataRegisterRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _populated_register() -> ProrrataRegister:
    carried_settled = ProrrataRegisterEntry(
        ejercicio=2024,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        provisional_percentage=Decimal("80"),
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref="303:2023:4T",
        definitive_percentage=Decimal("77"),
        definitive_volume_con_derecho=Decimal("154000.00"),
        definitive_volume_sin_derecho=Decimal("46000.00"),
    )
    authorised_sector = ProrrataRegisterEntry(
        ejercicio=2024,
        regime=ProrrataRegisterRegime.ESPECIAL,
        sector_id="arrendamiento",
        provisional_percentage=Decimal("60"),
        provisional_provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        authorisation_reference="AEAT-AUTH-2024-0007",
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=ProrrataEspecialTransitionKind.OPCION,
            evidence_reference="modelo-303-2024-prorrata-opcion",
        ),
    )
    interrupted = ProrrataRegisterEntry(
        ejercicio=2023,
        regime=ProrrataRegisterRegime.NINGUNA,
        especial_transition=None,
        interrupted=True,
    )
    sector_definition = SectorDefinition(
        sector_id="arrendamiento",
        letra=SectorDiferenciadoLetra.A,
        member_activity_codes=("6820",),
    )
    return ProrrataRegister(
        entries=(carried_settled, authorised_sector, interrupted),
        sector_definitions=(sector_definition,),
    )


def _activity_row(*, activity_id: str, slot: int) -> ProrrataActivityRow:
    return ProrrataActivityRow(
        ejercicio=2024,
        activity_id=activity_id,
        slot=slot,
        cnae_code="471",
        operaciones_total=Decimal("1000.00"),
        operaciones_con_derecho=Decimal("800.00"),
        prorrata_type=ProrrataActivityRowType.GENERAL,
        percentage=Decimal("80.00"),
        evidence_reference=f"operator-evidence:{activity_id}",
    )


def test_register_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """ProrrataRegister roundtrips through encrypted SQL, field-for-field."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="49a879c9-dab5-473a-a049-15d04aa31404"):
        repo = ProrrataRegisterRepository()
        original = _populated_register()
        repo.save(original)
        loaded = repo.load()

        assert loaded == original
        carried = loaded.entries[0]
        assert carried.regime is ProrrataRegisterRegime.GENERAL
        assert carried.provisional_percentage == Decimal("80")
        assert carried.provisional_provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
        assert carried.source_observation_ref == "303:2023:4T"
        assert carried.definitive_percentage == Decimal("77")
        assert carried.definitive_volume_con_derecho == Decimal("154000.00")
        assert carried.definitive_volume_sin_derecho == Decimal("46000.00")
        authorised = loaded.entries[1]
        assert authorised.regime is ProrrataRegisterRegime.ESPECIAL
        assert authorised.sector_id == "arrendamiento"
        assert authorised.provisional_provenance is ProrrataProvisionalProvenance.AEAT_AUTORIZADA
        assert authorised.authorisation_reference == "AEAT-AUTH-2024-0007"
        assert authorised.especial_transition is not None
        assert authorised.especial_transition.kind is ProrrataEspecialTransitionKind.OPCION
        assert authorised.especial_transition.evidence_reference == "modelo-303-2024-prorrata-opcion"
        assert loaded.is_sectorized is True
        sector_definition = loaded.sector_definition_for("arrendamiento")
        assert sector_definition is not None
        assert sector_definition.letra is SectorDiferenciadoLetra.A
        assert sector_definition.member_activity_codes == ("6820",)
        # The art. 105.Cinco interrupted (sin operaciones) marker crosses the
        # encrypted boundary: an inactive ejercicio carries no percentage/volume.
        interrupted = loaded.entry_for(2023)
        assert interrupted is not None
        assert interrupted.interrupted is True
        assert interrupted.provisional_percentage is None
        assert interrupted.definitive_percentage is None


def test_register_outer_secure_schema_matches_the_v2_document(tmp_path: Path) -> None:
    """A real save binds the SQL row and bare document to the same v2 contract."""
    import json as _json

    from sqlalchemy import select

    from ....persistence.storage.sql.session import session_scope
    from ...storage import PROFILE_PRORRATA_REGISTER_NAMESPACE, SECURE_OBJECT_SCHEMA_VERSION_V2
    from ...storage.crypto import decrypt_secure_object_payload, secure_object_payload_aad
    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f9d6d231-3774-48bb-a542-0a4bb1d1f5a6") as profile:
        engine = get_engine(profile.settings)
        ProrrataRegisterRepository().save(_populated_register())

        with session_scope(engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == PROFILE_PRORRATA_REGISTER_NAMESPACE.namespace,
                    SecureObjectRow.object_key == PROFILE_PRORRATA_REGISTER_NAMESPACE.require_default_object_key(),
                ),
            ).scalar_one()
            assert PROFILE_PRORRATA_REGISTER_NAMESPACE.schema_version == SECURE_OBJECT_SCHEMA_VERSION_V2
            assert row.schema_version == SECURE_OBJECT_SCHEMA_VERSION_V2
            plaintext = decrypt_secure_object_payload(
                bytes(row.payload),
                associated_data=secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version),
            )

        document = _json.loads(plaintext.decode(UTF_8_ENCODING))
        assert document["schema_version"] == PRORRATA_REGISTER_SCHEMA_VERSION == "2"


def test_register_outer_v1_row_refuses_without_a_tolerant_read(tmp_path: Path) -> None:
    """A re-encrypted v1 SQL row is refused; no upgrader or implicit restamp exists."""
    from sqlalchemy import select

    from ....persistence.storage.sql.session import session_scope
    from ...storage import PROFILE_PRORRATA_REGISTER_NAMESPACE
    from ...storage.crypto import (
        decrypt_secure_object_payload,
        encrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="c791265a-e7b5-4dcb-af93-d28e011972ca") as profile:
        engine = get_engine(profile.settings)
        repo = ProrrataRegisterRepository()
        repo.save(_populated_register())

        with session_scope(engine) as session:
            row = session.execute(
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == PROFILE_PRORRATA_REGISTER_NAMESPACE.namespace,
                    SecureObjectRow.object_key == PROFILE_PRORRATA_REGISTER_NAMESPACE.require_default_object_key(),
                ),
            ).scalar_one()
            plaintext = decrypt_secure_object_payload(
                bytes(row.payload),
                associated_data=secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version),
            )
            row.schema_version = 1
            row.payload = encrypt_secure_object_payload(
                plaintext,
                associated_data=secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version),
            )

        with pytest.raises(ProrrataRegisterError, match="unable to load prorrata register") as exc_info:
            repo.load()
        assert isinstance(exc_info.value.__cause__, StorageValidationError)
        assert "requires explicit schema migration before read" in str(exc_info.value.__cause__)


def test_register_upsert_replaces_entry_by_key(tmp_path: Path) -> None:
    """Declaring an entry for an existing (ejercicio, sector) key replaces it in place."""
    from ..prorrata_register import declare_prorrata_entry

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="789a648c-8348-42bc-b1b4-425b2de7d703"):
        first = ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("80"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        )
        declare_prorrata_entry(first)
        settled = first.model_copy(
            update={
                "definitive_percentage": Decimal("77"),
                "definitive_volume_con_derecho": Decimal("154000.00"),
                "definitive_volume_sin_derecho": Decimal("46000.00"),
            }
        )
        register = declare_prorrata_entry(settled)
        assert len(register.entries_for_ejercicio(2024)) == 1
        assert register.entry_for(2024) == settled


def test_register_upserts_retain_encrypted_activity_rows(tmp_path: Path) -> None:
    """All singleton mutations retain the canonical per-activity row substrate."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="474448e1-88e9-469a-bba5-b1fc9f007dbd"):
        repo = ProrrataRegisterRepository()
        retail = _activity_row(activity_id="retail", slot=1)
        repo.upsert_activity_row(retail)
        repo.upsert_entry(
            ProrrataRegisterEntry(
                ejercicio=2024,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
            ),
        )
        repo.upsert_sector_definition(
            SectorDefinition(
                sector_id="retail",
                letra=SectorDiferenciadoLetra.A,
                member_activity_codes=("471",),
            ),
        )
        replacement = retail.model_copy(update={"operaciones_total": Decimal("1250.00")})
        saved = repo.upsert_activity_row(replacement)

        assert saved.activity_rows_for_ejercicio(2024) == (replacement,)
        loaded = repo.load()
        assert loaded.activity_rows_for_ejercicio(2024) == (replacement,)
        assert loaded.entry_for(2024) is not None
        assert loaded.sector_definition_for("retail") is not None


def test_register_secure_object_write_keeps_a_conflicted_batch_atomic(tmp_path: Path) -> None:
    """The prorrata write remains composable in the real secure-object transaction."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a757428a-41a7-4da8-8018-28d3190a434a") as profile:
        repository = ProrrataRegisterRepository()
        write = repository.to_secure_object_write(_populated_register())
        conflicting = write.model_copy(update={"expected_revision_id": ABSENT_SECURE_OBJECT_REVISION_ID})

        with pytest.raises(SecureObjectRevisionConflictError):
            profile.repository.save_many((write, conflicting))

        assert repository.load() == ProrrataRegister()


def test_register_corrupted_percentage_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology: corrupting a persisted percentage must surface at load.

    Persists a populated register, reaches into the encrypted SecureObjectRow,
    rewrites the first entry's ``provisional_percentage`` to a different value,
    and asserts the strict-equality witness flags the drift after reload. If this
    ever passes silently, the register boundary is tautological.
    """
    from sqlalchemy import select

    from ...storage import PROFILE_PRORRATA_REGISTER_NAMESPACE
    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="519ac791-622a-4e61-b3c0-84d953c7cfee") as profile:
        engine = get_engine(profile.settings)
        repo = ProrrataRegisterRepository()
        original = _populated_register()
        repo.save(original)

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == PROFILE_PRORRATA_REGISTER_NAMESPACE.namespace,
            SecureObjectRow.object_key == PROFILE_PRORRATA_REGISTER_NAMESPACE.require_default_object_key(),
        )

        def mutate(document):
            assert document["entries"][0]["provisional_percentage"] == "80"
            document["entries"][0]["provisional_percentage"] = "55"

        mutate_encrypted_secure_object_json(engine, row_statement=stmt, mutate=mutate)

        reloaded = repo.load()
        assert reloaded != original
        assert reloaded.entries[0].provisional_percentage == Decimal("55")


def test_register_missing_regime_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology: a *deleted* required field must raise at load.

    A save-drops-field / load-re-defaults-field regression is invisible to a
    mutation probe — only an absent-field probe catches it. ``regime`` is
    required, so its deletion must raise ``ValidationError``, never silently
    rehydrate an entry with no regime.
    """
    from sqlalchemy import select

    from ...storage import PROFILE_PRORRATA_REGISTER_NAMESPACE
    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="3db70f92-5cec-4355-a65b-62dc53f15ada") as profile:
        engine = get_engine(profile.settings)
        repo = ProrrataRegisterRepository()
        repo.save(_populated_register())

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == PROFILE_PRORRATA_REGISTER_NAMESPACE.namespace,
            SecureObjectRow.object_key == PROFILE_PRORRATA_REGISTER_NAMESPACE.require_default_object_key(),
        )

        def mutate(document):
            assert "regime" in document["entries"][0]
            del document["entries"][0]["regime"]

        mutate_encrypted_secure_object_json(engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(pydantic.ValidationError, match="regime"):
            repo.load()


def test_register_v1_document_refuses_at_encrypted_load(tmp_path: Path) -> None:
    """A v1 durable document is not upgraded or silently re-persisted as v2."""
    from sqlalchemy import select

    from ...storage import PROFILE_PRORRATA_REGISTER_NAMESPACE
    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="91ee6d98-f877-42b0-8e13-c783a6209b37") as profile:
        engine = get_engine(profile.settings)
        repo = ProrrataRegisterRepository()
        repo.save(_populated_register())

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == PROFILE_PRORRATA_REGISTER_NAMESPACE.namespace,
            SecureObjectRow.object_key == PROFILE_PRORRATA_REGISTER_NAMESPACE.require_default_object_key(),
        )

        def mutate(document):
            document["schema_version"] = "1"

        mutate_encrypted_secure_object_json(engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(pydantic.ValidationError, match="unsupported ProrrataRegister schema_version '1'"):
            repo.load()
