"""Encrypted roundtrip, guarded mutation and profile scope of the modelo 360 solicitud register.

Persists :class:`Modelo360SolicitudRegister` under
``cadrumo.persistence.profile.modelo_360_solicitud`` at ``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture fills every optional field, a representante included, and the
refund account carries a non-SEPA bank block. A probe rewrites the persisted IBAN to another
checksum-valid one and checks the reload differs; another breaks its check digits and checks
the load refuses rather than accepting an account no bank would pay into. All data is
synthetic.
"""

from __future__ import annotations

from pathlib import Path

import pydantic
import pytest
from sqlalchemy import select

from .....application.filing.producer_snapshot_m360 import (
    M360AmbitoEstablecimiento,
    M360CausaPresentacion,
    M360HaciendaForal,
    M360NivelCalidadDatos,
    M360TitularEnCalidadDe,
    Modelo360CuentaTitularFacts,
    Modelo360DomicilioEspana,
    Modelo360EstablecimientoFacts,
    Modelo360ProfileFacts,
    Modelo360RepresentanteFacts,
    Modelo360SolicitanteFacts,
    Modelo360SolicitudEntry,
    Modelo360SolicitudFacts,
    Modelo360SolicitudRegister,
)
from .....core.period import Period
from .....domain.deadlines.models import RefundAccount
from ...storage.secure_object_namespaces import PROFILE_MODELO_360_SOLICITUD_NAMESPACE
from ...storage.sql.engine import get_engine
from ...storage.sql.orm import SecureObjectRow
from ...storage.tests.secure_sql import (
    isolated_runtime_profile,
    isolated_two_bucket_runtime,
    mutate_encrypted_secure_object_json,
)
from ..modelo_360_solicitud import Modelo360SolicitudRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PERIOD_2025 = Period.from_year_and_code(2025, "AD-HOC")
_PERIOD_2024 = Period.from_year_and_code(2024, "AD-HOC")
#: Synthetic, checksum-valid IBANs: the ISO 13616 published example and a German sibling.
_IBAN = "ES9121000418450200051332"
_OTHER_VALID_IBAN = "DE89370400440532013000"


def _facts(*, pais_destino: str = "FR") -> Modelo360ProfileFacts:
    return Modelo360ProfileFacts(
        solicitud=Modelo360SolicitudFacts(
            nivel_calidad_datos=M360NivelCalidadDatos.MAXIMA,
            pais_destino=pais_destino,
            causa_presentacion=M360CausaPresentacion.MODIFICACION,
            numero_registro_declaracion_anterior="3600000000001ABC",
            comunicacion_prorrata_definitiva=False,
            presentacion_en_pruebas=True,
        ),
        solicitante=Modelo360SolicitanteFacts(
            email="solicitante@example.es",
            phone="948000000",
            establecimiento=Modelo360EstablecimientoFacts(
                ambito=M360AmbitoEstablecimiento.HACIENDA_FORAL,
                hacienda_foral=M360HaciendaForal.NAVARRA,
            ),
            domicilio=Modelo360DomicilioEspana(nombre_via="MAYOR", codigo_postal="31001", provincia="31"),
        ),
        representante=Modelo360RepresentanteFacts(
            tax_id="00000000T",
            full_name="ASESORES PRUEBA SL",
            email="representante@example.es",
        ),
        cuenta=Modelo360CuentaTitularFacts(
            titular_nombre="ASESORES PRUEBA SL",
            titular_en_calidad_de=M360TitularEnCalidadDe.REPRESENTANTE,
            divisa="EUR",
        ),
    )


def _account() -> RefundAccount:
    return RefundAccount(
        iban=_IBAN,
        swift_bic="CAIXESBBXXX",
        bank_name="BANCO PRUEBA",
        bank_address="CALLE FALSA 1",
        bank_city="PAMPLONA",
        bank_country_code="ES",
    )


def _entry(period: Period = _PERIOD_2025, *, refund_account: RefundAccount | None = None) -> Modelo360SolicitudEntry:
    return Modelo360SolicitudEntry(period=period, facts=_facts(), refund_account=refund_account or _account())


def _register_row():
    return select(SecureObjectRow).where(
        SecureObjectRow.namespace == PROFILE_MODELO_360_SOLICITUD_NAMESPACE.namespace,
        SecureObjectRow.object_key == PROFILE_MODELO_360_SOLICITUD_NAMESPACE.require_default_object_key(),
    )


