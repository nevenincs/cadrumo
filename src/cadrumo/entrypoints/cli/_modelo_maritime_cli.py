"""Typer registration for modelo maritime preview commands.

This module is the transport boundary for
``aeat app modelo work preview-maritime-exemption``. The command body keeps CLI
responsibilities narrow: parse Decimal options, require an active profile,
delegate profile fact reading and RETMAR retry policy to
:func:`preview_maritime_exemption_for_active_profile`,
then serialise the returned observations into
:class:`WorkPreviewMaritimeExemptionResult`.

See Also:
    :mod:`_maritime_preview`:
        Active-profile application service consumed by this CLI adapter.
    :class:`CasillaObservationPayload`:
        JSON payload row carrying the legal/source references emitted by the
        maritime resolver.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import typer

from ...application.modelo import preview_maritime_exemption_for_active_profile
from ...core.errors import resolve_error_message
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...domain.renta import RentaValidationError
from ._command_policy import command_execution_policy
from ._common import _emit_envelope
from ._modelo_cli_support import optional_decimal_option
from ._modelo_execution_policies import CALCULATION_READ
from ._modelo_payloads import (
    CasillaObservationPayload,
    WorkPreviewMaritimeExemptionResult,
)


def register_maritime_commands(
    work_app: typer.Typer,
    *,
    require_active_profile: Callable[[], None],
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    bad_parameter_from_error: Callable[[Exception], typer.BadParameter],
) -> None:
    """Register maritime worker preview commands against the work Typer app.

    The caller supplies the shared modelo-work CLI hooks so this extracted
    module does not import the monolithic modelo command root. The registered
    command emits a
    :class:`WorkPreviewMaritimeExemptionResult`
    envelope through :func:`_emit_envelope`.
    """

    @work_app.command(
        "preview-maritime-exemption",
        help=tr(
            "cli.app.modelo.work.preview_maritime_exemption_help",
            default=(
                "Preview the Art. 7.p) / REBECA maritime worker IRPF exemption resolved "
                "from the active profile's maritime_worker facts. Emits typed "
                "CasillaObservation rows with legal_refs; surfaces the RETMAR mandatory-"
                "filing warning when retmar_registered=True; refuses with the DA 41 "
                "inactive code when the tuna-fleet selector resolves."
            ),
        ),
    )
    @command_execution_policy(CALCULATION_READ)
    def work_preview_maritime_exemption(
        ctx: typer.Context,
        annual_salary: Annotated[
            str | None,
            typer.Option(
                "--annual-salary",
                help=tr(
                    "cli.app.modelo.work.preview_maritime_exemption_annual_salary_help",
                    default=(
                        "Gross annual salary in EUR (Decimal). Required when the active "
                        "profile triggers Art. 7.p) eligibility (vessel_flag=foreign or "
                        "waters_type=international)."
                    ),
                ),
            ),
        ] = None,
        qualifying_days: Annotated[
            int | None,
            typer.Option(
                "--qualifying-days",
                min=1,
                max=365,
                help=tr(
                    "cli.app.modelo.work.preview_maritime_exemption_qualifying_days_help",
                    default=(
                        "Calendar days worked outside Spanish territory in the tax year. "
                        "Required alongside --annual-salary when Art. 7.p) applies."
                    ),
                ),
            ),
        ] = None,
        gross_navigation_income: Annotated[
            str | None,
            typer.Option(
                "--gross-navigation-income",
                help=tr(
                    "cli.app.modelo.work.preview_maritime_exemption_gross_navigation_income_help",
                    default=(
                        "Total gross employment income from navigation in EUR (Decimal). "
                        "Required when the active profile triggers REBECA eligibility "
                        "(vessel_registry in REBECA / rebeca_eu_eea / scheduled_canary_route)."
                    ),
                ),
            ),
        ] = None,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Resolve and render the maritime exemption preview for the active profile.

        Decimal parsing stays at the CLI boundary. Legal pathway selection,
        profile fact extraction, RETMAR warning handling, and typed observation
        construction stay in
        :func:`preview_maritime_exemption_for_active_profile`.
        """
        activate_output_language(ctx, output_language)
        require_active_profile()

        annual_salary_decimal = optional_decimal_option(
            annual_salary,
            translation_key="cli.app.modelo.work.preview_maritime_exemption_annual_salary_not_decimal",
            default=(
                "--annual-salary must be a decimal amount; received: {value}. "
                "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
            ),
        )
        gross_navigation_decimal = optional_decimal_option(
            gross_navigation_income,
            translation_key=("cli.app.modelo.work.preview_maritime_exemption_gross_navigation_income_not_decimal"),
            default=(
                "--gross-navigation-income must be a decimal amount; received: {value}. "
                "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
            ),
        )

        try:
            preview = preview_maritime_exemption_for_active_profile(
                annual_salary=annual_salary_decimal,
                qualifying_days=qualifying_days,
                gross_navigation_income=gross_navigation_decimal,
            )
        except RentaValidationError as exc:
            raise bad_parameter_from_error(exc) from exc

        facts = preview.facts
        result = preview.result
        retmar_warning = (
            resolve_error_message(preview.retmar_warning_error) if preview.retmar_warning_error is not None else None
        )
        observation_payloads = [
            CasillaObservationPayload(
                casilla_id=obs.casilla_id,
                value=str(obs.value),
                formula_id=obs.formula_id,
                legal_refs=list(obs.legal_refs),
                source_refs=list(obs.source_refs),
            )
            for obs in result.observations
        ]
        casilla_values = {key: str(value) for key, value in result.casilla_values.items()}

        payload = WorkPreviewMaritimeExemptionResult(
            worker_class=facts.worker_class,
            vessel_flag=facts.vessel_flag,
            waters_type=facts.waters_type,
            vessel_registry=facts.vessel_registry,
            retmar_registered=facts.retmar_registered,
            retmar_mandatory_filing=result.retmar_mandatory_filing or facts.retmar_registered,
            retmar_warning=retmar_warning,
            casilla_values=casilla_values,
            observations=observation_payloads,
        )

        lines: list[str] = [
            "operation\tmodelo.work.preview_maritime_exemption",
            f"worker_class\t{facts.worker_class or '-'}",
            f"vessel_flag\t{facts.vessel_flag or '-'}",
            f"waters_type\t{facts.waters_type or '-'}",
            f"vessel_registry\t{facts.vessel_registry or '-'}",
            f"retmar_registered\t{str(facts.retmar_registered).lower()}",
            f"observation_count\t{len(observation_payloads)}",
        ]
        for obs in result.observations:
            lines.append(
                "observation\t"
                + "\t".join(
                    (
                        f"casilla={obs.casilla_id}",
                        f"value={obs.value}",
                        f"legal_refs={'; '.join(obs.legal_refs)}",
                        f"source_refs={','.join(obs.source_refs)}",
                    ),
                ),
            )
        for key, value in casilla_values.items():
            lines.append(f"casilla_value\t{key}\t{value}")
        if retmar_warning is not None:
            lines.append(f"retmar_warning\t{retmar_warning}")

        _emit_envelope(
            ctx,
            command="modelo.work.preview_maritime_exemption",
            result=payload,
            lines=lines,
        )
