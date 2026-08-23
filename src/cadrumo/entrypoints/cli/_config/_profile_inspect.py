"""Profile inspection and readiness verbs: ``show``, ``preflight``, ``validate``.

``show`` reads and renders the active (or named) profile's persisted
:class:`UserProfileRecord`, alongside its schema validity; ``preflight``
reports which profile fields a given filing context still needs; ``validate`` is
the report-only companion to ``show`` (same validator, no fact dump). Their
public behavior targets live here while CommandSpecs own the executable shape.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import typer

from ....core import Period as _Period
from ....core.errors import CadrumoError as _CadrumoError
from ....core.external_constants import OutputLanguage as _OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from ....core.logging import get_logger as _get_logger
from ....domain.calculations.registry import RevisionId
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope, no_active_profile_refusal
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._errors import ConfigBoundaryError as _ConfigBoundaryError
from ._profile_readiness import (
    _emit_profile_record_missing,
    _emit_profile_record_unreadable,
    _read_profile_record,
)

_log = _get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ....application.user_profile import ProfileValidationReport as _ProfileValidationReport
    from ....application.workflow import ProfileBucketPointer as _ProfileBucketPointer
    from ....domain.user_profile import UserProfileRecord as _UserProfileRecord


def _resolve_show_pointer(
    name: str | None,
    *,
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

    from ....application.workflow import ProfileLabelAmbiguousError as _ProfileLabelAmbiguousError
    from ....application.workflow import resolve_profile_bucket as _resolve_profile_bucket

    unknown = _CliRefusedBoundaryError(
        translated_message="cli.config.profile.unknown_profile",
        context={"name": name},
    )
    try:
        pointer = _resolve_profile_bucket(name)
    except _ProfileLabelAmbiguousError as exc:
        # ``ProfileLabelAmbiguousError`` is a ``WorkflowError``, NOT a
        # ``ValueError``; refuse clearly with the dedicated ambiguity
        # message rather than escaping to an unhandled traceback.
        raise _CliRefusedBoundaryError(
            translated_message="errors.refused.refused_profile_label_ambiguous",
        ) from exc
    except ValueError as exc:
        raise unknown from exc
    if pointer is None:
        raise unknown
    return pointer


def _read_record_for_show(ctx: typer.Context, pointer: _ProfileBucketPointer) -> _UserProfileRecord:
    """Read the profile record, rendering the unreadable/missing report and exiting 2."""
    from ....domain.user_profile import ProfileNotFoundError, UserProfileRecord

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
        _log.debug("config profile show wrapped unexpected profile-record exception", exc_info=True)
        boundary = _ConfigBoundaryError(exc)
        _emit_profile_record_unreadable(
            ctx,
            profile_id=pointer.bucket_id,
            bucket_id=pointer.bucket_id,
            label=pointer.label,
            error=boundary,
        )
        raise typer.Exit(code=2) from boundary


def config_profile_show(
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
    from ....application.user_profile import ProfileValidationService, record_to_path_values
    from ....domain.user_profile import load_user_profile_schema

    pointer = _resolve_show_pointer(name, resolve_active_profile_pointer=resolve_active_profile_pointer)
    if name is not None:
        from .. import bind_profile_target_to_invocation, resume_profile_session_for_target

        resume_profile_session_for_target(ctx, bucket_id=pointer.bucket_id)
        bind_profile_target_to_invocation(ctx, bucket_id=pointer.bucket_id)
    record = _read_record_for_show(ctx, pointer)
    from .._config_payloads import ConfigProfileShowResult, ProfileFactPayload, ProfileIssuePayload

    report = ProfileValidationService(schema=load_user_profile_schema()).validate_record(record)
    blocking = [issue for issue in report.issues if issue.severity.value == "error"]
    values = record_to_path_values(record)
    result = ConfigProfileShowResult(
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
    from ....application.user_profile import censo_divergence_notice

    divergence_notice = censo_divergence_notice(record)
    notices = [divergence_notice] if divergence_notice is not None else []
    emit_envelope(ctx, command="config.profile.show", result=result, lines=lines, notices=notices)
    if blocking:
        raise typer.Exit(code=2)


def _resolve_preflight_revision_id(*, modelo: str, period: _Period, revision_id: RevisionId | None) -> str:
    """Resolve the registry revision a preflight check is assessed against.

    When ``revision_id`` is supplied it is an explicit override and is
    validated against the registry for the modelo and filing year. When it
    is omitted the active revision for the natural key (modelo, filing
    year, period) is resolved through the modelo-addressing resolver, which
    consumes the :class:`ValidatedRegistryAuthority` and never a raw loader.

    Refuses instructively when the natural key resolves no revision or is
    ambiguous: the refusal names the candidate revisions or points at
    ``aeat app modelo describe <modelo>`` rather than emitting a bare error.
    """
    from ....application.modelo import (
        ModeloWorkRegistryYearMismatchError as _ModeloWorkRegistryYearMismatchError,
    )
    from ....application.modelo import resolve_registry_revision_for_work_target
    from ....domain.calculations.registry import (
        AmbiguousRevisionSelectionError,
        NoRevisionForPeriodError,
        RegistrySnapshotError,
    )

    try:
        return resolve_registry_revision_for_work_target(
            modelo=modelo,
            filing_year=period.filing_year,
            period=period,
            registry_revision_id=revision_id,
        )
    except AmbiguousRevisionSelectionError as exc:
        # ``select_revision`` selected more than one revision. The candidate
        # revision ids ride on the typed ``candidate_ids`` field, so the
        # refusal lists them without parsing the human-readable message.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.preflight_revision_ambiguous",
            context={
                "modelo": modelo,
                "period": period.registry_token,
                "candidates": ", ".join(exc.candidate_ids),
            },
        ) from exc
    except NoRevisionForPeriodError as exc:
        # The natural key resolved no revision. Point the operator at the
        # discovery command rather than emitting a bare unresolved error.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.preflight_revision_unresolved",
            context={"modelo": modelo, "filing_year": period.filing_year, "period": period.registry_token},
        ) from exc
    except RegistrySnapshotError as exc:
        # Any residual snapshot failure not modelled by the two typed
        # subclasses above still refuses instructively via the discovery
        # pointer rather than surfacing a bare error to the operator.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.preflight_revision_unresolved",
            context={"modelo": modelo, "filing_year": period.filing_year, "period": period.registry_token},
        ) from exc
    except _ModeloWorkRegistryYearMismatchError as exc:
        # An explicit ``--revision-id`` override that is unknown to the
        # modelo or does not cover the filing year. List the registered
        # revisions so the operator can correct the override.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.preflight_revision_override_invalid",
            context={"modelo": modelo, "filing_year": period.filing_year},
        ) from exc


def config_profile_preflight(
    ctx: typer.Context,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str | None = None,
    output_language: _OutputLanguage | None = None,
) -> None:
    from ._profile_support import resolve_active_profile_pointer

    """Report which profile fields a given filing context requires that are missing.

        Operates on the active profile. ``--revision-id`` is an explicit override
        for exact replay; when omitted the active revision for the natural key
        (modelo, filing year, period) is resolved through the modelo-addressing
        resolver. Exits with code ``2`` when any required field is missing so
        operators discover the gap via the shell exit status.
        """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.modelo import modelo_work_profile_preflight_report
    from ....core.resources import resources
    from ....domain.user_profile import ProfileNotFoundError

    pointer = resolve_active_profile_pointer()
    if pointer is None:
        raise no_active_profile_refusal()
    try:
        record = _read_profile_record(profile_id=pointer.bucket_id, bucket_id=pointer.bucket_id)
    except ProfileNotFoundError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": pointer.label or pointer.bucket_id},
        ) from exc
    try:
        filing_period = _Period.from_year_and_code(filing_year, period)
    except ValueError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.preflight_revision_unresolved",
            context={"modelo": modelo, "filing_year": filing_year, "period": period},
        ) from exc
    from .._config_payloads import ConfigProfilePreflightResult, ProfilePreflightMissingPayload

    report = modelo_work_profile_preflight_report(
        record=record,
        modelo=modelo,
        revision_id=revision_id.strip() if revision_id else "unresolved",
        filing_year=filing_period.filing_year,
        period=filing_period,
        resolve_revision_when_missing=False,
        authority=resources().modelos.authority,
    )
    if report.ready:
        resolved_revision_id = _resolve_preflight_revision_id(
            modelo=modelo,
            period=filing_period,
            revision_id=revision_id,
        )
        revision = resources().modelos.authority.validate_modelo(modelo).revisions[resolved_revision_id]
        report = modelo_work_profile_preflight_report(
            record=record,
            modelo=modelo,
            revision_id=resolved_revision_id,
            filing_year=filing_period.filing_year,
            period=filing_period,
            revision=revision,
            authority=resources().modelos.authority,
        )
    result = ConfigProfilePreflightResult(
        profile_id=report.profile_id,
        modelo=report.modelo,
        revision_id=report.revision_id,
        filing_year=report.filing_year,
        period=report.period,
        ready=report.ready,
        per_operation_requirements_assessed=report.per_operation_requirements_assessed,
        missing=[
            ProfilePreflightMissingPayload(
                selector=requirement.selector,
                section_key=requirement.section_key,
                field_key=requirement.field_key,
                label=requirement.label,
                legal_refs=list(requirement.legal_refs),
                modelos=list(requirement.modelos),
            )
            for requirement in report.missing
        ],
    )
    lines = [
        f"profile_readiness\t{'ready' if report.ready else 'missing'}\tmissing={len(report.missing)}",
        "readiness_scope\tprofile_fields_only",
        f"profile_id\t{report.profile_id}",
        f"modelo\t{report.modelo}",
        f"revision_id\t{report.revision_id}",
        f"filing_year\t{report.filing_year}",
        f"period\t{report.period.registry_token}",
    ]
    for requirement in report.missing:
        legal_refs = ", ".join(requirement.legal_refs) or "-"
        modelos = ", ".join(requirement.modelos) or "-"
        lines.append(
            f"missing\t{requirement.section_key}\t{requirement.field_key}\t{requirement.selector}\t"
            f"{requirement.label}\t{legal_refs}\t{modelos}",
        )
    notices: list[Notice] = []
    if not report.per_operation_requirements_assessed:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="config.profile.preflight.per_operation_axis_not_assessed",
                message=tr(
                    "cli.config.profile.preflight.per_operation_axis_not_assessed",
                    modelo=report.modelo,
                ),
                context={"modelo": report.modelo, "ready": str(report.ready)},
            ),
        )
    emit_envelope(ctx, command="config.profile.preflight", result=result, lines=lines, notices=tuple(notices))
    if not report.ready:
        raise typer.Exit(code=2)


def _resolve_validate_target_pointer(
    name: str | None,
    *,
    resolve_active_profile_pointer: Callable[[], _ProfileBucketPointer | None],
) -> _ProfileBucketPointer:
    """Resolve the profile the validate verb targets, refusing clearly when it cannot.

    A named profile resolves through the shared label reader (tombstoned
    records included, because validating one is legitimate); an omitted name
    falls back to the active profile pointer.
    """
    from ....application.workflow import ProfileLabelAmbiguousError as _ProfileLabelAmbiguousError
    from ....application.workflow import read_profile_bucket as _read_profile_bucket

    if name is None:
        pointer = resolve_active_profile_pointer()
        if pointer is None:
            raise no_active_profile_refusal()
        return pointer
    try:
        pointer = _read_profile_bucket(name)
    except _ProfileLabelAmbiguousError as exc:
        # ``ProfileLabelAmbiguousError`` is a ``WorkflowError``, NOT a
        # ``ValueError``; refuse clearly with the dedicated ambiguity
        # message rather than escaping to an unhandled traceback.
        raise _CliRefusedBoundaryError(
            translated_message="errors.refused.refused_profile_label_ambiguous",
        ) from exc
    except ValueError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        ) from exc
    if pointer is None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        )
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
        companion to ``config_profile_show`` — same validator, narrower
        payload (no fact dump).
        """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.modelo import modelo_work_profile_baseline_validation_issues
    from ....application.user_profile import ProfileValidationService
    from ....domain.user_profile import ProfileNotFoundError, load_user_profile_schema

    pointer = _resolve_validate_target_pointer(
        name,
        resolve_active_profile_pointer=resolve_active_profile_pointer,
    )
    if name is not None:
        from .. import bind_profile_target_to_invocation, resume_profile_session_for_target

        resume_profile_session_for_target(ctx, bucket_id=pointer.bucket_id)
        bind_profile_target_to_invocation(ctx, bucket_id=pointer.bucket_id)
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


__all__ = ["config_profile_preflight", "config_profile_show", "config_profile_validate"]
