"""Expose the ``aeat setup`` first-run interactive setup wizard sub-app.

Wires the setup wizard, verifier, and read-only display into a Typer
sub-app:

- ``aeat setup`` runs the interactive wizard. Accepts
  ``--non-interactive --from <path>`` for fully-scripted runs.
- ``aeat setup verify`` runs the verifier against an existing
  ``SetupAnswers`` JSON file without writing anything.
- ``aeat setup show`` pretty-prints a ``SetupAnswers`` JSON file.

The wizard, prompter, and verifier primitives live in
:mod:`aeat.application.setup`; this module is the typer-flavoured
entrypoint that translates CLI flags into those primitives.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ...application.setup import (
    SetupAnswers,
    SetupOutcome,
    SetupResult,
    SetupWizard,
    TyperPrompter,
    Verifier,
    VerifyFinding,
    load_answers_from_file,
)
from ...core.config import PROJECT_ROOT
from ...core.i18n import get_translation
from ._i18n import output_language, t, tr


SETUP_HELP = tr(
    t(
        "Asistente inicial: escribe env/.env, el perfil autonomo y la CCAA de residencia fiscal para RENTA.",
        "First-run setup: writes env/.env, the autonomo profile, and the RENTA tax-residence CCAA.",
        "Assistent inicial: escriu env/.env, el perfil autònom i la CCAA de residència fiscal per a la RENTA.",
        "Elso futtatas beallitasa: env/.env, autonomo profil es RENTA adoilletosegi CCAA mentese.",
    )
)
VERIFY_HELP = tr(
    t(
        "Verifica un JSON SetupAnswers sin escribir archivos.",
        "Verify a SetupAnswers JSON file without writing files.",
        "Verifica un JSON SetupAnswers sense escriure cap fitxer.",
        "SetupAnswers JSON ellenorzese fajlok irasa nelkul.",
    )
)
SHOW_HELP = tr(
    t(
        "Muestra un JSON SetupAnswers, incluida la CCAA RENTA configurada, sin ejecutar el asistente.",
        "Show a SetupAnswers JSON file, including the configured RENTA CCAA, without running setup.",
        "Mostra un JSON SetupAnswers, inclosa la CCAA RENTA configurada, sense executar l'assistent.",
        "SetupAnswers JSON megjelenitese, a beallitott RENTA CCAA-val, a beallitas futtatasa nelkul.",
    )
)

app = typer.Typer(
    name="setup",
    help=SETUP_HELP,
    no_args_is_help=False,
)

_console = Console()


def _render_findings(findings: tuple[VerifyFinding, ...]) -> None:
    """Render ``findings`` as a Rich table on the module console."""
    title = tr(
        t(
            "Hallazgos de verificación",
            "Verify findings",
            "Resultats de la verificació",
            "Ellenorzesi eredmenyek",
        )
    )
    name_col = tr(t("nombre", "name", "nom", "nev"))
    severity_col = tr(t("severidad", "severity", "severitat", "sulyossag"))
    message_col = tr(t("mensaje", "message", "missatge", "uzenet"))
    table = Table(title=title, show_lines=False)
    table.add_column(name_col)
    table.add_column(severity_col)
    table.add_column(message_col)
    lang = output_language()
    for finding in findings:
        message = get_translation(finding.message, lang) if finding.message else ""
        table.add_row(
            finding.name,
            finding.severity.value,
            message,
        )
    _console.print(table)


def _render_result(result: SetupResult) -> None:
    """Render a :class:`aeat.application.setup.SetupResult` summary."""
    outcome_label = tr(t("resultado del asistente", "setup outcome", "resultat de l'assistent", "beallitas eredmenye"))
    env_label = tr(t("archivo env", "env file", "fitxer env", "env fajl"))
    profile_label = tr(t("archivo perfil", "profile file", "fitxer del perfil", "profil fajl"))
    completed_label = tr(t("completados", "completed", "completats", "elvegezve"))
    skipped_label = tr(t("omitidos", "skipped", "omesos", "kihagyva"))

    _console.print(f"[bold]{outcome_label}:[/bold] {result.outcome.value}")
    _console.print(f"{env_label}: {result.env_file_path}")
    _console.print(f"{profile_label}: {result.profile_file_path}")
    _console.print(f"{completed_label}: {', '.join(step.value for step in result.steps_completed) or '-'}")
    if result.steps_skipped:
        _console.print(f"{skipped_label}:   {', '.join(step.value for step in result.steps_skipped)}")
    if result.verify_findings:
        _render_findings(result.verify_findings)


@app.callback(invoke_without_command=True)
def setup(
    ctx: typer.Context,
    env_file: Path = typer.Option(
        PROJECT_ROOT / "env" / ".env",
        "--env-file",
        help=tr(
            t(
                "Archivo env destino que se escribira.",
                "Target env file to write.",
                "Fitxer env de destinació que s'escriurà.",
                "Cel env fajl, amely irasra kerul.",
            )
        ),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help=tr(
            t(
                "Ejecuta sin preguntas; requiere --from con un JSON SetupAnswers completo.",
                "Run without prompts; requires --from with a complete SetupAnswers JSON file.",
                "Executa sense preguntes; requereix --from amb un JSON SetupAnswers complet.",
                "Kerdesek nelkuli futtatas; teljes SetupAnswers JSON kell a --from kapcsoloval.",
            )
        ),
    ),
    answers_from: Path | None = typer.Option(
        None,
        "--from",
        help=tr(
            t(
                "Ruta a un JSON SetupAnswers; obligatorio con --non-interactive y util como valores por defecto.",
                "Path to a SetupAnswers JSON file; required with --non-interactive and useful as defaults.",
                "Camí a un JSON SetupAnswers; obligatori amb --non-interactive i útil com a valors per defecte.",
                "SetupAnswers JSON utvonala; kotelezo --non-interactive mellett es alapertelmezesnek is hasznos.",
            )
        ),
    ),
) -> None:
    """Run the interactive setup wizard, or a scripted run with ``--from``.

    Args:
        ctx: The Typer context, consulted to detect a sub-command call.
        env_file: Target ``.env`` file to write.
        non_interactive: When ``True``, run without prompts; requires
            ``answers_from`` to be set.
        answers_from: Path to a ``SetupAnswers`` JSON file; required for
            ``non_interactive`` and useful as defaults otherwise.

    Raises:
        typer.BadParameter: When ``non_interactive`` is set without
            ``answers_from``.
        typer.Exit: With code ``2`` when the wizard aborts because the
            verifier reported errors.
    """
    if ctx.invoked_subcommand is not None:
        return

    defaults: SetupAnswers | None = None
    if answers_from is not None:
        defaults = load_answers_from_file(answers_from)

    if non_interactive:
        if defaults is None:
            raise typer.BadParameter(
                tr(
                    t(
                        "--non-interactive requiere --from <ruta>",
                        "--non-interactive requires --from <path>",
                        "--non-interactive requereix --from <camí>",
                        "--non-interactive a --from <utvonal> kapcsoloval kell",
                    )
                )
            )
        wizard = SetupWizard()
        result = wizard.run(
            env_file=env_file,
            non_interactive=True,
            defaults=defaults,
        )
    else:
        wizard = SetupWizard()
        result = wizard.run(
            env_file=env_file,
            non_interactive=False,
            defaults=defaults,
            prompter=TyperPrompter(),
        )

    _render_result(result)
    if result.outcome is SetupOutcome.ABORTED_VERIFY_FAILED:
        raise typer.Exit(code=2)


@app.command("verify", help=VERIFY_HELP)
def verify(
    answers_from: Path = typer.Option(
        ...,
        "--from",
        help=tr(
            t(
                "Ruta al JSON SetupAnswers que se verificara.",
                "Path to the SetupAnswers JSON file to verify.",
                "Camí al JSON SetupAnswers que es verificarà.",
                "Az ellenorzendo SetupAnswers JSON utvonala.",
            )
        ),
    ),
) -> None:
    """Run the pure :class:`aeat.application.setup.Verifier` without mutating state.

    Args:
        answers_from: Path to the ``SetupAnswers`` JSON file to verify.

    Raises:
        typer.Exit: With code ``2`` when the verifier reports any
            error-severity finding.
    """
    answers = load_answers_from_file(answers_from)
    findings = Verifier().run(answers)
    _render_findings(findings)
    if Verifier.has_error(findings):
        raise typer.Exit(code=2)


@app.command("show", help=SHOW_HELP)
def show(
    answers_from: Path = typer.Option(
        ...,
        "--from",
        help=tr(
            t(
                "Ruta al JSON SetupAnswers que se mostrara.",
                "Path to the SetupAnswers JSON file to display.",
                "Camí al JSON SetupAnswers que es mostrarà.",
                "A megjelenitendo SetupAnswers JSON utvonala.",
            )
        ),
    ),
) -> None:
    """Pretty-print a ``SetupAnswers`` payload as a Rich table.

    Never mutates state.

    Args:
        answers_from: Path to the ``SetupAnswers`` JSON file to display.
    """
    answers = load_answers_from_file(answers_from)
    field_col = tr(t("campo", "field", "camp", "mezo"))
    value_col = tr(t("valor", "value", "valor", "ertek"))
    table = Table(title=f"SetupAnswers @ {answers_from}")
    table.add_column(field_col)
    table.add_column(value_col)
    for name, value in answers.model_dump(mode="python").items():
        if name == "steps_to_skip":
            rendered = ", ".join(sorted(str(s) for s in value)) or "-"
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value) if value is not None else "-"
        table.add_row(name, rendered)
    _console.print(table)


__all__ = ["SETUP_HELP", "app"]
