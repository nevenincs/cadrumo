"""CLI projection of one complete, runtime-authorized profile view."""

from __future__ import annotations

import time
from dataclasses import dataclass

import typer

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.language_resolver import resolve_profile_output_language_hint
from ....application.user_profile.validation import COMPLETENESS_ISSUE_CODES
from ....application.user_profile.view_operation import (
    ProfileViewFactItem,
    ProfileViewIssueItem,
    ProfileViewNoticeItem,
    ProfileViewPageKind,
)
from ....core.config import load_settings
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import normalise_supported_language, tr
from ....core.json_contract import Notice
from ....domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....domain.user_profile.values import ProfileSetupState
from ..common import activate_subcommand_output_language
from ..config_payloads import (
    ConfigProfileValidateResult,
    ConfigProfileViewResult,
    ProfileFactPayload,
    ProfileIssuePayload,
)

_VIEW_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class CliRuntimeProfileView:
    """Complete existing CLI output parts, ready for the one envelope owner."""

    result: ConfigProfileViewResult
    lines: tuple[str, ...]
    notices: tuple[Notice, ...]
    blocking: bool


@dataclass(frozen=True, slots=True)
class CliRuntimeProfileValidation:
    """Report-only CLI output from the same authenticated view revision."""

    result: ConfigProfileValidateResult
    lines: tuple[str, ...]
    blocking: bool


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def _output_language(facts: tuple[ProfileViewFactItem, ...], *, requested: OutputLanguage | None) -> OutputLanguage:
    """Honor explicit CLI settings, then the exact profile fact, then default."""
    profile_value = next((fact.value for fact in facts if fact.path == PROFILE_OUTPUT_LANGUAGE_PATH), None)
    return _selected_language(profile_value, requested=requested)


def _selected_language(profile_value: str | None, *, requested: OutputLanguage | None) -> OutputLanguage:
    """Apply one precedence order to a protected fact or its nonsecret hint."""
    settings = load_settings()
    if requested is not None:
        return requested
    if "cadrumo_output_language" in settings.model_fields_set and settings.cadrumo_output_language is not None:
        return settings.cadrumo_output_language
    normalized = normalise_supported_language(profile_value)
    if normalized is not None:
        return OutputLanguage(normalized)
    return settings.cadrumo_output_language or OutputLanguage.ES


def resolve_runtime_profile_output_language(
    client: RuntimeFrontendClient, *, requested: OutputLanguage | None
) -> OutputLanguage:
    """Resolve one selected profile's language without reading its private facts."""
    return _selected_language(resolve_profile_output_language_hint(str(client.profile_id)), requested=requested)


def _typed_items[ItemT](items: tuple[object, ...], expected: type[ItemT]) -> tuple[ItemT, ...]:
    if not all(isinstance(item, expected) for item in items):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return tuple(item for item in items if isinstance(item, expected))


