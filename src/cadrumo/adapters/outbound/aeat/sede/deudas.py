"""Read-only boundary records for AEAT's *Consultar deudas* surface.

AEAT's recaudación surface exposes a debts consultation listing one row per
outstanding liability: its clave de liquidación, the objeto tributario naming
which legal object the debt is, the importe pendiente, the período, and the
situación describing where the debt sits procedurally. :class:`Deuda` is that
row, typed at the adapter boundary.

The surface is READ-ONLY and stays that way by construction. Viewing debts and
paying them are distinct AEAT trámites behind different apoderamiento codes,
but the payment controls — *pagar todas mis deudas*, *pagar algunas deudas*,
*pago parcial*, and the aplazamiento/fraccionamiento request — sit one control
away from the listing this module reads. This application never files, pays,
notifies or mutates remotely, so :func:`assert_deudas_landing` is the runtime
wall that refuses the moment AEAT dispatches the session anywhere but a
declared read page.

Nothing this module produces is a calculation input. An AEAT-imposed liability
is downstream of the taxpayer's tax position for a period rather than part of
it, so no binding source kind, aggregation channel, relation or casilla
resolution consumes a :class:`Deuda`. Displaying AEAT's own reported figures
asserts nothing under a legal provision, which is why the register needs no
grounded oracle; the moment it *interprets* a figure — a surcharge percentage
band, an aplazamiento rate — that interpretation needs its establishing
provision in the legal catalogue first.

See Also:
    :class:`~core.ObjetoTributario`
        Which LGT object a reported deuda is.
    :class:`~core.Period`
        The filing period a deuda is attributed to.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core import DeudaDireccion, ObjetoTributario, Period
from .....core.config import Settings
from .....core.identity import AeatClaveLiquidacion
from .....domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy
from ._adapter_utils import assert_read_landing

__all__ = [
    "DEUDAS_READ_SURFACE",
    "Deuda",
    "assert_deudas_landing",
    "deudas_read_path_prefixes",
]

_EXTERNAL = Settings.external_constants()
# Built on the UNNUMBERED origin, matching the IVA compensation wallet reader.
# ``www{n}`` is a per-SESSION variable: AEAT load-balances the authenticated
# surface across its numbered pool and assigns whichever host answers a given
# session, so a captured number describes one session and not the surface. The
# live capture that grounded this module landed on ``www6``; naming that here
# would encode a coincidence of that session as though it were the route.
#
# Numbered dispatch is admitted by ``allowed_host_suffixes`` below, which is the
# field that actually carries the load-balancer case.
_SEDE_HOST: Final = urlsplit(_EXTERNAL.aeat.domains.sede).netloc
_AEAT_HOST_SUFFIX: Final = _EXTERNAL.aeat.domains.host_suffix

DEUDAS_READ_SURFACE: Final = "deudas consulta"
"""Surface label a deudas landing refusal names, so a refusal says who refused."""

_DEUDAS_CONSULTA_PATH: Final = _EXTERNAL.aeat.sede_paths.deudas_consulta
_DEUDAS_PAGAR_TODAS_PATH: Final = _EXTERNAL.aeat.sede_paths.deudas_pagar_todas


class Deuda(BaseModel):
    """One row from AEAT's *Consultar deudas* listing.

    The row is external AEAT state read as reported, never a filed-declaration
    casilla and never an input to one.

    Attributes:
        clave_liquidacion: AEAT's identifier for the liquidación the debt
            arises from, as printed on the listing row.
        objeto_tributario: Which LGT object this debt is.
        importe_pendiente: The outstanding amount, a NON-NEGATIVE magnitude.
            Flow direction is carried solely by :attr:`direccion`; a sign here
            would let the two disagree with nothing establishing which a
            reader should trust.
        direccion: Whether the taxpayer owes this amount or AEAT owes it back.
        periodo: The filing period the debt is attributed to, or ``None`` when
            the listing attributes the debt to no single period.
        situacion: AEAT's procedural-state label, carried as the free-text
            string AEAT printed. It is deliberately not a closed enum: this
            application does not control the label vocabulary and cannot
            enumerate it, so the honest shape is the bounded string, the same
            shape the declarations register's own ``estado`` label ships.
        mode: Structural read-only marker. A record that cannot be anything
            but ``"read"`` cannot be repurposed to drive an AEAT mutation.
    """

    model_config = _STRICT_FROZEN

    clave_liquidacion: AeatClaveLiquidacion
    objeto_tributario: ObjetoTributario
    importe_pendiente: Decimal = Field(ge=Decimal("0"))
    direccion: DeudaDireccion
    periodo: Period | None = None
    situacion: str = Field(min_length=1, max_length=64)
    mode: Literal["read"] = "read"

    @field_validator("clave_liquidacion", "situacion")
    @classmethod
    def _reject_blank_labels(cls, value: str) -> str:
        """Refuse a whitespace-only identifier or state label.

        A ``min_length`` bound alone admits ``"   "``, which is what an empty
        listing cell parses to. Accepting it would record a row whose identity
        and procedural state are both unknown as though AEAT had reported
        them, so the boundary refuses rather than storing a blank that later
        reads as real.

        ``clave_liquidacion`` keeps its place here after being retyped onto
        :data:`~core.identity.AeatClaveLiquidacion`: that alias carries the
        length bound, which is exactly the bound this validator exists to
        supplement, so dropping the field from this list on the grounds that
        it is "now typed" would silently re-admit the blank.
        """
        if not value.strip():
            raise ValueError("must not be blank")
        return value


# The debts consulta is an AUTHENTICATED read surface, so the policy pins the
# AEAT apex the same way the adjacent authenticated readers do: AEAT
# load-balances across its numbered pool and assigns the host per session, so
# pinning one number would refuse a legitimate dispatch.
#
# ``allowed_browser_action_patterns`` is deliberately EMPTY. No control on this
# surface may be driven — every payment and aplazamiento action is a control,
# so any browser action added here fails the guard until it is declared, which
# is the refusal we want rather than a gap.
#
# ``allowed_read_post_paths`` carries the consulta and nothing else. The debts
# consulta is a TWO-STEP surface: the endpoint renders a NIF form, and the
# listing exists only behind that form's submission, so the read genuinely needs
# a POST. That is a query, not a mutation — it retrieves and changes nothing —
# and it is the same shape the IVA compensation wallet reader already declares.
# The guard admits a POST only for an ``authenticated_read_surface`` at a path
# named here, so this stays one endpoint rather than a method-wide relaxation.
_READ_GUARD_POLICY: Final = RemoteStateGuardPolicy(
    id="aeat-sede-deudas-consulta-read",
    evidence_tier="official_source_guidance",
    classification="authenticated_read_surface",
    allowed_hosts=(_SEDE_HOST,),
    allowed_host_suffixes=(_AEAT_HOST_SUFFIX,),
    allowed_read_post_paths=(_DEUDAS_CONSULTA_PATH,),
    allowed_browser_action_patterns=(),
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
)

# Populated from an authenticated capture of the live consulta, which landed on
# this exact path with no redirect. It replaces the empty tuple this guard
# shipped with while no specimen existed.
#
# THE ENTRY IS THE ENDPOINT, NOT ITS APPLICATION PREFIX, and that distinction is
# the whole finding. AEAT serves *pagar todas mis deudas* from
# ``/wlpl/SRVO-JDIT/PagarTodas`` — the SAME ``/wlpl/SRVO-JDIT/`` application as
# the consulta. Allow-listing that shared prefix, the obvious shape to reach for,
# would admit the payment launcher into a read guard whose entire purpose is
# keeping it out. The two are siblings in AEAT's routing and only their endpoint
# segment separates them, so only the endpoint may be declared.
#
# The payment flow must never appear here under any future edit. A prefix
# admitting a "pagar" path, an aplazamiento request or any procedure launcher
# would put a taxpayer's money one navigation from a read.
_DEUDAS_READ_PATH_PREFIXES: tuple[str, ...] = (_DEUDAS_CONSULTA_PATH,)


def deudas_read_path_prefixes() -> tuple[str, ...]:
    """Return the path prefixes the deudas reader may land on.

    Exposed so conformance gates exercise the real tuple rather than a
    mirrored copy that would keep passing if this one changed shape.

    Returns:
        The declared read-page prefixes. Empty means every landing is
        refused.
    """
    return _DEUDAS_READ_PATH_PREFIXES


def assert_deudas_landing(landing_url: str | None) -> None:
    """Refuse a landing that is not a declared deudas read page.

    Delegates to the shared :func:`assert_read_landing` allow-list wall rather
    than restating it: that function already fails closed at every step — an
    unreadable origin is refused, an off-policy landing is refused, a surface
    declaring no read pages refuses everything, and a landing outside the
    declared pages is refused. A second copy of that logic here would be a
    duplicate authority that could drift from the one every sibling reader is
    audited against.

    The prefix tuple now carries the observed consulta endpoint, so a landing on
    that endpoint is admitted and everything else — including the payment
    launcher sharing its application prefix — is still refused.

    Args:
        landing_url: The URL AEAT actually served, after redirects — read off
            the page, never the URL that was requested.

    Raises:
        SedeNavigationError: When the landing is unreadable, off-policy, or
            outside the declared read pages.
    """
    assert_read_landing(
        landing_url,
        surface=DEUDAS_READ_SURFACE,
        policy=_READ_GUARD_POLICY,
        allowed_path_prefixes=_DEUDAS_READ_PATH_PREFIXES,
    )
