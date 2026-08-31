"""Profile inspection verbs: ``view`` and ``validate``.

``view`` reads and renders the active (or named) profile's persisted
:class:`UserProfileRecord`, alongside its schema validity; ``validate`` is
the report-only companion to ``view`` (same validator, no fact dump). Their
public behavior targets live here while CommandSpecs own the executable shape.

Filing-context readiness is NOT reported here. ``app modelo readiness`` is the
one home for that question: it reports the same missing profile requirements
over the same gate, and adds the registry, binding and ledger axes this module
never covered.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import typer

from ....core.errors.hierarchy import CadrumoError as _CadrumoError
from ....core.external_constants import OutputLanguage as _OutputLanguage
from ....core.i18n import tr
from ....core.logging import get_logger as _get_logger
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope, no_active_profile_refusal
from ..errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._profile_readiness import (
    _emit_profile_record_missing,
    _emit_profile_record_unreadable,
    _read_profile_record,
)
from .errors import ConfigBoundaryError as _ConfigBoundaryError

_log = _get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ....application.user_profile.commands import ProfileValidationReport as _ProfileValidationReport
    from ....application.workflow.profile_bucket_models import ProfileBucketPointer as _ProfileBucketPointer
    from ....domain.user_profile.values import UserProfileRecord as _UserProfileRecord


def _resolve_show_pointer(
    name: str | None,
    *,
    ctx: typer.Context,
    resolve_active_profile_pointer: Callable[[], _ProfileBucketPointer | None],
) -> _ProfileBucketPointer:
    """Resolve the profile ``show`` inspects, by name or the active pointer.

    ``show`` is the inspect surface for a current committed capsule. The
    pointer supplies identity and label; setup state is read from the
    authenticated record below.
    """
    if name is None:
        pointer = resolve_active_profile_pointer()
        if pointer is None:
            raise no_active_profile_refusal()
        return pointer

    from .._profile_authentication_gate import resolved_command_profile_target

    pointer = resolved_command_profile_target(ctx)
    if pointer is not None:
        return pointer
    raise RuntimeError("explicit profile show target was not resolved by parsed dispatch")


def _read_record_for_show(ctx: typer.Context, pointer: _ProfileBucketPointer) -> _UserProfileRecord:
    """Read the profile record, rendering the unreadable/missing report and exiting 2."""
    from ....domain.user_profile.errors import ProfileNotFoundError
    from ....domain.user_profile.values import UserProfileRecord

    try:
        record = cast(object, _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id))
        if not isinstance(record, UserProfileRecord):
            raise _ConfigBoundaryError(TypeError("profile record reader returned an invalid record"))
        return record
    except ProfileNotFoundError as exc:
        _emit_profile_record_missing(
            ctx,
            profile_id=pointer.bucket_id,
            bucket_id=pointer.bucket_id,
            label=pointer.label,
        )
        raise typer.Exit(code=2) from exc
    except _CadrumoError as exc:
        _emit_profile_record_unreadable(
            ctx,
            profile_id=pointer.bucket_id,
            bucket_id=pointer.bucket_id,
            label=pointer.label,
            error=exc,
        )
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        _log.debug("config profile view wrapped unexpected profile-record exception", exc_info=True)
        boundary = _ConfigBoundaryError(exc)
        _emit_profile_record_unreadable(
            ctx,
            profile_id=pointer.bucket_id,
            bucket_id=pointer.bucket_id,
            label=pointer.label,
            error=boundary,
        )
        raise typer.Exit(code=2) from boundary


def config_profile_view(
    ctx: typer.Context,
    name: str | None = None,
    output_language: _OutputLanguage | None = None,
) -> None:
    from ._profile_support import resolve_active_profile_pointer

    """View one profile's facts (defaults to the active profile).

        Emits a ``record_validity`` header line carrying the validation
        outcome of the canonical ProfileValidationService — the persisted
        record's schema validity, a distinct notion from the *filing
        readiness* gate reported by ``config profile status``. When blocking
        issues exist, the command exits with code 2 after rendering the report
        so operators discover the failure on stdout and via the shell exit
        status.
        """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.user_profile.projections import record_to_path_values
    from ....application.user_profile.validation import ProfileValidationService
    from ....domain.user_profile.loader import load_user_profile_schema

    pointer = _resolve_show_pointer(name, ctx=ctx, resolve_active_profile_pointer=resolve_active_profile_pointer)
    record = _read_record_for_show(ctx, pointer)
    from .._config_payloads import ConfigProfileViewResult, ProfileFactPayload, ProfileIssuePayload

    report = ProfileValidationService(schema=load_user_profile_schema()).validate_record(record)
    blocking = [issue for issue in report.issues if issue.severity.value == "error"]
    values = record_to_path_values(record)
    result = ConfigProfileViewResult(
        profile_id=record.profile_id,
        display_name=pointer.label,
        setup_state=record.setup_state,
        valid=not blocking,
        schema_version=report.schema_version,
        issues=[
            ProfileIssuePayload(
                severity=issue.severity,
                code=issue.code,
                path=issue.path,
                message=issue.message,
            )
            for issue in report.issues
        ],
        facts=[ProfileFactPayload(path=path, value=str(value)) for path, value in sorted(values.items())],
    )
    lines = _record_validity_lines(
        record=record,
        report=report,
        blocking_count=len(blocking),
        values=values,
        display_name=pointer.label,
    )
    from ....application.user_profile.cotejo_apply import censo_divergence_notice

    divergence_notice = censo_divergence_notice(record)
    notices = [divergence_notice] if divergence_notice is not None else []
    emit_envelope(ctx, command="config.profile.show", result=result, lines=lines, notices=notices)
    if blocking:
        raise typer.Exit(code=2)


def _resolve_validate_target_pointer(
    name: str | None,
    *,
    ctx: typer.Context,
    resolve_active_profile_pointer: Callable[[], _ProfileBucketPointer | None],
) -> _ProfileBucketPointer:
    """Resolve the profile the validate verb targets, refusing clearly when it cannot.

    A named profile resolves through the shared label reader (tombstoned
    records included, because validating one is legitimate); an omitted name
    falls back to the active profile pointer.
    """
    if name is None:
        pointer = resolve_active_profile_pointer()
        if pointer is None:
            raise no_active_profile_refusal()
        return pointer
    from .._profile_authentication_gate import resolved_command_profile_target

    pointer = resolved_command_profile_target(ctx)
    if pointer is None:
        raise RuntimeError("explicit profile validate target was not resolved by parsed dispatch")
    return pointer


def config_profile_validate(
    ctx: typer.Context,
    name: str | None = None,
    output_language: _OutputLanguage | None = None,
) -> None:
    from ._profile_support import resolve_active_profile_pointer

    """Validate a profile against the loaded schema (defaults to the active profile).

        Exits with code ``2`` when blocking issues surface so operators discover
        schema-conformance failures via the shell exit status. Report-only
        companion to ``config_profile_view`` — same validator, narrower
        payload (no fact dump).
        """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.modelo.profile_readiness_gate import modelo_work_profile_baseline_validation_issues
    from ....application.user_profile.validation import ProfileValidationService
    from ....domain.user_profile.errors import ProfileNotFoundError
    from ....domain.user_profile.loader import load_user_profile_schema

    pointer = _resolve_validate_target_pointer(
        name,
        ctx=ctx,
        resolve_active_profile_pointer=resolve_active_profile_pointer,
    )
    try:
        record = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name or pointer.label or pointer.bucket_id},
        ) from exc
    from .._config_payloads import ConfigProfileValidateResult, ProfileIssuePayload

    report = ProfileValidationService(schema=load_user_profile_schema()).validate_record(record)
    issues = list(report.issues)
    seen_issues = {(issue.code, issue.path) for issue in issues}
    for issue in modelo_work_profile_baseline_validation_issues(record):
        key = (issue.code, issue.path)
        if key in seen_issues:
            continue
        seen_issues.add(key)
        issues.append(issue)
    blocking = [issue for issue in issues if issue.severity.value == "error"]
    result = ConfigProfileValidateResult(
        profile_id=record.profile_id,
        display_name=pointer.label,
        setup_state=record.setup_state,
        valid=not blocking,
        schema_version=report.schema_version,
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
    lines = [
        f"readiness\t{'blocked' if blocking else 'ready'}\tissues={len(issues)}",
        f"profile_id\t{record.profile_id}",
        f"display_name\t{pointer.label}",
        f"setup_state\t{record.setup_state.value}",
        f"schema_version\t{report.schema_version}",
        f"valid\t{not blocking}",
    ]
    for issue in issues:
        lines.append(f"{issue.severity.value}\t{issue.code}\t{issue.path or '-'}\t{issue.message}")
    emit_envelope(ctx, command="config.profile.validate", result=result, lines=lines)
    if blocking:
        raise typer.Exit(code=2)


def _record_validity_verdict(*, blocking_count: int, issue_count: int) -> tuple[str, str]:
    """Return the localised verdict prose and its machine ``record_validity`` row.

    ``show`` reports *record validity* (does the persisted profile record
    satisfy its schema?), a distinct notion from the *filing readiness* gate
    that ``config profile status`` reports (does the profile carry the facts
    needed to start filing — tax_id and an activity?). Both surfaces once
    printed the bare token ``readiness`` with ``ready``/``blocked``, so a
    schema-valid but onboarding-incomplete profile read as a
    self-contradiction (``show: ready`` vs ``status: blocked``). ``show``
    emits ``record_validity`` with ``valid``/``invalid`` instead, so the two
    measures no longer collide.
    """
    if blocking_count:
        prose = tr(
            "cli.config.profile.show.summary_invalid",
            count=blocking_count,
        )
        return prose, f"record_validity\tinvalid\tissues={blocking_count}"
    prose = tr("cli.config.profile.show.summary_valid")
    return prose, f"record_validity\tvalid\tissues={issue_count}"


def _record_validity_lines(
    *,
    record: _UserProfileRecord,
    report: _ProfileValidationReport,
    blocking_count: int,
    values: Mapping[str, object],
    display_name: str,
) -> list[str]:
    """Render the ``show`` text report for one profile record.

    Only the leading verdict is prose: the tab-separated key/value rows
    mirror the JSON envelope and key on stable machine identifiers, so they
    are deliberately not localised. The verdict line is what the
    ``--language`` / ``--output-language`` flag visibly affects.
    """
    prose, validity_row = _record_validity_verdict(
        blocking_count=blocking_count,
        issue_count=len(report.issues),
    )
    # The label names WHICH profile this report is about, and the text surface
    # needs it more than the JSON one does: the identifier is redacted on the
    # way out, so without the label an operator reads one taxpayer's facts with
    # nothing on screen saying whose they are. The JSON payload has carried
    # `display_name` throughout; this row is what stops the two renderings
    # disagreeing about whether the subject is stated.
    lines = [
        prose,
        validity_row,
        f"profile_id\t{record.profile_id}",
        f"display_name\t{display_name}",
        f"setup_state\t{record.setup_state.value}",
    ]
    lines.extend(
        f"{issue.severity.value}\t{issue.code}\t{issue.path or '-'}\t{issue.message}" for issue in report.issues
    )
    lines.extend(f"{path}\t{value}" for path, value in sorted(values.items()))
    return lines


__all__ = ["config_profile_validate", "config_profile_view"]