def project_profile_view(
    ctx: typer.Context,
    client: RuntimeFrontendClient,
    *,
    display_name: str,
    requested_output_language: OutputLanguage | None,
) -> CliRuntimeProfileView:
    """Assemble facts, validation and notices only from one settled revision."""
    deadline = time.monotonic() + _VIEW_TIMEOUT_SECONDS
    facts_collection = client.read_profile_view((ProfileViewPageKind.FACTS,), timeout=_remaining(deadline))
    facts = _typed_items(facts_collection.items(ProfileViewPageKind.FACTS), ProfileViewFactItem)
    language = _output_language(facts, requested=requested_output_language)
    activate_subcommand_output_language(ctx, language)
    details = client.read_profile_view(
        (ProfileViewPageKind.ISSUES, ProfileViewPageKind.OVERVIEW),
        output_language=language,
        expected_revision=facts_collection.record_revision,
        expected_content_digest=facts_collection.content_digest,
        timeout=_remaining(deadline),
    )
    if (
        details.profile_id != facts_collection.profile_id
        or details.setup_state != facts_collection.setup_state
        or details.schema_version != facts_collection.schema_version
        or details.valid != facts_collection.valid
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    issues = _typed_items(details.items(ProfileViewPageKind.ISSUES), ProfileViewIssueItem)
    notices = tuple(
        item for item in details.items(ProfileViewPageKind.OVERVIEW) if isinstance(item, ProfileViewNoticeItem)
    )
    blocking_count = sum(
        issue.severity.value == "error"
        and (details.setup_state is ProfileSetupState.COMPLETE or issue.code not in COMPLETENESS_ISSUE_CODES)
        for issue in issues
    )
    if details.valid == bool(blocking_count):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    ordered_values = tuple(sorted((fact.path, fact.value) for fact in facts))
    if len({path for path, _ in ordered_values}) != len(ordered_values):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    result = ConfigProfileViewResult(
        profile_id=str(client.profile_id),
        display_name=display_name,
        setup_state=details.setup_state,
        valid=details.valid,
        schema_version=details.schema_version,
        issues=[
            ProfileIssuePayload(
                severity=issue.severity,
                code=issue.code,
                path=issue.path,
                message=issue.message,
            )
            for issue in issues
        ],
        facts=[ProfileFactPayload(path=path, value=value) for path, value in ordered_values],
    )
    if blocking_count:
        prose = tr("cli.config.profile.show.summary_invalid", count=blocking_count)
        verdict = f"record_validity\tinvalid\tissues={blocking_count}"
    else:
        prose = tr("cli.config.profile.show.summary_valid")
        verdict = f"record_validity\tvalid\tissues={len(issues)}"
    lines = (
        prose,
        verdict,
        f"profile_id\t{client.profile_id}",
        f"display_name\t{display_name}",
        f"setup_state\t{details.setup_state.value}",
        *(f"{issue.severity.value}\t{issue.code}\t{issue.path or '-'}\t{issue.message}" for issue in issues),
        *(f"{path}\t{value}" for path, value in ordered_values),
    )
    return CliRuntimeProfileView(
        result=result,
        lines=lines,
        notices=tuple(
            Notice(
                severity=notice.severity,
                code=notice.code,
                message=notice.message,
                context=None if notice.context is None else {entry.key: entry.value for entry in notice.context},
            )
            for notice in notices
        ),
        blocking=bool(blocking_count),
    )


def project_profile_validate(
    ctx: typer.Context,
    client: RuntimeFrontendClient,
    *,
    display_name: str,
    requested_output_language: OutputLanguage | None,
) -> CliRuntimeProfileValidation:
    """Render only canonical issues; every error remains blocking for validate."""
    language = resolve_runtime_profile_output_language(client, requested=requested_output_language)
    activate_subcommand_output_language(ctx, language)
    deadline = time.monotonic() + _VIEW_TIMEOUT_SECONDS
    collection = client.read_profile_view(
        (ProfileViewPageKind.READINESS_ISSUES,), output_language=language, timeout=_remaining(deadline)
    )
    issues = _typed_items(collection.items(ProfileViewPageKind.READINESS_ISSUES), ProfileViewIssueItem)
    blocking = any(issue.severity.value == "error" for issue in issues)
    result = ConfigProfileValidateResult(
        profile_id=str(collection.profile_id),
        display_name=display_name,
        setup_state=collection.setup_state,
        valid=not blocking,
        schema_version=collection.schema_version,
        issues=[
            ProfileIssuePayload(
                severity=issue.severity,
                code=issue.code,
                path=issue.path,
                message=issue.message,
            )
            for issue in issues
        ],
    )
    lines = (
        f"readiness\t{'blocked' if blocking else 'ready'}\tissues={len(issues)}",
        f"profile_id\t{result.profile_id}",
        f"display_name\t{display_name}",
        f"setup_state\t{result.setup_state.value}",
        f"schema_version\t{result.schema_version}",
        f"valid\t{not blocking}",
        *(f"{issue.severity.value}\t{issue.code}\t{issue.path or '-'}\t{issue.message}" for issue in issues),
    )
    return CliRuntimeProfileValidation(result=result, lines=lines, blocking=blocking)


__all__ = [
    "CliRuntimeProfileValidation",
    "CliRuntimeProfileView",
    "project_profile_validate",
    "project_profile_view",
    "resolve_runtime_profile_output_language",
]
