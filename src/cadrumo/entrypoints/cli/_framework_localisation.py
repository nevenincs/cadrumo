"""Bind Typer/Click's own framework prose to Cadrumo's output locale.

Typer vendors Click, and Click renders its plain-text section headings and its
parser-error prefixes through strings the framework owns: a ``gettext`` call
bound to ``_`` inside :mod:`typer.core`, and the ``Missing option`` / ``Invalid
value`` prefixes raised during argument parsing. Neither ships a catalogue for
any locale, so both resolve to English regardless of the operator's language
while every ``tr()``-bound string beside them localises correctly.

The rebinds live here rather than in the package facade because they are one
concern with one caller: :func:`~cadrumo.entrypoints.cli.main` runs them once
per console process, after the root language flag has been resolved and before
the command tree is invoked. They are invocation-scoped by construction — a
real ``aeat`` run is one process per invocation, so a module-global rebind
reflects only that process's locale, and the in-process test runner never
reaches them because it does not call ``main``.
"""

from __future__ import annotations

import re
from typing import IO, Any, Protocol, cast

from ...core.i18n.render import tr


class _TyperExceptionsState(Protocol):
    """Local marker for Cadrumo's idempotent Typer localisation state."""

    cadrumo_parse_errors_localised: bool


def localise_help_section_headers() -> None:
    """Localise Click's plain-text ``--help`` section headings to the resolved locale.

    Click's plain-text help formatter renders the ``Arguments`` / ``Options`` /
    ``Commands`` section headings through ``gettext.gettext`` bound to the name
    ``_`` inside :mod:`typer.core` (``with formatter.section(_("Options")): ...``),
    but Typer/Click ship no translation catalogue for any locale, so the call
    resolves to the literal English string regardless of the process locale. The
    already-``tr()``-bound option *descriptions* localise via the
    :func:`_apply_language_argv_to_environment` env promotion, but the
    framework-owned section headings stayed English — the residual gap the
    operator-surface ``--language`` help-honesty contract leaves open. This
    rebinds :mod:`typer.core`'s ``_`` name to a small dispatch table so those
    three headings resolve through Cadrumo's own locale catalogue; every other
    string Click passes through ``_()`` (which this project does not translate)
    renders unchanged.

    Invocation-scoped, no cross-invocation leak: it runs once per console
    process from :func:`main` after the language flag has been promoted, always
    sets every heading to *this* invocation's locale (never a partial/stale set),
    and is never reached by the in-process test runner (which does not call
    :func:`main`). Real ``aeat`` runs are one process per invocation, so the
    module-global rebind reflects only the current process's locale.
    """
    import typer.core as _typer_core

    headings = {
        "Arguments": tr("cli.help.panel.arguments", default="Arguments"),
        "Options": tr("cli.help.panel.options", default="Options"),
        "Commands": tr("cli.help.panel.commands", default="Commands"),
    }

    def _localised_gettext(message: str) -> str:
        return headings.get(message, message)

    _typer_core.__dict__["_"] = _localised_gettext


#: Strips a Rich console markup tag (``[blue]``, ``[/]``, ``[bold red]``, ...).
#: The ``cli.help.try_for_help`` catalogue entry carries Rich markup in its
#: default value (written for the now-disabled Rich renderer); this pattern
#: lets the plain-text error path reuse the same catalogue entry unstyled.
_RICH_MARKUP_TAG_RE = re.compile(r"\[/?[a-zA-Z_ ]*\]")


#: Typer's English "Missing …" prefixes, most specific first, each paired with its
#: catalogue key and the exact prefix to strip. The bare ``"Missing "`` fallback
#: deliberately strips only ``"Missing"`` so the following space survives, and it
#: MUST stay last or it would shadow the three specific spellings above it.
_MISSING_PARAMETER_PREFIXES: tuple[tuple[str, str, str, str], ...] = (
    ("Missing argument", "cli.help.missing_argument", "Missing argument", "Missing argument"),
    ("Missing option", "cli.help.missing_option", "Missing option", "Missing option"),
    ("Missing parameter", "cli.help.missing_parameter", "Missing parameter", "Missing parameter"),
    ("Missing ", "cli.help.missing_parameter", "Missing parameter", "Missing"),
)


def _localised_missing_prefix(rendered: str) -> str:
    """Swap Typer's English ``Missing …`` prefix for its localised equivalent."""
    for match_prefix, key, default, strip_prefix in _MISSING_PARAMETER_PREFIXES:
        if rendered.startswith(match_prefix):
            return f"{tr(key, default=default)}{rendered.removeprefix(strip_prefix)}"
    return rendered


def _localised_invalid_value(rendered: str) -> str:
    """Swap Typer's English ``Invalid value`` prefix and integer wording for the locale."""
    if rendered.startswith("Invalid value for "):
        prefix, separator, detail = rendered.partition(": ")
        parameter = prefix.removeprefix("Invalid value for ")
        rendered = (
            f"{tr('cli.help.invalid_value_for', default='Invalid value for %{parameter}', parameter=parameter)}"
            f"{separator}{detail}"
        )
    elif rendered.startswith("Invalid value"):
        invalid_value = tr("cli.help.invalid_value", default="Invalid value")
        rendered = f"{invalid_value}{rendered.removeprefix('Invalid value')}"
    localised_integer = tr("cli.help.not_valid_integer", default="is not a valid integer.")
    # Typer vendors its own Click fork whose IntParamType.name is ``int``
    # (upstream Click uses ``integer``), so the conversion failure reads
    # "is not a valid int."; localise both spellings. The "int." form is
    # not a substring of the "integer." form, so the two replacements are
    # order-independent and non-overlapping.
    return rendered.replace(
        "is not a valid integer.",
        localised_integer,
    ).replace(
        "is not a valid int.",
        localised_integer,
    )


