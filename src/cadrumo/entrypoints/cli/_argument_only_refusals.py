"""Refusals decidable from parsed arguments alone, evaluated before state gates.

A refusal that depends only on what the operator typed must be raised before one
that depends on profile or storage state. Otherwise the operator is sent to fix
the environment for a request the application was never going to accept.

The concrete case: ``modelo work create --modelo 650`` names a modelo this
application does not implement -- ISD is ceded to the autonomous communities and
filed through their own surfaces. ``guard_unsupported_work_modelo`` refuses it
with the governing legal reference, but that guard lives INSIDE the handler,
while ``modelo.work.create`` declares ``write_route = "profile-bound"``. The
profile-bound write gate in :mod:`._profile_session_gate` therefore refuses
first with ``profile.active``, telling the operator to create a profile -- after
which the modelo is refused anyway. The instructive refusal loses to the generic
one purely on gate ordering.

Nothing here duplicates the policy it enforces: the stub-only decision and its
locale key both come from
:func:`~cadrumo.application.modelo.modelo_work_create_refusal_locale_key`, the
same authority the in-handler guard consults. The in-handler guard stays --- it
is the one that fires once a profile IS active, and it is reached through paths
that do not pass this gate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .command_spec import CommandSpec

#: Schema identity of the verb whose modelo argument is decidable on its own.
_WORK_CREATE_IDENTITY = "modelo.work.create"

#: Parameter carrying the requested modelo code on that verb.
_MODELO_PARAMETER = "modelo"

#: Parameter carrying the causante's CCAA on that verb. Parsed before the
#: stub-only check because a foral territory is the MORE SPECIFIC refusal: País
#: Vasco and Navarra levy under their own concierto/convenio, so naming that is
#: better guidance than the generic "file with your regional Hacienda". The
#: handler already establishes this precedence by parsing the region first, and
#: this seam preserves it rather than inverting it.
_CAUSANTE_CCAA_PARAMETER = "causante_ccaa_raw"


def refuse_on_arguments_alone(spec: CommandSpec, arguments: Mapping[str, object]) -> None:
    """Raise the argument-only refusal for this invocation, if one applies.

    Args:
        spec: The resolved command spec being dispatched.
        arguments: The parsed arguments for this invocation.

    Raises:
        CliRefusedBoundaryError: When the arguments alone settle the refusal.
    """
    from ...application.modelo.work_create_policy import modelo_work_create_refusal_locale_key
    from .errors import CliRefusedBoundaryError

    if (spec.result_schema.identity or spec.key) != _WORK_CREATE_IDENTITY:
        return
    causante_ccaa = arguments.get(_CAUSANTE_CCAA_PARAMETER)
    if isinstance(causante_ccaa, str):
        from ...domain.contribuyente.tax_residence import parse_tax_region

        # Raises for a foral territory, which is the more specific refusal.
        parse_tax_region(causante_ccaa)
    requested = arguments.get(_MODELO_PARAMETER)
    if not isinstance(requested, str):
        return
    modelo_code = requested.strip()
    locale_key = modelo_work_create_refusal_locale_key(modelo_code)
    if locale_key is None:
        return
    raise CliRefusedBoundaryError(translated_message=locale_key, context={"modelo": modelo_code})


__all__ = ["refuse_on_arguments_alone"]
