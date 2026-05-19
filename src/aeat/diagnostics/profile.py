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

from ..application.user_profile._orchestration import (
    build_lifecycle_service,
    fact_value,
    set_active_field,
)
from ..application.wizard._catalogue import WIZARD_FLOWS
from ..application.wizard._errors import WizardValidationError
from ..application.wizard._widgets import validate_widget_answer
from ..application.workflow._models import resolve_active_bucket_id
from ..application.workflow._persistence import workflow_state_repository
from ..application.workflow._profile_bucket_scan import read_profile_bucket
from ..domain.profile import get_profile_key
from ..domain.user_profile import ProfileNotFoundError, UserProfileFact


def _question_for_profile_key(profile_key: str):
    """Return the descriptor's question for ``profile_key``, or ``None``."""

    for flow in WIZARD_FLOWS:
        for section in flow.sections:
            for question in section.questions:
                if question.profile_key == profile_key:
                    return question
    return None


def _resolve_target_profile(profile: str | None) -> str:
    """Resolve the bucket id to operate on: explicit override or the active pointer."""

    if profile is not None:
        target = profile.strip()
        if not target:
            raise typer.BadParameter("--profile must not be empty when supplied.")
        return target
    active = resolve_active_bucket_id()
    if active is None:
        raise typer.BadParameter(
            "No active profile and no --profile NAME supplied; run `aeat config profile switch NAME` first."
        )
    return active


def register(app: typer.Typer) -> None:
    """Mount the ``profile`` sub-app onto ``app``."""

    sub = typer.Typer(
        name="profile",
        help="Engineer-only profile field inspection and surgical edits.",
        no_args_is_help=True,
    )

    @sub.command("get", help="Read one profile key's stored value.")
    def _get(
        key: str = typer.Argument(..., help="Profile key (e.g. iva.regime)."),
        profile: str | None = typer.Option(None, "--profile", help="Profile to read; defaults to the active profile."),
    ) -> None:
        try:
            get_profile_key(key)
        except KeyError as exc:
            raise typer.BadParameter(f"unknown profile key: {key}") from exc
        target = _resolve_target_profile(profile)
        pointer = read_profile_bucket(target)
        if pointer is None:
            raise typer.BadParameter(f"unknown profile: {target}")
        service = build_lifecycle_service(bucket_id=pointer.bucket_id)
        try:
            record = service.read(target)
        except ProfileNotFoundError as exc:
            raise typer.BadParameter(f"unknown profile: {target}") from exc
        value = fact_value(record, key) or ""
        typer.echo(f"{key}\t{value or '<unset>'}")

    @sub.command("set", help="Write one profile key value, validated against the wizard descriptor.")
    def _set(
        key: str = typer.Argument(..., help="Profile key."),
        value: str = typer.Argument(..., help="Value to store."),
        profile: str | None = typer.Option(None, "--profile", help="Profile to write; defaults to the active profile."),
    ) -> None:
        try:
            registered = get_profile_key(key)
        except KeyError as exc:
            raise typer.BadParameter(f"unknown profile key: {key}") from exc
        canonical_key = registered.key
        question = _question_for_profile_key(canonical_key)
        coerced = value
        if question is not None:
            try:
                coerced = validate_widget_answer(question, value)
            except WizardValidationError as exc:
                choices = ", ".join(choice.value for choice in question.choices)
                translated = exc.translated_message or f"invalid value for {key}: {value!r}"
                raise typer.BadParameter(
                    f"{translated} ({choices})" if choices else translated
                ) from exc
        target = _resolve_target_profile(profile)
        fact = UserProfileFact(path=canonical_key, value=coerced)
        repository = workflow_state_repository()
        updated = repository.update(lambda current: set_active_field(current, fact))
        record = updated.active_profile_record() if target == resolve_active_bucket_id() else None
        if record is None:
            pointer = read_profile_bucket(target)
            if pointer is None:
                raise typer.BadParameter(f"unknown profile: {target}")
            service = build_lifecycle_service(bucket_id=pointer.bucket_id)
            record = service.read(target)
        stored_value = fact_value(record, canonical_key) or ""
        typer.echo(f"{canonical_key}\t{stored_value}")

    @sub.command("unset", help="Clear one profile key value.")
    def _unset(
        key: str = typer.Argument(..., help="Profile key."),
        profile: str | None = typer.Option(None, "--profile", help="Profile to clear; defaults to the active profile."),
    ) -> None:
        try:
            get_profile_key(key)
        except KeyError as exc:
            raise typer.BadParameter(f"unknown profile key: {key}") from exc
        _resolve_target_profile(profile)
        fact = UserProfileFact(path=key, value=None)
        repository = workflow_state_repository()
        repository.update(lambda current: set_active_field(current, fact))
        typer.echo(f"{key}\t<unset>")

    app.add_typer(sub)