def localise_typer_parse_error_messages() -> None:
    """Bind Typer's vendored parser-error prefixes to the active locale.

    Typer vendors Click, so Click's gettext integration cannot reach the
    ``Missing option`` and ``Invalid value`` strings emitted during argument
    parsing.  Rebind only those presentation prefixes here, after the root
    language flag has been resolved and before the command tree is invoked.

    Also rebinds ``ClickException.show`` / ``UsageError.show`` — the plain-text
    error renderer every parse/usage failure falls back to now that Rich
    rendering is disabled (see :func:`._stdio.disable_rich_cli_rendering`).
    Both hardcode ``"Error: ..."`` and ``"Try '{cmd} {opt}' for help."``
    verbatim with no gettext hook at all, so this is a from-scratch
    reimplementation of each method's body rather than a wrapped delegate.
    """
    from typer._click import exceptions as _typer_exceptions
    from typer._click import formatting as _typer_formatting

    if getattr(_typer_exceptions, "cadrumo_parse_errors_localised", False):
        return

    missing_parameter_format_message = _typer_exceptions.MissingParameter.format_message
    bad_parameter_format_message = _typer_exceptions.BadParameter.format_message
    write_usage = _typer_formatting.HelpFormatter.write_usage

    def localised_missing_parameter_format_message(self: _typer_exceptions.MissingParameter) -> str:
        return _localised_missing_prefix(missing_parameter_format_message(self))

    def localised_bad_parameter_format_message(self: _typer_exceptions.BadParameter) -> str:
        return _localised_invalid_value(bad_parameter_format_message(self))

    def localised_write_usage(
        self: _typer_formatting.HelpFormatter, prog: str, args: str = "", prefix: str | None = None
    ) -> None:
        return write_usage(
            self,
            prog,
            args,
            tr("cli.help.usage_prefix", default="Usage: ") if prefix is None else prefix,
        )

    def _localised_error_prefix() -> str:
        return tr("cli.help.panel.error", default="Error")

    # ADAPTER-INTERNAL-ALIAS-RATIONALE-CLICK-SHOW: mirrors Click's own
    # untyped ClickException.show(file: IO[Any] | None) signature so this
    # monkeypatched override stays substitutable for the original method.
    def localised_click_exception_show(
        self: _typer_exceptions.ClickException,
        file: IO[Any] | None = None,
    ) -> None:
        from typer._click._compat import get_text_stderr
        from typer._click.utils import echo

        if file is None:
            file = get_text_stderr()
        echo(
            f"{_localised_error_prefix()}: {self.format_message()}",
            file=file,
            color=self.show_color,
        )

    # ADAPTER-INTERNAL-ALIAS-RATIONALE-CLICK-SHOW: mirrors Click's own
    # untyped UsageError.show(file: IO[Any] | None) signature so this
    # monkeypatched override stays substitutable for the original method.
    def localised_usage_error_show(
        self: _typer_exceptions.UsageError,
        file: IO[Any] | None = None,
    ) -> None:
        from typer._click._compat import get_text_stderr
        from typer._click.utils import echo

        if file is None:
            file = get_text_stderr()
        color = None
        hint = ""
        if self.ctx is not None and self.ctx.command.get_help_option(self.ctx) is not None:
            command = self.ctx.command_path
            option = self.ctx.help_option_names[0]
            # RICH_HELP's stored value carries Rich's ``[blue]…[/]`` markup for
            # the (now-dead) Rich renderer; strip any ``[tag]`` bracket before
            # using it as plain stderr text so a translated catalogue entry
            # copied from the Rich default doesn't leak literal brackets.
            hint_template = _RICH_MARKUP_TAG_RE.sub(
                "",
                tr(
                    "cli.help.try_for_help",
                    default="Try '{command_path} {help_option}' for help.",
                ),
            )
            hint = f"{hint_template.format(command_path=command, help_option=option)}\n"
        if self.ctx is not None:
            color = self.ctx.color
            echo(f"{self.ctx.get_usage()}\n{hint}", file=file, color=color)
        echo(
            f"{_localised_error_prefix()}: {self.format_message()}",
            file=file,
            color=color,
        )

    _typer_exceptions.MissingParameter.format_message = localised_missing_parameter_format_message
    _typer_exceptions.BadParameter.format_message = localised_bad_parameter_format_message
    _typer_formatting.HelpFormatter.write_usage = localised_write_usage
    _typer_exceptions.ClickException.show = localised_click_exception_show
    _typer_exceptions.UsageError.show = localised_usage_error_show
    typer_exceptions_state = cast(  # CAST-RATIONALE-TYPER-EXCEPTIONS-STATE: module attribute is Cadrumo-owned.
        "_TyperExceptionsState", _typer_exceptions
    )
    typer_exceptions_state.cadrumo_parse_errors_localised = True
