"""``aeat setup`` — first-run interactive setup wizard (#61).

Typer sub-app exposing four commands:

* ``aeat setup`` — interactive wizard. Accepts
  ``--non-interactive --from <path>`` for fully-scripted runs.
* ``aeat setup verify`` — run the verifier against an existing env
  file without writing anything.
* ``aeat setup show`` — print the current setup configuration.
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
from ...core.config import PROJECT_ROOT, load_settings
from ...core.i18n import Language, Translatable, get_translation


def _t(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


def _lang() -> Language:
    try:
        return Language(load_settings().aeat_output_language)
    except (KeyError, ValueError):
        return Language.ES


def _msg(message: Translatable) -> str:
    return get_translation(message, _lang())


SETUP_HELP = _msg(
    _t(
        "Asistente inicial: escribe env/.env, el perfil autonomo y la CCAA de residencia fiscal para RENTA.",
        "First-run setup: writes env/.env, the autonomo profile, and the RENTA tax-residence CCAA.",
        "Elso futtatas beallitasa: env/.env, autonomo profil es RENTA adoilletosegi CCAA mentese.",
    )
)
VERIFY_HELP = _msg(
    _t(
        "Verifica un JSON SetupAnswers sin escribir archivos.",
        "Verify a SetupAnswers JSON file without writing files.",
        "SetupAnswers JSON ellenorzese fajlok irasa nelkul.",
    )
)
SHOW_HELP = _msg(
    _t(
        "Muestra un JSON SetupAnswers, incluida la CCAA RENTA configurada, sin ejecutar el asistente.",
        "Show a SetupAnswers JSON file, including the configured RENTA CCAA, without running setup.",
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
    table = Table(title="Verify findings", show_lines=False)
    table.add_column("name")
    table.add_column("severity")
    table.add_column("message")
    for finding in findings:
        table.add_row(
            finding.name,
            finding.severity.value,
            finding.message.get("en", ""),
        )
    _console.print(table)


def _render_result(result: SetupResult) -> None:
    _console.print(f"[bold]setup outcome:[/bold] {result.outcome.value}")
    _console.print(f"env file: {result.env_file_path}")
    _console.print(f"profile file: {result.profile_file_path}")
    _console.print(f"completed: {', '.join(step.value for step in result.steps_completed) or '-'}")
    if result.steps_skipped:
        _console.print(f"skipped:   {', '.join(step.value for step in result.steps_skipped)}")
    if result.verify_findings:
        _render_findings(result.verify_findings)


@app.callback(invoke_without_command=True)
def setup(
    ctx: typer.Context,
    env_file: Path = typer.Option(
        PROJECT_ROOT / "env" / ".env",
        "--env-file",
        help=_msg(
            _t(
                "Archivo env destino que se escribira.",
                "Target env file to write.",
                "Cel env fajl, amely irasra kerul.",
            )
        ),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help=_msg(
            _t(
                "Ejecuta sin preguntas; requiere --from con un JSON SetupAnswers completo.",
                "Run without prompts; requires --from with a complete SetupAnswers JSON file.",
                "Kerdesek nelkuli futtatas; teljes SetupAnswers JSON kell a --from kapcsoloval.",
            )
        ),
    ),
    answers_from: Path | None = typer.Option(
        None,
        "--from",
        help=_msg(
            _t(
                "Ruta a un JSON SetupAnswers; obligatorio con --non-interactive y util como valores por defecto.",
                "Path to a SetupAnswers JSON file; required with --non-interactive and useful as defaults.",
                "SetupAnswers JSON utvonala; kotelezo --non-interactive mellett es alapertelmezesnek is hasznos.",
            )
        ),
    ),
) -> None:
    """Run the interactive setup wizard (or a scripted run with ``--from``)."""
    if ctx.invoked_subcommand is not None:
        return

    defaults: SetupAnswers | None = None
    if answers_from is not None:
        defaults = load_answers_from_file(answers_from)

    if non_interactive:
        if defaults is None:
            raise typer.BadParameter("--non-interactive requires --from <path>")
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
        help=_msg(
            _t(
                "Ruta al JSON SetupAnswers que se verificara.",
                "Path to the SetupAnswers JSON file to verify.",
                "Az ellenorzendo SetupAnswers JSON utvonala.",
            )
        ),
    ),
) -> None:
    """Run the pure verifier without mutating any state."""
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
        help=_msg(
            _t(
                "Ruta al JSON SetupAnswers que se mostrara.",
                "Path to the SetupAnswers JSON file to display.",
                "A megjelenitendo SetupAnswers JSON utvonala.",
            )
        ),
    ),
) -> None:
    """Pretty-print a SetupAnswers payload. Never writes."""
    answers = load_answers_from_file(answers_from)
    table = Table(title=f"SetupAnswers @ {answers_from}")
    table.add_column("field")
    table.add_column("value")
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
