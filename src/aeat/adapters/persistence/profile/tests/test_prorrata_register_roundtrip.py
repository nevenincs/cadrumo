"""Strict roundtrip across the cross-period IVA prorrata register repo.

Persists :class:`ProrrataRegister` under
``aeat.persistence.profile.prorrata_register`` at ``SensitivityClass.FINANCIAL``.

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
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from .....core.external_constants import UTF_8_ENCODING
from .....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry, SectorDefinition
from .....tests.secure_sql import isolated_runtime_profile
from ....persistence.storage.sql.engine import get_engine
from ..prorrata_register import ProrrataRegisterRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _populated_register() -> ProrrataRegister:
    carried_settled = ProrrataRegisterEntry(
        ejercicio=2024,
        regime=ProrrataRegisterRegime.GENERAL,
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
    )
    interrupted = ProrrataRegisterEntry(
        ejercicio=2023,
        regime=ProrrataRegisterRegime.NINGUNA,
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


def test_register_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """ProrrataRegister roundtrips through encrypted SQL, field-for-field."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="prorrata-rt-survives"):
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
        assert loaded.is_sectorized is True
        assert loaded.sector_definition_for("arrendamiento").letra is SectorDiferenciadoLetra.A
        assert loaded.sector_definition_for("arrendamiento").member_activity_codes == ("6820",)
        # The art. 105.Cinco interrupted (sin operaciones) marker crosses the
        # encrypted boundary: an inactive ejercicio carries no percentage/volume.
        interrupted = loaded.entry_for(2023)
        assert interrupted is not None
        assert interrupted.interrupted is True
        assert interrupted.provisional_percentage is None
        assert interrupted.definitive_percentage is None


def test_register_upsert_replaces_entry_by_key(tmp_path: Path) -> None:
    """Declaring an entry for an existing (ejercicio, sector) key replaces it in place."""
    from ..prorrata_register import declare_prorrata_entry

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="prorrata-rt-upsert"):
        first = ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
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


def test_register_corrupted_percentage_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology: corrupting a persisted percentage must surface at load.

    Persists a populated register, reaches into the encrypted SecureObjectRow,
    rewrites the first entry's ``provisional_percentage`` to a different value,
    and asserts the strict-equality witness flags the drift after reload. If this
    ever passes silently, the register boundary is tautological.
    """
    import json as _json

    from sqlalchemy import select

    from ....persistence.storage.sql.session import session_scope
    from ...storage.crypto import (
        decrypt_secure_object_payload,
        encrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ...storage.sql import SecureObjectRow
    from ..prorrata_register import _REGISTER_NAMESPACE, _REGISTER_OBJECT_KEY

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="prorrata-rt-corrupt") as profile:
        engine = get_engine(profile.settings)
        repo = ProrrataRegisterRepository()
        original = _populated_register()
        repo.save(original)

        with session_scope(engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == _REGISTER_NAMESPACE,
                SecureObjectRow.object_key == _REGISTER_OBJECT_KEY,
            )
            row = session.execute(stmt).scalar_one()
            aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            plain = decrypt_secure_object_payload(bytes(row.payload), associated_data=aad)
            document = _json.loads(plain.decode(UTF_8_ENCODING))
            assert document["entries"][0]["provisional_percentage"] == "80"
            document["entries"][0]["provisional_percentage"] = "55"
            row.payload = encrypt_secure_object_payload(
                _json.dumps(document).encode(UTF_8_ENCODING), associated_data=aad
            )

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
    import json as _json

    from sqlalchemy import select

    from ....persistence.storage.sql.session import session_scope
    from ...storage.crypto import (
        decrypt_secure_object_payload,
        encrypt_secure_object_payload,
        secure_object_payload_aad,
    )
    from ...storage.sql import SecureObjectRow
    from ..prorrata_register import _REGISTER_NAMESPACE, _REGISTER_OBJECT_KEY

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="prorrata-rt-missing") as profile:
        engine = get_engine(profile.settings)
        repo = ProrrataRegisterRepository()
        repo.save(_populated_register())

        with session_scope(engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == _REGISTER_NAMESPACE,
                SecureObjectRow.object_key == _REGISTER_OBJECT_KEY,
            )
            row = session.execute(stmt).scalar_one()
            aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
            plain = decrypt_secure_object_payload(bytes(row.payload), associated_data=aad)
            document = _json.loads(plain.decode(UTF_8_ENCODING))
            assert "regime" in document["entries"][0]
            del document["entries"][0]["regime"]
            row.payload = encrypt_secure_object_payload(
                _json.dumps(document).encode(UTF_8_ENCODING), associated_data=aad
            )

        with pytest.raises(pydantic.ValidationError, match="regime"):
            repo.load()
