"""Declaring, listing and removing Modelo 360 solicitudes through the operation's own action logic.

The registers are held in memory behind the same protocols the worker binds;
every account number is a synthetic published example.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import pydantic
import pytest

from ....core.period import Period
from ....domain.transactions.own_accounts import (
    OwnAccountHolding,
    OwnAccountRegister,
    OwnBankAccountDetails,
)
from ...filing.producer_snapshot_m360 import (
    M360AmbitoEstablecimiento,
    M360CausaPresentacion,
    M360NivelCalidadDatos,
    M360TitularEnCalidadDe,
    Modelo360CuentaTitularFacts,
    Modelo360EstablecimientoFacts,
    Modelo360OwnAccountChoice,
    Modelo360ProfileFacts,
    Modelo360RepresentanteFacts,
    Modelo360SolicitanteFacts,
    Modelo360SolicitudEntry,
    Modelo360SolicitudFacts,
    Modelo360SolicitudRegister,
)
from ..m360_solicitud_operation import (
    Modelo360RepresentanteAccountInput,
    Modelo360SolicitudRefusedError,
    Modelo360SolicitudRequest,
    apply_solicitud_request,
    solicitud_period,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_ES_IBAN = "ES9121000418450200051332"
_DE_IBAN = "DE89370400440532013000"


class _Solicitudes:
    def __init__(self) -> None:
        self.register = Modelo360SolicitudRegister()

    def load(self) -> Modelo360SolicitudRegister:
        return self.register

    def declare(self, entry: Modelo360SolicitudEntry) -> Modelo360SolicitudRegister:
        self.register = self.register.with_entry(entry)
        return self.register

    def remove(self, period: Period) -> Modelo360SolicitudRegister:
        self.register = Modelo360SolicitudRegister(
            entries=tuple(entry for entry in self.register.entries if entry.period != period)
        )
        return self.register


def _own_accounts(*, bic: str = "CAIXESBBXXX", closed: bool = False) -> Callable[[], OwnAccountRegister]:
    register = OwnAccountRegister().with_new_account(
        OwnBankAccountDetails(label="nómina", holding=OwnAccountHolding.TITULAR, iban=_ES_IBAN, swift_bic=bic)
    )
    if closed:
        from datetime import date

        register = register.with_closed_account("acc-01", date(2026, 6, 30))
    return lambda: register


def _facts(holder: M360TitularEnCalidadDe) -> Modelo360ProfileFacts:
    representante = (
        Modelo360RepresentanteFacts(tax_id="00000000T", full_name="ASESORES PRUEBA SL")
        if holder is M360TitularEnCalidadDe.REPRESENTANTE
        else None
    )
    return Modelo360ProfileFacts(
        solicitud=Modelo360SolicitudFacts(
            nivel_calidad_datos=M360NivelCalidadDatos.MAXIMA,
            pais_destino="FR",
            causa_presentacion=M360CausaPresentacion.INICIAL,
        ),
        solicitante=Modelo360SolicitanteFacts(
            email="solicitante@example.es",
            establecimiento=Modelo360EstablecimientoFacts(ambito=M360AmbitoEstablecimiento.TERRITORIO_COMUN),
        ),
        representante=representante,
        cuenta=Modelo360CuentaTitularFacts(titular_nombre="TITULAR PRUEBA", titular_en_calidad_de=holder, divisa="EUR"),
    )


def _declare_own(year: int = 2025) -> Modelo360SolicitudRequest:
    return Modelo360SolicitudRequest(
        profile_id=_PROFILE,
        action="declare",
        filing_year=year,
        facts=_facts(M360TitularEnCalidadDe.SOLICITANTE),
        own_account_id="acc-01",
    )


def test_a_solicitante_solicitud_references_its_own_account_and_lists_masked() -> None:
    solicitudes = _Solicitudes()

    declared = apply_solicitud_request(_declare_own(), repository=solicitudes, own_accounts=_own_accounts())

    assert declared.changed is True
    entry = solicitudes.register.entry_for(solicitud_period(2025))
    assert entry is not None
    assert entry.account == Modelo360OwnAccountChoice(own_account_id="acc-01")
    (row,) = declared.solicitudes
    assert (row.filing_year, row.account_kind, row.own_account_id, row.masked_iban) == (
        2025,
        "own_account",
        "acc-01",
        None,
    )
    listed = apply_solicitud_request(
        Modelo360SolicitudRequest(profile_id=_PROFILE, action="list"),
        repository=solicitudes,
        own_accounts=_own_accounts(),
    )
    assert listed.solicitudes == declared.solicitudes
    assert listed.changed is False
    again = apply_solicitud_request(_declare_own(), repository=solicitudes, own_accounts=_own_accounts())
    assert again.changed is False


def test_a_representante_account_is_embedded_and_shown_only_by_its_mask() -> None:
    solicitudes = _Solicitudes()
    request = Modelo360SolicitudRequest(
        profile_id=_PROFILE,
        action="declare",
        filing_year=2025,
        facts=_facts(M360TitularEnCalidadDe.REPRESENTANTE),
        representante_account=Modelo360RepresentanteAccountInput(iban=_DE_IBAN, swift_bic="COBADEFFXXX"),
    )

    result = apply_solicitud_request(request, repository=solicitudes, own_accounts=_own_accounts())

    (row,) = result.solicitudes
    assert (row.account_kind, row.masked_iban, row.has_representante) == ("representante", "DE ···· 3000", True)
    assert _DE_IBAN not in result.model_dump_json()
    assert "ASESORES" not in result.model_dump_json()


@pytest.mark.parametrize(
    ("own_accounts", "reason"),
    [
        (_own_accounts(bic=""), "account_bic_missing"),
        (_own_accounts(closed=True), "account_closed"),
        (lambda: OwnAccountRegister(), "account_unknown"),
    ],
)
def test_a_solicitante_account_must_be_open_registered_and_carry_its_bic(
    own_accounts: Callable[[], OwnAccountRegister], reason: str
) -> None:
    solicitudes = _Solicitudes()

    with pytest.raises(Modelo360SolicitudRefusedError) as raised:
        apply_solicitud_request(_declare_own(), repository=solicitudes, own_accounts=own_accounts)

    assert raised.value.translated_message == f"errors.refused.refused_modelo_360_solicitud_{reason}"
    assert solicitudes.register == Modelo360SolicitudRegister()


def test_facts_that_name_the_other_holder_and_an_invalid_account_are_refused() -> None:
    solicitudes = _Solicitudes()
    mismatched = Modelo360SolicitudRequest(
        profile_id=_PROFILE,
        action="declare",
        filing_year=2025,
        facts=_facts(M360TitularEnCalidadDe.REPRESENTANTE),
        own_account_id="acc-01",
    )
    with pytest.raises(Modelo360SolicitudRefusedError) as holder:
        apply_solicitud_request(mismatched, repository=solicitudes, own_accounts=_own_accounts())
    assert holder.value.translated_message == "errors.refused.refused_modelo_360_solicitud_holder_mismatch"

    broken = Modelo360SolicitudRequest(
        profile_id=_PROFILE,
        action="declare",
        filing_year=2025,
        facts=_facts(M360TitularEnCalidadDe.REPRESENTANTE),
        representante_account=Modelo360RepresentanteAccountInput(iban=_DE_IBAN[:-1] + "1", swift_bic="COBADEFFXXX"),
    )
    with pytest.raises(Modelo360SolicitudRefusedError) as invalid:
        apply_solicitud_request(broken, repository=solicitudes, own_accounts=_own_accounts())
    assert invalid.value.translated_message == "errors.refused.refused_modelo_360_solicitud_account_invalid"
    assert solicitudes.register == Modelo360SolicitudRegister()


def test_removal_drops_only_its_year_and_refuses_an_undeclared_one() -> None:
    solicitudes = _Solicitudes()
    for year in (2024, 2025):
        apply_solicitud_request(_declare_own(year), repository=solicitudes, own_accounts=_own_accounts())

    removed = apply_solicitud_request(
        Modelo360SolicitudRequest(profile_id=_PROFILE, action="remove", filing_year=2024),
        repository=solicitudes,
        own_accounts=_own_accounts(),
    )

    assert removed.changed is True
    assert [row.filing_year for row in removed.solicitudes] == [2025]
    with pytest.raises(Modelo360SolicitudRefusedError) as raised:
        apply_solicitud_request(
            Modelo360SolicitudRequest(profile_id=_PROFILE, action="remove", filing_year=2024),
            repository=solicitudes,
            own_accounts=_own_accounts(),
        )
    assert raised.value.translated_message == "errors.refused.refused_modelo_360_solicitud_undeclared"


def test_the_request_takes_exactly_the_fields_its_action_needs() -> None:
    with pytest.raises(pydantic.ValidationError):
        Modelo360SolicitudRequest(profile_id=_PROFILE, action="list", filing_year=2025)
    with pytest.raises(pydantic.ValidationError):
        Modelo360SolicitudRequest(
            profile_id=_PROFILE,
            action="declare",
            filing_year=2025,
            facts=_facts(M360TitularEnCalidadDe.SOLICITANTE),
            own_account_id="acc-01",
            representante_account=Modelo360RepresentanteAccountInput(iban=_DE_IBAN, swift_bic="COBADEFFXXX"),
        )
    with pytest.raises(pydantic.ValidationError):
        Modelo360SolicitudRequest(profile_id=_PROFILE, action="remove")


@pytest.mark.parametrize("year", [1999, 2100])
def test_a_solicitud_cannot_select_a_year_outside_the_shared_filing_window(year: int) -> None:
    """The request cannot accept a year that its persisted period refuses."""
    with pytest.raises(pydantic.ValidationError):
        Modelo360SolicitudRequest(profile_id=_PROFILE, action="remove", filing_year=year)
