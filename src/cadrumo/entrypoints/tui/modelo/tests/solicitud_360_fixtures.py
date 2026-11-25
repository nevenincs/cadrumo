"""An in-memory Modelo 360 solicitud door over the application's own action logic.

Each request is applied with ``apply_solicitud_request`` against registers held
in memory behind the protocols the worker binds, so screens are driven by the
same admission, refusals and masked projection the registered operation
publishes. Every account number and person is synthetic.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from .....application.filing.producer_snapshot_m360 import (
    M360AmbitoEstablecimiento,
    M360CausaPresentacion,
    M360NivelCalidadDatos,
    M360TitularEnCalidadDe,
    Modelo360CuentaTitularFacts,
    Modelo360EstablecimientoFacts,
    Modelo360ProfileFacts,
    Modelo360RepresentanteFacts,
    Modelo360SolicitanteFacts,
    Modelo360SolicitudEntry,
    Modelo360SolicitudFacts,
    Modelo360SolicitudRegister,
)
from .....application.modelo.m360_solicitud_input import Modelo360ProfileInput
from .....application.modelo.m360_solicitud_operation import (
    Modelo360SolicitudRequest,
    Modelo360SolicitudResult,
    apply_solicitud_request,
)
from .....core.external_constants import UTF_8_ENCODING
from .....core.i18n.render import tr
from .....core.period import Period
from .....domain.transactions.own_accounts import OwnAccountHolding, OwnAccountRegister, OwnBankAccountDetails

SOLICITUD_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
SYNTHETIC_OWN_IBAN = "ES9121000418450200051332"
SYNTHETIC_REPRESENTANTE_IBAN = "DE89370400440532013000"


def synthetic_facts_json(holder: M360TitularEnCalidadDe) -> str:
    """Synthetic solicitud facts as the command line's document carries them."""
    representante = (
        Modelo360RepresentanteFacts(tax_id="00000000T", full_name="ASESORES PRUEBA SL")
        if holder is M360TitularEnCalidadDe.REPRESENTANTE
        else None
    )
    facts = Modelo360ProfileFacts(
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
    return Modelo360ProfileInput.model_validate(facts.model_dump()).model_dump_json()


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


class MemorySolicitudDoor:
    """Apply requests through the application's own action logic over in-memory registers."""

    def __init__(self, *, own_account_bic: str = "CAIXESBBXXX") -> None:
        """Hold one open own account, ``acc-01``, and an empty solicitud register."""
        self.solicitudes = _Solicitudes()
        self.own_accounts = OwnAccountRegister().with_new_account(
            OwnBankAccountDetails(
                label="nómina", holding=OwnAccountHolding.TITULAR, iban=SYNTHETIC_OWN_IBAN, swift_bic=own_account_bic
            )
        )
        self.requests: list[Modelo360SolicitudRequest] = []

    @property
    def profile_id(self) -> UUID:
        """The synthetic profile every request names."""
        return SOLICITUD_PROFILE_ID

    async def __call__(self, request: Modelo360SolicitudRequest) -> Modelo360SolicitudResult:
        """Record and apply one request."""
        self.requests.append(request)
        return apply_solicitud_request(request, repository=self.solicitudes, own_accounts=lambda: self.own_accounts)

    async def read_facts(self, path: str) -> Modelo360ProfileInput:
        """Validate a facts file as the runtime door does, never echoing its content."""
        try:
            return Modelo360ProfileInput.model_validate_json(Path(path).read_text(encoding=UTF_8_ENCODING))
        except OSError:
            raise ValueError(tr("tui.modelo.m360_solicitud.source_unreadable", path=path)) from None
        except ValidationError as error:
            raise ValueError(
                tr("tui.modelo.m360_solicitud.source_invalid", path=path, count=error.error_count())
            ) from None