def test_an_absent_register_loads_empty_and_names_no_period(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1a2b3c4d-5e6f-4a70-8b81-360000000001"):
        register = Modelo360SolicitudRepository().load()

    assert register == Modelo360SolicitudRegister()
    assert register.entry_for(_PERIOD_2025) is None


def test_the_register_survives_encrypted_storage_field_for_field(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1a2b3c4d-5e6f-4a70-8b81-360000000002"):
        repository = Modelo360SolicitudRepository()
        repository.declare(_entry(_PERIOD_2025))
        written = repository.declare(_entry(_PERIOD_2024))

        loaded = Modelo360SolicitudRepository().load()

    assert loaded == written
    assert loaded.entries == (_entry(_PERIOD_2024), _entry(_PERIOD_2025))
    entry = loaded.entry_for(_PERIOD_2025)
    assert entry is not None
    assert entry.refund_account == _account()
    assert entry.facts.representante is not None
    assert entry.facts.representante.full_name == "ASESORES PRUEBA SL"


def test_an_entry_without_an_account_stays_undeclared_rather_than_empty(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1a2b3c4d-5e6f-4a70-8b81-360000000003"):
        repository = Modelo360SolicitudRepository()
        repository.declare(Modelo360SolicitudEntry(period=_PERIOD_2025, facts=_facts()))

        entry = Modelo360SolicitudRepository().load().entry_for(_PERIOD_2025)

    assert entry is not None
    assert entry.refund_account is None


def test_redeclaring_a_period_replaces_its_entry_and_keeps_the_others(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1a2b3c4d-5e6f-4a70-8b81-360000000004"):
        repository = Modelo360SolicitudRepository()
        repository.declare(_entry(_PERIOD_2024))
        repository.declare(_entry(_PERIOD_2025))
        corrected = Modelo360SolicitudEntry(
            period=_PERIOD_2025,
            facts=_facts(pais_destino="IT"),
            refund_account=_account(),
        )
        repository.declare(corrected)

        loaded = repository.load()

    assert loaded.entries == (_entry(_PERIOD_2024), corrected)


def test_a_register_with_two_entries_for_one_period_is_refused() -> None:
    with pytest.raises(pydantic.ValidationError, match="two entries for one period"):
        Modelo360SolicitudRegister(entries=(_entry(_PERIOD_2025), _entry(_PERIOD_2025)))


def test_a_rewritten_iban_surfaces_on_reload(tmp_path: Path) -> None:
    bucket_id = "1a2b3c4d-5e6f-4a70-8b81-360000000005"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repository = Modelo360SolicitudRepository()
        written = repository.declare(_entry())

        def mutate(document):
            assert document["entries"][0]["refund_account"]["iban"] == _IBAN
            document["entries"][0]["refund_account"]["iban"] = _OTHER_VALID_IBAN

        mutate_encrypted_secure_object_json(get_engine(profile.settings), row_statement=_register_row(), mutate=mutate)

        reloaded = repository.load()

    assert reloaded != written
    entry = reloaded.entry_for(_PERIOD_2025)
    assert entry is not None
    assert entry.refund_account is not None
    assert entry.refund_account.iban == _OTHER_VALID_IBAN


def test_a_persisted_iban_with_broken_check_digits_refuses_the_load(tmp_path: Path) -> None:
    bucket_id = "1a2b3c4d-5e6f-4a70-8b81-360000000006"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repository = Modelo360SolicitudRepository()
        repository.declare(_entry())

        def mutate(document):
            document["entries"][0]["refund_account"]["iban"] = "ES0021000418450200051332"

        mutate_encrypted_secure_object_json(get_engine(profile.settings), row_statement=_register_row(), mutate=mutate)

        with pytest.raises(pydantic.ValidationError):
            repository.load()


def test_one_profile_never_reads_another_profiles_solicitud(tmp_path: Path) -> None:
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        Modelo360SolicitudRepository(objects=runtime.primary.repository).declare(_entry())
        with runtime.switch_to_secondary():
            secondary = Modelo360SolicitudRepository(objects=runtime.secondary.repository)
            assert secondary.load() == Modelo360SolicitudRegister()
            secondary.declare(_entry(refund_account=RefundAccount(iban=_OTHER_VALID_IBAN, swift_bic="DEUTDEFFXXX")))
        primary = Modelo360SolicitudRepository(objects=runtime.primary.repository).load()

    assert primary.entry_for(_PERIOD_2025) == _entry()
