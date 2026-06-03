"""Engineer-only ``profile get/set/unset KEY [--profile NAME]`` verbs.

Field-at-a-time profile fact access lives under
``python -m aeat.diagnostics profile`` so the operator surface does not
advertise it. Operators use the wizard (``aeat config profile create``
/ ``aeat config profile edit``) for the canonical flow; the
diagnostics surface exists for engineer-driven inspection and surgical
repair where the wizard would be the wrong tool.

The implementation delegates to the same application-layer helpers
the deleted ``aeat config profile {get,set,unset}`` operator verbs
used, so the behaviour the engineer surface preserves is
byte-identical to the retired operator path.
"""

from __future__ import annotations

import typer

from ..application.user_profile import (
    build_lifecycle_service,
    fact_value,
    profile_storage_session,
    set_active_field,
)
from ..application.wizard._catalogue import WIZARD_FLOWS
from ..application.wizard._errors import WizardValidationError
from ..application.wizard._widgets import validate_widget_answer
from ..application.workflow import workflow_state_repository
from ..core import resolve_active_bucket_id
from ..core.i18n import tr
from ..core.redaction import redact_for_cli_output
from ..domain.contribuyente import get_profile_key
from ..domain.user_profile import ProfileNotFoundError, UserProfileFact


def _question_for_profile_key(profile_key: str):
    """Return the descriptor's question for ``profile_key``, or ``None``."""
    for flow in WIZARD_FLOWS:
        for section in flow.sections:
            for question in section.questions:
                if question.profile_key == profile_key:
                    return question
    return None


def _refuse(message: str) -> typer.Exit:
    """Emit ``message`` to stderr and return an exit-2 sentinel to raise.

    Emits the localized refusal directly rather than via
    :class:`typer.BadParameter`, whose Rich-panel renderer truncates the
    message at narrow terminal widths (the default CliRunner shell). The
    boundary-check tests assert that the offending input echoes back in
    the output stream; the raw stderr emit preserves the message
    verbatim.
    """
    typer.echo(message, err=True)
    return typer.Exit(code=2)


def _bad_profile_empty() -> typer.Exit:
    return _refuse(tr("cli.diagnostics.profile.errors.profile_empty"))


def _bad_ambiguous_profile(profile: str) -> typer.Exit:
    return _refuse(tr("cli.diagnostics.profile.errors.ambiguous_profile", profile=profile))


def _bad_unknown_profile(profile: str) -> typer.Exit:
    return _refuse(tr("cli.diagnostics.profile.errors.unknown_profile", profile=profile))


def _bad_no_active_profile() -> typer.Exit:
    return _refuse(tr("cli.diagnostics.profile.errors.no_active_profile"))


def _bad_unknown_profile_key(key: str) -> typer.Exit:
    return _refuse(tr("cli.diagnostics.profile.errors.unknown_profile_key", key=key))


def _resolve_target_profile(profile: str | None):
    """Resolve the profile bucket to operate on.

    An explicit ``--profile`` value is an operator label and resolves
    through the manifest scan; otherwise the active-profile pointer (a
    UUID) resolves directly. Returns a ``ProfileBucketPointer`` carrying
    the immutable UUID ``bucket_id`` and the operator ``label``.
    """
    from ..application.workflow import (
        read_profile_bucket,
        read_profile_bucket_by_id,
    )

    if profile is not None:
        target = profile.strip()
        if not target:
            raise _bad_profile_empty()
        try:
            pointer = read_profile_bucket(target)
        except ValueError as exc:
            raise _bad_ambiguous_profile(target) from exc
        if pointer is None:
            raise _bad_unknown_profile(target)
        return pointer
    active = resolve_active_bucket_id()
    if active is None:
        raise _bad_no_active_profile()
    pointer = read_profile_bucket_by_id(active)
    if pointer is None:
        raise _bad_unknown_profile(active)
    return pointer


def register(app: typer.Typer) -> None:
    """Mount the ``profile`` sub-app onto ``app``."""
    sub = typer.Typer(
        name="profile",
        help=tr("cli.diagnostics.profile.help"),
        no_args_is_help=True,
    )

    @sub.command("get", help=tr("cli.diagnostics.profile.get_help"))
    def _get(
        key: str = typer.Argument(..., help=tr("cli.diagnostics.profile.key_help")),
        profile: str | None = typer.Option(None, "--profile", help=tr("cli.diagnostics.profile.profile_help")),
    ) -> None:
        try:
            registered = get_profile_key(key)
        except KeyError as exc:
            raise _bad_unknown_profile_key(key) from exc
        canonical_key = registered.key
        pointer = _resolve_target_profile(profile)
        with profile_storage_session(pointer.bucket_id):
            service = build_lifecycle_service(bucket_id=pointer.bucket_id)
            try:
                record = service.read(pointer.bucket_id)
            except ProfileNotFoundError as exc:
                raise _bad_unknown_profile(pointer.label) from exc
        value = fact_value(record, canonical_key) or ""
        typer.echo(
            redact_for_cli_output(f"{canonical_key}\t{value or tr('cli.diagnostics.profile.unset_placeholder')}")
        )

    @sub.command("set", help=tr("cli.diagnostics.profile.set_help"))
    def _set(
        key: str = typer.Argument(..., help=tr("cli.diagnostics.profile.key_help")),
        value: str = typer.Argument(..., help=tr("cli.diagnostics.profile.value_help")),
        profile: str | None = typer.Option(None, "--profile", help=tr("cli.diagnostics.profile.profile_help")),
    ) -> None:
        try:
            registered = get_profile_key(key)
        except KeyError as exc:
            raise _bad_unknown_profile_key(key) from exc
        canonical_key = registered.key
        question = _question_for_profile_key(canonical_key)
        coerced = value
        if question is not None:
            try:
                coerced = validate_widget_answer(question, value)
            except WizardValidationError as exc:
                choices = ", ".join(choice.value for choice in question.choices)
                translated = exc.translated_message or tr(
                    "cli.diagnostics.profile.errors.invalid_value_fallback",
                    key=key,
                    value=value,
                )
                raise typer.BadParameter(
                    tr("cli.diagnostics.profile.errors.invalid_value_with_choices", message=translated, choices=choices)
                    if choices
                    else translated
                ) from exc
        pointer = _resolve_target_profile(profile)
        fact = UserProfileFact(path=canonical_key, value=coerced)
        with profile_storage_session(pointer.bucket_id):
            repository = workflow_state_repository()
            updated = repository.update(lambda current: set_active_field(current, fact))
            record = updated.active_profile_record()
        stored_value = fact_value(record, canonical_key) or ""
        typer.echo(redact_for_cli_output(f"{canonical_key}\t{stored_value}"))

    @sub.command("unset", help=tr("cli.diagnostics.profile.unset_help"))
    def _unset(
        key: str = typer.Argument(..., help=tr("cli.diagnostics.profile.key_help")),
        profile: str | None = typer.Option(None, "--profile", help=tr("cli.diagnostics.profile.profile_help")),
    ) -> None:
        try:
            registered = get_profile_key(key)
        except KeyError as exc:
            raise _bad_unknown_profile_key(key) from exc
        canonical_key = registered.key
        fact = UserProfileFact(path=canonical_key, value=None)
        pointer = _resolve_target_profile(profile)
        with profile_storage_session(pointer.bucket_id):
            repository = workflow_state_repository()
            repository.update(lambda current: set_active_field(current, fact))
        typer.echo(redact_for_cli_output(f"{canonical_key}\t{tr('cli.diagnostics.profile.unset_placeholder')}"))

    app.add_typer(sub)
