"""Refusals decidable from parsed arguments alone, evaluated before state gates.

A refusal that depends only on what the operator typed must be raised before one
that depends on profile or storage state. Otherwise the operator is sent to fix
the environment for a request the application was never going to accept.

The concrete case: ``modelo work create --modelo 650`` names a modelo this
application does not implement -- ISD is ceded to the autonomous communities and
filed through their own surfaces. ``guard_unsupported_work_modelo`` refuses it
with the governing legal reference, but that guard lives INSIDE the handler,
while ``modelo.work.create`` declares ``write_route = "profile-bound"``. The
profile-bound write gate in :mod:`.profile_session_gate` therefore refuses
first with ``profile.active``, telling the operator to create a profile -- after
which the modelo is refused anyway. The instructive refusal loses to the generic
one purely on gate ordering.

Nothing here duplicates the policy it enforces: the stub-only decision and its
locale key both come from
:func:`~cadrumo.application.modelo.work_create_policy.modelo_work_create_refusal_locale_key`, the
same authority the in-handler guard consults. The in-handler guard stays --- it
is the one that fires once a profile IS active, and it is reached through paths
that do not pass this gate.

The same seam keeps a calculate option on the modelo that declares it. The
Modelo 303 filing-evidence options (the joint-return election and the Modelo 390
attestation pair) have no meaning on another modelo's calculation; refusing them
here, and again once the handler has read the work unit's own modelo, ends the
command before any calculation is submitted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cadrumo_client.commands.spec import CommandSpec

#: Schema identity of the verb whose modelo argument is decidable on its own.
_WORK_CREATE_IDENTITY = "modelo.work.create"

#: Schema identity of the calculation verb that carries modelo-specific options.
_WORK_CALCULATE_IDENTITY = "modelo.work.calculate"

#: Locale key of the refusal for a filing-evidence option supplied to another modelo.
_FILING_EVIDENCE_OPTION_SCOPE_LOCALE_KEY = "cli.app.modelo.work.filing_evidence_option_other_modelo"

#: Parameter carrying the requested modelo code on that verb.
_MODELO_PARAMETER = "modelo"

#: Parameter carrying the causante's CCAA on that verb. Parsed before the
#: stub-only check because a foral territory is the MORE SPECIFIC refusal: País
#: Vasco and Navarra levy under their own concierto/convenio, so naming that is
#: better guidance than the generic "file with your regional Hacienda". The
#: handler already establishes this precedence by parsing the region first, and
#: this seam preserves it rather than inverting it.
_CAUSANTE_CCAA_PARAMETER = "causante_ccaa_raw"


def refuse_filing_evidence_options_for_other_modelo(modelo: str, arguments: Mapping[str, object]) -> None:
    """Refuse the Modelo 303 filing-evidence options on a calculation of any other modelo.

    The option names are the fields of the evidence request the calculation
    carries, and the modelo they belong to is the one that evidence's owner
    admits it for, so neither is restated here. A supplied option is one the
    operator typed: an unsupplied option is ``None``.

    Args:
        modelo: The modelo the calculation targets.
        arguments: The parsed arguments for this invocation.

    Raises:
        CliRefusedBoundaryError: When an option is supplied for another modelo.
    """
    from cadrumo_client.commands.errors import CliRefusedBoundaryError

    from ...application.modelo.m303_filing_evidence import m303_filing_evidence_modelo
    from ...application.modelo.work_calculation_contracts import ModeloWorkCalculateOrdinaryM303EvidenceRequestV2

    supplied = tuple(
        f"--{name.replace('_', '-')}"
        for name in ModeloWorkCalculateOrdinaryM303EvidenceRequestV2.model_fields
        if arguments.get(name) is not None
    )
    if not supplied:
        return
    owner = m303_filing_evidence_modelo()
    requested = modelo.strip()
    if requested == owner:
        return
    raise CliRefusedBoundaryError(
        translated_message=_FILING_EVIDENCE_OPTION_SCOPE_LOCALE_KEY,
        context={"modelo": requested, "applies_to": owner, "options": ", ".join(supplied)},
    )


def refuse_on_arguments_alone(spec: CommandSpec, arguments: Mapping[str, object]) -> None:
    """Raise the argument-only refusal for this invocation, if one applies.

    Args:
        spec: The resolved command spec being dispatched.
        arguments: The parsed arguments for this invocation.

    Raises:
        CliRefusedBoundaryError: When the arguments alone settle the refusal.
    """
    from cadrumo_client.commands.errors import CliRefusedBoundaryError

    from ...application.modelo.work_create_policy import modelo_work_create_refusal_locale_key

    identity = spec.result_schema.identity or spec.key
    if identity == _WORK_CALCULATE_IDENTITY:
        calculated = arguments.get(_MODELO_PARAMETER)
        if isinstance(calculated, str):
            refuse_filing_evidence_options_for_other_modelo(calculated, arguments)
        return
    if identity != _WORK_CREATE_IDENTITY:
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


__all__ = ["refuse_filing_evidence_options_for_other_modelo", "refuse_on_arguments_alone"]
